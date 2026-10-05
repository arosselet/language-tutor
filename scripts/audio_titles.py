#!/usr/bin/env python3
"""The audio lanes' public names — what a soak, drill or rotation is CALLED, and
which words it aired.

A file rather than a derivation: a mission's name is its script's first line and
a knock's is in the knock log, but a soak leaves only an mp3, so the name exists
only at the moment the sheet is written. Not `episodes.json`, which registers
numbered missions only.

One writer, `lanes.deliver_rendered`; one reader for names, `rebuild_rss`; and the
words list is what a tap on the artifact may open (the teach gate trusts a listen,
never a render stamp).
"""
import json
import os
import re

from state_io import AUDIO_TITLES_PATH

# Read one-handed on a lock screen. The mandates ask for 3-6 words; this is the backstop.
TITLE_CAP = 60


def clean(title: str) -> str:
    """One line, trimmed, capped — never an empty string dressed as a name."""
    one = " ".join((title or "").split())
    return one[:TITLE_CAP].rstrip(" -—·,") if one else ""


def load() -> dict:
    """stem -> {"title": str, "words": [str]}. An unreadable file is an empty map,
    never a raise: a feed rebuild falls back to dated titles and still builds."""
    try:
        with open(AUDIO_TITLES_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    out = {}
    for k, v in data.items():
        row = dict(v or {})
        if isinstance(row.get("title"), str) and row["title"].strip():
            out[k] = {"title": row["title"], "words": list(row.get("words") or [])}
    return out


def record(stem: str, title: str, words=()) -> bool:
    """Name one dose and record which words it AIRED (`delivered`: audible in the
    finished artifact, never planned). Merge-write: overlay one key, leave the
    rest. Returns whether anything changed, so the caller commits only real writes."""
    title = clean(title)
    if not stem or not title:
        return False
    names = load()
    row = {"title": title, "words": [w for w in words if w]}
    if names.get(stem) == row:
        return False
    names[stem] = row
    AUDIO_TITLES_PATH.write_text(
        json.dumps(dict(sorted(names.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return True


LANE_WORD = {"drill": "Drill", "soak": "Soak", "rotation": "Rotation"}
LANE_RE = re.compile(r"(drill|soak|rotation)_")
# The date, plus the time only when the date alone does not separate two doses.
# Read off the filename: the stem is stable for the life of the item.
STAMP_RE = re.compile(r"_(\d{4}-\d{2}-\d{2})(?:_(\d{2})(\d{2}))?")


def lane_title(filename: str) -> str:
    """"soak_2026-08-30_2004.mp3" -> "Soak — <recorded name>", or "" to fall back.
    The recorded name says what a dose is ABOUT; a lane's fallback only says what
    it IS, which every member of the lane shares."""
    m = LANE_RE.match(os.path.basename(filename))
    row = load().get(os.path.basename(filename).removesuffix(".mp3")) or {}
    named = row.get("title", "")
    return f"{LANE_WORD[m.group(1)]} — {named}" if m and named else ""


def words_for(stem: str) -> list:
    """What this artifact aired — the set a tap on it may open."""
    return (load().get(stem) or {}).get("words", [])


def disambiguator(filename: str) -> str:
    """What to add to a name two doses share; empty when the filename has no date."""
    m = STAMP_RE.search(os.path.basename(filename))
    if not m:
        return ""
    return f"{m.group(1)} {m.group(2)}:{m.group(3)}" if m.group(2) else m.group(1)


def distinct(titles: dict) -> dict:
    """Every title distinct in the feed and the rating picker. Recognisable is
    the writer's job and can fail, so any title claimed by more than one stem gets
    its own timestamp, and only those: a unique name never pays for a date."""
    seen = {}
    for stem, title in titles.items():
        seen.setdefault(title, []).append(stem)
    out = dict(titles)
    for title, stems in seen.items():
        if len(stems) < 2:
            continue
        for stem in stems:
            mark = disambiguator(stem)
            if mark:
                out[stem] = f"{title} · {mark}"
    return out


def dose_minutes(days: int = 7, today=None) -> dict:
    """MINUTES ATTENDED over a trailing window — what was PLAYED, never what was
    commissioned, so the system cannot satisfy the meter by writing files. Each
    play row froze its `minutes` at tap time. `plays` is re-listens per artifact,
    which is also the quality meter."""
    from datetime import timedelta
    from state_io import FEEDBACK_LOG_PATH, load_json, local_today
    start = ((today or local_today()) - timedelta(days=days - 1)).isoformat()
    plays: dict[str, int] = {}
    total = 0.0
    for row in load_json(FEEDBACK_LOG_PATH) or []:
        if "[audio rating]" not in row.get("note", "") or row.get("date", "") < start:
            continue
        total += float(row.get("minutes") or 0.0)
        key = row.get("id") or "(no id)"
        plays[key] = plays.get(key, 0) + 1
    taps = sum(plays.values())
    return {"minutes": total, "per_day": total / days, "days": days,
            "plays": plays, "taps": taps,
            # Taps with no minutes behind them read as "stopped listening" when
            # the duration never reached the row — so say which it is.
            "unmeasured": bool(taps) and not total}
