# Playbook — video from a slide deck PDF

Person sends a PDF of slides (exported from PowerPoint, Canva, Google Slides, Keynote…)
and maybe extra images, and says something like "làm video từ slide này".

## 0. Ask for the right file
- Best: **the PDF exported from the slide tool** ("File → Download → PDF"). Those PDFs are
  *vector*: every text box, shape and picture is a separate object, and the video
  reveals them exactly as the author drew them.
- A PDF made of screenshots/images (or AI-generated slide pictures) is *flat*: it still
  works, but elements must be cut out of the picture — slower and less exact. If they
  have the original deck, ask for a PDF export of it instead.

## 1. Import
Save the file into the folder (e.g. `inbox/deck.pdf`), then:

```
./os deck inbox/deck.pdf "<tên video>" --subject HÓA
```

It prints each page's mode (`vector` / `flat`) and element count, and writes
`videos/<v>/deck/pNN.marks.png` — the page with **numbered green boxes**, one per
element. Open every marks image and look at it before writing anything.

## 2. Write the narration — `videos/<v>/script.json`
The import made one scene per page with a placeholder step. Replace it:

```json
{"type": "slide", "page": 2, "steps": [
  {"say": "Nguyên tố hóa học là tập hợp các nguyên tử có cùng số proton.",
   "reveal": [{"el": 3, "at": "tập hợp"}, {"el": 5, "at": "cùng số proton", "anim": "pop"}]},
  {"say": "Ví dụ, mọi nguyên tử có sáu proton đều là carbon.",
   "reveal": [{"el": [6, 7], "at": "Ví dụ"}]}
]}
```

- `el` — the number from the marks image; a list reveals several as one.
- `at` — the words in `say` at which it lands (must be copied **exactly** from `say`;
  `check` enforces it). Without `at`, elements land at the start of the step.
- `anim` — `rise` (default), `fade`, `pop`, `left`, `right`, `drop`.
- Elements never listed in any `reveal` are simply part of the page from the start
  (logos, frames, decorations). Reveal only what the narration talks about — 3–6 per
  page is plenty.
- An element grouped too coarsely (two bullets in one box)? Use a custom box instead
  of `el`: `{"box": [x0, y0, x1, y1], "at": "…"}` in 1920×1080 pixels. On vector pages
  it takes exactly the objects inside; on flat pages the marks image has a pixel grid.
- Dialogue (teacher + student): give a step its own `"voice": "Trúc Ly"`.
- Narration rules are the same as every video (spoken form, ≤ 220 characters/step).
  A page usually needs 2–5 steps.
- Default layout keeps the slide in a card with captions underneath; set top-level
  `"captions": "overlay"` (captions over the slide) or `"off"`.

## 3. Check → preview → voice → render
Same as `make-video.md`: `check`, `preview` (one frame per step — show it to the person),
`voice`, `render`. Deck renders are fast (no animation engine): ~1 minute.

## Flat pages: what to watch
- Proposed boxes on flat pages are guesses. If a box cuts through a drawing, write your
  own `box` from the grid. Grow it ~15 px around the artwork.
- Something lying *on top of* another element (a stamp across two cards) leaves a pale
  patch until it lands — reveal the covering piece right after what it covers.
