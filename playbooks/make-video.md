# Playbook — make a video

Person says something like "làm video về định luật Ohm lớp 9" or "làm bài xét dấu đạo hàm".

## 1. Pin down the brief (ask at most 3 questions, only what you can't infer)

- Subject + grade + the exact problem or concept. If they have an exercise (photo, text,
  page of a book), use it verbatim — ask for it.
- Which slot in the plan this fills (check `plans/` and today's `days/*/slate.md`); if the
  slate already names hook / format / topic, use those.
- Format: TikTok is 9:16 (default). For an in-app lesson or anything they'll show on a
  screen, use `"format": "16:9"`.
- Their own images (a photo, a diagram, AI-made art): copy them into `assets/images/`
  and use them as a scene `background` or an `image` element (context/script-format.md).
- Voice: default `Minh Quân Pro`. Ask only if they haven't said: "Dùng giọng AI (Minh Quân
  hoặc Trúc Ly) hay chị/anh tự đọc?"

## 2. Solve it yourself first

Work the problem fully in your head/notes before writing anything. Check each step, sign,
unit and final answer. If the source's answer disagrees with yours, stop and ask.

## 3. Write the script

`./os new "<title>" --subject <TOÁN|LÝ|HÓA|SINH|ANH|…>` then write
`videos/<v>/script.json` following `context/script-format.md`. House rules:

- **Length 45–75 s** → 8–14 steps. One idea per step. Each `say` ≤ 220 characters.
- **First step is the hook** (see `context/hooks.md`): the problem or the surprising claim
  on screen in the first 2 seconds. No greetings, no "xin chào các em".
- `say` is **spoken Vietnamese**: "y phẩy", "trừ 1", "x bình phương", "căn bậc hai của x".
  No symbols — `check` rejects them.
- The screen shows the maths; the voice explains it. Don't put the whole sentence on
  screen — captions already show the words.
- Default shape for exercises: **Dạng bài → Công thức cần nhớ → Lời giải → Kết luận**.
  Concept explainers may use other shapes (see `context/formats.md`).
- Last step: the one sentence to remember (it becomes the save-worthy takeaway).

## 4. Check and preview

```
./os check <v>        # fix every problem it lists, re-run until "script OK"
./os preview <v>      # ~1 min
```

Open `videos/<v>/preview.png` yourself and look at it: overlaps, text running off the
edge, a formula that looks wrong, an empty step. Fix and re-preview. Then **show the image
to the person** and ask: "Hình minh họa như thế này được chưa?" Wait for ok.

## 5. Voice

- AI voice: `./os voice <v>` (or `--voice "Trúc Ly"`). Every line is checked locally.
  - `ok` → fine.  `LISTEN` → play that line (`videos/<v>/voice/lines/<key>.wav`) to the
    person; accept only if they say it sounds right. If nobody can listen now, reword the
    flagged word (units and loanwords like "ampe", "ôm" are the usual cause — try the
    full word or a synonym) and run `voice` again until the line is `ok`.
  - `REDO` → the voice skipped or changed a word. `voice` already retried twice; reword
    that `say` slightly (shorter, clearer) and run `voice` again.
- Their own voice: follow `playbooks/record-voice.md` instead.

## 6. Render

`./os render <v>` (5–10 minutes; tell them). Then check it yourself: extract 3–4 frames
(`ffmpeg -ss <t> -i final.mp4 -frames:v 1 x.png`) and look at them. Tell the person:

> Video xong: `videos/<v>/final.mp4`, ảnh bìa: `videos/<v>/cover.png`.
> Caption gợi ý: … Hashtag: …

Write the suggested caption (≤ 150 chars, question or promise + 3–5 hashtags, see
`context/brand.md`) into `videos/<v>/caption.txt`.

## 7. Then

When they post it, `playbooks/publish.md`.
