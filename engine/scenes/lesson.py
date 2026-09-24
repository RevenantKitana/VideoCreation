"""
One generic scene that animates any `scenes[i]` block of a video's script.json.

A scene is a heading plus a vertical stack of *slots*. Each step of the script says
one narration line and changes what is on screen:

    show: [{id, text|math|rich|image, style?}]   id new  -> fades/writes in
                                                  id seen -> transforms in place
    hide: [id, ...]                               fades out
    band: [x0, x1]                                highlight an interval on the graph
    draw_graph: true                              draws the scene's graph

Slots are laid out ONCE, from every version of every element the scene will ever
show, so nothing jumps when a later step replaces a formula with a longer one. That
is the generalised form of aiducation-manim's hand-written `replacement()` helper.

Ported look (safe areas, brand rule, cream/jade/ink, beat + hold_for pacing) comes
from aiducation-manim's AiducationScene; only the authoring model is new.
"""

from __future__ import annotations

import json
import math as pymath
from pathlib import Path

import numpy as np
from manim import (
    AnimationGroup,
    Indicate,
    DOWN,
    LEFT,
    UP,
    Dot,
    Axes,
    Create,
    DashedLine,
    FadeIn,
    FadeOut,
    ImageMobject,
    Line,
    Rectangle,
    Scene,
    Square,
    Text,
    Transform,
    VGroup,
    Write,
    config,
)

from . import theme, typeset
from .setup import ROOT

BREATH = 0.45  # silence after each line before the next begins, seconds

SAFE_FUNCS = {
    k: getattr(np, k) for k in ("sin", "cos", "tan", "exp", "log", "sqrt", "abs", "arctan")
}
SAFE_FUNCS.update(pi=pymath.pi, e=pymath.e)


def _fn(expr: str):
    code = compile(expr.replace("^", "**"), "<graph>", "eval")
    for name in code.co_names:
        if name != "x" and name not in SAFE_FUNCS:
            raise ValueError(f"graph function uses unknown name {name!r}: {expr}")
    return lambda x: float(eval(code, {"__builtins__": {}}, {**SAFE_FUNCS, "x": x}))


def build_element(el: dict, figures: dict | None = None):
    """One on-screen element. `figures` holds a scene's named geometry/charts so a
    step can say {"id": "tri", "figure": "tri", "draw": ["AB", "BC"]}."""
    from . import figures as F
    style = el.get("style", "body")
    if "figure" in el:
        spec = (figures or {})[el["figure"]]
        kind = "chart" if "data" in spec else "geometry"
        el = {**el, kind: spec}
    if "geometry" in el:
        return F.geometry(el["geometry"], el.get("draw"))
    if "chart" in el:
        return F.chart(el["chart"], el.get("draw"))
    if "passage" in el:
        return F.passage(el["passage"])
    if "math" in el:
        return typeset.math(el["math"], style)
    if "rich" in el:
        return typeset.block(el["rich"], style)
    if "text" in el:
        return typeset.block(el["text"], style)
    if "image" in el:
        img = ImageMobject(str(ROOT / el["image"]))
        return img.scale_to_fit_height(el.get("height", 4.0))
    raise ValueError(f"element {el.get('id')!r} has no text/math/rich/image")


