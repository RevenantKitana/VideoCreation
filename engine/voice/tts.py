"""
VieNeu-TTS, local, one call per narration line.

Voices:
    "Minh Quân Pro"   default (male, Northern)
    "Trúc Ly"         alternative (female, Northern)
    "clone:<name>"    a staff voice cloned from voices/<name>/sample.wav (3–8 s, clean)

Every generated line is cached by (text, voice) under .cache/tts, so re-rendering a
video after a visual tweak costs no synthesis at all.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "tts"
VOICES_DIR = ROOT / "voices"
SR = 48_000
DEFAULT_VOICE = "Minh Quân Pro"
ALLOWED_PRESETS = ("Minh Quân Pro", "Trúc Ly")
# English (Kokoro-82M, Apache-2.0, local): US and UK, male and female.
ENGLISH = {"en:af_heart": "en-us", "en:am_michael": "en-us", "en:bf_emma": "en-gb", "en:bm_george": "en-gb"}
KOKORO_DIR = ROOT / "models" / "kokoro"

_engine = None
_kokoro = None


def lang_of(voice: str) -> str:
    return "en" if voice.startswith("en:") else "vi"


def _espeak_data() -> str:
    """espeak-ng keeps its data path in a ~160-byte buffer: a path deeper than that is
    silently truncated and it falls back to a compiled-in default that doesn't exist
    (".../runner/work/espeakng-loader/..."). The pip package's own copy sits too deep
    inside .pixi, so a copy lives at models/espeak-ng-data — or in a short temp dir if
    even that path is long."""
    import shutil
    import tempfile

    import espeakng_loader
    for dst in (ROOT / "models" / "espeak-ng-data", Path(tempfile.gettempdir()) / "esng-data"):
        if len(str(dst)) < 140:
            if not (dst / "phontab").exists():
                shutil.copytree(espeakng_loader.get_data_path(), dst, dirs_exist_ok=True)
            return str(dst)
    raise RuntimeError("no short path available for espeak-ng data")


def kokoro():
    global _kokoro
    if _kokoro is None:
        import espeakng_loader
        import kokoro_onnx
        import kokoro_onnx.session
        import onnxruntime as ort

        available = ort.get_available_providers()
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if "CUDAExecutionProvider" in available else ["CPUExecutionProvider"]
        
        # Override create_session so it uses CUDA when available, falling back to CPU
        kokoro_onnx.session.create_session = lambda model_path: ort.InferenceSession(model_path, providers=providers)

        cfg = kokoro_onnx.EspeakConfig(lib_path=espeakng_loader.get_library_path(), data_path=_espeak_data())
        _kokoro = kokoro_onnx.Kokoro(str(KOKORO_DIR / "kokoro-v1.0.onnx"), str(KOKORO_DIR / "voices-v1.0.bin"),
                                     espeak_config=cfg)
        sess = getattr(_kokoro, 'sess', getattr(_kokoro, 'session', None))
        provs = sess.get_providers() if sess else []
        active_prov = provs[0] if provs else "CPUExecutionProvider"
        dev_tag = "⚡ GPU (CUDA)" if "CUDA" in active_prov else "💻 CPU"
        print(f"  [Kokoro-TTS] Đang nạp mô hình vào: {dev_tag} ({active_prov})")
    return _kokoro


def _patch_vieneu_gpu():
    """If CUDAExecutionProvider is available in ONNX Runtime, ensure VieNeu runs on GPU."""
    try:
        import onnxruntime as ort
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            import vieneu._v3_turbo_engine.onnx_runtime_lite as lite_mod
            _orig_init = lite_mod.OnnxV3LiteEngine.__init__

            def _gpu_init(self, *args, **kwargs):
                _orig_session = ort.InferenceSession

                def _session_with_gpu(path_or_bytes, *s_args, providers=None, **s_kwargs):
                    if providers == ["CPUExecutionProvider"]:
                        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                    return _orig_session(path_or_bytes, *s_args, providers=providers, **s_kwargs)

                ort.InferenceSession = _session_with_gpu
                try:
                    return _orig_init(self, *args, **kwargs)
                finally:
                    ort.InferenceSession = _orig_session

            lite_mod.OnnxV3LiteEngine.__init__ = _gpu_init
    except Exception:
        pass


def engine():
    global _engine
    if _engine is None:
        _patch_vieneu_gpu()
        from vieneu import Vieneu
        _engine = Vieneu()
        if hasattr(_engine, 'engine') and hasattr(_engine.engine, 'sess_pre'):
            provs = _engine.engine.sess_pre.get_providers()
            active_prov = provs[0] if provs else "CPUExecutionProvider"
            dev_tag = "⚡ GPU (CUDA)" if "CUDA" in active_prov else "💻 CPU"
            print(f"  [VieNeu-TTS] Đang nạp mô hình vào: {dev_tag} ({active_prov})")
    return _engine


def trim(a: np.ndarray, sr: int, pad_in: float = 0.03, pad_out: float = 0.12) -> np.ndarray:
    """Cut leading/trailing silence so lines butt up against their beats."""
    loud = np.where(np.abs(a) > 0.01)[0]
    if not len(loud):
        return a
    return a[max(loud[0] - int(pad_in * sr), 0): loud[-1] + int(pad_out * sr)]


def synth(text: str, voice: str = DEFAULT_VOICE, attempt: int = 0) -> Path:
    """Return a wav path for `text` in `voice`. `attempt` > 0 forces a fresh take
    (VieNeu samples, so a re-roll can fix a line the checker rejected)."""
    key = hashlib.sha1(f"{voice}\n{text}\n{attempt}".encode()).hexdigest()[:20]
    out = CACHE / f"{key}.wav"
    if out.exists():
        return out
    CACHE.mkdir(parents=True, exist_ok=True)

    np.random.seed(int(key[:8], 16) % (2**31))
    if voice in ENGLISH:
        audio, sr = kokoro().create(text, voice=voice[3:], speed=1.0, lang=ENGLISH[voice])
        a = trim(np.asarray(audio, dtype=np.float32).flatten(), sr)
        sf.write(out, a, sr)
        return out
    v = engine()
    if voice.startswith("clone:"):
        sample = VOICES_DIR / voice.split(":", 1)[1] / "sample.wav"
        if not sample.exists():
            raise FileNotFoundError(f"No voice sample at {sample}. Run: os clone-voice <name> <file>")
        audio = v.infer(text, ref_audio=str(sample))
    else:
        if voice not in ALLOWED_PRESETS:
            raise ValueError(f"voice must be one of {ALLOWED_PRESETS + tuple(ENGLISH)} or clone:<name>, got {voice!r}")
        audio = v.infer(text, voice=voice)
    a = trim(np.asarray(audio, dtype=np.float32).flatten(), SR)
    sf.write(out, a, SR)
    return out
