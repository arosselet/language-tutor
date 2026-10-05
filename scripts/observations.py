#!/usr/bin/env python3
"""The observation log: every fact the system learns about the learner and a
word, appended and never spent. `lexicon_view` folds it into the lexicon; this
file only appends and names the vocabulary.

A log rather than mutable fields because setting a field SPENDS an observation:
the rung moves and the channel, the question and the confidence are gone. With a
log, changing the policy means re-deriving, not purging.

Five fields carry the design: `kind` (an exposure is not a test), `channel`
(carries trust: declared channels are recorded and never vote), `axis` (the two
move independently), `medium` (reading is not hearing) and `source` (the
artifact, for audit).

A JSON array rather than JSONL: `publish.UNIONABLE` resolves a rebase conflict on
an append-only array by keeping every row from both sides, keyed on `id`.
A bad constant warns rather than raising, because every unattended lane imports this.
"""
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from state_io import BASE, load_json, save_json

OBSERVATIONS_PATH = BASE / "progress" / "observations.json"

# Above the line the system watched it happen; below, it was told.
CHANNELS = {
    "session",      # the tutor's own observation in a live session
    "eavesdrop",    # a judged catch of an overheard line
    "knock", "text", "volley", "challenge", "fielding", "audio",  # a judged phone reply, by modality
    "episode", "drill", "soak", "rotation",   # a dose was delivered
    "check",        # the Receptive Check
    "media",        # native media the learner reported back on
    # ── declared, never watched: recorded, excluded by policy ──
    "seed",         # a setup-time self-estimate
    "self-report",  # a mission debrief: how it FELT, not what happened
}
DECLARED = {"seed", "self-report"}
WATCHED = CHANNELS - DECLARED

# Which sense received it. A property of the channel everywhere except `check`,
# which runs by ear or on the page, so that writer passes it explicitly.
MEDIA = {"audio", "text"}
EAR = {"eavesdrop", "audio", "media", "episode", "soak", "drill", "rotation"}

KINDS = {
    "taught",       # a full Teach Beat — first contact, generously given
    "attended",     # the learner RECEIVED it: a press of play. The only kind that is
                    # a fact about the learner rather than about what the machine
                    # emitted; a delivery-channel `taught` is pending until one covers it
    "exposed",      # it went past them in a dose; heard is not known
    "tested",       # they were asked and something came back
    "asked-about",  # THEY raised it: unsolicited and honest
    "claimed",      # asserted without a test behind it
}

AXES = {"recognition", "production", None}
RESULTS = {"right", "wrong", "partial", None}
# The judges' vocabularies, translated into the log's. One home each.
CATCH_RESULT = {"caught": "right", "half-caught": "partial", "missed": "wrong", "miss": "wrong"}
HEARD_RESULT = {"right": "right", "misread": "wrong"}
FIRE_RESULT = {"cold": "right", "hinted": "partial", "capped": "partial"}


def _checked(value, allowed, field):
    """`value` if legal, else a loud, greppable marker. Never raises."""
    if value in allowed:
        return value
    print(f"   ⚠ observations: unknown {field} {value!r} — recorded as-is, "
          f"not one of {sorted(a for a in allowed if a)}", file=sys.stderr)
    return f"unknown:{value}"


def medium_of(event) -> str:
    """Which sense received it: the writer's own answer, else its channel's."""
    return (event["medium"] if event.get("medium") in MEDIA
            else "audio" if event.get("channel") in EAR else "text")


def record(word, channel, kind, *, axis=None, result=None, source="", note=""):
    """Append ONE observation; returns it. `lexicon_view.observe` is the write
    path that records AND folds, and every writer uses that one."""
    return record_many([dict(word=word, channel=channel, kind=kind, axis=axis,
                             result=result, source=source, note=note)])[0]


def record_many(events):
    """Append several at once: one read and one write."""
    log = load_json(OBSERVATIONS_PATH) or []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    written = []
    for e in events:
        row = {
            "id": uuid.uuid4().hex[:12],
            "at": e.get("at") or now,
            "word": e.get("word", ""),
            "channel": _checked(e.get("channel"), CHANNELS, "channel"),
            "kind": _checked(e.get("kind"), KINDS, "kind"),
            "axis": _checked(e.get("axis"), AXES, "axis"),
            "result": _checked(e.get("result"), RESULTS, "result"),
            "medium": _checked(medium_of(e), MEDIA, "medium"),
            "source": e.get("source") or "",
            "note": e.get("note") or "",
        }
        log.append(row)
        written.append(row)
    save_json(OBSERVATIONS_PATH, log)
    return written
