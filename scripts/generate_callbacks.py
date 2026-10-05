#!/usr/bin/env python3
"""Spaced-repetition callback picker — a small query over the lexicon.

A callback is a SOFT target: a met word going stale that the next audio dose
should weave back in. It is not the dose's payload; that is the soak order.

  - Pool: every row that has surfaced, words and patterns, at every rung.
    Never-surfaced rows are new ground, the main ticket's job, not decayed material.
  - Due-ness: a recognition-aware interval on `last_surfaced`. A weak trace comes
    back soonest, because retrieval gains scale with how far it has decayed.
  - Patterns get up to PATTERN_SLOTS seats (never more than half): words
    outnumber them many times over and would otherwise take every seat, and the
    patterns carry the sentence skeleton comprehension needs.

    python scripts/generate_callbacks.py [--max 5]
"""

import argparse
from datetime import date

from state_io import LEXICON_PATH, RECOGNITION_RANK, load_json, local_today

INTERVAL_DAYS = {"solid": 21, "comfortable": 10, "struggled": 5, "untested": 5}
PATTERN_SLOTS = 2


def days_since(iso: str | None, today: date) -> int | None:
    if not iso:
        return None
    y, m, d = (int(x) for x in iso.split("-"))
    return (today - date(y, m, d)).days


def due_callbacks(lexicon: dict, today: date, max_n: int) -> list[dict]:
    candidates: list[dict] = []
    for word, rec in lexicon.items():
        recog = rec.get("recognition", "struggled")
        interval = INTERVAL_DAYS.get(recog, 5)
        ds = days_since(rec.get("last_surfaced"), today)
        if ds is None:
            continue
        overdue = ds - interval
        if overdue >= 0:
            candidates.append({
                "word": word,
                "gloss": rec.get("gloss", ""),
                "production": rec.get("production", "none"),
                "recognition": recog,
                "direction": rec.get("direction", "fire"),
                "last_surfaced": rec.get("last_surfaced"),
                "overdue": overdue,
                "pattern": rec.get("type") == "pattern",
            })
    # Most overdue first; equally overdue, the weaker trace first.
    order = lambda c: (-c["overdue"], RECOGNITION_RANK.get(c["recognition"], 0))
    candidates.sort(key=order)
    natural = candidates[:max_n]
    pats = [c for c in candidates if c["pattern"]]
    # A floor, never a ceiling: tops up only when patterns won no seats on their own.
    reserved = min(len(pats), PATTERN_SLOTS, max_n // 2)
    if sum(1 for c in natural if c["pattern"]) >= reserved:
        return natural
    picked = pats[:reserved] + [c for c in candidates if not c["pattern"]][:max_n - reserved]
    picked.sort(key=order)
    return picked


def main():
    parser = argparse.ArgumentParser(description="Pick spaced-repetition callbacks from the lexicon")
    parser.add_argument("--max", type=int, default=5, help="Max callback words (default: 5)")
    args = parser.parse_args()

    lexicon = load_json(LEXICON_PATH)
    if lexicon is None:  # empty ({}) is valid day-zero state; only missing is an error
        print("Error: progress/lexicon.json not found. See SETUP.md.")
        return

    today = local_today()
    callbacks = due_callbacks(lexicon, today, args.max)

    print("CALLBACKS (soft target, weave into the next episode):")
    print("-" * 52)
    if not callbacks:
        print("  (nothing due — the recognized set is fresh)")
    for cb in callbacks:
        gloss = cb["gloss"] or "[no gloss]"
        when = cb["last_surfaced"] or "never surfaced"
        tag = cb["recognition"] + (" · ear" if cb["direction"] == "catch" else "")
        print(f"  - {cb['word']} — {gloss}  [{tag}]  (last: {when})")

    backlog = len(due_callbacks(lexicon, today, 10 ** 6))
    print(f"\nDecay backlog: {backlog} met rows are past their return interval.")


if __name__ == "__main__":
    main()
