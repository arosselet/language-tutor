#!/usr/bin/env python3
"""THE TIMELINE — the phase schedule between the month and the stake's date.

A month knows when it ends; it does not know what it is FOR. When the stake has
a date (a trip, a wedding, an exam), the run-up has a shape, and the shape
answers three questions no other file can:

  1. WHICH DIRECTION production work leans — which room of people the learner
     is working up to, easiest and most error-tolerant first.
  2. WHEN TO STOP ADDING. Near the event intake goes to zero: an item learned
     late is not available under pressure, and a failed retrieval in front of
     the people who matter costs the rest of the conversation. Taper, like a race.
  3. WHAT THE EAR IS FED — voices and whether the situation is given, ramping to
     harder than the real room, so the real room feels slow.

The mechanism is fixed; the phases are DATA (`config.timeline`), written at setup
from the learner's stake, so a wedding next month and a trip next year each get
their own plan. Phases before the event with `days: null` share the run-up
evenly, remainder to the last one (nearest the event); the event spans its dates.

NOTHING IS STORED BUT THE THREE DATES (`learner.json.timeline`: opened,
event_from, event_to). The phase is asked, never read: a stored phase would read
green while the calendar walked past it. A marker is a sentence on a status
surface — behavioural, involving a real human — never a field, a thing collected
or a thing scored.
"""
from datetime import date, timedelta

from pack import TIMELINE
from state_io import load_json, local_today, LEARNER_PATH

KEY = "timeline"
PHASES = list(TIMELINE.get("phases") or [])
ORDER = [p["name"] for p in PHASES]
EVENT = TIMELINE.get("event") or next((p["name"] for p in PHASES if p.get("event")), "event")
DIRECTIONS = TIMELINE.get("directions") or {}
DEFAULT_DIRECTION = TIMELINE.get("default_direction") or next(iter(DIRECTIONS), "")
# Which word-pool registers LEAD in each direction, and which trail everywhere.
LEADS = {d: set(v.get("leads") or []) for d, v in DIRECTIONS.items()}
TRAILS = set(TIMELINE.get("trails") or [])
# Who a lean points at, for the surfaces that say it out loud.
ROOMS = {d: v.get("room", d) for d, v in DIRECTIONS.items()}
# The label a ticket prints: WHERE IN THE ORDER, not what kind of thing.
RANK_NAMES = {0: "lead", 1: "mid", 2: "dessert"}

_EVENT_AT = next((i for i, p in enumerate(PHASES) if p.get("event")), len(PHASES))
_BEFORE, _AFTER = PHASES[:_EVENT_AT], PHASES[_EVENT_AT + 1:]
_FLEX = [p["name"] for p in _BEFORE if p.get("days") is None]
_FIXED_BEFORE = sum(p["days"] for p in _BEFORE if p.get("days") is not None)


def _d(s) -> date | None:
    """An ISO date, or None. Never raises: a malformed date is a LOUD problem."""
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def load(learner: dict | None = None) -> dict:
    """The live timeline record, or {} when none has been opened."""
    if learner is None:
        learner = load_json(LEARNER_PATH) or {}
    rec = learner.get(KEY)
    return rec if isinstance(rec, dict) else {}


def problem(rec: dict) -> str:
    """Why there is no schedule, in one sentence, or "". The absence is loud:
    every failure here otherwise looks like success — the ticket still returns
    rows, simply ordered by nothing."""
    if not PHASES:
        return "no timeline module — the stake has no date"
    if not rec:
        return "no timeline is open — `sync_state.py timeline --from <date> --to <date>`"
    opened, efrom, eto = (_d(rec.get("opened")), _d(rec.get("event_from")),
                          _d(rec.get("event_to")))
    if not opened:
        return f"timeline.opened is not a date: {rec.get('opened')!r}"
    if not efrom or not eto:
        return f"the {EVENT} has no dates: {rec.get('event_from')!r}..{rec.get('event_to')!r}"
    if eto < efrom:
        return f"the {EVENT} ends before it starts: {efrom} .. {eto}"
    pool = (efrom - opened).days - _FIXED_BEFORE
    if pool < len(_FLEX):
        return (f"no room for the run-up: {opened} to {efrom} leaves {pool}d for "
                f"{', '.join(_FLEX)} after the fixed phases")
    return ""


