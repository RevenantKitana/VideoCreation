# Slide-deck mode — locked tuning

> **If the source .pptx is available, use `scripts/slides_pptx.py` instead of keying.**
> None of the tuning below applies to that path — there is nothing to tune, because
> nothing is estimated. Keying remains the fallback for flattened-image-only decks.


**Status: validated and frozen (tag `slides-v1`, 2026-08-12).**
Two full decks shipped on these values — a dark HUD deck (`hoa10-m3`, 8 slides) and a
light hand-drawn deck (`hoa10-nto`, 12 slides, two-speaker dialogue).

Every number below was set by a **measured failure**, not by taste. Each entry records
what breaks if you move it. Change one at a time and re-run
`python3 scripts/slides_key.py <project> --check`.

---

## scripts/slides_key.py

| constant | value | why this value |
|---|---|---|
| `CUT` | `t0=8, t1=26, dilate=1, blur=1.1` | The shape that flies. `dilate=1` keeps each stroke's anti-aliased halo attached, so a landed element composites back to the source exactly. Drop the dilation and landed art goes subtly thin and hard-edged. |
| `ERASE` | `t0=3, t1=13, dilate=5, blur=2.2` | **The single most important pair.** A stroke's halo scores *below* the cut threshold, so at `CUT`'s setting halos are never erased — and summed over an element they trace a fully legible ghost of it on "empty" paper. This was the reported bug. Raising `t0` back toward 8 brings the silhouettes straight back. |
| `ERASE_GAIN` | `1.7` | Pushes the erase mask's soft edge to solid. Below ~1.3 a faint rim survives around every stroke. |
| `MARGIN` | `16` | The bbox is grown by this before keying. A hand-drawn box outline or folder corner routinely sits a few px outside a hand-placed bbox, and anything outside is never erased — it stays as a clean rectangle outline of the missing element. Setting this dropped QA flags from 18 → 4. |
| `PAD` | `28` (scaled: `max(PAD, 0.35·min(w,h))`) | Context ring the background is rebuilt from. Fixed 28px around a 415×365 hole leaves the middle with nothing to hear from, and it settles on a washed-out mean. |
| `SOLID` | `0.35` | Threshold for interior-hole flood fill. Without hole filling a hand-drawn circle flies as a bare ring and its fill stays behind. |
| `FLAT_STD` | `26.0` | Above this the deck background is textured and keying is skipped. **Known imprecise:** the nebula deck scores *under* it and does get keyed. Its keys are actually good, so this is not urgent — but do not trust `auto` blindly on a photographic deck; set `key_mode` explicitly. |
| `MERGE_DIST` | `26.0` | Ring colours closer than this are one colour. Quantizing to a 12-step grid splits one flat cream across two bins and scores a perfectly uniform ring at 0.52 instead of 0.89, which then fails the flat-fill gate. |
| `RING_FLAT_SHARE` / `RING_FLAT_SPREAD` | `0.65` / `30.0` | Above/below these the surround is uniform enough to fill with one flat colour, which beats any diffusion. Measured: folder `0.91/15.6` → flat; sticky-note-over-board `0.51/45.1` → must diffuse. The old `0.55/14.0` gate missed the folder by a hair and left a grey patch. |
| `COV_SPLIT`, `COARSE_LEVELS`, `FINE_LEVELS` | `0.35`, `(16,8,4)`, `(4,)` | Large holes need coarse-to-fine diffusion; thin strokes must **not** touch a coarse level, because at 1/16 scale a line of text is sub-pixel and the coarse pass smears the ink into a grey haze exactly where the text was. |

### Overlap resolution

Contested pixels go to the **smaller** element (on a slide, the small thing lies on
top), and only inside its **own bbox** — never its padding ring, where its matte has
already picked up the neighbour's artwork. Allowing the ring bit the label off a
neighbouring folder.

---

## scripts/slides_render.py

| constant | value | why |
|---|---|---|
| `FLASH` | `{dark: 0.55, light: 0.08}` | Brightening a cream background by 50% clips to pure white, so the landing flash stops reading as a glow and stamps a hard white rectangle for the length of the reveal. Visible on the first full light-deck render. |
| `REVEAL_DUR` | `0.55` s | Fly-in duration. |
| travel cap | `260px` / `200px` | Capped, not proportional: a 1100px-wide title sliding 60% of its own width crosses the frame and reads as a swipe, not a placement. |
| `base_level` | `0.88` (light decks: `0.94`) | Muted toward the deck's own **paper colour** on light decks, never toward black. |

---

## scripts/slides_audio.py

| constant | value | why |
|---|---|---|
| `REVEAL_LEAD_S` | `0.12` | Land the element a hair before its word is spoken. |
| `TURN_GAP_S` | `0.45` | Pause between speakers in a dialogue. Offsets use each segment's **measured** duration, not the alignment's last timestamp — mp3s carry encoder padding. |
| `TAIL_PAD_S` | `2.0` | Music is generated to the measured narration length plus this. |

---

## Things that are NOT tuning, and must not be "fixed" by tuning

- **Background-removal models fail on this content.** `fal-ai/imageutils/rembg`
  measured on five representative elements: kept only the red proton and deleted an
  entire atom's orbit; ghosted a sticky note to nothing; chewed the corner off a
  folder; dropped a diamond's sparkles. It segments *salient objects*; flat line art
  has none. Do not re-introduce it.
- **Overlapping artwork cannot be fully recovered.** What is *under* the top piece was
  never in the source image. A stamp lying across two folders leaves a pale patch
  until it lands. The fix is scheduling — cue it close behind what it covers — not a
  threshold. This is the one case where a generative in-place edit would genuinely
  add information.
- **Cues must be literal substrings of their slide's narration.** That is what makes
  timing exact rather than fuzzy. Verify before spending anything on TTS.
- **`eleven_multilingual_v2` has no Vietnamese.** Use `eleven_v3`.

## Regression check

The refactor that consolidated these constants was verified by re-keying a full deck
and comparing every output byte: **116 key files, 0 changed**. Any future refactor
claiming to be behaviour-preserving should clear the same bar:

```bash
md5 out/<deck>/keys/*.png > /tmp/before.txt
rm -rf out/<deck>/keys && python3 scripts/slides_key.py out/<deck>
md5 out/<deck>/keys/*.png | diff /tmp/before.txt -    # must be empty
```
