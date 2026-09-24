"""
Render one scene of a script.json in a fresh process.

    python -m engine.scenes.render_job <job.json>

job.json: {"spec": {...}, "scene_index": 0, "format": "9:16"|"16:9", "durations": {"s0.0": 4.2, ...},
           "out": "videos/V-0001/build/scene0", "mode": "final" | "preview"}

final   -> <out>.webm  transparent VP9 (Remotion composites it over the brand frame)
preview -> <out>.mp4   opaque, half resolution @15fps, for contact sheets. Seconds, not minutes.
Both write <out>.timings.json: when each narration line starts inside the scene.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from manim import config, tempconfig


def main(job_path: str) -> None:
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    out = Path(job["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    final = job.get("mode", "final") == "final"
    w, h = (1920, 1080) if job.get("format") == "16:9" else (1080, 1920)

    media = Path(tempfile.mkdtemp(prefix="manim-"))
    opts = {
        "pixel_width": w if final else w // 2,
        "pixel_height": h if final else h // 2,
        "frame_rate": 60 if final else 15,
        "transparent": final,
        "format": "mov" if final else "mp4",
        "media_dir": str(media),
        "disable_caching": True,
        "verbosity": "WARNING",
        "progress_bar": "none",
        "output_file": "scene",
    }
    with tempconfig(opts):
        from engine.scenes import setup
        setup.apply()
        from engine.scenes.lesson import LessonScene

        class Job(LessonScene):
            spec = job["spec"]
            durations = job.get("durations", {})
            scene_index = job["scene_index"]
            timings_path = str(out) + ".timings.json"

        scene = Job()
        scene.render()
        movie = Path(scene.renderer.file_writer.movie_file_path)

    if final:
        # Remotion cannot decode Manim's QuickTime; VP9 WebM keeps alpha and it can.
        # -auto-alt-ref 0 is required or libvpx silently drops the alpha plane.
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", str(movie),
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28",
            "-row-mt", "1", "-auto-alt-ref", "0", "-speed", "2",
            str(out) + ".webm",
        ], check=True)
    else:
        shutil.copy(movie, str(out) + ".mp4")
    shutil.rmtree(media, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1])
