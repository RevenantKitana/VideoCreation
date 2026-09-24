# aiducation-tiktok-production-os

A folder that works like `data-analytics-os`, but for TikTok: staff open it in the Claude
desktop app, ChatGPT/Codex or Antigravity. The agent reads `AGENTS.md` and does
everything: writes the script, makes the video, and runs the daily analytics loop. The
staff member only chats, approves previews, records their voice if they want to, posts
the video and sends screenshots.

**Everything runs on the laptop.** There are no API keys and no paid services. The
network is used only once, by setup.

## What it makes

1080×1920 vertical lessons in the dau-dao-ham style: flat cream/jade, maths animated in
Manim, word-by-word karaoke captions, Vietnamese narration.

```
script.json ──check──▶ preview.png ──(person ok)──▶ voice ──▶ render ──▶ final.mp4 + cover.png
   (agent)      typeset     540p Manim       VieNeu TTS or       Manim (transparent VP9, parallel)
                every        contact          studio recording    + Remotion (brand frame, karaoke,
                formula      sheet            → local checker       audio) → H.264
```

| Piece | What | Why this one |
|---|---|---|
| Toolchain | **pixi** + conda-forge, installed into `.pixi/` | One lockfile solves for win-64, osx-64 and osx-arm64. pycairo has no Mac wheel on PyPI, so pip alone would have needed Homebrew. |
| Maths type | **ziamath** (LaTeX → SVG, pure Python) | There is no LaTeX distribution on any laptop. Manim's `MathTex` would have needed TeX, and dvisvgm doesn't exist on conda-forge. |
| Animation | Manim 0.20, one generic `LessonScene` driven by `script.json` | The dau-dao-ham style is ported from aiducation-manim. Authoring is JSON, not Python. |
| Voice | **VieNeu-TTS** v3 Turbo (Apache-2.0, CPU). Voices: Minh Quân Pro (default), Trúc Ly, or a clone from a 3–8 s staff sample | Local and free. |
| Checker | **CTC forced alignment**: `wav2vec2-base-vi-vlsp2020`, exported to ONNX (`models/aligner/`) | Checks that every line actually says the script, and gives word timings for the karaoke captions. |
| Compositing | Remotion 4.0.508 (ported ManimLesson + karaoke captions) | Kept by decision. |
| Recording | `record` opens a local studio page: sample reading, karaoke pace, one take per line, instant check | Staff voice without an editor. |

## Measured on this Mac (M-series, 2026-09-23)

- **Install:** `pixi install` took 28 s from cache. The folder is 2.9 GB in total: `.pixi` 1.3 G, `node_modules` 568 M, VieNeu models 608 M, aligner 367 M.
- **dau-dao-ham rebuilt from `script.json` alone** (`vi-du/01-toan-12-dau-dao-ham-tiktok`):
  - `check` took 6 s and `preview` about 40 s.
  - `voice` took 1 min 42 s for 14 lines, and all 14 passed the checker.
  - `render` took 4.5 min for 61 s of video.
- **Checker thresholds, measured on the dau-dao-ham lines:**
  - Deliberately wrong lines (with "trừ" dropped, "trừ" swapped for "cộng", or "phẩy" dropped) score −10.3 or lower on the missing word.
  - Correct lines (14 lines × 5 voices) score no lower than −5.9.
  - The same holds on noisy Opus takes sent through the studio.
  - Rule: below −8 the line must be redone; −6 to −8 means a person listens.
