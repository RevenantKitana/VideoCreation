# Vendored verbatim from vox-director-fal/scripts/slides_key.py (MIT; fork of
# github.com/Alisa0808/vox-director). Tuning is frozen: read the header of
# engine/deck/KEYING-TUNING.md (copied from vox-director-fal) before changing any constant.
# Used by engine/deck/pdf.py only for FLATTENED (image-only) PDF pages.
#!/usr/bin/env python3
"""
Slide-deck mode, stage 1.5: cut every element out of its slide, and rebuild the
background behind it.

WHY NOT A BACKGROUND-REMOVAL MODEL. `fal-ai/imageutils/rembg` was tried first and
is the wrong tool for slides (measured on this deck): it kept only the red proton
and deleted an entire atom's orbit, ghosted a sticky note to nothing, chewed the
corner off a folder, and dropped a diamond's sparkles. It is a *salient object*
segmenter trained on photographs; on flat line art there is no salient object to
find. Colour keying against the deck's own background is deterministic, free, and
kept all four of those cases intact.

WHAT THIS PRODUCES, per element:
  keys/<id>_<name>.png    RGBA cutout — the element with a real alpha shape
  keys/<id>_<name>_bg.png the same rectangle with the element ERASED and the
                          background reconstructed behind it

Together those two reconstruct the original slide exactly, which is what lets the
renderer show a genuinely empty slot before the reveal and a real object shape
during the flight — instead of two offset rectangles, which is what it did before.

Keying is skipped automatically on decks whose background is not flat (a nebula, a
photo); there, a rectangle is honest and a key would shred the art. Override with
`key_mode: "colour" | "none"` in slides.json.

Usage:
  python3 slides_key.py <project_dir> [--only 3,5] [--check]

  --check   also write preview/keycheck.jpg — every cutout on a checkerboard with
            its metrics, so all of them can be eyeballed in one pass
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ===================== VALIDATED TUNING — read before changing ================
# Every number here was set by a measured failure, not by taste. The rationale and
# the evidence for each one is in references/slides-tuning.md. Changing any of them
# re-opens a specific artefact that is currently fixed, so change one at a time and
# re-run `slides_key.py <project> --check`.

PAD = 28              # context ring used to reconstruct the background
MARGIN = 16           # bbox grown before keying, to catch strokes drawn just outside
SOLID = 0.35          # alpha above this counts as "element" for hole-filling
FLAT_STD = 26.0       # background std above this = textured deck, don't key

# The CUT mask is precise: it decides the shape that flies. The ERASE mask is
# deliberately far more generous, because a stroke's anti-aliased halo scores below
# the cut threshold and, left behind, traces a legible ghost of the whole element.
CUT = dict(t0=8.0, t1=26.0, dilate=1, blur=1.1)
ERASE = dict(t0=3.0, t1=13.0, dilate=5, blur=2.2)
ERASE_GAIN = 1.7      # pushes the erase mask's soft edges to solid

MERGE_DIST = 26.0     # ring colours closer than this are one colour, not two
RING_FLAT_SHARE = 0.65   # ring this uniform -> fill flat, no diffusion needed
RING_FLAT_SPREAD = 30.0
COV_SPLIT = 0.35      # above this an erase hole is "large", below it "thin strokes"
COARSE_LEVELS, FINE_LEVELS = (16, 8, 4), (4,)
# ==============================================================================

T0, T1 = CUT["t0"], CUT["t1"]        # back-compat default for matte()


# ---------------------------------------------------------------- deck probes

def paper_colour(img):
    small = img.resize((64, 36)).convert("RGB")
    return max(small.getcolors(64 * 36), key=lambda c: c[0])[1]


def background_flatness(img, paper):
    """Std of the pixels that are close to the paper colour. A flat paper deck
    scores low; a nebula/photo background scores high."""
    a = np.asarray(img.resize((240, 135)).convert("RGB"), dtype=np.float32)
    dist = np.sqrt(((a - np.array(paper, dtype=np.float32)) ** 2).sum(axis=2))
    near = a[dist < 60]
    return float(near.std()) if near.size else 999.0


# ---------------------------------------------------------------- matte

def _fill_holes(alpha):
    """Anything transparent but NOT connected to the border is an interior hole —
    the inside of an outlined shape — so make it solid. Without this a hand-drawn
    circle flies as a thin ring and its fill stays behind."""
    solid = (alpha > SOLID).astype(np.uint8) * 255
    h, w = solid.shape
    padded = Image.new("L", (w + 2, h + 2), 0)
    padded.paste(Image.fromarray(solid, "L"), (1, 1))
    ImageDraw.floodfill(padded, (0, 0), 128)          # mark border-connected bg
    flooded = np.asarray(padded)[1:h + 1, 1:w + 1]
    holes = (flooded == 0)                            # bg, but unreachable
    out = alpha.copy()
    out[holes] = 1.0
    return out


def ring_palette(padded, inner, pad=PAD, max_colours=3, min_share=0.12):
    """The colours actually BEHIND this element, sampled from the ring of context
    around its box — not the page's paper colour.

    This matters: a summary row sitting on a mint clipboard has a mint background,
    and keying it against the page's cream keeps 100% of the box (measured). A ring
    can also be legitimately bimodal — a sticky note straddling a board edge — so
    up to `max_colours` are kept and a pixel is background if it matches ANY of them.
    """
    a = np.asarray(padded.convert("RGB"))
    h, w = a.shape[:2]
    ix0, iy0, ix1, iy1 = inner
    mask = np.ones((h, w), dtype=bool)
    mask[max(0, iy0):iy1, max(0, ix0):ix1] = False        # exclude the element box
    ring = a[mask]
    if ring.size == 0:
        return [tuple(int(v) for v in a.reshape(-1, 3).mean(axis=0))], 1.0, 0.0
    quant = (ring // 12 * 12).astype(np.uint8)             # tolerate print noise
    cols, counts = np.unique(quant.reshape(-1, 3), axis=0, return_counts=True)
    order = np.argsort(-counts)
    total = counts.sum()
    # Merge buckets that are really the same colour. Quantizing to a 12-step grid
    # splits one flat cream across two neighbouring bins, which halves its apparent
    # share and makes a perfectly uniform ring look mixed (measured: a plain-paper
    # surround scoring 0.52 instead of ~1.0).
    merged = []            # [colour, weight]
    for i in order:
        c = ring[(quant == cols[i]).all(axis=1)].mean(axis=0).astype(np.float32)
        wgt = float(counts[i])
        for m in merged:
            if np.sqrt(((m[0] - c) ** 2).sum()) < MERGE_DIST:
                m[0] = (m[0] * m[1] + c * wgt) / (m[1] + wgt)
                m[1] += wgt
                break
        else:
            merged.append([c, wgt])
        if len(merged) > max_colours * 3:
            break
    merged.sort(key=lambda m: -m[1])
    out = [tuple(float(v) for v in m[0]) for m in merged[:max_colours]
           if m[1] / total >= min_share or m is merged[0]]

    # how uniform is the ring? a plain-paper surround can be filled with one flat
    # colour exactly, which beats any diffusion and leaves no grey patch behind
    top = float(merged[0][1] / total)
    spread = float(np.abs(ring.astype(np.float32) - np.array(out[0])).mean())
    return out, top, spread


def matte(crop, palette, t0=T0, t1=T1, dilate=0, blur=1.1, holes=True):
    """Alpha = distance to the NEAREST background colour in the palette."""
    a = np.asarray(crop.convert("RGB"), dtype=np.float32)
    dist = None
    for c in palette:
        d = np.sqrt(((a - np.array(c, dtype=np.float32)) ** 2).sum(axis=2))
        dist = d if dist is None else np.minimum(dist, d)
    alpha = np.clip((dist - t0) / (t1 - t0), 0.0, 1.0)
    if holes:
        alpha = _fill_holes(alpha)
    m = Image.fromarray((alpha * 255).astype("uint8"), "L")
    if dilate:
        m = m.filter(ImageFilter.MaxFilter(2 * int(dilate) + 1))
    return m.filter(ImageFilter.GaussianBlur(blur))


def erase_matte(crop, palette):
    """A deliberately GENEROUS mask, used only for erasing — never for the cutout.

    Every hand-drawn stroke carries an anti-aliased halo whose colour distance sits
    just under the cutout threshold. At `T0` those halo pixels score alpha 0, so
    they are never erased, and what is left behind is a faint but perfectly legible
    outline of the whole element — the "silhouette" of an item that has not flown
    in yet. Erasing with a lower threshold plus a few pixels of dilation removes
    the halo as well; on a flat background over-erasing costs nothing, because the
    fill is the same colour as what it replaces.
    """
    m = matte(crop, palette, **ERASE)
    a = np.clip(np.asarray(m, dtype=np.float32) * ERASE_GAIN, 0, 255)
    return Image.fromarray(a.astype("uint8"), "L")


# ---------------------------------------------------------------- erase

def _diffuse(rgb, known, iters):
    """Push known pixels into the unknown region by repeated blur + re-stamp."""
    work = Image.fromarray(rgb.astype("uint8"), "RGB")
    keep = rgb.copy()
    for _ in range(iters):
        work = work.filter(ImageFilter.GaussianBlur(2.0))
        a = np.asarray(work.convert("RGB"), dtype=np.float32)
        a[known] = keep[known]
        work = Image.fromarray(a.astype("uint8"), "RGB")
    return np.asarray(work.convert("RGB"), dtype=np.float32)


def inpaint(crop, alpha_mask, levels=None, iters=26, flat_fill=None):
    """See below. `flat_fill` short-circuits the whole thing when the surrounding
    background is a single flat colour, and `levels` adapts to the hole size."""
    if flat_fill is not None:
        out = np.asarray(crop.convert("RGB"), dtype=np.float32)
        soft = (np.asarray(alpha_mask, dtype=np.float32) / 255.0)[..., None]
        fill = np.array(flat_fill, dtype=np.float32)[None, None, :]
        return Image.fromarray((out * (1 - soft) + fill * soft).astype("uint8"), "RGB")
    if levels is None:
        cov = float((np.asarray(alpha_mask, dtype=np.float32) / 255.0).mean())
        # Thin strokes (low coverage) must NOT be solved at a coarse level: at 1/16
        # scale a line of text is sub-pixel, so the coarse pass averages the ink
        # into the fill and leaves a grey haze exactly where the text was.
        levels = COARSE_LEVELS if cov > COV_SPLIT else FINE_LEVELS
    return _inpaint_pyramid(crop, alpha_mask, levels, iters)


def _inpaint_pyramid(crop, alpha_mask, levels=(16, 8, 4), iters=26):
    """Reconstruct what is behind an element by diffusing the surrounding
    background inward, COARSE TO FINE.

    A single-scale diffusion cannot carry colour across a large hole: the middle
    of the gap never hears from the boundary and settles on the global mean, which
    showed up as a washed-out patch where a sticky note covered a dark board. Each
    level here solves a hole that is small *relative to its own resolution*, then
    seeds the next — so the board's colour actually reaches the centre.
    """
    known_full = np.asarray(alpha_mask) < 40                   # background pixels
    if not known_full.any():
        return crop.copy()
    w, h = crop.size
    kimg = Image.fromarray((known_full * 255).astype("uint8"), "L")

    seed = None
    for div in levels:
        sw, sh = max(2, w // div), max(2, h // div)
        kn = np.asarray(kimg.resize((sw, sh))) > 128
        if not kn.any():
            continue
        arr = np.asarray(crop.resize((sw, sh)).convert("RGB"), dtype=np.float32)
        if seed is None:
            arr[~kn] = arr[kn].mean(axis=0)
        else:
            up = np.asarray(Image.fromarray(seed.astype("uint8"), "RGB")
                            .resize((sw, sh), Image.BILINEAR), dtype=np.float32)
            arr[~kn] = up[~kn]
        seed = _diffuse(arr, kn, iters)
    if seed is None:
        return crop.copy()

    filled = np.asarray(Image.fromarray(seed.astype("uint8"), "RGB")
                        .resize((w, h), Image.BILINEAR), dtype=np.float32)
    out = np.asarray(crop.convert("RGB"), dtype=np.float32).copy()
    soft = (np.asarray(alpha_mask, dtype=np.float32) / 255.0)[..., None]
    out = out * (1 - soft) + filled * soft
    return Image.fromarray(out.astype("uint8"), "RGB")


# ---------------------------------------------------------------- qa

def metrics(alpha_mask):
    a = np.asarray(alpha_mask, dtype=np.float32) / 255.0
    cov = float(a.mean())
    border = np.concatenate([a[0, :], a[-1, :], a[:, 0], a[:, -1]])
    return cov, float((border > 0.5).mean())


def warn_for(cov, edge):
    w = []
    if cov > 0.95:
        w.append("nothing keyed: bbox is all foreground")
    elif cov < 0.02:
        w.append("almost nothing kept: key too aggressive")
    if edge > 0.35:
        w.append(f"clipped by bbox ({edge:.0%} of the border is element)")
    return w


def checkerboard(size, sq=16):
    im = Image.new("RGB", size, (238, 238, 238))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], sq):
        for x in range(0, size[0], sq):
            if (x // sq + y // sq) % 2:
                d.rectangle([x, y, x + sq, y + sq], fill=(203, 203, 203))
    return im


def build_check_sheet(entries, dest, cols=4, tw=430, th=270):
    rows = (len(entries) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, (th + 34) * rows), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, e in enumerate(entries):
        cut = Image.open(e["key"]).convert("RGBA")
        bg = checkerboard(cut.size)
        bg.paste(cut, (0, 0), cut)
        bg.thumbnail((tw - 12, th - 12))
        x, y = (i % cols) * tw, (i // cols) * (th + 34)
        sheet.paste(bg, (x + (tw - bg.width) // 2, y + 30 + (th - 12 - bg.height) // 2))
        head = f"{e['slide']}/{e['name']}  cov={e['coverage']:.0%} edge={e['edge']:.0%}"
        d.text((x + 8, y + 6), head, fill=(0, 0, 0))
        if e["warnings"]:
            d.rectangle([x + 2, y + 2, x + tw - 4, y + th + 30], outline=(220, 30, 60), width=3)
            d.text((x + 8, y + 18), e["warnings"][0][:58], fill=(190, 20, 50))
    sheet.save(dest, quality=88)


# ---------------------------------------------------------------- main

def run(project_dir, only=None, check=False):
    spath = os.path.join(project_dir, "slides.json")
    spec = json.load(open(spath))
    kdir = os.path.join(project_dir, "keys")
    os.makedirs(kdir, exist_ok=True)
    mode = spec.get("key_mode", "auto")

    entries, flagged = [], 0
    for s in spec["slides"]:
        sid = str(s["id"])
        if only and sid not in only:
            continue
        img = Image.open(os.path.join(project_dir, s["image"])).convert("RGB")
        W, H = img.size
        paper = paper_colour(img)
        flat = background_flatness(img, paper)
        use = mode if mode != "auto" else ("colour" if flat < FLAT_STD else "none")
        if use != "colour":
            print(f"[{sid}] background not flat (std {flat:.1f}) — keeping rectangles")
            for el in s["elements"]:
                el.pop("key", None)
                el.pop("key_bg", None)
            continue

        # --- pass 1: matte every element -------------------------------------
        built = []
        for el in s["elements"]:
            # Grow the box a little before keying. A hand-drawn box outline or a
            # folder corner routinely sits a few pixels outside the bbox that was
            # eyeballed for it, and whatever falls outside is never erased — it
            # stays as a clean rectangle outline of the missing element. Growing
            # costs nothing, because only actual element pixels get erased.
            x0, y0, x1, y1 = el["bbox"]
            x0, y0 = max(0, x0 - MARGIN), max(0, y0 - MARGIN)
            x1, y1 = min(W, x1 + MARGIN), min(H, y1 + MARGIN)
            el["key_box"] = [x0, y0, x1, y1]
            # the reconstruction ring has to scale with the hole: a fixed 28px of
            # context around a 415x365 element leaves the middle of the gap with
            # nothing to hear from, and it settles on a washed-out mean.
            pad = max(PAD, int(0.35 * min(x1 - x0, y1 - y0)))
            px0, py0 = max(0, x0 - pad), max(0, y0 - pad)
            px1, py1 = min(W, x1 + pad), min(H, y1 + pad)
            padded = img.crop((px0, py0, px1, py1))
            ix0, iy0 = x0 - px0, y0 - py0
            ix1, iy1 = ix0 + (x1 - x0), iy0 + (y1 - y0)
            palette, top_share, spread = ring_palette(padded, (ix0, iy0, ix1, iy1))
            pmask = matte(padded, palette, **CUT)
            emask = erase_matte(padded, palette)
            flat = palette[0] if (top_share > RING_FLAT_SHARE
                                  and spread < RING_FLAT_SPREAD) else None
            built.append({"el": el, "pad": (px0, py0, px1, py1),
                          "inner": (ix0, iy0, ix1, iy1), "img": padded,
                          "alpha": np.asarray(pmask, dtype=np.float32).copy(),
                          "erase": np.asarray(emask, dtype=np.float32).copy(),
                          "flat": flat, "area": (x1 - x0) * (y1 - y0)})

        # --- pass 2: resolve overlapping artwork ------------------------------
        # A stamp lies across two folders; a sticky note sits on a board. A
        # rectangle crop therefore drags a piece of its neighbour, and that piece
        # flies in with it — visible as a torn fragment mid-flight. Give contested
        # pixels to the SMALLER element (on a slide, the small thing is the one on
        # top) and subtract them from the larger, which reveals without them.
        for a in built:
            ax0, ay0, ax1, ay1 = a["pad"]
            for b in built:
                if b is a or b["area"] >= a["area"]:
                    continue
                # b may only claim pixels inside its OWN bbox, never its padding
                # ring — b's matte out there has already picked up a's artwork, and
                # subtracting it bites chunks out of a (observed: a folder losing
                # its label to a neighbouring stamp's padding).
                bpx0, bpy0 = b["pad"][0], b["pad"][1]
                bx0, by0, bx1, by1 = b["el"]["bbox"]
                ox0, oy0 = max(ax0, bx0), max(ay0, by0)
                ox1, oy1 = min(ax1, bx1), min(ay1, by1)
                if ox1 <= ox0 or oy1 <= oy0:
                    continue
                a_sub = a["alpha"][oy0 - ay0:oy1 - ay0, ox0 - ax0:ox1 - ax0]
                b_sub = b["alpha"][oy0 - bpy0:oy1 - bpy0, ox0 - bpx0:ox1 - bpx0]
                # only confident b pixels take ownership
                a_sub[:] = np.where(b_sub > 128, np.clip(a_sub - b_sub, 0, 255), a_sub)

        # --- pass 3: write cutouts + erased backgrounds -----------------------
        for item in built:
            el = item["el"]
            ix0, iy0, ix1, iy1 = item["inner"]
            padded = item["img"]
            pmask = Image.fromarray(item["alpha"].astype("uint8"), "L")
            emask = Image.fromarray(item["erase"].astype("uint8"), "L")
            crop = padded.crop((ix0, iy0, ix1, iy1))
            amask = pmask.crop((ix0, iy0, ix1, iy1))

            cut = crop.convert("RGBA")
            cut.putalpha(amask)
            # erase with the GENEROUS mask, not the cutout's: the cutout threshold
            # leaves every stroke's anti-aliased halo behind, and those halos add up
            # to a fully legible ghost of an element that hasn't arrived yet
            erased_pad = inpaint(padded, emask, flat_fill=item["flat"])
            erased = erased_pad.crop((ix0, iy0, ix1, iy1))

            kp = os.path.join(kdir, f"{sid}_{el['name']}.png")
            bp = os.path.join(kdir, f"{sid}_{el['name']}_bg.png")
            cut.save(kp)
            erased.save(bp)

            cov, edge = metrics(amask)
            warns = warn_for(cov, edge)
            el["key"] = os.path.relpath(kp, project_dir)
            el["key_bg"] = os.path.relpath(bp, project_dir)
            el["key_coverage"] = round(cov, 3)
            el["key_edge"] = round(edge, 3)
            el["key_warnings"] = warns
            flagged += bool(warns)
            entries.append({"slide": sid, "name": el["name"], "key": kp,
                            "coverage": cov, "edge": edge, "warnings": warns})
            mark = "  <-- " + warns[0] if warns else ""
            print(f"[{sid}/{el['name']}] cov={cov:.0%} edge={edge:.0%}{mark}")

    with open(spath, "w") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    if check and entries:
        pdir = os.path.join(project_dir, "preview")
        os.makedirs(pdir, exist_ok=True)
        dest = os.path.join(pdir, "keycheck.jpg")
        build_check_sheet(entries, dest)
        print(f"\ncheck sheet -> {dest}")
    print(f"\n{len(entries)} elements keyed, {flagged} flagged for review")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir")
    ap.add_argument("--only", default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    run(os.path.abspath(a.project_dir), set(a.only.split(",")) if a.only else None,
        check=a.check)