class LessonScene(Scene):
    """Configured by class attributes set in render_job.py before render()."""

    spec: dict = {}
    durations: dict[str, float] = {}
    scene_index: int = 0

    # ------------------------------------------------------------------ frame
    def setup(self) -> None:
        super().setup()
        self._beats: list[dict] = []
        self._beat_t: dict[str, float] = {}
        if not config.transparent:
            self.camera.background_color = theme.PAPER
        fh, fw = config.frame_height, config.frame_width
        vertical = config.pixel_height > config.pixel_width
        if vertical:
            # TikTok chrome: top bar ~12%, caption/CTA/author stack ~20% at the bottom.
            top, bottom, side, caption = 0.12, 0.20, 0.06, 2.3
        else:
            # 16:9 (app lessons, slide decks): no platform chrome, an even editorial
            # margin, and a shorter caption band because lines are wider.
            top, bottom, side, caption = 0.06, 0.05, 0.06, 1.15
        self.SAFE_TOP = fh / 2 - top * fh
        self.SAFE_BOTTOM = -fh / 2 + bottom * fh
        self.SAFE_LEFT = -fw / 2 + side * fw
        self.SAFE_RIGHT = fw / 2 - side * fw
        self.SAFE_WIDTH = self.SAFE_RIGHT - self.SAFE_LEFT
        # Remotion draws the karaoke caption in this band; scenes never draw into it.
        self.CONTENT_BOTTOM = self.SAFE_BOTTOM + caption
        self.CONTENT_TOP = self.SAFE_TOP

    # ------------------------------------------------------------------ pacing
    def beat(self, name: str) -> None:
        t = float(self.renderer.time)
        self._beats.append({"name": name, "t": round(t, 4)})
        self._beat_t[name] = t

    def hold_for(self, name: str, minimum: float = 0.4) -> None:
        want = self.durations.get(name)
        if want is None:
            self.wait(1.2)  # no voice yet (preview): a readable default
            return
        remaining = want + BREATH - (float(self.renderer.time) - self._beat_t[name])
        self.wait(max(remaining, minimum))

    # ------------------------------------------------------------------ brand
    def brand_in(self, animate: bool = True) -> VGroup:
        y = self.SAFE_TOP
        rule = Line([self.SAFE_LEFT, y, 0], [self.SAFE_RIGHT, y, 0],
                    color=theme.JADE, stroke_width=theme.STROKE)
        bug = Square(side_length=0.22, color=theme.JADE, fill_opacity=1, stroke_width=0)
        bug.move_to([self.SAFE_LEFT, y, 0])
        self.CONTENT_TOP = y - 0.55
        if animate:
            self.play(Create(rule, run_time=0.45), FadeIn(bug, run_time=0.25))
        else:
            self.add(rule, bug)
        return VGroup(rule, bug)

    def heading(self) -> VGroup:
        s = self.spec
        horizontal = config.pixel_width > config.pixel_height
        group = VGroup(Text(s["heading"], font_size=theme.SIZE_TITLE * (0.8 if horizontal else 1.0),
                            color=theme.JADE, weight="BOLD"))
        if s.get("subheading"):
            sub = Text(s["subheading"], font_size=theme.SIZE_SUBTITLE, color=theme.INK_MUTED)
            group.add(sub.next_to(group[0], DOWN, buff=0.22))
        if group.width > self.SAFE_WIDTH:
            group.scale_to_fit_width(self.SAFE_WIDTH)
        group.move_to([0, self.CONTENT_TOP - group.height / 2, 0])
        return group

    # ------------------------------------------------------------------ graph
    def build_graph(self, g: dict):
        x0, x1 = g["x"]
        y0, y1 = g["y"]
        axes = Axes(
            x_range=[x0, x1, 1], y_range=[y0, y1, 1],
            x_length=g.get("width", 6.5), y_length=g.get("height", 3.4), tips=False,
            axis_config={"color": theme.INK_MUTED, "stroke_width": theme.STROKE_HAIRLINE,
                         "include_ticks": False},
        )
        fns = [(p["from"], p["to"], _fn(p["f"])) for p in g["pieces"]]
        pieces = VGroup(*[
            axes.plot(f, x_range=[a, b], color=theme.JADE, stroke_width=theme.STROKE)
            for a, b, f in fns
        ])
        marks = VGroup()
        for m in g.get("marks", []):
            if isinstance(m, dict) and "point" in m:
                # A marked point: dot + dashed guides to both axes + both values labelled.
                px, py = m["point"]
                marks.add(DashedLine(axes.c2p(px, 0), axes.c2p(px, py), color=theme.INK_FAINT,
                                     stroke_width=theme.STROKE_HAIRLINE, dash_length=0.06))
                marks.add(DashedLine(axes.c2p(0, py), axes.c2p(px, py), color=theme.INK_FAINT,
                                     stroke_width=theme.STROKE_HAIRLINE, dash_length=0.06))
                marks.add(Dot(axes.c2p(px, py), radius=0.07, color=theme.JADE))
                marks.add(typeset.math(m.get("xlabel", str(px)), "muted").next_to(axes.c2p(px, 0), DOWN, buff=0.16))
                marks.add(typeset.math(m.get("ylabel", str(py)), "muted").next_to(axes.c2p(0, py), LEFT, buff=0.14))
                continue
            xv = m if isinstance(m, (int, float)) else m["x"]
            label = str(xv) if isinstance(m, (int, float)) else m.get("label", str(xv))
            yv = next((f(xv) for a, b, f in fns if a <= xv <= b), 0.0)
            marks.add(DashedLine(axes.c2p(xv, 0), axes.c2p(xv, yv), color=theme.INK_FAINT,
                                 stroke_width=theme.STROKE_HAIRLINE, dash_length=0.06))
            tick = typeset.math(label, "muted")
            marks.add(tick.next_to(axes.c2p(xv, 0), DOWN, buff=0.16))
        if g.get("origin", True) and x0 <= 0 <= x1 and y0 <= 0 <= y1:
            marks.add(typeset.math("O", "muted").next_to(axes.c2p(0, 0), DOWN + LEFT, buff=0.08))
        labels = g.get("labels", {"x": "x", "y": "y"})
        if labels.get("x"):
            marks.add(typeset.math(labels["x"], "muted").next_to(axes.c2p(x1, 0), [1, 0, 0], buff=0.14))
        if labels.get("y"):
            marks.add(typeset.math(labels["y"], "muted").next_to(axes.c2p(0, y1), UP, buff=0.10))
        return axes, pieces, marks

    def band(self, axes: Axes, x0: float, x1: float) -> Rectangle:
        (y0, y1) = self.spec["graph"]["y"]
        lo, hi = axes.c2p(x0, y0), axes.c2p(x1, y1)
        r = Rectangle(width=hi[0] - lo[0], height=hi[1] - lo[1], stroke_width=0,
                      fill_color=theme.JADE_SOFT, fill_opacity=0.75)
        r.move_to([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0])
        r.set_z_index(-1)  # behind the curve, or the wash dims what it highlights
        return r

    # ------------------------------------------------------------------ layout
    def layout(self, heading: VGroup):
        """Build every element version, size slots, place everything once."""
        steps = self.spec["steps"]
        order: list[str] = []
        versions: dict[str, list[tuple[int, object]]] = {}
        for i, step in enumerate(steps + [{"show": self.spec.get("end", [])}]):
            for el in step.get("show", []):
                if el["id"] not in versions:
                    order.append(el["id"])
                    versions[el["id"]] = []
                versions[el["id"]].append((i, build_element(el, self.spec.get("figures"))))

        graph = None
        slots = []
        if self.spec.get("graph"):
            axes, pieces, marks = self.build_graph(self.spec["graph"])
            graph = VGroup(axes, pieces, marks)
            slots.append(("__graph__", graph.width, graph.height))
        for sid in order:
            mobs = [m for _, m in versions[sid]]
            slots.append((sid, max(m.width for m in mobs), max(m.height for m in mobs)))

        buff = self.spec.get("spacing", 0.7)
        horizontal = config.pixel_width > config.pixel_height
        top = heading.get_bottom()[1] - (0.4 if horizontal else buff)
        bottom = self.CONTENT_BOTTOM
        from .figures import Figure
        fig_ids = {"__graph__"} | {sid for sid in order if isinstance(versions[sid][0][1], Figure)}

        def fit(items, width, height):
            """Figures scale first — grown up to 1.8x into free room, shrunk to 0.55x
            before any text shrinks (small formulas are unreadable on a phone; a
            smaller graph is not). Returns (figure factor, text factor, boxes)."""
            for f in (1.8, 1.6, 1.4, 1.25, 1.1, 1.0, 0.9, 0.8, 0.7, 0.62, 0.55):
                sized = [(sid, w * f, h * f) if sid in fig_ids else (sid, w, h) for sid, w, h in items]
                boxes = VGroup(*[Rectangle(width=w, height=h) for _, w, h in sized]).arrange(DOWN, buff=buff)
                if boxes.width <= width and boxes.height <= height:
                    return f, 1.0, boxes
            t = min(width / boxes.width, height / boxes.height)
            return 0.55 * t, t, boxes.scale(t)

        horizontal = config.pixel_width > config.pixel_height
        figs = [x for x in slots if x[0] in fig_ids]
        texts = [x for x in slots if x[0] not in fig_ids]
        factors, centers = {}, {}
        if horizontal and figs and texts:
            # 16:9 with a figure and text: side by side, figure left, text right —
            # stacking them wastes the width and leaves both small.
            cols = [(figs, self.SAFE_LEFT + 0.29 * self.SAFE_WIDTH, 0.56 * self.SAFE_WIDTH),
                    (texts, self.SAFE_RIGHT - 0.21 * self.SAFE_WIDTH, 0.40 * self.SAFE_WIDTH)]
        else:
            cols = [(slots, 0.0, self.SAFE_WIDTH)]
        for items, cx, width in cols:
            f, t, boxes = fit(items, width, top - bottom)
            boxes.move_to([cx, (top + bottom) / 2, 0])
            for (sid, _, _), box in zip(items, boxes):
                centers[sid] = box.get_center()
                factors[sid] = f if sid in fig_ids else t

        if graph is not None:
            graph.scale(factors["__graph__"]).move_to(centers["__graph__"])
        for sid in order:
            for _, m in versions[sid]:
                m.scale(factors[sid])
                # a Figure is placed by its frame, so every version lands on the same spot
                anchor = m.frame if hasattr(m, "frame") else m
                m.shift(centers[sid] - anchor.get_center())
        return graph, versions

    # ------------------------------------------------------------------ run
    def construct(self):
        # The first scene of a video is the hook: its first frame must already show the
        # heading and the first step's content (context/hooks.md). Later scenes animate in.
        opening = self.scene_index == 0
        marks_brand = self.brand_in(animate=not opening)
        head = self.heading()
        if opening:
            self.add(head)
        else:
            self.play(FadeIn(head, shift=DOWN * 0.2, run_time=0.5))

        graph, versions = self.layout(head)
        on_screen: dict[str, object] = {}
        band = None
        steps = self.spec["steps"]

        for i, step in enumerate(steps):
            name = f"s{self.scene_index}.{i}"
            self.beat(name)

            instant = opening and i == 0
            if step.get("draw_graph") and graph is not None:
                axes, pieces, marks = graph
                if instant:
                    self.add(axes, pieces, marks)
                else:
                    self.play(Create(axes, run_time=0.6), FadeIn(marks, run_time=0.4))
                    self.play(Create(pieces, run_time=1.1))

            # Everything a step changes moves together, starting with the voice.
            # Played one after another they lag the narration by 2 s or more.
            anims = []
            if step.get("band") and graph is not None:
                nb = self.band(graph[0], *step["band"])
                if band is None:
                    band = nb
                    anims.append(FadeIn(band, run_time=0.5))
                else:
                    anims.append(Transform(band, nb, run_time=0.6))
            for h in step.get("hide", []):
                # "p#marks" clears every mark drawn on passage p
                keys = [k for k in on_screen if k.startswith(h[:-6] + "#m")] if h.endswith("#marks") else [h]
                for k in keys:
                    if k in on_screen:
                        anims.append(FadeOut(on_screen.pop(k), run_time=0.4))
            for el in step.get("show", []):
                mob = next(m for k, m in versions[el["id"]] if k == i)
                old = on_screen.get(el["id"])
                if old is not None and hasattr(old, "parts") and hasattr(mob, "parts"):
                    # Same figure, different parts: draw what's new, remove what's gone,
                    # leave the rest exactly where it is.
                    merged = {}
                    for name, part in mob.parts.items():
                        if name in old.parts:
                            merged[name] = old.parts[name]
                        else:
                            anims.append(Create(part, run_time=0.8) if not isinstance(part, VGroup) else FadeIn(part, run_time=0.6))
                            merged[name] = part
                    for name, part in old.parts.items():
                        if name not in mob.parts:
                            anims.append(FadeOut(part, run_time=0.4))
                    wrapper = VGroup(*merged.values())
                    wrapper.parts = merged
                    wrapper.words = getattr(mob, "words", None)
                    on_screen[el["id"]] = wrapper
                elif old is not None:
                    anims.append(Transform(old, mob, run_time=0.7))
                elif hasattr(mob, "parts"):
                    anims.append(AnimationGroup(*[Create(p) if not isinstance(p, VGroup) else FadeIn(p)
                                                  for p in mob.parts.values()], lag_ratio=0.12, run_time=1.4))
                    on_screen[el["id"]] = mob
                else:
                    anims.append(Write(mob, run_time=1.0) if "math" in el
                                 else FadeIn(mob, shift=UP * 0.15, run_time=0.6))
                    on_screen[el["id"]] = mob
            later = []  # emphasis must run after the parts it points at have arrived
            for ref in step.get("emphasize", []):
                fid, _, part = ref.partition(":")
                target = on_screen.get(fid)
                if target is not None and part and hasattr(target, "parts") and part in target.parts:
                    later.append(Indicate(target.parts[part], color=theme.JADE, scale_factor=1.08, run_time=0.9))
                elif target is not None and not part:
                    later.append(Indicate(target, color=theme.JADE, scale_factor=1.04, run_time=0.9))
            from . import figures as F
            for n, m in enumerate(step.get("mark", [])):
                target = on_screen.get(m["id"])
                if target is None or not getattr(target, "words", None):
                    continue
                words = F.find_words(target, m["words"])
                if words:
                    mk = F.mark(words, m.get("style", "highlight"))
                    anims.append(FadeIn(mk, run_time=0.4) if m.get("style", "highlight") == "highlight" else Create(mk, run_time=0.6))
                    on_screen[f"{m['id']}#m{i}.{n}"] = mk
            if instant:
                self.add(*[on_screen[el["id"]] for el in step.get("show", [])])
                if band is not None:
                    self.add(band)
            elif anims:
                self.play(*anims)
            if later:
                self.play(*later)

            self.hold_for(name)

        end = [m for k, m in (v for sid in versions for v in versions[sid]) if k == len(steps)]
        if end:
            self.play(*[FadeIn(m, run_time=0.4) for m in end])
            self.wait(0.5)

        self.beat("outro")  # last fully-built frame; contact sheets sample just before it
        leaving = [m for m in self.mobjects if m is not marks_brand]
        self.play(*[FadeOut(m) for m in leaving], FadeOut(marks_brand), run_time=0.45)
        self.beat("end")

    def tear_down(self) -> None:
        out = getattr(self, "timings_path", None)
        if out:
            Path(out).write_text(json.dumps({
                "scene": self.scene_index,
                "fps": config.frame_rate,
                "duration": round(float(self.renderer.time), 4),
                "beats": self._beats,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        super().tear_down()
