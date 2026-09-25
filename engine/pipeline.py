"""
The production pipeline behind run.py. Every step reads and writes files inside
videos/<id>/, so any step can be re-run alone and an agent can always see where a
video stands by listing its folder.

    script.json                 the only file a person (or the agent) writes
    build/preview/…             cheap 540p renders + preview.png contact sheet
    voice/lines/<step>.wav      one take per narration line (TTS or recorded)
    voice/report.json           checker verdict + word timings per line
    build/final/…               transparent scene clips, audio.wav, lesson.json
    final.mp4 · cover.png · sheet.png
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ROOT / "videos"
FPS = 60
SCENE_GAP = 0.2  # seconds of held brand frame between scenes


CONSENT = """# Đồng ý sử dụng giọng nói — {name}

Tôi đồng ý để Aiducation dùng bản sao giọng nói của tôi (tạo bằng máy, chạy trên máy
tính của công ty) để đọc lời cho video bài giảng của Aiducation. Tôi có thể rút lại
sự đồng ý này bất cứ lúc nào bằng cách báo cho quản lý; khi đó thư mục voices/{name}
sẽ bị xoá.

Họ và tên: ____________
Ngày: ____________
"""


def consent_signed(name: str) -> bool:
    """Signed = both the name and date lines have been filled in (no blank line left)."""
    f = ROOT / "voices" / name / "consent.md"
    if not f.exists():
        return False
    fields = {k: v.strip() for line in f.read_text(encoding="utf-8").splitlines()
              if ":" in line for k, v in [line.split(":", 1)]}
    return all(fields.get(k) and "____" not in fields[k] for k in ("Họ và tên", "Ngày"))


# ---------------------------------------------------------------------- lookup
def find_video(ref: str) -> Path:
    """Accept 'V-0001', '1', 'dau-dao-ham' or the full folder name."""
    ref = ref.strip()
    if re.fullmatch(r"\d+", ref):
        ref = f"V-{int(ref):04d}"
    hits = [p for p in VIDEOS.iterdir() if p.is_dir() and (p.name == ref or p.name.startswith(ref + "-") or p.name.endswith("-" + ref))]
    if len(hits) != 1:
        raise SystemExit(f"Cannot find exactly one video for {ref!r} in videos/ (found {[h.name for h in hits]})")
    return hits[0]


def load_script(vdir: Path) -> dict:
    return json.loads((vdir / "script.json").read_text(encoding="utf-8"))


def steps(script: dict):
    """(scene_index, step_index, key, step) for every narration line, in order."""
    for si, scene in enumerate(script["scenes"]):
        for ti, step in enumerate(scene["steps"]):
            yield si, ti, f"s{si}.{ti}", step


def slugify(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def fmt(script: dict) -> str:
    """'9:16' (TikTok, default) or '16:9' (app lessons, slide decks)."""
    f = script.get("format", "9:16")
    if f not in ("9:16", "16:9"):
        raise SystemExit(f"format must be '9:16' or '16:9', got {f!r}")
    return f


def size(script: dict) -> tuple[int, int]:
    return (1920, 1080) if fmt(script) == "16:9" else (1080, 1920)


def py() -> list[str]:
    # Prioritize pixi toolchain python if available
    pixi_py_win = ROOT / ".pixi" / "envs" / "default" / "python.exe"
    pixi_py_nix = ROOT / ".pixi" / "envs" / "default" / "bin" / "python"
    if sys.platform == "win32" and pixi_py_win.exists():
        return [str(pixi_py_win)]
    elif sys.platform != "win32" and pixi_py_nix.exists():
        return [str(pixi_py_nix)]
    
    pixi_bin = ROOT / ".tools" / ("pixi.exe" if sys.platform == "win32" else "pixi")
    if pixi_bin.exists():
        return [str(pixi_bin), "run", "--manifest-path", str(ROOT / "pixi.toml"), "python"]
        
    return [sys.executable]


# ---------------------------------------------------------------------- new
TEMPLATE_SCENES = [
    {"heading": "Dạng bài", "subheading": "<chủ đề>", "steps": [
        {"say": "<câu dẫn: cho đề bài>", "show": [{"id": "de", "math": "<công thức đề bài>"}]},
        {"say": "<gọi tên dạng bài>", "show": [{"id": "dang", "text": "<tên dạng bài>", "style": "accent"}]}]},
    {"heading": "Công thức cần nhớ", "steps": [
        {"say": "<phát biểu công thức 1>", "show": [{"id": "r1", "rich": "<$công thức$ và chữ>"}]}]},
    {"heading": "Lời giải", "steps": [
        {"say": "<bước 1>", "show": [{"id": "work", "math": "<biến đổi>"}]}]},
    {"heading": "Kết luận", "steps": [
        {"say": "<ghi nhớ>", "show": [{"id": "takeaway", "text": "<câu ghi nhớ>", "style": "accent"}]}]},
]


def new(title: str, subject: str = "TOÁN", slug: str | None = None) -> Path:
    VIDEOS.mkdir(exist_ok=True)
    nums = [int(m.group(1)) for p in VIDEOS.iterdir() if (m := re.match(r"V-(\d{4})", p.name))]
    vid = f"V-{(max(nums) + 1 if nums else 1):04d}"
    vdir = VIDEOS / f"{vid}-{slug or slugify(title)}"
    vdir.mkdir()
    script = {"id": vid, "slug": vdir.name.split("-", 2)[-1], "title": title, "subject": subject,
              "voice": "Minh Quân Pro", "scenes": TEMPLATE_SCENES}
    (vdir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    return vdir


def deck(pdf: Path, title: str, subject: str = "", voice: str = "Minh Quân Pro") -> Path:
    """New 16:9 video from a PDF deck: one slide scene per page, a draft step per page."""
    from engine.deck.pdf import import_pdf
    vdir = new(title, subject)
    info = import_pdf(pdf, vdir)
    scenes = []
    for p in info["pages"]:
        scenes.append({"type": "slide", "page": p["page"], "steps": [{
            "say": f"<lời giảng cho trang {p['page']}>",
            "reveal": [{"el": e["id"]} for e in p["elements"]],
        }]})
    script = load_script(vdir)
    script.update({"format": "16:9", "voice": voice, "scenes": scenes})
    (vdir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    return vdir


# ---------------------------------------------------------------------- check
def check(vdir: Path) -> list[str]:
    """Everything that can be caught before spending render time."""
    from engine.voice.text import lint

    s = load_script(vdir)
    problems = []
    for key in ("id", "title", "scenes"):
        if key not in s:
            problems.append(f"script.json is missing '{key}'")
    voice = s.get("voice", "Minh Quân Pro")
    from engine.voice.tts import ENGLISH
    ok_voices = ("Minh Quân Pro", "Trúc Ly", "record", "none") + tuple(ENGLISH)
    if voice not in ok_voices and not voice.startswith("clone:"):
        problems.append(f"voice {voice!r} must be one of {', '.join(ok_voices)} or 'clone:<name>'")
    silent = voice == "none"
    clones = {v for v in [voice] + [st.get("voice", "") for _, _, _, st in steps(s)] if str(v).startswith("clone:")}
    for v in sorted(clones):
        name = v[6:]
        if not (ROOT / "voices" / name / "sample.wav").exists():
            problems.append(f"voice {v!r}: no voices/{name}/sample.wav — run clone-voice first")
        elif not consent_signed(name):
            problems.append(f"voice {v!r}: voices/{name}/consent.md is not signed (name + date) — "
                            "a cloned voice cannot be used until its owner agrees")

    deck_info = None
    if any(sc.get("type") == "slide" for sc in s.get("scenes", [])):
        dj = vdir / "deck" / "deck.json"
        if not dj.exists():
            problems.append("slide scenes need deck/deck.json — create the video with the deck command")
        else:
            deck_info = json.loads(dj.read_text(encoding="utf-8"))
    for si, scene in enumerate(s.get("scenes", [])):
        if scene.get("type") == "slide":
            where = f"scene {si + 1} (slide page {scene.get('page', '?')})"
            if not deck_info:
                continue
            pages = {p["page"]: p for p in deck_info["pages"]}
            page = pages.get(scene.get("page"))
            if not page:
                problems.append(f"{where}: page {scene.get('page')} is not in the deck (1-{len(pages)})")
                continue
            ids = {e["id"] for e in page["elements"]}
            used = set()
            for ti, step in enumerate(scene.get("steps", [])):
                here = f"{where}, step {ti + 1}"
                if step.get("voice") and step["voice"] not in ("Minh Quân Pro", "Trúc Ly") + tuple(ENGLISH) and not str(step["voice"]).startswith("clone:"):
                    problems.append(f"{here}: voice {step['voice']!r} is not an allowed voice")
                for p in lint(step.get("say", ""), "en" if str(step.get("voice", voice)).startswith("en:") else "vi"):
                    problems.append(f"{here}: narration {p}")
                if "<" in step.get("say", ""):
                    problems.append(f"{here}: narration is still the placeholder")
                for r in step.get("reveal", []):
                    els = [] if "box" in r else ([r.get("el")] if isinstance(r.get("el"), int) else list(r.get("el") or []))
                    if "box" in r:
                        b = r["box"]
                        if len(b) != 4 or not (0 <= b[0] < b[2] <= 1920 and 0 <= b[1] < b[3] <= 1080):
                            problems.append(f"{here}: box {b} must be [x0, y0, x1, y1] inside 1920x1080")
                    for e in els:
                        if e not in ids:
                            problems.append(f"{here}: element {e} does not exist on page {page['page']} (1-{len(ids)})")
                        if e in used:
                            problems.append(f"{here}: element {e} is revealed twice")
                        used.add(e)
                    if r.get("at") and _norm_words(r["at"]) and not _contains(_norm_words(step.get("say", "")), _norm_words(r["at"])):
                        problems.append(f"{here}: cue {r['at']!r} is not a phrase in this step's narration")
            continue
        where = f"scene {si + 1} ({scene.get('heading', '?')})"
        if not scene.get("heading"):
            problems.append(f"{where}: missing heading")
        if not scene.get("steps"):
            problems.append(f"{where}: has no steps")
        seen = set()
        for ti, step in enumerate(scene.get("steps", [])):
            here = f"{where}, step {ti + 1}"
            if not silent:
                for p in lint(step.get("say", ""), step.get("lang") or ("en" if str(step.get("voice", voice)).startswith("en:") else "vi")):
                    problems.append(f"{here}: narration {p}")
            for el in step.get("show", []):
                if "id" not in el:
                    problems.append(f"{here}: a shown element has no id")
                if not any(k in el for k in ("text", "math", "rich", "image", "geometry", "chart", "figure", "passage")):
                    problems.append(f"{here}: element {el.get('id')!r} needs text, math, rich, image, geometry, chart, figure or passage")
                if "figure" in el and el["figure"] not in scene.get("figures", {}):
                    problems.append(f"{here}: figure {el['figure']!r} is not defined in this scene's 'figures'")
                if "image" in el and not (ROOT / el["image"]).exists():
                    problems.append(f"{here}: image {el['image']} not found")
                seen.add(el.get("id"))
            for h in step.get("hide", []):
                if h not in seen:
                    problems.append(f"{here}: hides {h!r}, which was never shown")
            if (step.get("band") or step.get("draw_graph")) and not scene.get("graph"):
                problems.append(f"{here}: uses the graph but the scene has no 'graph'")
    if problems:
        return problems

    # Typeset every element once: a LaTeX typo fails here in seconds, not mid-render.
    code = (
        "import json,sys\n"
        "from manim import tempconfig\n"
        "s0=json.load(open(sys.argv[1],encoding='utf-8'))\n"
        "with tempconfig({'pixel_width':540,'pixel_height':960} if s0.get('format','9:16')=='9:16' else {'pixel_width':960,'pixel_height':540}):\n"
        "  from engine.scenes import setup; setup.apply()\n"
        "  from engine.scenes.lesson import build_element, _fn\n"
        "  s=json.load(open(sys.argv[1],encoding='utf-8')); bad=[]\n"
        "  for si,sc in enumerate(s['scenes']):\n"
        "    if sc.get('type')=='slide': continue\n"
        "    for p in (sc.get('graph') or {}).get('pieces',[]):\n"
        "      try: _fn(p['f'])(0.5)\n"
        "      except Exception as e: bad.append(f\"scene {si+1}: graph function {p['f']!r}: {e}\")\n"
        "    for ti,st in enumerate(sc['steps']+[{'show':sc.get('end',[])}]):\n"
        "      for el in st.get('show',[]):\n"
        "        try: build_element(el, sc.get('figures'))\n"
        "        except Exception as e: bad.append(f\"scene {si+1}, step {ti+1}, {el.get('id')!r}: cannot typeset ({type(e).__name__}: {e})\")\n"
        "  print(json.dumps(bad,ensure_ascii=False))\n"
    )
    r = subprocess.run(py() + ["-c", code, str(vdir / "script.json")], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    try:
        problems += json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        problems.append("typesetting check crashed:\n" + r.stderr[-2000:])
    return problems


# ---------------------------------------------------------------------- scenes
def _render_scenes(vdir: Path, mode: str, durations: dict | None = None) -> dict[int, Path]:
    s = load_script(vdir)
    out_dir = vdir / "build" / mode
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(si: int) -> Path:
        job = out_dir / f"scene{si}.job.json"
        job.write_text(json.dumps({
            "spec": s["scenes"][si], "scene_index": si, "mode": mode, "format": fmt(s),
            "durations": durations or {}, "out": str(out_dir / f"scene{si}"),
        }, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(py() + ["-m", "engine.scenes.render_job", str(job)], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(f"scene {si + 1} failed to render:\n{r.stderr[-3000:]}")
        return out_dir / f"scene{si}.{'webm' if mode == 'final' else 'mp4'}"

    todo = [i for i, sc in enumerate(s["scenes"]) if sc.get("type", "lesson") == "lesson"]
    if not todo:
        return {}
    workers = max(1, min(len(todo), os.cpu_count() or 4))
    with ThreadPoolExecutor(workers) as ex:
        return dict(zip(todo, ex.map(one, todo)))


# ---------------------------------------------------------------------- slides
SLIDE_LEAD, SLIDE_TAIL, REVEAL_LEAD = 0.5, 0.8, 0.12
REVEAL_S = 0.55  # vox-director's measured fly-in duration
BREATH = 0.45


def _norm_words(text: str) -> list[str]:
    t = unicodedata.normalize("NFC", text.lower())
    return [w for w in (re.sub(r"[^\w]", "", x) for x in t.split()) if w]


def _contains(hay: list[str], needle: list[str]) -> bool:
    return any(hay[i:i + len(needle)] == needle for i in range(len(hay) - len(needle) + 1))


def _cue_time(line: dict | None, cue: str | None) -> float | None:
    """Start time (s, within the line) of the first word of `cue`, from the aligner."""
    if not line or not cue:
        return None
    words = line.get("words") or []
    toks = [(_norm_words(w["text"]) or [""])[0] for w in words]
    want = _norm_words(cue)
    for i in range(len(toks) - len(want) + 1):
        if toks[i:i + len(want)] == want:
            return words[i]["start"]
    return None


def _slide_scene(vdir: Path, si: int, scene: dict, rep: dict | None, mode: str) -> tuple[dict, dict]:
    """Timings ({duration, beats}) and the Remotion shot for one deck page."""
    from engine.deck.pdf import build_slide
    out_dir = vdir / "build" / mode
    t = SLIDE_LEAD
    beats, reveals = [], []
    for ti, step in enumerate(scene["steps"]):
        key = f"s{si}.{ti}"
        line = (rep or {}).get("lines", {}).get(key)
        dur = line["duration"] if line and "duration" in line else 3.0
        beats.append({"name": key, "t": round(t, 3)})
        for j, r in enumerate(step.get("reveal", [])):
            cue = _cue_time(line, r.get("at"))
            at = t + (cue - REVEAL_LEAD if cue is not None else 0.15 + 0.4 * j)
            reveals.append({**r, "t": max(at, t)})
        t += dur + BREATH
    beats.append({"name": "outro", "t": round(t, 3)})
    duration = t + SLIDE_TAIL
    reveals.sort(key=lambda r: r["t"])
    built = build_slide(vdir, scene["page"], reveals, out_dir, f"s{si}")
    shot = {
        "kind": "slide",
        "states": [{"src": src, "from": 0 if k == 0 else round((reveals[k - 1]["t"] + REVEAL_S) * FPS)}
                   for k, src in enumerate(built["states"])],
        "reveals": [{"src": sp["src"], "box": sp["box"], "from": round(r["t"] * FPS),
                     "anim": r.get("anim", "rise")} for sp, r in zip(built["sprites"], reveals)],
    }
    return {"duration": round(duration, 3), "beats": beats}, shot


def preview(vdir: Path) -> Path:
    """Contact sheet: the finished frame of every narration step, every scene."""
    from PIL import Image

    from tools.sheet import frames_from_movie, sheet_from_frames
    s = load_script(vdir)
    rep_path = vdir / "voice" / "report.json"
    rep = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else None
    movies = _render_scenes(vdir, "preview", _durations(vdir))
    frames = []
    for si, scene in enumerate(s["scenes"]):
        if scene.get("type") == "slide":
            tm, shot = _slide_scene(vdir, si, scene, rep, "preview")
            out = vdir / "build" / "preview"
            for ti, step in enumerate(scene["steps"]):
                # state after every reveal of this step has landed
                end = tm["beats"][ti + 1]["t"]
                k = sum(1 for r in shot["reveals"] if r["from"] / FPS < end)
                f = out / f"s{si}.step{ti}.jpg"
                Image.open(out / shot["states"][k]["src"]).convert("RGB").resize((640, 360)).save(f, quality=88)
                frames.append(f)
        else:
            frames += frames_from_movie(movies[si])
    return sheet_from_frames(frames, vdir / "preview.png")


# ---------------------------------------------------------------------- voice
def _durations(vdir: Path) -> dict | None:
    rep = vdir / "voice" / "report.json"
    if not rep.exists():
        return None
    return {k: v["duration"] for k, v in json.loads(rep.read_text(encoding="utf-8"))["lines"].items()}


def voice(vdir: Path, override: str | None = None, retries: int = 2) -> dict:
    """Make (or collect) one take per line, then check every take.

    TTS lines that fail the check are re-rolled up to `retries` times automatically;
    recorded lines that fail are reported so the person re-records just that line.
    """
    import soundfile as sf
    from engine.voice import align, tts

    s = load_script(vdir)
    v = override or s.get("voice", tts.DEFAULT_VOICE)
    lines_dir = vdir / "voice" / "lines"
    lines_dir.mkdir(parents=True, exist_ok=True)
    report = {"voice": v, "lines": {}}

    for si, ti, key, step in steps(s):
        say = step.get("say", "")
        if v == "none":
            # Silent video (e.g. a reading drill): each step simply holds on screen.
            report["lines"][key] = {"say": say, "status": "ok", "problem_words": [],
                                    "duration": float(step.get("hold", 3.0)), "takes": 0, "words": []}
            continue
        take = lines_dir / f"{key}.wav"
        attempts = 0
        while True:
            if v == "record":
                if not take.exists():
                    report["lines"][key] = {"say": say, "status": "missing", "problem_words": []}
                    break
                src = take
            else:
                # A step may name its own voice: dialogue decks (teacher / student).
                src = tts.synth(say, step.get("voice", v), attempt=attempts)
                shutil.copy(src, take)
            audio, sr = sf.read(take, dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(1)
            lang = step.get("lang") or tts.lang_of(step.get("voice", v))
            words = align.align(audio, sr, say, lang)
            status, bad = align.verdict(words, lang)
            if status == "redo" and v != "record" and attempts < retries:
                attempts += 1
                continue
            report["lines"][key] = {
                "say": say, "status": status, "problem_words": bad,
                "duration": round(len(audio) / sr, 3), "takes": attempts + 1,
                "words": align.to_json(words),
            }
            break

    (vdir / "voice" / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


# ---------------------------------------------------------------------- render
def render(vdir: Path, force: bool = False) -> Path:
    import numpy as np
    import soundfile as sf

    s = load_script(vdir)
    rep_path = vdir / "voice" / "report.json"
    if not rep_path.exists():
        raise SystemExit("No voice yet. Run: voice <video> (or record it) first.")
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    for v in {rep.get("voice", "")} | {st.get("voice", "") for _, _, _, st in steps(s)}:
        if str(v).startswith("clone:") and not consent_signed(v[6:]):
            raise SystemExit(f"voices/{v[6:]}/consent.md is not signed — cannot render with a cloned voice.")
    blocked = {k: l for k, l in rep["lines"].items() if l["status"] in ("redo", "missing")}
    if blocked and not force:
        lines = "\n".join(f"  {k}: {l['status']} {l.get('problem_words', [])} — {l['say']}" for k, l in blocked.items())
        raise SystemExit(f"These lines are not usable yet:\n{lines}\nFix them, or pass --force to render anyway.")
    durations = {k: l["duration"] for k, l in rep["lines"].items() if "duration" in l}

    clips = _render_scenes(vdir, "final", durations)
    final = vdir / "build" / "final"

    # Timeline: scenes back to back with a short held gap; each line at its beat.
    shots, captions = [], []
    t0 = 0.0
    sr = 48_000
    placements = []
    hidden_captions = {key for _, _, key, st in steps(s) if st.get("caption") is False}
    for si, scene in enumerate(s["scenes"]):
        start = t0 + (SCENE_GAP if si else 0)
        if scene.get("type") == "slide":
            tm, shot = _slide_scene(vdir, si, scene, rep, "final")
        else:
            clip = clips[si]
            tm = json.loads(Path(str(clip.with_suffix("")) + ".timings.json").read_text(encoding="utf-8"))
            shot = {"kind": "clip", "src": clip.name}
        shot.update({"from": round(start * FPS), "durationInFrames": round(tm["duration"] * FPS)})
        if scene.get("background"):
            bg = dict(scene["background"])
            src = ROOT / bg["image"]
            shutil.copy(src, final / f"bg{si}{src.suffix}")
            bg["src"] = f"bg{si}{src.suffix}"
            shot["background"] = bg
        shots.append(shot)
        beats = {b["name"]: b["t"] for b in tm["beats"]}
        names = [b["name"] for b in tm["beats"]]
        for i, name in enumerate(names):
            if name not in rep["lines"]:
                continue
            line = rep["lines"][name]
            nxt = beats[names[i + 1]] if i + 1 < len(names) else tm["duration"]
            cap_from = round((start + beats[name]) * FPS)
            wav = vdir / "voice" / "lines" / f"{name}.wav"
            if not line.get("words") or not wav.exists():
                continue  # silent step: nothing to caption or play
            placements.append((start + beats[name], wav))
            if name in hidden_captions:
                continue  # dictation / quiz line: heard, not shown
            captions.append({
                "from": cap_from,
                "durationInFrames": max(round((nxt - beats[name]) * FPS), 1),
                "words": [{"text": w["text"], "from": round(w["start"] * FPS), "to": max(round(w["end"] * FPS), round(w["start"] * FPS) + 1)}
                          for w in line.get("words", [])],
            })
        t0 = start + tm["duration"]

    total = t0 + 0.5
    track = np.zeros(int(total * sr) + sr, dtype=np.float32)
    for at, wav in placements:
        a, asr = sf.read(wav, dtype="float32")
        if a.ndim > 1:
            a = a.mean(1)
        if asr != sr:
            import soxr
            a = soxr.resample(a, asr, sr)
        i = int(at * sr)
        track[i:i + len(a)] += a[: len(track) - i]
    raw = final / "voice_raw.wav"
    sf.write(raw, track, sr)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", str(sr), str(final / "audio.wav")], check=True)

    fonts = final / "fonts"
    fonts.mkdir(exist_ok=True)
    for f in (ROOT / "assets" / "fonts").glob("*.ttf"):
        shutil.copy(f, fonts / f.name)

    W, H = size(s)
    props = {"fps": FPS, "width": W, "height": H, "durationInFrames": round(total * FPS),
             "subject": s.get("subject", ""), "audio": "audio.wav", "shots": shots, "captions": captions,
             "captions_mode": "off" if s.get("voice") == "none" else s.get("captions", "on")}
    (final / "lesson.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    rdir = ROOT / "engine" / "remotion"
    npx = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
    out = vdir / "final.mp4"
    concurrency = max(2, min(8, os.cpu_count() or 4))
    cmd = [npx, "remotion", "render", "src/index.ts", "Lesson", str(out),
           f"--props={final / 'lesson.json'}", f"--public-dir={final}",
           f"--concurrency={concurrency}", "--log=error"]
    r = subprocess.run(cmd, cwd=rdir, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("Remotion render failed:\n" + (r.stderr or r.stdout)[-3000:])

    # Cover for the TikTok upload screen: the first fully built frame of scene 1.
    first_step_end = captions[1]["from"] / FPS if len(captions) > 1 else 2.0
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{first_step_end - 0.2:.2f}", "-i", str(out),
                    "-frames:v", "1", str(vdir / "cover.png")], check=True)
    return out
