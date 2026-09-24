# Playbook — clone a staff voice for the AI to read with

Use when someone wants videos in their own voice without recording every line
(guide page 6 tells them the same steps, in Vietnamese).

1. **Consent first.** Explain in one or two sentences: the AI will be able to speak any
   text in their voice; it stays on company laptops and is used only for Aiducation
   lessons; they can withdraw at any time. Only clone the voice of the person you are
   talking to (or someone who will sign themselves) — never a celebrity, a student or a
   colleague who isn't present.
2. **Get a sample:** ~10 seconds of them reading naturally, quiet room, no music. A phone
   voice memo is fine; so is a take from the recording studio
   (`videos/<v>/voice/lines/<key>.wav`). Save it into the folder, e.g. `inbox/`.
3. `./os clone-voice <ten-khong-dau> <file>` — the name is plain letters/digits/dashes
   (`co-lan`, `thay-minh`). It trims silence, cleans the sample (needs ≥3 s of speech;
   uses up to 8 s), writes `voices/<name>/consent.md` (Vietnamese) and a test line
   `voices/<name>/test.wav`.
4. **Play `test.wav` to them** (tell them where it is). Not like them → a cleaner/longer
   sample and run clone-voice again.
5. **They fill in `consent.md`** — "Họ và tên" and "Ngày". Until both are filled in,
   `check` and `render` refuse any video using `clone:<name>`. Never fill it in for them.
6. Use it: `"voice": "clone:<name>"` for the whole video, or on single steps for dialogue.
   Cloned voices speak Vietnamese; English sentences use the `en:` voices.

Withdrawal: delete `voices/<name>/` entirely and tell them it's done.
