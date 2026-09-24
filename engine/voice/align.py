"""
The voice checker: does this audio actually say this line? And when is each word?

Forced alignment, not transcription. A speech recogniser (Whisper) guesses the most
likely sentence, and for Vietnamese maths that guess is wrong in both directions:
unprompted it hears "trừ" as "chữ" and "phẩy" as "phải" on perfect audio; given the
line as a prompt it echoes the script and passes audio that skipped words. Measured
2026-09-23 on the dau-dao-ham lines, see README.

Instead: a Vietnamese character-level CTC model (wav2vec2-base-vi-vlsp2020, run
through onnxruntime, no torch) scores how well each expected word is supported by
the sound. A skipped or swapped word has nothing in the audio to align to and scores
far below any word that was spoken:

    deliberately wrong lines   worst word  <= -10.3
    correct lines (70 lines,   worst word  >= -5.9
      5 voices)

So:  score < FAIL -> the line is wrong, redo it.  FAIL..WARN -> a human listens.
The same alignment gives every word's start/end time, which drives the karaoke
captions. Fully local; the model file ships in models/aligner/.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soxr

from .text import tokens

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models" / "aligner"

FAIL = -8.0
WARN = -6.0
# English (wav2vec2-base-960h, trained on American LibriSpeech): correct US-voice lines
# score >= -1.6 and dropped words <= -13.9 (Kokoro, 4 voices, 2026-09-23). But British
# voices drop the final "r" ("hear" -> /hɪə/) and score -5..-6 on perfectly good audio,
# so English keeps the same -6 "listen" line. Swapped words (-3.6..-7.2) are therefore
# only partly caught — acceptable: a TTS voice reads exactly what is written; swaps are
# a human-recording failure, and English recording is not offered.
WARN_BY_LANG = {"vi": WARN, "en": WARN}
# Single Latin letters ("K", "y") are read several ways; never block on them alone.
LETTER_FLOOR = -9.5

_MODELS: dict[str, tuple] = {}

# English: facebook/wav2vec2-base-960h (Apache-2.0) as published in ONNX by Xenova
# (transformers.js); downloaded once by setup into models/hf. Outputs raw logits.
EN_REPO = "Xenova/wav2vec2-base-960h"


def _load(lang: str = "vi"):
    """(vocab, session, input name, outputs-are-logits, upper-case letters)."""
    if lang not in _MODELS:
        so = ort.SessionOptions()
        so.intra_op_num_threads = min(os.cpu_count() or 4, 8)
        if lang == "en":
            from huggingface_hub import hf_hub_download
            model = hf_hub_download(EN_REPO, "onnx/model.onnx")
            vocab = json.loads(Path(hf_hub_download(EN_REPO, "vocab.json")).read_text(encoding="utf-8"))
            sess = ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])
            _MODELS[lang] = (vocab, sess, sess.get_inputs()[0].name, True, True)
        else:
            vocab = json.loads((MODEL_DIR / "vi_ctc.vocab.json").read_text(encoding="utf-8"))
            sess = ort.InferenceSession(str(MODEL_DIR / "vi_ctc.onnx"), so, providers=["CPUExecutionProvider"])
            _MODELS[lang] = (vocab, sess, "audio", False, False)
    return _MODELS[lang]


def _viterbi(lp: np.ndarray, toks: list[int], blank: int):
    T = lp.shape[0]
    ext = np.array([blank if s % 2 == 0 else toks[s // 2] for s in range(2 * len(toks) + 1)])
    S = len(ext)
    skip = np.zeros(S, bool)
    skip[2:] = (ext[2:] != blank) & (ext[2:] != ext[:-2])
    dp = np.full(S, -1e9)
    dp[0], dp[1] = lp[0, ext[0]], lp[0, ext[1]]
    bp = np.zeros((T, S), np.int8)
    for t in range(1, T):
        a = dp
        b = np.r_[-1e9, dp[:-1]]
        c = np.where(skip, np.r_[-1e9, -1e9, dp[:-2]], -1e9)
        st = np.stack([a, b, c])
        bp[t] = st.argmax(0)
        dp = st.max(0) + lp[t, ext]
    s = S - 1 if dp[S - 1] > dp[S - 2] else S - 2
    path = np.zeros(T, int)
    for t in range(T - 1, -1, -1):
        path[t] = s
        s = int(s) - int(bp[t, s])
    return path, ext


@dataclass
class Word:
    text: str          # as written in the script (what the caption shows)
    start: float       # seconds from the start of this line's audio
    end: float
    score: float       # 0 = clearly spoken; very negative = not in the audio


def align(audio: np.ndarray, sr: int, say: str, lang: str = "vi") -> list[Word]:
    vocab, sess, inp, logits, upper = _load(lang)
    blank, sep = vocab["<pad>"], vocab["|"]
    a = soxr.resample(audio.astype(np.float32), sr, 16000)
    # A clip that ends right on its last word leaves the model no trailing context and
    # scores that word low (measured: "hear." -5.2 on clean audio). 0.3 s of silence
    # after the clip fixes it; timings are unaffected because nothing is added before.
    a = np.concatenate([a, np.zeros(int(0.3 * 16000), dtype=np.float32)])
    a = (a - a.mean()) / np.sqrt(a.var() + 1e-7)
    lp = sess.run(None, {inp: a[None].astype(np.float32)})[0][0]
    if logits:  # log-softmax, numerically stable
        lp = lp - lp.max(1, keepdims=True)
        lp = lp - np.log(np.exp(lp).sum(1, keepdims=True))
    frame = len(a) / 16000 / lp.shape[0]

    written = tokens(say, lang)
    if upper:
        written = [(w, [t.upper() for t in sp]) for w, sp in written]
    toks, owner = [], []
    flat = [(wi, t) for wi, (_, sp) in enumerate(written) for t in sp]
    for k, (wi, tok) in enumerate(flat):
        for ch in tok:
            if ch in vocab:
                toks.append(vocab[ch])
                owner.append(wi)
        if k < len(flat) - 1:
            toks.append(sep)
            owner.append(-1)
    if not toks:
        return []

    path, ext = _viterbi(lp, toks, blank)
    best = lp.max(1)
    frames: dict[int, list[int]] = {}
    for t, s in enumerate(path):
        if s % 2 == 1 and owner[s // 2] >= 0:
            frames.setdefault(owner[s // 2], []).append(t)

    out = []
    for wi, (text, _) in enumerate(written):
        f = frames.get(wi, [])
        if not f:
            out.append(Word(text, 0.0, 0.0, -99.0))
            continue
        score = float(np.mean([lp[t, ext[path[t]]] - best[t] for t in f]))
        out.append(Word(text, round(f[0] * frame, 3), round((f[-1] + 1) * frame, 3), round(score, 2)))
    return out


def verdict(words: list[Word], lang: str = "vi") -> tuple[str, list[str]]:
    """'ok' | 'listen' | 'redo', plus the words that caused it."""
    warn = WARN_BY_LANG.get(lang, WARN)
    worst = []
    status = "ok"
    for w in words:
        is_letter = len(w.text.strip(".,:;!?()")) == 1 and w.text.strip(".,:;!?()").isalpha()
        fail_at = LETTER_FLOOR if is_letter else FAIL
        if w.score < fail_at:
            status = "redo"
            worst.append(w.text)
        elif w.score < warn and status != "redo":
            status = "listen"
            worst.append(w.text)
    return status, worst


def to_json(words: list[Word]) -> list[dict]:
    return [asdict(w) for w in words]
