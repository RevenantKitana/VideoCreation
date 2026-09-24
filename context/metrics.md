# Metrics — the only place a metric is defined

Implemented in `engine/analytics.py` `derived()`. Change both together. Reviews and
findings cite these ids. Raw fields come from TikTok Studio screenshots (see
`playbooks/daily-review.md`).

| id | name | formula | read at | what it answers |
|---|---|---|---|---|
| T-01 | Views | `views` | all | reach (mostly luck on one post) |
| T-02 | Hold 3 s % | `retention_3s_pct` (retention curve at 3 s) | 24h | did the first frame + first line stop the scroll? |
| T-03 | Finish % | `watched_full_pct` | 48h | did the lesson hold to the end? |
| T-04 | Avg watch % | `avg_watch_time_s / video duration × 100` | 48h | depth of viewing, comparable across lengths |
| T-05 | Saves / 1k views | `1000 × saves / views` | 48h | **main quality signal for education**: "I'll come back to this" |
| T-06 | Shares / 1k views | `1000 × shares / views` | 48h | would a student send it to a friend? |
| T-07 | Follows / 1k views | `1000 × new_followers / views` | 7d | does the video build the channel (the usual goal)? |
| T-08 | For You % | `src_for_you_pct` | 24h | was it pushed beyond followers? low = not distributed |
| T-09 | Search % | `src_search_pct` | 7d | evergreen search demand — compounds over months |

> **Caveats that travel with every number**
> - Compare same-age readouts only (48h vs 48h). Numbers keep growing for days.
> - The comparison is against **our own** rolling median (scorecard), not internet
>   benchmarks. Vendor benchmarks (e.g. "3 s hold > 65%", "completion 40–50% for
>   30–60 s") are folklore; TikTok publishes none.
> - One post is an anecdote. Tag-level conclusions need ~5 posts per tag.
> - Views are heavy-tailed: use medians, never means.
> - Exam season and holidays move everything (context/calendar.md).

## Proposing a new metric
Add a row here as `PROPOSED` with formula and the question it answers, ask the person,
then implement it in `derived()`.