def schedule(rec: dict) -> list[dict]:
    """Every phase with its dates, in order; [] when `problem` says why not.
    Flexible phases are derived, not declared, so a moved date needs one edit."""
    if problem(rec):
        return []
    opened, efrom, eto = _d(rec["opened"]), _d(rec["event_from"]), _d(rec["event_to"])
    pool = (efrom - opened).days - _FIXED_BEFORE
    share = pool // len(_FLEX)
    out, cursor = [], opened

    def span(p: dict, days: int):
        nonlocal cursor
        out.append({**p, "phase": p["name"], "from": cursor.isoformat(),
                    "to": (cursor + timedelta(days=days - 1)).isoformat()})
        cursor += timedelta(days=days)

    for p in _BEFORE:
        if p.get("days") is not None:
            span(p, p["days"])
        else:
            last = p["name"] == _FLEX[-1]
            span(p, pool - share * (len(_FLEX) - 1) if last else share)
    if _EVENT_AT < len(PHASES):
        span(PHASES[_EVENT_AT], (eto - efrom).days + 1)
    for p in _AFTER:
        span(p, p["days"])
    return out


def phase(rec: dict, today: date | None = None) -> dict:
    """The phase `today` falls in, or {}."""
    iso = (today or local_today()).isoformat()
    for p in schedule(rec):
        if p["from"] <= iso <= p["to"]:
            return p
    return {}


def direction(rec: dict, today: date | None = None) -> str:
    """Which way production work leans now. Outside a timeline it is the
    neutral default, not nothing: a lane that forgets to check still gets a sane
    sort, and `problem` is where the absence is loud."""
    return phase(rec, today).get("direction", DEFAULT_DIRECTION)


def register_rank(row: dict, lean: str) -> int:
    """0 leads, 1 middle, 2 trails — the prefix every ordering carries. An
    unregistered row sorts middle, never last."""
    reg = row.get("register", "")
    if reg in TRAILS:
        return 2
    return 0 if reg and reg in LEADS.get(lean, set()) else 1


def intake_cap(rec: dict, default: int, today: date | None = None) -> int:
    """New word types per audio dose after the phase has its say: the phase's
    `intake` where set, else the profile dial untouched (it has one owner)."""
    over = phase(rec, today).get("intake")
    return default if over is None else over


def days_to_event(rec: dict, today: date | None = None) -> int | None:
    """Days until the event starts. None when no timeline is open."""
    efrom = _d(rec.get("event_from"))
    return None if not efrom else (efrom - (today or local_today())).days


def is_over(rec: dict, today: date | None = None) -> bool:
    """Past the last phase. A timeline that cannot be scheduled reads as OVER:
    an unbounded one is the conveyor again, one scale up."""
    s = schedule(rec)
    return (s[-1]["to"] < (today or local_today()).isoformat()) if s else bool(rec)


def table(rec: dict, today: date | None = None) -> list[str]:
    """The phase table, one line per phase, `→` on the live one. A read surface
    beside the schedule it renders, so the command and the dashboard share it."""
    iso = (today or local_today()).isoformat()
    return [f"{'→' if p['from'] <= iso <= p['to'] else ' '} {p['phase']:11} "
            f"{p['from']} → {p['to']}  lean {p['direction']:6} · ear {p['voices']}v"
            f"{'' if p['situation_given'] else '/cold'}"
            f"{'' if p.get('intake') is None else f' · intake {p['intake']}'}"
            for p in schedule(rec)]


def opened_record(opened: str, event_from: str, event_to: str, prev: dict) -> dict:
    """The three dates, assembled here so `problem` can be asked of the result
    before anything lands: an unschedulable record is worse than none."""
    return {"opened": opened or local_today().isoformat(),
            "event_from": event_from or prev.get("event_from", ""),
            "event_to": event_to or prev.get("event_to", "")}


def status_line(rec: dict, today: date | None = None) -> str:
    """One line for the dashboards and the agent brief; names the problem when
    there is one."""
    bad = problem(rec)
    if bad:
        return f"Timeline: NOT SCHEDULED — {bad}"
    p = phase(rec, today)
    if not p:
        s = schedule(rec)
        return (f"Timeline: opens {s[0]['from']}" if (today or local_today()).isoformat() < s[0]["from"]
                else f"Timeline: over since {s[-1]['to']} — re-cut it")
    left = (_d(p["to"]) - (today or local_today())).days
    d = days_to_event(rec, today)
    return (f"Phase {ORDER.index(p['phase']) + 1}/{len(ORDER)} {p['phase']} "
            f"({left}d left) · leaning {p['direction']} · T-{d} to the {EVENT}\n"
            f"  next marker: {p['marker']}")
