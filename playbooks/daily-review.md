# Playbook — the daily review (screenshots in, tomorrow's slate out)

Run every working day, usually when the person sends screenshots or says "số liệu hôm qua".

## 1. What is due
`./os today` → lists readouts due (24h / 48h / 7d per posted video) and creates
`days/<today>/inbox/`. Ask for exactly the screenshots it lists, per due video, in
TikTok Studio (app: Hồ sơ → ☰ → TikTok Studio → Phân tích → chọn video):
Tổng quan (top numbers), the retention graph, traffic sources + search terms, Viewers tab.

## 2. Read the screenshots
Save the images they send into `days/<today>/inbox/` (and copy into
`videos/<v>/metrics/screens/`). For each video + readout, read the numbers **carefully**
into a JSON file using only the field names in `engine/analytics.py` `FIELDS`:

```json
{"views": 12300, "likes": 840, "comments": 31, "shares": 55, "saves": 402,
 "new_followers": 18, "avg_watch_time_s": 21.4, "watched_full_pct": 17.2,
 "retention_3s_pct": 71, "src_for_you_pct": 88.1, "src_search_pct": 4.2,
 "src_profile_pct": 3.9, "src_following_pct": 2.6, "src_other_pct": 1.2,
 "search_queries": [{"term": "xét dấu đạo hàm", "pct": 34}],
 "retention_curve": [{"t": 0, "pct": 100}, {"t": 3, "pct": 71}, {"t": 10, "pct": 44}]}
```

- "12,3K" = 12300; "1,2M" = 1200000 (Vietnamese UI uses a comma decimal).
- Leave out anything not visible. Never guess. `retention_3s_pct` = read the curve at 3 s.
- Match each screenshot to its video by caption/cover/date. If unsure which video it is,
  ask — don't guess.
- `./os readout <v> <24h|48h|7d> <file.json>` — it validates (sources ≈ 100%, counts ≤
  views) and refuses to overwrite. If it rejects, re-read the image.

## 3. Score
`./os scorecard` (48h by default; `--at 24h` for early signals, `--at 7d` for outcomes).
Read it with `context/metrics.md` open:
- 24h: T-02 hold 3s and T-08 For You % — did TikTok push it?
- 48h: T-03 finish %, T-05 saves/1k, T-06 shares/1k — was it good?
- 7d: T-07 follows/1k, T-09 Search % — did it build the channel?

## 4. Write `days/<today>/review.md`
```
# Review <date>
## What came in        (videos + readouts saved, with file paths)
## What the numbers say (≤5 bullets, each citing a readout or the scorecard)
## What they can't tell us   (required: n, same-age caveat, luck, calendar)
## Against the goal     (progress toward goals/G-00x target, one line)
```
Rules: one post is an anecdote; a tag pattern needs ~5 posts. Check `context/calendar.md`
(exam weeks, Tết) before calling a trend.

## 5. Decide tomorrow → `days/<tomorrow>/slate.md`
Follow the plan's mix (default **70% proven format + new topic / 20% one-variable variant
of a recent winner / 10% new bet**). For each slot: topic, format F-id, hook H-id, the
one variable being tested (if a variant), voice. Show the slate to the person in 3–5
lines and ask for ok. Then offer to start the first video (make-video.md).

## 6. Promote patterns
If a pattern has held across ≥5 posts per side, run `./os finding "<the conclusion>"`
and fill it in (citing readouts). If it changes the plan, add a dated amendment to the
plan (never rewrite the plan).
