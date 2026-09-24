"""
Process-wide Manim setup. Ported from aiducation-manim/aiducation/config.py, minus
LaTeX: formulas are typeset by ziamath (see typeset.py), so no TeX install exists on
any employee laptop and nothing here may assume one.
"""

from __future__ import annotations

import random
import warnings
from pathlib import Path

import manimpango
import numpy as np
from manim import Text, config

from . import theme

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT / "assets" / "fonts"
SEED = 20260813

# Manim's 16:9 default density. Keeping it across aspects is what keeps font_size=44
# the same physical size in a vertical render as in a horizontal one.
_PX_PER_UNIT = 1920 / 14.222222222222221


def normalize_frame() -> None:
    """Make frame_width/height describe what the camera shows.

    Manim leaves the logical 16:9 frame alone when pixel size changes, so a 1080x1920
    render would silently report frame_height=8 while showing 25 units. Every layout
    computed from frame_height would then be wrong by 3x.
    """
    # Geometry is fixed at the 1080x1920 delivery size whatever the pixel count, so a
    # 540x960 preview is the same picture at half resolution, not a different layout.
    vertical = config.pixel_height >= config.pixel_width
    config.frame_width = (1080 if vertical else 1920) / _PX_PER_UNIT
    config.frame_height = (1920 if vertical else 1080) / _PX_PER_UNIT


def register_fonts() -> None:
    for path in sorted(FONT_DIR.glob("*.ttf")):
        if not manimpango.register_font(str(path)):
            warnings.warn(f"Pango refused to register {path.name}", stacklevel=2)
    if theme.FONT_BODY not in set(manimpango.list_fonts()):
        raise RuntimeError(
            f"{theme.FONT_BODY!r} is not visible to Pango. Vietnamese would fall back to "
            "a system font with unknown coverage, so this is fatal."
        )


def patch_straight_alpha() -> None:
    """Un-premultiply alpha on transparent renders.

    Cairo hands Manim premultiplied RGBA and Manim encodes it as straight alpha, so
    every semi-transparent pixel composites too dark (jade-soft turns grey mid-fade).
    ffmpeg's unpremultiply filter does not fix it; it has to happen before encoding.
    """
    from manim.scene import scene_file_writer as sfw

    # manim 0.21 moved encoding into _PartialMovieEncodeJob; 0.20 (conda-forge) has it
    # on SceneFileWriter. Patch whichever exists.
    job = getattr(sfw, "_PartialMovieEncodeJob", None)
    name = "_encode_and_write_frame"
    if job is None or not hasattr(job, name):
        job, name = sfw.SceneFileWriter, "encode_and_write_frame"
    original = getattr(job, name, None)
    if original is None:
        raise RuntimeError(
            "Manim's frame writer moved (manim upgraded?). Re-check whether it now "
            "un-premultiplies alpha itself; if not, re-point this patch."
        )
    if getattr(original, "_patched", False):
        return

    def _encode_and_write_frame(self, frame, num_frames):
        if config.transparent and frame.ndim == 3 and frame.shape[2] == 4:
            alpha = frame[:, :, 3].astype(np.uint16)[:, :, None]
            rgb = frame[:, :, :3].astype(np.uint16)
            safe = np.maximum(alpha, 1)
            out = np.minimum((rgb * 255 + safe // 2) // safe, 255)
            frame = frame.copy()
            frame[:, :, :3] = np.where(alpha > 0, out, 0).astype(np.uint8)
        return original(self, frame, num_frames)

    _encode_and_write_frame._patched = True
    setattr(job, name, _encode_and_write_frame)


_applied = False


def apply() -> None:
    global _applied
    normalize_frame()
    # Manim's text cache defaults to ./media in the working dir; keep it in .cache/
    # (render_job passes its own temp media_dir, which is left alone).
    if str(config.media_dir) in ("./media", "media"):
        config.media_dir = str(ROOT / ".cache" / "manim")
    if _applied:
        return
    patch_straight_alpha()
    register_fonts()
    Text.set_default(font=theme.FONT_BODY, color=theme.INK, font_size=theme.SIZE_BODY)
    random.seed(SEED)
    np.random.seed(SEED)
    _applied = True
