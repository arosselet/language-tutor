#!/usr/bin/env python3
"""THE REACH BUDGET: when the tutor may reach the learner, how often, and how
little.

One concept obeyed by two channels (the knock lane and the push queue), so it
lives below both: a channel never owns an invariant more than one channel obeys.
The WHEN and HOW OFTEN are learner facts and come from the pack; the supply floor
is pedagogy and is fixed. Imports `pack` and `state_io` only.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from pack import MAX_REACHES_PER_DAY, MIN_GAP_HOURS, WAKING_END_HOUR, WAKING_START_HOUR
from state_io import LOCAL_TZ, is_fire, local_date

# The rails are re-exported: lanes ask `rails`, never the pack, for the budget.
__all__ = ["MAX_REACHES_PER_DAY", "MIN_GAP_HOURS", "WAKING_END_HOUR", "WAKING_START_HOUR",
           "in_waking_window", "reaches_today", "last_fire", "SUPPLY_WINDOW_DAYS",
           "SUPPLY_FLOOR_MIN", "PLEASURE_MIN_GAP_DAYS", "pleasure_due"]


def in_waking_window(now: datetime | None = None) -> bool:
    """Inside the learner's waking hours, local time? The ONE definition — the
    rails gate, the queue's deferral and `push_to_phone` all read it. The cron
    ticks a UTC superset; this filters."""
    now = now or datetime.now(timezone.utc)
    return WAKING_START_HOUR <= now.astimezone(LOCAL_TZ).hour < WAKING_END_HOUR


def reaches_today(klog: list, now_local_date) -> int:
    """Reaches that actually went out today on the learner's clock. (Not "fires":
    a fire is a word the learner produced.)"""
    return sum(1 for k in klog
               if is_fire(k) and local_date(k.get("timestamp", "")) == now_local_date)


def last_fire(klog: list) -> dict | None:
    """The most recent reach that went out — what the min gap is measured from."""
    fires = [k for k in klog if is_fire(k) and k.get("timestamp")]
    return fires[-1] if fires else None


# ── How LITTLE (the supply floor) ────────────────────────────────────────────
# Every rail above is a ceiling; this is the floor. Audio is commissioned inside
# sessions, so without it supply is gated on attendance: a tired learner gets
# fewer sessions, fewer doses, less in their ears, and fades further. A fade is
# palatability data, never answered with accountability machinery — so this
# makes the SYSTEM owe contact, a floor on what is PRODUCED, never on what was
# played (a floor they could fail by not listening would be a streak).
SUPPLY_WINDOW_DAYS = 7
SUPPLY_FLOOR_MIN = 30
# A spacing so a quiet week fills steadily rather than all at once.
PLEASURE_MIN_GAP_DAYS = 2


def pleasure_due(produced_min: float, days_since_last: float | None) -> str:
    """"" when a no-strings dose is owed; otherwise why not. A reason string, not
    a bool: this runs unattended, and "it did not fire" has several causes."""
    if days_since_last is not None and days_since_last < PLEASURE_MIN_GAP_DAYS:
        return f"last pleasure dose was {days_since_last:.1f}d ago (gap {PLEASURE_MIN_GAP_DAYS}d)"
    if produced_min >= SUPPLY_FLOOR_MIN:
        return (f"the shelf is stocked: {produced_min:.0f} min produced in "
                f"{SUPPLY_WINDOW_DAYS}d (floor {SUPPLY_FLOOR_MIN})")
    return ""
