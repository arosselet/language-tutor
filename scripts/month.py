#!/usr/bin/env python3
"""THE MONTH — one arc of the world's life, and the unit between the day and the
year.

Without it nothing is ever FINISHED, so the only structure the learner can
perceive is the ritual and the only continuity is their own recurring mistakes —
lessons that feel narrow and pointed at their failures. A month gives the story
an arc and the vocabulary a home.

MEMBERSHIP IS DERIVED, and so is completion: the month's words are the union of
the NEW payload its episodes actually taught, folded every call. A stored set or
counter drifts and reads green while doing nothing; a fold cannot.

THE WIN IS THE FINALE EAR TEST, NEVER THE COUNT. The learner hears the arc's last
episode without captions and says what happened; two thirds of the key lines
right wins. Comprehension is produced, never self-reported. No number leaves the
tutor's mouth.

Not owned here: the order candidates arrive in (`suggest_targets`), which
episodes exist, what happens in the world (`content/world.md`). Sidecars and
episodes are PASSED IN — the layer boundary.
"""
from datetime import date

from state_io import load_json, local_today, LEARNER_PATH

# One month is live at a time, under this key in learner.json; git holds the rest.
KEY = "month"

# The ear rung that closes a member — the rung the rest of the system treats as
# "they have this".
EAR_RUNG = {"comfortable", "solid"}

# Two thirds of the finale's key lines, a partial worth half. A starting number:
# re-base it after two finales from what the verdicts look like.
WIN_SHARE = 2 / 3


def load(learner: dict | None = None) -> dict:
    """The live month, or {} when none has been opened."""
    if learner is None:
        learner = load_json(LEARNER_PATH) or {}
    rec = learner.get(KEY)
    return rec if isinstance(rec, dict) else {}


def closes_on(today: date) -> str:
    """The last day of the calendar month — a reset on a date the learner
    already recognises."""
    nxt = date(today.year + (today.month == 12), (today.month % 12) + 1, 1)
    return (nxt.fromordinal(nxt.toordinal() - 1)).isoformat()


def is_over(rec: dict, today: date | None = None) -> bool:
    """Past its close date. A record missing `closes` reads as OVER: an
    unbounded month is the conveyor this file exists to remove."""
    if not rec:
        return False
    return (rec.get("closes") or "") < (today or local_today()).isoformat()


def opened_record(name: str, today: date | None = None) -> dict:
    """A new arc: a name, an open date, a close date — not one of them a target."""
    today = today or local_today()
    return {"name": name, "opened": today.isoformat(), "closes": closes_on(today)}


def arc_missions(rec: dict, episodes: dict) -> list[int]:
    """Mission numbers produced inside this month, oldest first. An episode with
    no `produced` date is LEFT OUT rather than assumed recent: a denominator that
    grows by guessing is a dishonest meter."""
    lo, hi = rec.get("opened") or "", rec.get("closes") or ""
    return sorted(int(n) for n, e in (episodes or {}).items()
                  if str(n).isdigit() and isinstance(e, dict)
                  and lo <= (e.get("produced") or "") <= hi)


def members(rec: dict, episodes: dict, sidecars: dict) -> list[str]:
    """THE MONTH'S VOCABULARY: the union of its episodes' `new_words_landed` —
    what the Producer recorded as taught, not what a plan intended. `sidecars`
    is mission number -> parsed sidecar; a missing one is reported by `standing`."""
    out = []
    for n in arc_missions(rec, episodes):
        for w in (sidecars.get(n) or {}).get("new_words_landed") or {}:
            if w not in out:
                out.append(w)
    return out


def axis_of(row: dict) -> str:
    """The ear for a `catch` row, the mouth otherwise. A fact about the row, so
    not stored."""
    return "ear" if row.get("direction") == "catch" else "mouth"


def is_closed(row: dict) -> bool:
    """Has this member reached its axis's rung? Asks the log, never a claim."""
    if axis_of(row) == "ear":
        return row.get("recognition") in EAR_RUNG
    return row.get("production") == "cold"


def standing(rec: dict, lexicon: dict, episodes: dict, sidecars: dict) -> dict:
    """The month's live state, recomputed every call, never persisted.
    `missing` (a member gone from the lexicon) and `unrecorded` (an episode with
    no sidecar) are loud: a silently shrinking denominator is a lying meter."""
    words = members(rec, episodes, sidecars)
    done, missing, still_open = [], [], []
    for w in words:
        row = lexicon.get(w)
        if not isinstance(row, dict):
            missing.append(w)
        elif is_closed(row):
            done.append(w)
        else:
            still_open.append(w)
    return {
        "total": len(words),
        "closed": len(done), "closed_words": done,
        "open_words": still_open, "missing": sorted(missing),
        "ear": sum(1 for w in words if axis_of(lexicon.get(w) or {}) == "ear"),
        "missions": arc_missions(rec, episodes),
        "unrecorded": [n for n in arc_missions(rec, episodes) if not sidecars.get(n)],
    }


def key_line_events(rec: dict, events: list) -> list[dict]:
    """The finale test's recorded lines for THIS month's finale, sourced on its
    mission number so a re-cut month cannot inherit another arc's verdict."""
    src = f"finale:M{rec.get('finale')}"
    return [e for e in (events or [])
            if isinstance(e, dict) and e.get("source") == src
            and e.get("channel") == "check"]


def verdict(rec: dict, events: list) -> dict:
    """THE WIN, as a fold over recorded key lines; there is no stored `won`. The
    tutor records what the learner PRODUCED for each line; a partial counts half,
    because scoring a half-catch as a miss makes the meter lie downward."""
    seen = key_line_events(rec, events)
    if not seen:
        return {"tested": 0, "score": 0.0, "of": 0, "won": False, "run": False}
    score = sum({"right": 1.0, "partial": 0.5}.get(e.get("result"), 0.0) for e in seen)
    return {"tested": len(seen), "score": score, "of": len(seen),
            "won": score >= WIN_SHARE * len(seen), "run": True}


def carry(rec: dict, lexicon: dict, episodes: dict, sidecars: dict) -> list[str]:
    """What an expiring month hands the next arc: its open members, as
    CANDIDATES only. There is no debt field, and that is load-bearing: the reset
    is the forgiveness mechanism, and a count of what was missed becomes a streak."""
    return standing(rec, lexicon, episodes, sidecars)["open_words"]
