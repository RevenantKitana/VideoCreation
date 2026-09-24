"""Contact sheets: one frame from the end of every narration step."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


def frames_from_movie(mv: Path) -> list[Path]:
    """The last fully built frame of each step of a rendered Manim scene."""
    t = json.loads(Path(str(mv.with_suffix("")) + ".timings.json").read_text(encoding="utf-8"))
    beats = [b["t"] for b in t["beats"] if b["name"] != "end"]
    tmp = Path(tempfile.mkdtemp())
    out = []
    for i in range(len(beats) - 1):
        f = tmp / f"{mv.stem}-{i:03d}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(max(beats[i + 1] - 0.15, 0)),
                        "-i", str(mv), "-frames:v", "1", str(f)], check=True)
        out.append(f)
    return out


def sheet_from_frames(frames: list[Path], out: Path, tile_w_portrait: int = 420, tile_w_landscape: int = 640) -> Path:
    """Grid of frames: 4 columns for vertical video, 3 for horizontal."""
    imgs = [Image.open(f).convert("RGB") for f in frames]
    portrait = imgs[0].height > imgs[0].width
    tw = tile_w_portrait if portrait else tile_w_landscape
    th = round(tw * imgs[0].height / imgs[0].width)
    cols = min(len(imgs), 4 if portrait else 3)
    rows = -(-len(imgs) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * th), "white")
    for i, im in enumerate(imgs):
        sheet.paste(im.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sheet.save(out)
    return out


def sheet(movies: list[Path], out: Path) -> Path:
    frames = [f for mv in movies for f in frames_from_movie(mv)]
    return sheet_from_frames(frames, out)


if __name__ == "__main__":
    print(sheet([Path(p) for p in sys.argv[2:]], Path(sys.argv[1])))
