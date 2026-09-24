# Playbook — when something breaks

Fix it yourself; tell the person only what they must do.

| Symptom | Fix |
|---|---|
| `doctor` NOT READY | run setup (Mac `bash setup/setup-mac.command`, Windows `powershell -ExecutionPolicy Bypass -File setup\setup-windows.ps1`). Needs internet once. |
| "aligner model" missing | `models/aligner/vi_ctc.onnx` (385 MB) must be copied from the master copy of this folder — it is not downloadable. Ask whoever gave them the folder. |
| `check`: "cannot typeset" | a LaTeX typo: unbalanced `{}`, `\\` vs `\`, a command ziamath lacks. Simplify the formula; `\dfrac`→`\frac`, remove `\left`/`\right`. |
| `check`: narration has symbols | rewrite in spoken form (see context/script-format.md). |
| preview: something overlaps / too small | fewer elements in that scene (split the scene), shorter lines, or lower `spacing`. Max ~5 elements + graph per scene. |
| `voice`: a line REDO after retries | reword that `say` (shorter, simpler words, spell out symbols), run `voice` again. |
| `voice`: VieNeu load error "External data path escapes model directory" | `HF_HUB_DISABLE_SYMLINKS` wasn't set: always run through `./os` / `os.cmd`, never plain `python`. Delete `models/hf` and run `warmup`. |
| `render`: Remotion fails "browser" | `cd engine/remotion` and run `npx remotion browser ensure` through pixi (setup step 3). |
| `render` very slow | normal on older laptops: ~1 min per 10 s of video. Don't run two renders at once. |
| studio: mic blocked | browser site permission → Microphone → Allow → reload. |
| studio: port 8765 in use | an old studio is still open; close that terminal / kill the process, run `record` again. |
| Windows: `./os` not found | use `os.cmd`. |
| Anything else | read the error, look at the relevant file in `engine/`, fix, and note the fix at the bottom of this file. |
