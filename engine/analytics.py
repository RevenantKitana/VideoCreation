"""
The daily TikTok loop: goal -> plan -> post -> screenshots -> scorecard -> next slate.

Data lives next to each video, so a video folder tells its whole story:

    videos/<id>/post.json              url, posted_at, tags (hook/format/topic/experiment)
    videos/<id>/metrics/<24h|48h|7d>.json   one readout, written once, never edited
    videos/<id>/metrics/screens/…      the screenshots it was read from

Metric names and formulas are defined ONLY in context/metrics.md (T-01…). This file
implements exactly those formulas; if you change one, change both.
"""

from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path

from engine.pipeline import ROOT, VIDEOS, find_video

READOUTS = {"24h": 24, "48h": 48, "7d": 168}

# Raw fields read off TikTok Studio screenshots. Counts are integers ("12,3K" -> 12300),
# percentages are numbers 0-100, times are seconds.
FIELDS = {
    "views": "count", "likes": "count", "comments": "count", "shares": "count", "saves": "count",
    "new_followers": "count", "total_play_time_s": "sec", "avg_watch_time_s": "sec",
    "watched_full_pct": "pct", "retention_3s_pct": "pct",
    "src_for_you_pct": "pct", "src_following_pct": "pct", "src_profile_pct": "pct",
    "src_search_pct": "pct", "src_sound_pct": "pct", "src_other_pct": "pct",
    "viewers_new_pct": "pct", "viewers_returning_pct": "pct",
}
LISTS = ("search_queries", "retention_curve")  # [{term, pct}], [{t, pct}]

# Which screenshots to ask for, in the words staff will see in TikTok Studio.
SCREENS = [
    "Tab Tổng quan (Overview): phần trên cùng có lượt xem, thích, bình luận, chia sẻ, lưu",
    "Tab Tổng quan: biểu đồ 'Tỷ lệ giữ chân người xem' (retention) và thời gian xem trung bình",
    "Tab Tổng quan: 'Nguồn lưu lượng truy cập' (Traffic source) và 'Cụm từ tìm kiếm' nếu có",
    "Tab Người xem (Viewers): người xem mới / quay lại",
]


def _now() -> datetime:
    return datetime.now().astimezone()


def posted(ref: str, url: str, when: str | None = None, **tags) -> Path:
    vdir = find_video(ref)
    at = datetime.fromisoformat(when).astimezone() if when else _now()
    post = {"url": url, "posted_at": at.isoformat(timespec="minutes"), **{k: v for k, v in tags.items() if v}}
    (vdir / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    return vdir


def posts() -> list[tuple[Path, dict]]:
    out = []
    for v in sorted(p for p in VIDEOS.iterdir() if p.is_dir()):
        pj = v / "post.json"
        if pj.exists():
            out.append((v, json.loads(pj.read_text(encoding="utf-8"))))
    # Rolling medians compare each post with the ones published BEFORE it.
    return sorted(out, key=lambda vp: datetime.fromisoformat(vp[1]["posted_at"]))


def due(now: datetime | None = None) -> list[tuple[Path, str, float]]:
    """(video, readout label, hours since post) for every readout that is due and missing."""
    now = now or _now()
    todo = []
    for v, p in posts():
        age = (now - datetime.fromisoformat(p["posted_at"])).total_seconds() / 3600
        for label, hours in READOUTS.items():
            if age >= hours and not (v / "metrics" / f"{label}.json").exists():
                todo.append((v, label, round(age, 1)))
    return todo


def validate(m: dict) -> list[str]:
    problems = []
    for k, v in m.items():
        if k in FIELDS:
            if not isinstance(v, (int, float)):
                problems.append(f"{k} must be a number, got {v!r}")
            elif FIELDS[k] == "pct" and not 0 <= v <= 100:
                problems.append(f"{k} is a percentage, got {v}")
        elif k not in LISTS and k not in ("captured_at", "hours_since_post", "source", "screens", "notes"):
            problems.append(f"unknown field {k!r} (allowed: see engine/analytics.py FIELDS)")
    src = [m[k] for k in m if k.startswith("src_") and isinstance(m[k], (int, float))]
    if src and not 90 <= sum(src) <= 110:
        problems.append(f"traffic sources add up to {sum(src):.0f}%, expected ~100%: re-read the screenshot")
    if m.get("views") and any(m.get(k, 0) > m["views"] for k in ("likes", "saves", "shares", "comments")):
        problems.append("a count is larger than views: likely a misread (K vs M?)")
    return problems


def save_readout(ref: str, label: str, metrics: dict) -> Path:
    if label not in READOUTS:
        raise SystemExit(f"label must be one of {list(READOUTS)}")
    vdir = find_video(ref)
    out = vdir / "metrics" / f"{label}.json"
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} already exists; readouts are written once.")
    problems = validate(metrics)
    if problems:
        raise SystemExit("not saved:\n" + "\n".join(f"  - {p}" for p in problems))
    post = json.loads((vdir / "post.json").read_text(encoding="utf-8"))
    metrics.setdefault("captured_at", _now().isoformat(timespec="minutes"))
    metrics.setdefault("hours_since_post", round(
        (datetime.fromisoformat(metrics["captured_at"]) - datetime.fromisoformat(post["posted_at"])).total_seconds() / 3600, 1))
    metrics.setdefault("source", "screenshot")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# --- T-metrics (context/metrics.md is the definition; keep in sync) ----------------
