# script.json — the only file a video is made from

One file per video: `videos/V-NNNN-slug/script.json`. The reference example is
`vi-du/01-toan-12-dau-dao-ham-tiktok/script.json` — read it before writing a new one.
Every folder in `vi-du/` is a finished example (script + final.mp4) of one kind of video;
`vi-du/README.md` lists them. Copy the closest one's structure.

```jsonc
{
  "id": "V-0007",
  "title": "Định luật Ohm",
  "subject": "LÝ",                // shown in the corner wordmark
  "voice": "Minh Quân Pro",       // | "Trúc Ly" | "record" | "clone:<name>" | "none" (silent)
                                  // English: "en:bf_emma" (UK f) "en:bm_george" (UK m)
                                  //          "en:af_heart" (US f) "en:am_michael" (US m)
  "format": "9:16",               // TikTok (default) | "16:9" for app lessons / slide decks
  "captions": "on",               // | "overlay" | "off"   (16:9 slide pages: "on" = strip below)
  "scenes": [                     // 2–5 scenes; each is one screen with a heading
    {
      "heading": "Định luật Ohm",
      "subheading": "Vật lý 9",   // optional
      "spacing": 0.8,             // optional: gap between elements (default 0.7)
      "graph": { … },             // optional, see below
      "steps": [                  // one step = one narration line = one change on screen
        {
          "say": "Cường độ dòng điện tỉ lệ thuận với hiệu điện thế.",
          "show": [ {"id": "law", "math": "I = \\dfrac{U}{R}"} ],
          "hide": [ "old-id" ],   // optional: remove things
          "band": [-1, 1],        // optional: highlight x-interval on the graph
          "draw_graph": true      // optional: draw the graph on this step
        }
      ],
      "end": [ {"id": "note", "text": "…", "style": "muted"} ]  // optional, after last step
    }
  ]
}
```

## Elements (`show`)

| key | content | example |
|---|---|---|
| `math` | LaTeX maths (no `$`) | `"y = -x \\Rightarrow y' = -1 < 0"` |
| `rich` | Vietnamese with `$maths$` inside | `"Bước 1: $x \\in (-\\infty;\\ -1)$"` |
| `text` | plain Vietnamese; `\n` for a new line | `"Hàm số nghịch biến"` |
| `image` | a PNG/JPG in the folder + optional `height` | `"image": "assets/img/te-bao.png"` |
| `figure` | a named figure from the scene's `figures` (below) + optional `draw` | `{"id": "tri", "figure": "tri", "draw": ["AB", "CA"]}` |
| `passage` | a reading card; words can be marked later | `{"id": "p", "passage": "Human beings do not…"}` |

