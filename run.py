"""
aiducation-tiktok-production-os — the single entry point.

Run through the wrapper so the folder's own toolchain is used:
    Mac:      ./os <verb> ...
    Windows:  os.cmd <verb> ...

Verbs
  welcome [--open]                start-of-session menu: video modes + examples (opens gallery first time)
  doctor                          is this laptop ready? (fonts, models, node, voice)
  new "<title>" [--subject TOÁN]  create videos/V-000N-<slug>/script.json from the template
  deck <file.pdf> "<title>" [--subject HÓA] [--voice NAME]
                                  new 16:9 video from a slide deck PDF (see playbooks/deck-video.md)
  check <video>                   validate script.json (seconds, no rendering)
  preview <video>                 cheap renders + videos/<id>/preview.png contact sheet
  voice <video> [--voice NAME]    make + check every narration line (VieNeu, local)
  record <video>                  open the recording studio in the browser
  render <video> [--force]        final.mp4 + cover.png (needs a clean voice report)
  status [<video>]                where each video stands
  clone-voice <name> <file>       register a staff voice from a 3–8 s clean sample

TikTok loop
  posted <video> <url> [--hook H --format F --topic T --experiment E --at ISO]
  today                           readouts due + which screenshots to ask for; makes days/<today>/
  readout <video> <24h|48h|7d> <metrics.json>   save one readout (validated, write-once)
  scorecard [--at 48h]            posts vs rolling median, and by hook/format/topic
  finding "<title>"               start findings/NNNN-<slug>.md from the template; refresh index

<video> is V-0001, 1, or the slug. Nothing here uses the network or any API key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Local-only rule (AGENTS.md §3.1): only setup's `warmup` may download models. Every other
# verb runs with Hugging Face forced offline — set before anything imports huggingface_hub.
import os  # noqa: E402
os.environ["HF_HUB_OFFLINE"] = "0" if sys.argv[1:2] == ["warmup"] else "1"

from engine import pipeline  # noqa: E402
from engine.pipeline import CONSENT, consent_signed  # noqa: E402


def _flag(args: list[str], name: str, default=None):
    if name in args:
        i = args.index(name)
        val = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
        return val
    return default


def cmd_doctor(_args):
    import shutil
    ok = True

    def row(label, good, hint=""):
        nonlocal ok
        ok &= good
        print(f"  [{'ok' if good else 'MISSING'}] {label}" + ("" if good else f" — {hint}"))

    print("Toolchain")
    row("python", True)
    for mod in ("manim", "vieneu", "ziamath", "onnxruntime", "soundfile"):
        try:
            __import__(mod)
            row(mod, True)
        except Exception as e:  # noqa: BLE001
            row(mod, False, f"reinstall with setup ({e})")
    row("ffmpeg", bool(shutil.which("ffmpeg")), "run setup")
    row("node", bool(shutil.which("node")), "run setup")
    row("remotion", (ROOT / "engine/remotion/node_modules/remotion").exists(), "run setup")
    print("Models and assets")
    row("aligner model", (ROOT / "models/aligner/vi_ctc.onnx").exists(),
        "copy models/aligner/vi_ctc.onnx from the shared OS folder")
    row("fonts", len(list((ROOT / "assets/fonts").glob("*.ttf"))) >= 3, "copy assets/fonts")
    row("VieNeu voices downloaded", any((ROOT / "models/hf").glob("hub/models--pnnbao-ump--VieNeu*")),
        "run setup once with internet")
    row("English voices (Kokoro)", (ROOT / "models/kokoro/voices-v1.0.bin").exists(), "run setup once with internet")
    row("English checker", any((ROOT / "models/hf").glob("hub/models--Xenova--wav2vec2-base-960h")),
        "run setup once with internet")
    print("\nREADY" if ok else "\nNOT READY — run setup/setup-mac.command or setup\\setup-windows.bat")
    return 0 if ok else 1


def cmd_welcome(args):
    """The start-of-session menu: video modes with their examples (Vietnamese).
    Opens the gallery in the browser on this laptop's first session, or with --open."""
    import webbrowser
    ex = json.loads((ROOT / "vi-du" / "examples.json").read_text(encoding="utf-8"))
    print("XƯỞNG TIKTOK — CÁC KIỂU VIDEO LÀM ĐƯỢC")
    for i, m in enumerate(ex["modes"], 1):
        print(f"\n{i}. {m['name']}\n   {m['what']}\n   Nói: “{m['say']}”")
        for e in m["examples"]:
            print(f"   ▶ mẫu: vi-du/{e}/final.mp4 — {ex['examples'][e]['title']}")
    print(f"\nGiọng đọc: {ex['voices']}\n{ex['also']}")
    gallery = ROOT / "vi-du" / "index.html"
    if not gallery.exists():
        from tools.make_gallery import build
        build()
    marker = ROOT / ".cache" / "welcomed"
    if "--open" in args or not marker.exists():
        webbrowser.open(gallery.resolve().as_uri())
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("shown\n", encoding="utf-8")
        print(f"\n(gallery opened in the browser: {gallery.relative_to(ROOT)})")
    else:
        print(f"\n(gallery: {gallery.relative_to(ROOT)} — open with: welcome --open)")


