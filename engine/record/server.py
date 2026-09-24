"""
The recording studio: a local web page for reading the script aloud, line by line.

    ./os record V-0001      -> opens http://127.0.0.1:8765 in the browser

For every line the page offers:
  * "Nghe mẫu"  a VieNeu reading of the line, to hear the intended pace and stress;
  * karaoke     the words light up at that pace while you record, so you can follow;
  * one take per line, checked the moment you stop: the same local checker as TTS
    lines, so a skipped or wrong word is caught now, not after the render.

Takes land in videos/<id>/voice/lines/<key>.wav, cleaned (silence trimmed, gentle
denoise). "Hoàn tất" writes the voice report and switches the script to voice=record.
Everything stays on this laptop; the browser only talks to 127.0.0.1.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import soundfile as sf

from engine import pipeline
from engine.voice import align, tts

PAGE = Path(__file__).with_name("studio.html")
PORT = 8765


def _clean(raw: Path, out: Path) -> None:
    """Browser audio (webm/opus or mp4/aac) -> 48 kHz mono wav, denoised, trimmed."""
    tmp = out.with_suffix(".tmp.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-ac", "1", "-ar", "48000",
                    "-af", "highpass=f=70,afftdn=nf=-25", str(tmp)], check=True)
    a, sr = sf.read(tmp, dtype="float32")
    a = tts.trim(a, sr, pad_in=0.05, pad_out=0.15)
    peak = float(np.max(np.abs(a))) or 1.0
    sf.write(out, a * min(0.9 / peak, 8.0), sr)
    tmp.unlink(missing_ok=True)


def serve(vdir: Path, port: int = PORT) -> None:
    script = pipeline.load_script(vdir)
    lines = [(key, step["say"]) for _, _, key, step in pipeline.steps(script)]
    lines_dir = vdir / "voice" / "lines"
    raw_dir = vdir / "voice" / "raw"
    lines_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    guides: dict[str, dict] = {}
    guide_voice = script.get("guide_voice", tts.DEFAULT_VOICE)

    def make_guides():
        # Reference readings + their word timings drive "Nghe mẫu" and the karaoke pace.
        for key, say in lines:
            wav = tts.synth(say, guide_voice)
            a, sr = sf.read(wav, dtype="float32")
            guides[key] = {"wav": wav, "words": align.to_json(align.align(a, sr, say)),
                           "duration": len(a) / sr}

    threading.Thread(target=make_guides, daemon=True).start()

    def check_take(key: str, say: str) -> dict:
        a, sr = sf.read(lines_dir / f"{key}.wav", dtype="float32")
        words = align.align(a, sr, say)
        status, bad = align.verdict(words)
        results[key] = {"status": status, "problem_words": bad, "words": align.to_json(words),
                        "duration": round(len(a) / sr, 2)}
        return results[key]

    for key, say in lines:  # pick up takes from an earlier session
        if (lines_dir / f"{key}.wav").exists():
            check_take(key, say)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

        def do_GET(self):
            p = self.path.split("?")[0]
            if p == "/":
                return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if p.startswith("/fonts/") and p.endswith(".ttf"):
                f = pipeline.ROOT / "assets" / "fonts" / Path(p).name
                return self._send(200, f.read_bytes(), "font/ttf") if f.exists() else self._json({}, 404)
            if p == "/api/lines":
                return self._json({
                    "title": script.get("title", vdir.name),
                    "lines": [{"key": k, "say": s, "guide": guides.get(k, {}).get("words"),
                               "guide_duration": guides.get(k, {}).get("duration"),
                               "result": results.get(k)} for k, s in lines],
                })
            if p.startswith("/api/guide/"):
                key = p.rsplit("/", 1)[1].removesuffix(".wav")
                g = guides.get(key)
                return self._send(200, Path(g["wav"]).read_bytes(), "audio/wav") if g else self._json({"error": "not ready"}, 404)
            if p.startswith("/api/take/"):
                f = lines_dir / p.rsplit("/", 1)[1]
                return self._send(200, f.read_bytes(), "audio/wav") if f.exists() else self._json({}, 404)
            self._json({"error": "not found"}, 404)

        def do_POST(self):
            p = self.path.split("?")[0]
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if p.startswith("/api/take/"):
                key = p.rsplit("/", 1)[1]
                say = dict(lines).get(key)
                if say is None:
                    return self._json({"error": "unknown line"}, 404)
                ext = "mp4" if "mp4" in (self.headers.get("Content-Type") or "") else "webm"
                raw = raw_dir / f"{key}.{ext}"
                raw.write_bytes(body)
                _clean(raw, lines_dir / f"{key}.wav")
                return self._json(check_take(key, say))
            if p == "/api/finish":
                s = pipeline.load_script(vdir)
                s["voice"] = "record"
                (vdir / "script.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
                rep = pipeline.voice(vdir, "record")
                bad = [k for k, l in rep["lines"].items() if l["status"] in ("redo", "missing")]
                threading.Timer(1.0, httpd.shutdown).start()
                return self._json({"ok": not bad, "remaining": bad})
            self._json({"error": "not found"}, 404)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}/"
    print(f"Studio open at {url}  — close it with 'Hoàn tất' on the page (or Ctrl+C here).")
    if not os.environ.get("OS_NO_BROWSER"):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Studio closed.")
