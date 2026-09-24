"""
Deck mode: a PDF of slides becomes scenes whose elements build in on the spoken word.

Two paths, chosen per page automatically:

  VECTOR  (PowerPoint / Canva / Google Slides / Keynote exports — the normal case)
          The page's own objects are read with pdfium. Revealing an element is just
          "render the page without the objects that haven't arrived yet": every frame
          is the author's artwork, exact, with correct overlaps and nothing guessed.
          This is the PDF equivalent of vox-director's .pptx path.

  FLAT    (pages that are one picture — AI-generated or scanned decks)
          Elements are found from the pixels, and vox-director's frozen keying
          (engine/deck/keying.py, tuning in KEYING-TUNING.md) cuts them out and
          rebuilds the empty board.

Outputs live in videos/<id>/deck/:
    deck.pdf                 the source
    deck.json                per page: mode, canvas placement, numbered elements
    pNN.png                  the full page on a 1920x1080 canvas
    pNN.marks.png            the same with numbered element boxes (for the agent)
"""

from __future__ import annotations

import ctypes
import json
import shutil
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as raw
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CANVAS = (1920, 1080)
FONT = ROOT / "assets" / "fonts" / "BeVietnamPro-SemiBold.ttf"

BACKGROUND_SHARE = 0.55   # an object covering more of the page than this is background
GAP_X, GAP_Y = 0.010, 0.013  # objects closer than this (fraction of canvas) are one element
KINDS = {raw.FPDF_PAGEOBJ_TEXT: "text", raw.FPDF_PAGEOBJ_PATH: "shape",
         raw.FPDF_PAGEOBJ_IMAGE: "image", raw.FPDF_PAGEOBJ_SHADING: "shading",
         raw.FPDF_PAGEOBJ_FORM: "group"}


# ------------------------------------------------------------------ pdfium helpers
def _bounds(handle) -> tuple[float, float, float, float]:
    l, b, r, t = (ctypes.c_float() for _ in range(4))
    raw.FPDFPageObj_GetBounds(handle, ctypes.byref(l), ctypes.byref(b), ctypes.byref(r), ctypes.byref(t))
    return l.value, b.value, r.value, t.value


def _matrix(handle):
    m = raw.FS_MATRIX()
    raw.FPDFPageObj_GetMatrix(handle, ctypes.byref(m))
    return m.a, m.b, m.c, m.d, m.e, m.f


def _apply(m, box):
    a, b, c, d, e, f = m
    xs, ys = [], []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
        xs.append(a * x + c * y + e)
        ys.append(b * x + d * y + f)
    return min(xs), min(ys), max(xs), max(ys)


def _area(box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _leaves(page) -> tuple[list[dict], list[dict]]:
    """Every drawable object as a leaf with a path we can find again in a fresh copy.

    Many exporters wrap a whole slide (or big parts of it) in a form XObject. A form
    that covers most of the page is opened up so its children become elements; small
    forms (a logo, an icon made of 40 paths) stay whole, which is what a viewer
    thinks of as one thing anyway.
    """
    W, H = page.get_size()
    A = W * H
    leaves, background = [], []

    def visit(handle, path, box, depth):
        kind = raw.FPDFPageObj_GetType(handle)
        if kind == raw.FPDF_PAGEOBJ_FORM and _area(box) > BACKGROUND_SHARE * A and depth < 3:
            n = raw.FPDFFormObj_CountObjects(handle)
            m = _matrix(handle)
            for j in range(n):
                ch = raw.FPDFFormObj_GetObject(handle, j)
                visit(ch, path + (j,), _apply(m, _bounds(ch)), depth + 1)
            return
        leaf = {"path": list(path), "box": box, "kind": KINDS.get(kind, "other")}
        (background if _area(box) > BACKGROUND_SHARE * A else leaves).append(leaf)

    for i in range(raw.FPDFPage_CountObjects(page.raw)):
        h = raw.FPDFPage_GetObject(page.raw, i)
        visit(h, (i,), _bounds(h), 0)
    return [l for l in leaves if _area(l["box"]) > 0], background


def _placement(W: float, H: float) -> tuple[float, int, int]:
    """Scale and offset that fit a W x H (pt) page into the 1920x1080 canvas."""
    s = min(CANVAS[0] / W, CANVAS[1] / H)
    return s, round((CANVAS[0] - W * s) / 2), round((CANVAS[1] - H * s) / 2)


def _to_px(box, H, s, ox, oy) -> list[int]:
    l, b, r, t = box
    return [round(l * s + ox), round((H - t) * s + oy), round(r * s + ox), round((H - b) * s + oy)]


def _cluster(boxes: np.ndarray, gap: bool = True) -> list[list[int]]:
    """Union boxes that overlap (or, with gap=True, nearly touch). Groups of indices."""
    n = len(boxes)
    if n == 0:
        return []
    gx, gy = (GAP_X * CANVAS[0], GAP_Y * CANVAS[1]) if gap else (0.0, 0.0)
    e = boxes + np.array([-gx, -gy, gx, gy])
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    hit = ((e[:, None, 0] <= e[None, :, 2]) & (e[None, :, 0] <= e[:, None, 2]) &
           (e[:, None, 1] <= e[None, :, 3]) & (e[None, :, 1] <= e[:, None, 3]))
    for i, j in zip(*np.nonzero(np.triu(hit, 1))):
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pj] = pi
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _canvas(page_img: Image.Image, s, ox, oy) -> Image.Image:
    """Letterbox a rendered page onto the 1920x1080 canvas in the page's own edge colour."""
    edge = np.concatenate([np.asarray(page_img)[0], np.asarray(page_img)[-1]])
    colour = tuple(int(v) for v in np.median(edge.reshape(-1, 3), axis=0))
    canvas = Image.new("RGB", CANVAS, colour)
    canvas.paste(page_img, (ox, oy))
    return canvas


