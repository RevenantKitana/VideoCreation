# Playbook — posting to TikTok, and logging it

The person uploads by hand (TikTok app or tiktok.com/upload). You prepare and log.

## Before they upload
- File: `videos/<v>/final.mp4`. Cover: `videos/<v>/cover.png` (they can pick it as the
  cover frame).
- Caption: `videos/<v>/caption.txt` (question/promise + 3–5 hashtags). Remind them:
  bật "Cho phép lưu video" (allow saves) — saves are our main quality signal.
- Best slot: check `plans/` for the planned time; default evenings 19:00–21:00 or the
  slot the plan names.

## After they post
Ask for the link, then:

```
./os posted <v> <url> --hook <H-id> --format <F-id> --topic "<chủ đề>" [--experiment E-00x]
```

Tags must come from `context/hooks.md` and `context/formats.md` (use the ids). If they
posted at a different time than now, add `--at 2026-09-24T19:30`.

Tell them: "Sau 24 giờ, 48 giờ và 7 ngày em sẽ nhờ chị/anh chụp màn hình số liệu."
