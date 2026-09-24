"""
Figures for lesson scenes: geometry, charts and reading passages.

Every figure is a VGroup of NAMED PARTS plus an invisible frame. The frame spans the
whole figure (all points, all bars, the full passage), so a version that draws only
some parts has exactly the same size and position as the complete one. That is
what lets a step "draw BC next" or "add the Nuclear slice" without anything moving.

    geometry parts   A (point + label), AB (segment), poly:ABC, circle:O,
                     right:BAC, angle:BAC, len:AB
    chart parts      one per data item, by its label ("Than", "Khí", …)
    passage parts    w0, w1, … one per word (marks find words by text)
"""

from __future__ import annotations

import math
import re
import unicodedata

import numpy as np
from manim import (
    Arc,
    Dot,
    Line,
    DashedLine,
    Polygon,
    Rectangle,
    RoundedRectangle,
    Sector,
    VGroup,
    VMobject,
)

from . import theme, typeset

INK, JADE, SOFT, CLAY = theme.INK, theme.JADE, theme.JADE_SOFT, theme.CLAY


def _frame(x0, y0, x1, y1) -> Rectangle:
    r = Rectangle(width=max(x1 - x0, 0.01), height=max(y1 - y0, 0.01), stroke_width=0, fill_opacity=0)
    return r.move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0])


class Figure(VGroup):
    """A frame plus named parts. `parts` preserves drawing order."""

    def __init__(self, frame: VMobject, parts: dict[str, VMobject]):
        super().__init__(frame, *parts.values())
        self.frame = frame
        self.parts = parts


def select(parts: dict, draw) -> dict:
    """Keep the parts named in `draw` (None = all). 'AB' also matches 'len:AB'-style
    prefixes only when written out; point names pull in their label."""
    if draw is None:
        return parts
    want = set(draw)
    return {k: v for k, v in parts.items() if k in want}