def _render(pdf_path: Path, index: int, remove: list[list[int]] | None = None) -> Image.Image:
    """Render one page onto the canvas, optionally without some objects (by path)."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[index]
    W, H = page.get_size()
    s, ox, oy = _placement(W, H)
    if remove:
        # resolve every handle first, then remove deepest-first so indices stay valid
        targets = []
        for path in remove:
            container, handle = None, raw.FPDFPage_GetObject(page.raw, path[0])
            for j in path[1:]:
                container, handle = handle, raw.FPDFFormObj_GetObject(handle, j)
            targets.append((len(path), container, handle))
        for _, container, handle in sorted(targets, key=lambda t: -t[0]):
            if container is None:
                raw.FPDFPage_RemoveObject(page.raw, handle)
            else:
                raw.FPDFFormObj_RemoveObject(container, handle)
        page.gen_content()
    img = page.render(scale=s).to_pil().convert("RGB")
    out = _canvas(img, s, ox, oy)
    pdf.close()
    return out


# ------------------------------------------------------------------ flat pages
def _flat_elements(img: Image.Image) -> list[list[int]]:
    """Propose element boxes on a picture-only page: ink that differs from the paper."""
    from scipy import ndimage

    from engine.deck import keying
    small = img.resize((CANVAS[0] // 4, CANVAS[1] // 4))
    a = np.asarray(small, dtype=np.float32)
    paper = np.array(keying.paper_colour(img), dtype=np.float32)
    ink = np.abs(a - paper).max(2) > 38
    ink = ndimage.binary_dilation(ink, iterations=3)
    labels, _ = ndimage.label(ink)
    boxes = []
    h, w = ink.shape
    for sl in ndimage.find_objects(labels):
        # Ink touching the page edge is a frame or border doodle, not content: it
        # would otherwise chain every element on the slide into one box.
        if sl[0].start <= 1 or sl[1].start <= 1 or sl[0].stop >= h - 1 or sl[1].stop >= w - 1:
            continue
        y0, y1, x0, x1 = sl[0].start * 4, sl[0].stop * 4, sl[1].start * 4, sl[1].stop * 4
        if (x1 - x0) * (y1 - y0) > 0.002 * CANVAS[0] * CANVAS[1]:
            boxes.append([x0, y0, x1, y1])
    if not boxes:
        return []
    # The dilation above already joined nearby ink; merging by proximity again would
    # chain a whole hand-drawn slide into one box. Only overlapping boxes merge here.
    groups = _cluster(np.array(boxes, dtype=float), gap=False)
    merged = []
    for g in groups:
        b = np.array([boxes[i] for i in g])
        merged.append([int(b[:, 0].min()), int(b[:, 1].min()), int(b[:, 2].max()), int(b[:, 3].max())])
    return [m for m in merged if (m[2] - m[0]) * (m[3] - m[1]) < 0.8 * CANVAS[0] * CANVAS[1]]


# ------------------------------------------------------------------ analyse / import
def analyse(pdf_path: Path, out_dir: Path) -> dict:
    """deck.json + pNN.png + pNN.marks.png for every page."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    pages = []
    for i in range(len(pdf)):
        page = pdf[i]
        W, H = page.get_size()
        s, ox, oy = _placement(W, H)
        leaves, background = _leaves(page)
        full = _render(pdf_path, i)
        full.save(out_dir / f"p{i + 1:02d}.png")

        elements = []
        if leaves:
            mode = "vector"
            px = np.array([_to_px(l["box"], H, s, ox, oy) for l in leaves], dtype=float)
            textpage = page.get_textpage()
            leaf_rows = [{"path": l["path"], "box": [int(v) for v in px[k]]} for k, l in enumerate(leaves)]
            for g in _cluster(px):
                b = px[g]
                box = [int(b[:, 0].min()), int(b[:, 1].min()), int(b[:, 2].max()), int(b[:, 3].max())]
                pdfbox = [min(leaves[k]["box"][0] for k in g), min(leaves[k]["box"][1] for k in g),
                          max(leaves[k]["box"][2] for k in g), max(leaves[k]["box"][3] for k in g)]
                text = textpage.get_text_bounded(*pdfbox).replace("\r", " ").replace("\n", " ").strip()
                kinds = sorted({leaves[k]["kind"] for k in g})
                elements.append({"box": box, "paths": [leaves[k]["path"] for k in g],
                                 "kinds": kinds, "text": " ".join(text.split())[:160]})
        else:
            mode = "flat"
            leaf_rows = []
            elements = [{"box": b, "paths": [], "kinds": ["picture"], "text": ""} for b in _flat_elements(full)]

        # reading order: top-to-bottom in bands, then left-to-right
        elements.sort(key=lambda e: (round(e["box"][1] / 60), e["box"][0]))
        for n, e in enumerate(elements, 1):
            e["id"] = n
        _marks(full, elements, grid=(mode == "flat")).save(out_dir / f"p{i + 1:02d}.marks.png")
        pages.append({"page": i + 1, "mode": mode, "size_pt": [W, H], "scale": s, "offset": [ox, oy],
                      "background_objects": len(background), "elements": elements, "leaves": leaf_rows})
    pdf.close()
    deck = {"source": pdf_path.name, "canvas": list(CANVAS), "pages": pages}
    (out_dir / "deck.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
    return deck


def _marks(img: Image.Image, elements: list[dict], grid: bool = False) -> Image.Image:
    """Numbered boxes (set-of-marks) so the agent can say 'reveal 3 and 4' precisely.

    Picture-only pages also get a coordinate grid: their proposals are guesses, and
    the agent may need to write its own {"box": [x0, y0, x1, y1]} instead.
    """
    out = img.copy()
    d = ImageDraw.Draw(out, "RGBA")
    font = ImageFont.truetype(str(FONT), 26)
    if grid:
        small = ImageFont.truetype(str(FONT), 16)
        for x in range(0, CANVAS[0], 120):
            d.line([x, 0, x, CANVAS[1]], fill=(180, 85, 58, 70), width=1)
            d.text((x + 3, 3), str(x), font=small, fill=(180, 85, 58, 220))
        for y in range(0, CANVAS[1], 120):
            d.line([0, y, CANVAS[0], y], fill=(180, 85, 58, 70), width=1)
            d.text((3, y + 3), str(y), font=small, fill=(180, 85, 58, 220))
    for e in elements:
        x0, y0, x1, y1 = e["box"]
        d.rectangle([x0, y0, x1, y1], outline=(31, 111, 92, 255), width=3)
        label = str(e["id"])
        tw = d.textlength(label, font=font)
        d.rounded_rectangle([x0, y0 - 2, x0 + tw + 16, y0 + 32], radius=6, fill=(31, 111, 92, 235))
        d.text((x0 + 8, y0 + 1), label, font=font, fill=(245, 239, 226, 255))
    return out


def import_pdf(pdf: Path, vdir: Path) -> dict:
    ddir = vdir / "deck"
    ddir.mkdir(parents=True, exist_ok=True)
    shutil.copy(pdf, ddir / "deck.pdf")
    return analyse(ddir / "deck.pdf", ddir)


# ------------------------------------------------------------------ build a slide scene
def build_slide(vdir: Path, page: int, reveals: list[dict], out_dir: Path, key: str) -> dict:
    """States and fly-in sprites for one slide.

    `reveals` is the ordered list of {"el": id | [ids], "anim": ...} in the order they
    land. Returns {"states": [png...], "sprites": [{png, box}...]} where states[0] has
    every revealed element absent and states[k] has the first k present.
    """
    ddir = vdir / "deck"
    deck = json.loads((ddir / "deck.json").read_text(encoding="utf-8"))
    info = deck["pages"][page - 1]
    by_id = {e["id"]: dict(e) for e in info["elements"]}
    groups = []
    for n, r in enumerate(reveals):
        if "box" in r:
            # A custom box: on vector pages it claims every object whose centre lies
            # inside it (this is how an element grouped too coarsely gets split); on
            # picture pages it is keyed as drawn.
            x0, y0, x1, y1 = r["box"]
            inside = [l["path"] for l in info.get("leaves", [])
                      if x0 <= (l["box"][0] + l["box"][2]) / 2 <= x1 and y0 <= (l["box"][1] + l["box"][3]) / 2 <= y1]
            by_id[f"box{n}"] = {"box": [int(v) for v in r["box"]], "paths": inside}
            groups.append([f"box{n}"])
        else:
            groups.append([r["el"]] if isinstance(r["el"], int) else list(r["el"]))
    out_dir.mkdir(parents=True, exist_ok=True)

    if info["mode"] == "vector":
        states = []
        for k in range(len(groups) + 1):
            hidden = [p for g in groups[k:] for eid in g for p in by_id[eid]["paths"]]
            img = _render(ddir / "deck.pdf", page - 1, hidden)
            name = f"{key}.state{k}.png"
            img.save(out_dir / name)
            states.append(name)
        sprites = []
        for k, g in enumerate(groups):
            before = np.asarray(Image.open(out_dir / states[k]), dtype=np.int16)
            after_img = Image.open(out_dir / states[k + 1]).convert("RGB")
            after = np.asarray(after_img, dtype=np.int16)
            box = _union([by_id[e]["box"] for e in g], pad=6)
            diff = np.abs(after - before).max(2).astype(np.float32)
            alpha = np.clip((diff - 4) / 18, 0, 1)
            a = Image.fromarray((alpha * 255).astype("uint8")).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
            sprite = after_img.convert("RGBA")
            sprite.putalpha(a)
            name = f"{key}.sprite{k}.png"
            sprite.crop(box).save(out_dir / name)
            sprites.append({"src": name, "box": box})
        return {"states": states, "sprites": sprites}

    # flat page: vox keying on the chosen boxes
    return _build_flat(ddir, page, info, groups, by_id, out_dir, key)


def _union(boxes, pad=0):
    x0 = max(0, min(b[0] for b in boxes) - pad)
    y0 = max(0, min(b[1] for b in boxes) - pad)
    x1 = min(CANVAS[0], max(b[2] for b in boxes) + pad)
    y1 = min(CANVAS[1], max(b[3] for b in boxes) + pad)
    return [int(x0), int(y0), int(x1), int(y1)]


def _build_flat(ddir, page, info, groups, by_id, out_dir, key):
    import tempfile

    from engine.deck import keying
    img = Image.open(ddir / f"p{page:02d}.png").convert("RGB")
    tmp = Path(tempfile.mkdtemp(prefix="key-"))
    img.save(tmp / "slide.png")
    elements = [{"name": f"g{k}", "bbox": _union([by_id[e]["box"] for e in g])} for k, g in enumerate(groups)]
    (tmp / "slides.json").write_text(json.dumps({"key_mode": "colour", "slides": [
        {"id": 1, "image": "slide.png", "elements": elements}]}), encoding="utf-8")
    keying.run(str(tmp))
    spec = json.loads((tmp / "slides.json").read_text(encoding="utf-8"))["slides"][0]["elements"]

    # the empty board: every revealed element's erased patch pasted, largest first
    patches = []
    for k, el in enumerate(spec):
        kb = el["key_box"]
        patches.append((k, kb, Image.open(tmp / el["key_bg"]).convert("RGB"),
                        Image.open(tmp / el["key"]).convert("RGBA")))
    states = []
    for k in range(len(groups) + 1):
        st = img.copy()
        for j, kb, bg, _ in sorted(patches, key=lambda p: -(p[1][2] - p[1][0]) * (p[1][3] - p[1][1])):
            if j >= k:
                st.paste(bg, (kb[0], kb[1]))
        for j, kb, _, cut in patches:
            if j < k:
                st.paste(cut, (kb[0], kb[1]), cut)
        name = f"{key}.state{k}.png"
        st.save(out_dir / name)
        states.append(name)
    sprites = []
    for k, kb, _, cut in patches:
        name = f"{key}.sprite{k}.png"
        cut.save(out_dir / name)
        sprites.append({"src": name, "box": list(kb)})
    shutil.rmtree(tmp, ignore_errors=True)
    return {"states": states, "sprites": sprites}