- **A fresh agent built a new subject from the instructions alone:** `vi-du/02-vat-ly-9-dinh-luat-om-tiktok` (Ohm's law, with a graph). It worked from AGENTS.md and the playbooks with no help, and the maths came out correct. Its bug reports were fixed the same day: a blank hook frame, Hugging Face contacted at run time, graphs shrinking the text, and gaps in the docs.
- **Why Whisper isn't the checker:**
  - Without the script as a hint, it hears "trừ" as "chữ" and "phẩy" as "phải" even on correct audio.
  - With the line given as a prompt, it repeats the script back and passes skipped words.

## Added 2026-09-23 (second round)

- **Deck mode (`deck` command, `playbooks/deck-video.md`).** PDF slides become 16:9 videos whose elements build in on the spoken word.
  - Vector PDFs use pdfium page objects. Every state is an exact re-render with not-yet-revealed objects removed, including objects inside a group that wraps the whole page.
  - Flat (image-only) pages use vox-director's frozen keying (`engine/deck/keying.py`).
  - Tested on a synthetic vector deck (`vi-du/03-…`), on real company decks (analysis only, 3–12 elements per page), and on the hoa10 slides as a flat deck with a two-voice dialogue (`vi-du/04-…`, 90 s).
- **Geometry, charts (pie/bar/line) and reading passages with marks.** These are figures with named parts, drawn in place step by step (`vi-du/05-…`).
- **16:9 format.** When a figure and text share a scene, they sit side by side.
- **Background photos with slow zoom.** Staff supply their own images; images must carry no text.
- **Silent mode** (`"voice": "none"`, `vi-du/06-…`).
- **Per-step voice** for dialogue.
- **Karaoke caption pagination:** long lines never exceed two lines.
- **English voice (item 4).** Kokoro-82M (Apache-2.0) runs locally with 4 voices (UK/US, female/male), and any step can switch language.
  - The English checker is `Xenova/wav2vec2-base-960h` (ONNX), downloaded by setup.
  - Correct lines score −1.6 or better; dropped words score −13.9 or lower.
  - British voices lose a final "r" and score −5 to −6 on correct audio, so English uses the same −6 "listen" line as Vietnamese.
  - `"caption": false` hides a line's caption (dictation).
  - Gotcha: espeak-ng truncates data paths longer than about 160 bytes and silently falls back to a default path that doesn't exist. The data is copied to `models/espeak-ng-data`.
  - Test video: `vi-du/07-…`.

## Not verified yet — do these before rolling out

1. **Windows end to end.** The lockfile solves for win-64 and the wrappers exist (`os.cmd`, `setup\setup-windows.bat`), but this has never been run on a Windows PC. First real run: `setup-windows.bat`, then `os.cmd doctor`, then `os.cmd render 1`.
2. **Intel Mac.** Same situation: the lockfile solves for it but it has not been run.
3. **Real human recordings.** The checker was tested on synthetic voices through noise and a browser codec, not on a staff member reading into a laptop mic. Southern and Central accents in particular.
4. **Clone likeness.** Cloning runs and passes the checker, but nobody has listened to judge whether it sounds like the person.
5. **Remotion licence.** Remotion needs a paid company licence for teams of more than 3 people. Check remotion.dev/license before staff use it.

## Handing it to staff

**`bash tools/make_share_zip.sh`** builds `~/Desktop/xuong-tiktok-aiducation-<date>.zip` (344 MB). It includes the Vietnamese guide `HUONG-DAN-SU-DUNG.pdf` at the top level and unzips to a folder called `xuong-tiktok`. Re-run it after every update. The notes below explain what it includes and leaves out.

Copy the whole folder, including `models/aligner/vi_ctc.onnx`. That file isn't downloadable; it was exported once from the Hugging Face model with `tools/export_aligner_reference.py`. Leave out `.pixi/`, `.tools/`, `models/hf/` and `engine/remotion/node_modules/`, because setup rebuilds them for the right OS. That brings the folder down to 388 MB. Tested: a clean copy ran `setup/setup-mac.command` unchanged and reached READY in 2 min 42 s. That Mac already had pixi's package cache, so expect 10–20 min on a new laptop.

On the laptop, the agent runs setup the first time (`AGENTS.md` §1). Setup downloads about 2.5 GB.

## Layout

See `AGENTS.md` §4. The machinery is in `engine/`:
- `scenes/`: Manim, typesetting, layout
- `voice/`: TTS, checker, spoken-form text
- `record/`: the studio page
- `remotion/`: compositing
- `pipeline.py`: the steps
- `analytics.py`: the TikTok loop

## Lineage

- The look and scene base come from `aiducation-manim`.
- The ManimLesson composition and font loading come from `aiducation-ielts`.
- The operating model (binding instructions, a context layer that defines metrics, write-once data, numbered findings that cite files) comes from `data-analytics-os`, with two of its gaps fixed: findings are auto-numbered with a generated index, and there is a daily journal (`days/`).