def cmd_warmup(_args):
    """Download the voice models once (setup runs this) and prove both voices speak."""
    import soundfile as sf
    from engine.voice import align, tts
    import urllib.request
    tts.KOKORO_DIR.mkdir(parents=True, exist_ok=True)
    for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        if not (tts.KOKORO_DIR / f).exists():
            print(f"  downloading {f} …")
            urllib.request.urlretrieve(
                f"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/{f}", tts.KOKORO_DIR / f)
    tests = [(v, "Xin chào, đây là giọng đọc thử.") for v in tts.ALLOWED_PRESETS]
    tests += [(v, "Hello, this is a voice test.") for v in tts.ENGLISH]
    for v, line in tests:
        wav = tts.synth(line, v)
        a, sr = sf.read(wav, dtype="float32")
        lang = tts.lang_of(v)
        status, _ = align.verdict(align.align(a, sr, line, lang), lang)
        print(f"  {v}: {len(a) / sr:.1f}s, checker {status}")


def cmd_new(args):
    subject = _flag(args, "--subject", "TOÁN")
    vdir = pipeline.new(" ".join(args), subject)
    print(f"created {vdir.relative_to(ROOT)}/script.json")


def cmd_deck(args):
    subject = _flag(args, "--subject", "")
    voice = _flag(args, "--voice", "Minh Quân Pro")
    src = Path(args[0]).expanduser()
    vdir = pipeline.deck(src, " ".join(args[1:]) or src.stem, subject, voice)
    info = json.loads((vdir / "deck" / "deck.json").read_text(encoding="utf-8"))
    print(f"created {vdir.relative_to(ROOT)} from {src.name}: {len(info['pages'])} pages")
    for p in info["pages"]:
        print(f"  page {p['page']:2d}  {p['mode']:6s}  {len(p['elements']):2d} elements  -> deck/p{p['page']:02d}.marks.png")


def cmd_check(args):
    vdir = pipeline.find_video(args[0])
    problems = pipeline.check(vdir)
    if problems:
        print(f"{vdir.name}: {len(problems)} problem(s)")
        for p in problems:
            print("  -", p)
        return 1
    print(f"{vdir.name}: script OK")


def cmd_preview(args):
    vdir = pipeline.find_video(args[0])
    problems = pipeline.check(vdir)
    if problems:
        print("\n".join(["fix these first:"] + [f"  - {p}" for p in problems]))
        return 1
    out = pipeline.preview(vdir)
    print(f"preview sheet: {out.relative_to(ROOT)}")


def cmd_voice(args):
    override = _flag(args, "--voice")
    vdir = pipeline.find_video(args[0])
    rep = pipeline.voice(vdir, override)
    marks = {"ok": "ok    ", "listen": "LISTEN", "redo": "REDO  ", "missing": "NO TAKE"}
    print(f"{vdir.name} — voice: {rep['voice']}")
    for key, line in rep["lines"].items():
        extra = f"  words: {', '.join(line['problem_words'])}" if line.get("problem_words") else ""
        print(f"  {marks[line['status']]} {key}  {line['say'][:70]}{extra}")
    counts = {s: sum(1 for l in rep["lines"].values() if l["status"] == s) for s in marks}
    print("summary:", ", ".join(f"{v} {k}" for k, v in counts.items() if v))
    return 0 if not (counts["redo"] or counts["missing"]) else 1


def cmd_record(args):
    from engine.record.server import serve
    serve(pipeline.find_video(args[0]))


def cmd_render(args):
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    vdir = pipeline.find_video(args[0])
    out = pipeline.render(vdir, force=force)
    print(f"done: {out.relative_to(ROOT)}  (cover: {(vdir / 'cover.png').relative_to(ROOT)})")


def cmd_status(args):
    vids = [pipeline.find_video(args[0])] if args else sorted(p for p in pipeline.VIDEOS.iterdir() if p.is_dir())
    if not vids:
        print("no videos yet (examples are in vi-du/)")
    for v in vids:
        rep = v / "voice" / "report.json"
        stage = "script"
        if (v / "preview.png").exists():
            stage = "previewed"
        if rep.exists():
            lines = json.loads(rep.read_text(encoding="utf-8"))["lines"].values()
            bad = sum(1 for l in lines if l["status"] in ("redo", "missing"))
            stage = f"voice ({bad} line(s) to fix)" if bad else "voice ok"
        if (v / "final.mp4").exists():
            stage = "RENDERED"
        if (v / "post.json").exists():
            stage = "POSTED"
        print(f"  {v.name:40s} {stage}")