# ------------------------------------------------------------------ geometry
def geometry(spec: dict, draw=None) -> Figure:
    pts = {k: np.array(v, dtype=float) for k, v in spec["points"].items()}
    xs = [p[0] for p in pts.values()]
    ys = [p[1] for p in pts.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    size = spec.get("size", 5.0)
    k = size / span
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    P = {n: np.array([(p[0] - cx) * k, (p[1] - cy) * k, 0.0]) for n, p in pts.items()}
    centre = np.mean(list(P.values()), axis=0)

    parts: dict[str, VMobject] = {}
    # fills first so strokes sit on top
    for poly in spec.get("polygons", []):
        names = poly["pts"] if isinstance(poly, dict) else poly
        fill = poly.get("fill", True) if isinstance(poly, dict) else True
        parts[f"poly:{names}"] = Polygon(*[P[c] for c in names], stroke_width=0,
                                         fill_color=SOFT, fill_opacity=0.75 if fill else 0)
    for c in spec.get("circles", []):
        o = P[c["center"]]
        r = c["r"] * k if "r" in c else np.linalg.norm(P[c["through"]] - o)
        parts[f"circle:{c['center']}"] = Arc(radius=r, angle=2 * math.pi, arc_center=o, color=INK,
                                            stroke_width=theme.STROKE)
    dashed = set(spec.get("dashed", []))
    for seg in spec.get("segments", []):
        a, b = seg[0], seg[1]
        L = DashedLine if seg in dashed else Line
        parts[seg] = L(P[a], P[b], color=INK, stroke_width=theme.STROKE)
    for ang in spec.get("right_angles", []):
        p, v, q = P[ang[0]], P[ang[1]], P[ang[2]]
        u, w = (p - v) / np.linalg.norm(p - v), (q - v) / np.linalg.norm(q - v)
        s = 0.28
        parts[f"right:{ang}"] = VMobject(color=INK, stroke_width=theme.STROKE_HAIRLINE).set_points_as_corners(
            [v + s * u, v + s * u + s * w, v + s * w])
    for a in spec.get("angles", []):
        at = a["at"] if isinstance(a, dict) else a
        p, v, q = P[at[0]], P[at[1]], P[at[2]]
        t1 = math.atan2(*(p - v)[1::-1])
        t2 = math.atan2(*(q - v)[1::-1])
        d = (t2 - t1 + math.pi) % (2 * math.pi) - math.pi
        arc = Arc(radius=0.45, start_angle=t1, angle=d, arc_center=v, color=JADE, stroke_width=theme.STROKE_HAIRLINE + 1)
        group = VGroup(arc)
        if isinstance(a, dict) and a.get("label"):
            mid = t1 + d / 2
            lab = typeset.math(a["label"], "muted").move_to(v + 0.85 * np.array([math.cos(mid), math.sin(mid), 0]))
            group.add(lab)
        parts[f"angle:{at}"] = group
    for seg, text in spec.get("lengths", {}).items():
        a, b = P[seg[0]], P[seg[1]]
        mid = (a + b) / 2
        n = np.array([-(b - a)[1], (b - a)[0], 0.0])
        n /= np.linalg.norm(n) or 1
        if np.dot(n, mid - centre) < 0:
            n = -n
        lab = typeset.math(text, "deep")
        lab.move_to(mid + n * (0.3 + 0.5 * max(lab.width, lab.height)))
        parts[f"len:{seg}"] = lab
    labels = spec.get("labels", {n: n for n in pts})
    for n, p in P.items():
        g = VGroup(Dot(p, radius=0.06, color=INK))
        if labels.get(n):
            d = p - centre
            d = d / (np.linalg.norm(d) or 1)
            g.add(typeset.math(labels[n], "body").scale(0.8).move_to(p + d * 0.38))
        parts[n] = g

    full = VGroup(*parts.values())
    frame = _frame(full.get_left()[0] - 0.1, full.get_bottom()[1] - 0.1, full.get_right()[0] + 0.1, full.get_top()[1] + 0.1)
    return Figure(frame, select(parts, draw))


# ------------------------------------------------------------------ charts
def _colours(n, emphasis=None):
    ramp = list(theme.CHART_RAMP)
    return [ramp[i % len(ramp)] for i in range(n)]


def chart(spec: dict, draw=None) -> Figure:
    kind = spec.get("type", "bar")
    data = spec["data"]
    unit = spec.get("unit", "")
    colours = _colours(len(data))
    for i, d in enumerate(data):
        if d.get("emphasis") or d.get("colour") == "clay":
            colours[i] = CLAY
    parts: dict[str, VMobject] = {}

    if kind == "pie":
        R = spec.get("radius", 2.0)
        total = sum(d["value"] for d in data) or 1
        a0 = math.pi / 2
        for d, col in zip(data, colours):
            ang = -2 * math.pi * d["value"] / total
            sector = Sector(radius=R, start_angle=a0, angle=ang, fill_color=col, fill_opacity=1,
                            stroke_color=theme.PAPER, stroke_width=3)
            mid = a0 + ang / 2
            val = typeset.words(f"{_fmt(d['value'])}{unit}", "body").scale(0.8)
            val.move_to([0.68 * R * math.cos(mid), 0.68 * R * math.sin(mid), 0])
            if col in (theme.CHART_RAMP[0], theme.CHART_RAMP[1], CLAY):
                val.set_fill(theme.PAPER)
            lab = typeset.words(d["label"], "muted")
            lab.move_to([(R + 0.3 + lab.width / 2) * math.cos(mid), (R + 0.3) * math.sin(mid), 0])
            parts[d["label"]] = VGroup(sector, val, lab)
            a0 += ang
    elif kind == "line":
        W, H = spec.get("width", 7.0), spec.get("height", 3.6)
        vmax = spec.get("max", max(d["value"] for d in data) * 1.15)
        n = len(data)
        xs = [-W / 2 + W * i / max(n - 1, 1) for i in range(n)]
        ys = [-H / 2 + H * d["value"] / vmax for d in data]
        parts["__axis"] = VGroup(Line([-W / 2, -H / 2, 0], [W / 2, -H / 2, 0], color=theme.INK_MUTED,
                                      stroke_width=theme.STROKE_HAIRLINE))
        prev = None
        for i, d in enumerate(data):
            p = np.array([xs[i], ys[i], 0])
            g = VGroup(Dot(p, radius=0.07, color=colours[0] if not d.get("emphasis") else CLAY))
            if prev is not None:
                g.add(Line(prev, p, color=theme.CHART_RAMP[0], stroke_width=theme.STROKE))
            g.add(typeset.words(f"{_fmt(d['value'])}{unit}", "muted").next_to(p, [0, 1, 0], buff=0.15))
            g.add(typeset.words(d["label"], "muted").move_to([xs[i], -H / 2 - 0.35, 0]))
            parts[d["label"]] = g
            prev = p
    else:  # bar
        W, H = spec.get("width", 7.0), spec.get("height", 3.6)
        vmax = spec.get("max", max(d["value"] for d in data))
        n = len(data)
        slot = W / n
        bw = slot * 0.62
        parts["__axis"] = VGroup(Line([-W / 2, -H / 2, 0], [W / 2, -H / 2, 0], color=theme.INK_MUTED,
                                      stroke_width=theme.STROKE_HAIRLINE))
        for i, (d, col) in enumerate(zip(data, colours)):
            h = max(H * d["value"] / vmax, 0.02)
            x = -W / 2 + slot * (i + 0.5)
            bar = Rectangle(width=bw, height=h, fill_color=col, fill_opacity=1, stroke_width=0)
            bar.move_to([x, -H / 2 + h / 2, 0])
            val = typeset.words(f"{_fmt(d['value'])}{unit}", "muted").next_to(bar, [0, 1, 0], buff=0.12)
            lab = typeset.words(d["label"], "muted")
            if lab.width > slot * 0.95:
                lab.scale_to_fit_width(slot * 0.95)
            lab.move_to([x, -H / 2 - 0.35, 0])
            parts[d["label"]] = VGroup(bar, val, lab)

    full = VGroup(*parts.values())
    frame = _frame(full.get_left()[0] - 0.1, full.get_bottom()[1] - 0.1, full.get_right()[0] + 0.1, full.get_top()[1] + 0.1)
    keep = None if draw is None else list(draw) + ["__axis"]
    return Figure(frame, select(parts, keep))


def _fmt(v) -> str:
    return (f"{v:g}").replace(".", ",")  # Vietnamese decimal comma


# ------------------------------------------------------------------ passages
def passage(spec, draw=None) -> Figure:
    """A reading card: wrapped words, each its own part, on a paper-edge card."""
    text = spec if isinstance(spec, str) else spec["text"]
    width = 7.2 if isinstance(spec, str) else spec.get("width", 7.2)
    style = "body" if isinstance(spec, str) else spec.get("style", "body")
    words = text.split()
    pieces = [typeset.words(w, style).scale(0.72) for w in words]
    space = 0.13
    line_h = max(p.height for p in pieces) * 1.25
    x, y = 0.0, 0.0
    for p in pieces:
        if x > 0 and x + p.width > width:
            x, y = 0.0, y - line_h
        p.set_baseline(y).shift([x - p.get_left()[0], 0, 0])
        x += p.width + space
    body = VGroup(*pieces)
    card = RoundedRectangle(width=width + 0.7, height=body.height + 0.7, corner_radius=0.15,
                            fill_color=theme.PAPER_EDGE, fill_opacity=1, stroke_width=0).move_to(body)
    card.set_z_index(-2)  # highlights (z -1) sit between the card and the words
    parts = {"card": card}
    parts.update({f"w{i}": p for i, p in enumerate(pieces)})
    frame = _frame(card.get_left()[0], card.get_bottom()[1], card.get_right()[0], card.get_top()[1])
    fig = Figure(frame, parts)
    fig.words = words
    return fig


def _norm(w: str) -> str:
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFC", w.lower()))


def find_words(fig: Figure, text: str) -> list[VMobject]:
    """The word parts spelling `text` (first occurrence)."""
    want = [_norm(t) for t in text.split()]
    toks = [_norm(w) for w in fig.words]
    for i in range(len(toks) - len(want) + 1):
        if toks[i:i + len(want)] == want:
            return [fig.parts[f"w{j}"] for j in range(i, i + len(want))]
    return []


def mark(targets: list[VMobject], style: str = "highlight") -> VMobject:
    g = VGroup(*targets)
    pad = 0.06
    x0, x1 = g.get_left()[0] - pad, g.get_right()[0] + pad
    y0, y1 = g.get_bottom()[1] - pad, g.get_top()[1] + pad
    if style == "underline":
        return Line([x0, y0, 0], [x1, y0, 0], color=JADE, stroke_width=theme.STROKE)
    if style == "strike":
        ym = (y0 + y1) / 2
        return Line([x0, ym, 0], [x1, ym, 0], color=CLAY, stroke_width=theme.STROKE)
    if style == "box":
        return Rectangle(width=x1 - x0, height=y1 - y0, color=JADE, stroke_width=theme.STROKE_HAIRLINE + 1).move_to(g)
    if style == "circle":
        from manim import Ellipse
        return Ellipse(width=(x1 - x0) * 1.12, height=(y1 - y0) * 1.3, color=CLAY,
                       stroke_width=theme.STROKE_HAIRLINE + 1).move_to(g)
    r = Rectangle(width=x1 - x0, height=y1 - y0, stroke_width=0, fill_color=SOFT, fill_opacity=0.9).move_to(g)
    r.set_z_index(-1)
    return r
