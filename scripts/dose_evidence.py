#!/usr/bin/env python3
"""Was the dose HEARD? The evidence half of the slip ledger's escalation law.

A commission is a dose that was built, not a dose that was heard, and a
treatment is never escalated from an unplayed tape. Two states:

  heard     an `attended` observation on a payload word IN THE SAME LANE, on or
            after the commission date. Only this state can escalate, and only on
            a slip dated a LATER DAY than the listen.
  awaiting  nothing shows it was played. Not a failure: cue the ear block, never
            build a second dose on an unplayed first.

Same lane, because a long rotation that happens to carry one soak word is not a
listen to the soak. A commission records a lane and a payload, not an artifact,
so lane + payload word + date is the closest join the data allows.

With few listens logged, almost every tag reads `awaiting` and ESCALATE goes
quiet; the summary line counts each state so that never reads as "all healed".
A `frame:*` payload names a pattern, not a word, and never counts as heard.

Imports `state_io` and `observations` only; `slips` imports from here.
"""

from collections import Counter

from observations import OBSERVATIONS_PATH
from state_io import load_json, local_date

# The lanes a dose can be commissioned to — the ONE list: `sync_state`'s
# --soak-channel choices and `escalation_note` both read it.
DOSE_CHANNELS = ("episode", "soak", "drill")
# A listen is stamped with the feed item's FORMAT, which is not always the lane.
ATTENDED_AS = {"episode": "mission"}


def attended_events() -> list[dict]:
    """Every listen the log holds. Read once per ledger pass."""
    return [o for o in (load_json(OBSERVATIONS_PATH) or []) if o.get("kind") == "attended"]


def _bare(word: str) -> str:
    """A payload phrase and a registry phrase differ by punctuation."""
    return word.strip(" ?!.,¿¡")


def _heard_at(commission: dict, attended: list[dict]) -> str:
    """The earliest listen in the commissioned lane, on one of its words, on or
    after the commission day; "" when there is none."""
    words = {_bare(w) for w in commission.get("payload") or [] if not w.startswith("frame:")}
    lane = ATTENDED_AS.get(commission.get("channel"), commission.get("channel"))
    since = commission.get("at") or ""
    days = [(o["at"], local_date(o["at"])) for o in attended
            if o.get("channel") == lane and _bare(o.get("word") or "") in words]
    return min((at for at, d in days if d and d.isoformat() >= since), default="")


def judge_dose(commissions: list[dict], slip_days: list[str],
               attended: list[dict]) -> tuple[str, str, bool]:
    """(state, heard_at, slipped_after_heard) for one tag. A slip follows a
    listen only on a LATER DAY: a slip's date is when it was written, so same-day
    order cannot be trusted, and withholding an escalation a day is the cheap error."""
    if not commissions:
        return "", "", False
    heard = min((h for h in (_heard_at(c, attended) for c in commissions) if h), default="")
    if heard:
        return "heard", heard, any(d > local_date(heard).isoformat() for d in slip_days)
    return "awaiting", "", False


def dose_note(p: dict) -> str:
    """The one line a surface prints for a tag's dose state ("" when none)."""
    state = p.get("dose_state")
    if state == "heard":
        return f"✓ heard {p['heard_at'][:10]} and no slip since — test it, don't re-order it."
    if state == "awaiting":
        return ("⏳ dose built, nothing shows it was heard — not a failed treatment. "
                "Cue the ear block; don't build a second dose on an unplayed first.")
    return ""


def dose_summary(patterns: list[dict]) -> str:
    """Counts of each dose state, so a quiet ESCALATE reads as "nothing heard
    yet" and never as "nothing wrong"."""
    n = Counter(p.get("dose_state") for p in patterns if p.get("dose_state"))
    if not n:
        return ""
    return (f"Dose evidence: {n['heard']} heard, {n['awaiting']} awaiting attendance — "
            f"ESCALATE needs a listen; 'awaiting' is not 'failed'.")


def _and_join(items) -> str:
    items = list(items)
    return ", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else "".join(items)


def escalation_note(channels) -> str:
    """"soak tried; drill and episode untried" — change the format TO WHAT.
    Every lane tried says the repair has outgrown the audio lanes."""
    tried = [c for c in channels if c in DOSE_CHANNELS]
    left = [c for c in DOSE_CHANNELS if c not in tried]
    if not tried:
        return "a dose was built and the learner slipped again"
    if not left:
        return "every lane tried and it still slips — this has outgrown the audio lanes"
    return f"{_and_join(tried)} tried; {_and_join(left)} untried"