def derived(m: dict, duration_s: float | None) -> dict:
    v = m.get("views") or 0
    per_k = lambda x: round(1000 * x / v, 1) if v else None  # noqa: E731
    return {
        "T-01 views": v,
        "T-02 hold 3s %": m.get("retention_3s_pct"),
        "T-03 finish %": m.get("watched_full_pct"),
        "T-04 avg watch %": round(100 * m["avg_watch_time_s"] / duration_s, 1)
        if m.get("avg_watch_time_s") and duration_s else None,
        "T-05 saves/1k": per_k(m.get("saves", 0)),
        "T-06 shares/1k": per_k(m.get("shares", 0)),
        "T-07 follows/1k": per_k(m.get("new_followers", 0)),
        "T-08 For You %": m.get("src_for_you_pct"),
        "T-09 Search %": m.get("src_search_pct"),
    }


def _duration(vdir: Path) -> float | None:
    lj = vdir / "build" / "final" / "lesson.json"
    if lj.exists():
        d = json.loads(lj.read_text(encoding="utf-8"))
        return d["durationInFrames"] / d["fps"]
    return None


def scorecard(label: str = "48h", window: int = 10) -> str:
    """Markdown: each post at `label` vs the median of the previous `window` posts,
    then the same comparison rolled up by tag. Same-age readouts only (48h vs 48h)."""
    rows = []
    for v, p in posts():
        f = v / "metrics" / f"{label}.json"
        if f.exists():
            m = json.loads(f.read_text(encoding="utf-8"))
            rows.append((v, p, derived(m, _duration(v))))
    if not rows:
        return f"No {label} readouts yet."
    keys = list(rows[0][2].keys())
    lines = [f"## Scorecard at {label} (vs median of previous {window} posts)", "",
             "| video | " + " | ".join(keys) + " |", "|" + "---|" * (len(keys) + 1)]
    for i, (v, p, d) in enumerate(rows):
        prev = [r[2] for r in rows[max(0, i - window):i]]
        cells = []
        for k in keys:
            val = d[k]
            base = [x[k] for x in prev if x[k] is not None]
            if val is None:
                cells.append("–")
            elif len(base) >= 3:
                med = statistics.median(base)
                arrow = "▲" if val > med * 1.2 else "▼" if val < med * 0.8 else "·"
                cells.append(f"{val} {arrow}")
            else:
                cells.append(str(val))
        lines.append(f"| {v.name} | " + " | ".join(cells) + " |")

    lines += ["", "▲/▼ = more than 20% above/below the median of the previous posts; "
              "shown only once 3+ earlier readouts exist.", ""]
    for tag in ("hook", "format", "topic"):
        groups: dict[str, list[dict]] = {}
        for v, p, d in rows:
            if p.get(tag):
                groups.setdefault(p[tag], []).append(d)
        if len(groups) < 2:
            continue
        lines += [f"### By {tag}", "", f"| {tag} | posts | median views | median hold 3s % | median saves/1k |", "|---|---|---|---|---|"]
        for g, ds in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            med = lambda k: statistics.median([x[k] for x in ds if x[k] is not None]) if any(x[k] is not None for x in ds) else "–"  # noqa: E731
            lines.append(f"| {g} | {len(ds)} | {med('T-01 views')} | {med('T-02 hold 3s %')} | {med('T-05 saves/1k')} |")
        lines.append("")
    lines.append(f"_n = {len(rows)} posts. With fewer than ~5 posts per tag, differences are noise, not findings._")
    return "\n".join(lines)


def today_dir(d: date | None = None) -> Path:
    p = ROOT / "days" / (d or date.today()).isoformat()
    (p / "inbox").mkdir(parents=True, exist_ok=True)
    return p


def next_finding_number() -> int:
    nums = [int(f.name[:4]) for f in (ROOT / "findings").glob("[0-9][0-9][0-9][0-9]-*.md")]
    return max(nums, default=0) + 1


def findings_index() -> str:
    rows = ["| # | title | status |", "|---|---|---|"]
    for f in sorted((ROOT / "findings").glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = f.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        status = next((l.split(":", 1)[1].split("<!--")[0].strip() for l in text.splitlines()
                       if l.lower().startswith("status:")), "?")
        rows.append(f"| [{f.name[:4]}]({f.name}) | {title} | {status} |")
    return "\n".join(rows)
