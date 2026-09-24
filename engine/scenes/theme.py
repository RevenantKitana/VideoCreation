"""
Aiducation palette — FLAT EDITORIAL: cream, jade, matte black.

These values are not invented. They are transcribed from the Remotion project's
`aiducation-ielts/src/theme.ts`, which is the source of truth for the brand. If that
file changes, change this one to match — a Manim insert composited next to a Remotion
frame in the same cut has to be the same cream, or the seam shows.

House rules carried over from the Remotion side, because they apply doubly to
animation:
  - No gradients. Colour is flat fill; form comes from silhouette and value.
  - No blurred shadows. Cards lift by hard offset, not by blur.
  - Limited palette. Three colours carry everything. `CLAY` is the restrained fourth
    and means one thing only: "this is the wrong version."
"""

from __future__ import annotations

# --- cream -----------------------------------------------------------------
PAPER = "#F5EFE2"  # the page
PAPER_EDGE = "#EBE3D1"  # panels and cards — one step down, never white
PAPER_LINE = "#DFD5C0"  # rules, hairlines, dividers

# --- matte black -----------------------------------------------------------
INK = "#1C1C1A"  # primary text and marks. Warm, never pure black
INK_MUTED = "#57554E"  # secondary text, labels
INK_FAINT = "#A6A196"  # retired / dimmed lines

# --- jade ------------------------------------------------------------------
JADE = "#1F6F5C"  # brand accent: headings, targets, the correct version
JADE_SOFT = "#D3E3DA"  # flat jade wash for highlighter and panel fills
JADE_DEEP = "#14503F"  # pressed/darker jade for small solid shapes

# --- the restrained fourth -------------------------------------------------
# Negative signal ONLY: trap labels, the weak column, strikethroughs. Roughly one
# element per scene. To go strictly three-colour, point this at INK.
CLAY = "#B4553A"

# --- chart ramp ------------------------------------------------------------
# A value ramp inside the brand hue, so colour can carry the argument rather than
# merely distinguish categories. Mirrors CHART in theme.ts.
CHART_JADE_1 = "#1B6553"
CHART_JADE_2 = "#3D8B76"
CHART_JADE_3 = "#74AD9B"
CHART_JADE_4 = "#AFCCC1"

CHART_RAMP = [CHART_JADE_1, CHART_JADE_2, CHART_JADE_3, CHART_JADE_4]

# --- type ------------------------------------------------------------------
# Be Vietnam Pro ships a full Vietnamese subset (Latin Extended Additional,
# U+1EA0–U+1EF9). It is vendored in assets/fonts/ and registered at runtime — no
# system font install is assumed anywhere in this repo.
FONT_BODY = "Be Vietnam Pro"

# Type scale, in Manim font_size units (Manim's default body is 48).
# Tuned against a 1080×1920 vertical frame, which is the dominant delivery format.
SIZE_TITLE = 66
SIZE_SUBTITLE = 38
SIZE_BODY = 44
SIZE_CAPTION = 32
SIZE_LABEL = 28

# --- stroke ----------------------------------------------------------------
# One stroke weight across every shape in a scene. Flat design reads as flat because
# the line weight does not vary with importance; colour and size carry hierarchy.
STROKE = 4.0
STROKE_HAIRLINE = 2.0
