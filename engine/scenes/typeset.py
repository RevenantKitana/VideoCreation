"""
Typesetting without LaTeX.

Every body line — Vietnamese words and formulas alike — is drawn by ziamath from the
vendored fonts, so text and math share one unit system and one baseline. Manim only
places the resulting shapes.

Two things about Manim's SVG import shape this file:
  * it sizes an SVG by its glyph outlines, not its viewBox, so we inject an invisible
    rectangle covering the viewBox; bounds then equal the font box and the baseline
    sits at a known fraction of the height;
  * it drops the positions of ziamath's nested <svg> math-in-text, so mixed lines are
    split on `$...$` and assembled here piece by piece instead.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

import ziamath as zm
from manim import SVGMobject, Text, VGroup

from . import theme
from .setup import FONT_DIR, ROOT

zm.config.svg2 = False  # plain paths; Manim's parser mishandles <symbol>/<use> offsets

FONT_REGULAR = str(FONT_DIR / "BeVietnamPro-Regular.ttf")
FONT_SEMIBOLD = str(FONT_DIR / "BeVietnamPro-SemiBold.ttf")
CACHE = ROOT / ".cache" / "svg"
PX = 100  # ziamath render size; everything is rescaled by UNIT afterwards
# ziamath's type is optically larger than MathTex at the same nominal size; 0.8 matches
# the measured line widths of the reference lesson (aiducation-manim dau-dao-ham).
TYPE_SCALE = 0.8

# A minus (or plus) that starts an expression ("(-1", "= -x", "; -1") is unary. ziamath, like
# TeX, spaces a bare "-" as a binary operator there, which prints "( − ∞". Bracing it
# makes it an ordinary symbol. Done here so script writers never need to know that.
_UNARY = re.compile(r"(^|[=(\[;,<>&]|\\le|\\ge|\\in|\\Rightarrow|\\to|\\quad|\\ |\\text\{[^}]*\})\s*([-+])(?!\})")


def _unary_minus(latex: str) -> str:
    return _UNARY.sub(lambda m: m.group(1) + "{" + m.group(2) + "}", latex)

STYLES = {
    #          font size (Manim units)  colour              weight
    "body":   (theme.SIZE_BODY,        theme.INK,          "regular"),
    "accent": (theme.SIZE_SUBTITLE,    theme.JADE,         "bold"),
    "deep":   (theme.SIZE_BODY,        theme.JADE_DEEP,    "regular"),
    "muted":  (theme.SIZE_CAPTION,     theme.INK_MUTED,    "regular"),
    "wrong":  (theme.SIZE_BODY,        theme.CLAY,         "regular"),
}


class Piece(VGroup):
    """A typeset fragment that knows where its baseline is."""

    # Where the baseline sits, as a fraction of height measured from the bottom.
    # Stored as a fraction so it survives any later scale().
    bfrac: float = 0.25

    @property
    def baseline(self) -> float:
        return self.bfrac * self.height

    @baseline.setter
    def baseline(self, value: float) -> None:
        self.bfrac = value / self.height if self.height else 0.25

    def baseline_y(self) -> float:
        return self.get_bottom()[1] + self.baseline

    def set_baseline(self, y: float) -> "Piece":
        return self.shift([0, y - self.baseline_y(), 0])


def _svg_piece(drawable, color: str) -> Piece:
    svg = drawable.svg()
    m = re.search(r'viewBox="([-\d.e]+) ([-\d.e]+) ([-\d.e]+) ([-\d.e]+)"', svg)
    minx, miny, w, h = (float(v) for v in m.groups())
    box = f'<rect x="{minx}" y="{miny}" width="{w}" height="{h}" fill="none" stroke="none"/>'
    svg = re.sub(r"(<svg[^>]*>)", r"\1" + box, svg, count=1)

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{hashlib.md5(svg.encode()).hexdigest()[:16]}.svg"
    if not path.exists():
        path.write_text(svg, encoding="utf-8")

    mob = SVGMobject(str(path), height=None, stroke_width=0)
    mob.set_fill(color, 1).set_stroke(width=0)
    mob[0].set_fill(opacity=0)  # the viewBox rectangle stays invisible
    mob.scale(UNIT())

    piece = Piece(*mob.submobjects)
    # baseline is svg y=0; the box runs miny..miny+h downwards
    piece.baseline = (miny + h) / h * piece.height
    return piece


@lru_cache(maxsize=None)
def UNIT() -> float:
    """Manim units per ziamath px, calibrated so a ziamath line at a given style
    renders at the same cap height as Manim's own Text at that font_size."""
    manim_cap = Text("H", font_size=100).height
    probe = zm.Text("H", textfont=FONT_REGULAR, size=PX).svg()
    # glyph-tight height of "H" in svg units: read it from the path's y extent
    ys = [float(v) for v in re.findall(r"[ML] [-\d.]+ ([-\d.]+)", probe)]
    return manim_cap / (max(ys) - min(ys))


def _font(weight: str) -> str:
    return FONT_SEMIBOLD if weight == "bold" else FONT_REGULAR


def math(latex: str, style: str = "body") -> Piece:
    size, color, _ = STYLES[style]
    p = _svg_piece(zm.Math.fromlatex(_unary_minus(latex), size=PX), color)
    return p.scale(TYPE_SCALE * size / 100, about_point=p.get_bottom())


def words(text: str, style: str = "body") -> Piece:
    size, color, weight = STYLES[style]
    p = _svg_piece(zm.Text(text, textfont=_font(weight), size=PX), color)
    return p.scale(TYPE_SCALE * size / 100, about_point=p.get_bottom())


def rich_line(s: str, style: str = "body") -> Piece:
    """One line mixing Vietnamese and `$math$`, assembled on a shared baseline."""
    size = STYLES[style][0]
    gap = 0.28 * TYPE_SCALE * size / 100 * Text("H", font_size=100).height  # about one word space
    parts = [p for p in re.split(r"(\$[^$]+\$)", s) if p != ""]
    pieces: list[Piece] = []
    x = 0.0
    for i, part in enumerate(parts):
        is_math = part.startswith("$")
        body = part[1:-1] if is_math else part
        if not body.strip():
            continue
        piece = math(body, style) if is_math else words(body.strip(), style)
        if pieces:
            touching = (not is_math and not part[:1].isspace()) or (
                is_math and not parts[i - 1][-1:].isspace()
            )
            x += 0 if touching else gap
        piece.set_baseline(0).shift([x - piece.get_left()[0], 0, 0])
        x = piece.get_right()[0]
        pieces.append(piece)
    line = Piece(*pieces)
    line.baseline = 0 - line.get_bottom()[1]
    return line


def block(s: str, style: str = "body", line_spacing: float = 1.45) -> Piece:
    """Multi-line (`\\n`) rich text, centred, with even baselines."""
    lines = [rich_line(l, style) for l in s.split("\n")]
    step = line_spacing * TYPE_SCALE * STYLES[style][0] / 100 * Text("H", font_size=100).height * 1.6
    for i, l in enumerate(lines):
        l.set_baseline(-i * step)
        l.shift([-l.get_center()[0], 0, 0])
    out = Piece(*lines)
    out.baseline = lines[-1].baseline_y() - out.get_bottom()[1]
    return out