def cmd_clone_voice(args):
    """Register a staff voice: clean the sample, write the consent form, make a test line."""
    import re as _re
    import subprocess
    import soundfile as sf
    from engine.voice import align, tts
    name, src = args[0], Path(args[1]).expanduser()
    if not _re.fullmatch(r"[a-z0-9-]{2,30}", name):
        raise SystemExit("name must be 2-30 plain letters/digits/dashes, e.g. 'co-lan' (no accents, no spaces)")
    if not src.exists():
        raise SystemExit(f"no such file: {src}")
    d = ROOT / "voices" / name
    d.mkdir(parents=True, exist_ok=True)
    # Trim silence at both ends, gentle denoise, level it, keep at most 8 s (VieNeu uses 3-8 s).
    trim = "silenceremove=start_periods=1:start_threshold=-45dB"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "48000", "-af",
                    f"highpass=f=70,afftdn=nf=-25,{trim},areverse,{trim},areverse,loudnorm=I=-18:TP=-2",
                    "-t", "8", str(d / "sample.wav")], check=True)
    a, sr = sf.read(d / "sample.wav", dtype="float32")
    if len(a) / sr < 3:
        (d / "sample.wav").unlink()
        raise SystemExit(f"sample has only {len(a) / sr:.1f} s of speech after trimming silence; need 3-8 s")
    if not (d / "consent.md").exists():
        (d / "consent.md").write_text(CONSENT.format(name=name), encoding="utf-8")
    line = "Xin chào các em, hôm nay chúng ta cùng học một bài mới."
    test = tts.synth(line, f"clone:{name}")
    import shutil
    shutil.copy(test, d / "test.wav")
    ta, tsr = sf.read(d / "test.wav", dtype="float32")
    status, _ = align.verdict(align.align(ta, tsr, line))
    print(f"voice saved: voices/{name}/sample.wav ({len(a) / sr:.1f} s of speech)")
    print(f"test line:   voices/{name}/test.wav  — play it to the person: does it sound like them? (checker: {status})")
    print(f"consent:     voices/{name}/consent.md — {'SIGNED' if consent_signed(name) else 'NOT SIGNED yet: they fill in name + date'}")
    print(f"use it with \"voice\": \"clone:{name}\" (videos are blocked until the consent is signed)")


def cmd_posted(args):
    from engine import analytics
    tags = {k: _flag(args, f"--{k}") for k in ("hook", "format", "topic", "experiment")}
    when = _flag(args, "--at")
    vdir = analytics.posted(args[0], args[1], when, **tags)
    print(f"{vdir.name}: posted. Readouts will be due at 24h, 48h and 7d.")


def cmd_today(_args):
    from engine import analytics
    d = analytics.today_dir()
    todo = analytics.due()
    print(f"today's folder: {d.relative_to(ROOT)}  (put screenshots in {(d / 'inbox').relative_to(ROOT)})")
    if not todo:
        print("no readouts due.")
    for v, label, age in todo:
        print(f"  DUE {label:3s} {v.name}  (posted {age:.0f}h ago)")
    if todo:
        print("screenshots to ask for, per video:")
        for s in analytics.SCREENS:
            print("   -", s)


def cmd_readout(args):
    from engine import analytics
    metrics = json.loads(Path(args[2]).read_text(encoding="utf-8"))
    out = analytics.save_readout(args[0], args[1], metrics)
    print(f"saved {out.relative_to(ROOT)}")


def cmd_scorecard(args):
    from engine import analytics
    print(analytics.scorecard(_flag(args, "--at", "48h")))


def cmd_finding(args):
    import re as _re
    from engine import analytics
    from engine.pipeline import slugify
    n = analytics.next_finding_number()
    title = " ".join(args)
    f = ROOT / "findings" / f"{n:04d}-{slugify(title)}.md"
    tpl = (ROOT / "findings" / "TEMPLATE.md").read_text(encoding="utf-8")
    f.write_text(_re.sub(r"^# .*", f"# {n:04d} · {title}", tpl, count=1, flags=_re.M), encoding="utf-8")
    (ROOT / "findings" / "INDEX.md").write_text("# Findings\n\n" + analytics.findings_index() + "\n", encoding="utf-8")
    print(f"created {f.relative_to(ROOT)}")


VERBS = {
    "welcome": cmd_welcome, "doctor": cmd_doctor, "warmup": cmd_warmup, "new": cmd_new, "deck": cmd_deck, "check": cmd_check, "preview": cmd_preview,
    "voice": cmd_voice, "record": cmd_record, "render": cmd_render, "status": cmd_status,
    "clone-voice": cmd_clone_voice, "posted": cmd_posted, "today": cmd_today,
    "readout": cmd_readout, "scorecard": cmd_scorecard, "finding": cmd_finding,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in VERBS:
        print(__doc__)
        return 0 if not argv else 2
    return VERBS[argv[0]](argv[1:]) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