`style`: `body` (default) · `accent` (jade, bold — conclusions) · `deep` (dark jade —
step labels) · `muted` (small grey — notes) · `wrong` (clay — ONLY for "this is the wrong
way"; never for a negative sign or a decreasing function).

**Same `id` again = the element transforms in place** (formula → next formula). New `id`
= a new line below. Layout is computed once from every version, so nothing jumps.

Maths is typeset by ziamath (no LaTeX install): `\frac \dfrac \sqrt \begin{cases}
\begin{array} \Rightarrow \in \infty \le \ge \cdot \times \Delta \alpha…`, sub/superscripts,
`\text{…}` all work. Chemistry: `2H_2 + O_2 \rightarrow 2H_2O`. Minus signs are spaced
correctly automatically.

## Graph (optional, one per scene)

```json
"graph": {
  "x": [-3.2, 3.2], "y": [-0.5, 3.5],
  "pieces": [ {"f": "-x", "from": -3.2, "to": -1}, {"f": "x**2", "from": -1, "to": 1} ],
  "marks": [-1, 1, {"x": 2, "label": "x_0"}, {"point": [6, 0.5], "xlabel": "6", "ylabel": "0{,}5"}],
  "labels": {"x": "U\\,(V)", "y": "I\\,(A)"},
  "origin": true,                 // "O" at the origin (default true)
  "width": 6.5, "height": 3.4     // size before fitting (defaults shown)
}
```

- `marks`: a number = dashed line from the axis up to the curve at that x, labelled.
  `{"x", "label"}` = same with a custom label. `{"point": [x, y], "xlabel", "ylabel"}` =
  a dot with dashed guides to BOTH axes and both values labelled.
- If a scene is too full, the graph shrinks first (to 55%) before any text shrinks.

`f` is a formula in `x` using `+ - * / ** ( )` and `sin cos tan exp log sqrt abs pi e`.
The graph is the first thing under the heading; draw it with `"draw_graph": true`.

## Figures: geometry and charts (`figures` on the scene)

Define once per scene, then show it — whole, or part by part with `draw` (the figure
never moves; new parts are drawn in place, missing parts fade out).

```json
"figures": {
  "tri": {"points": {"A": [0,0], "B": [4,0], "C": [0,3]},
          "segments": ["AB", "CA", "BC"], "polygons": ["ABC"], "right_angles": ["BAC"],
          "angles": [{"at": "ABC", "label": "\\alpha"}], "lengths": {"AB": "4", "BC": "c"},
          "circles": [{"center": "O", "r": 2}], "dashed": ["CH"], "size": 4.5},
  "pie": {"type": "pie", "unit": "%", "data": [{"label": "Than", "value": 34},
          {"label": "Hạt nhân", "value": 10, "emphasis": true}]},
  "bars": {"type": "bar", "unit": "%", "data": [{"label": "2019", "value": 42}]},
  "trend": {"type": "line", "data": [{"label": "T1", "value": 3}, {"label": "T2", "value": 5}]}
}
```

Part names for `draw` / `emphasize`: geometry — point `A`, segment `AB`, `poly:ABC`,
`circle:O`, `right:BAC`, `angle:ABC`, `len:AB`; charts — each data `label`.

Step actions: `"emphasize": ["tri:BC", "pie:Hạt nhân"]` flashes a part in jade;
`"mark": [{"id": "p", "words": "chronotypes", "style": "circle"}]` marks words in a
passage (`highlight` default, `underline`, `circle`, `strike`, `box`);
`"hide": ["p#marks"]` clears a passage's marks.

In 16:9, a scene with a figure and text lays them side by side (figure left).

## Background photo (any lesson scene)

`"background": {"image": "assets/images/x.jpg", "zoom": "in", "wash": 0.75}` — the
person's own image (or one they made with ChatGPT/Gemini), slow zoom, cream wash so text
stays readable. **Images must contain no text**: image tools garble Vietnamese; the
engine draws all text itself.

## Mixing languages and hiding a caption

- Any step can set its own `"voice"`: an English sentence in `en:bf_emma` inside a
  Vietnamese lesson, or teacher/student dialogue. The checker switches language with it
  (or set `"lang": "en"` / `"vi"` explicitly).
- Vietnamese voices can say short English words inside Vietnamese sentences; whole English
  sentences should use an English voice.
- `"caption": false` on a step — it is heard but its words are not shown (dictation,
  "listen and answer" quizzes).
- English lines may use apostrophes (don't, it's); other symbols still must be words.

## Silent videos

`"voice": "none"` — no narration, no captions; each step stays on screen for
`"hold": <seconds>` (default 3). For reading drills and quick visual reveals.

## Slide-deck scenes

`{"type": "slide", "page": N, "steps": [...]}` — see `playbooks/deck-video.md`.

## The first frame is the hook

The first scene opens already built: heading and the first step's `show` are on screen
at frame 1 (no animation). So put the problem/claim in scene 1, step 1 — not a title card.

## Narration (`say`) rules — `check` enforces the first two

- Spoken form only: no `$ \ ^ _ = < > ' + /`. Write "y phẩy", "bằng", "lớn hơn",
  "x bình phương", "cộng", "chia".
- ≤ 220 characters per line (~15 s).
- Numbers may stay as digits ("trừ 1", "2,5") — they are read and checked correctly.
- Single letters (K, x, y) are read as letter names; that's expected.

## Other shapes (non-exercise)

- **Concept in 3 beats**: heading = the question; steps: intuition → formula → example.
- **Mistake callout**: scene 1 shows the common wrong answer with `style: "wrong"`, scene 2
  the correct one; the hook line names the mistake.
- **Compare two things** (biology/chemistry): two `rich` lines per step, then a summary
  `math` `\begin{array}`.
