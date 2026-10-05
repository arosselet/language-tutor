#!/usr/bin/env python3
"""The lexicon is a view over the observation log.

Every evidence field on a lexicon row (`EVIDENCE`) is written by exactly one
function, `rebuild`, and it writes what the log supports. A writer records an
event through `observe` and the rung follows. The static half of a row (gloss,
type, register, direction, pairs_with) is curriculum, hand-owned.

THE POLICY: a rung is what watched tests support — recognition climbs one per
pass and falls one per miss, production is the best grade ever fired, and
declared channels never vote. No recency decay: the ear is tested too rarely for
a clock to measure anything but the instrument's cadence.

THE FOLD IS SPARSE. A field is rewritten only where the log speaks to it, so a
row the log has never mentioned keeps what the file says. `--check` holds the
file equal to the fold on the real tree. A `seed` claim makes its axis spoken and
then does not vote, so the fold returns the default.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import observations
from observations import WATCHED
from state_io import (DEMOTE, LEXICON_PATH, PRODUCTION_RANK, RECOGNITION_DEFAULT,
                      RECOGNITION_NEXT, load_json, local_date, resolve, save_json)

EVIDENCE = ("recognition", "production", "reps", "exposures", "heard_on",
            "last_surfaced", "seen_in", "taught_on", "heard_times")
PRODUCTION_FOR = {"right": "cold", "partial": "hinted"}
EPISODE_SRC = re.compile(r"^episode:M?(\d+)$")
# Channels whose Teach Beat needs no proof of receipt: the tutor said it TO the
# learner, live. Every other channel hands a file to a phone and hopes.
SELF_ATTENDING = {"session"}


def derive(events):
    """Fold the log into `{word: evidence}`. Pure. `spoken` names the fields the
    log has an opinion on; `rebuild` rewrites only those."""
    view = {}
    for e in sorted(events, key=lambda e: e.get("at") or ""):
        row = view.setdefault(e["word"], {
            "recognition": RECOGNITION_DEFAULT, "production": "none", "reps": 0,
            "exposures": 0, "heard_on": None, "last_surfaced": None, "seen_in": [],
            "taught_on": None, "taught_pending": None, "heard_times": 0,
            "tests": 0, "channels": set(), "spoken": set()})
        row["channels"].add(e["channel"])
        kind, axis, res = e["kind"], e.get("axis"), e.get("result")
        if kind == "claimed" and axis:
            row["spoken"].add(axis)          # an opinion: recorded, never counted
        if e["channel"] not in WATCHED:
            continue
        day = local_date(e.get("at") or "")
        day = day.isoformat() if day else None
        if day and kind in ("tested", "exposed", "taught", "attended"):
            row["last_surfaced"] = day
            row["spoken"].add("last_surfaced")
        if kind == "taught":
            # Spoken either way: a delivery-channel Teach Beat is an opinion the
            # fold declines to count until attendance discharges it.
            row["spoken"].add("taught_on")
            if e["channel"] in SELF_ATTENDING:
                row["taught_on"] = row["taught_on"] or day
            else:
                row["taught_pending"] = row["taught_pending"] or day
            m = EPISODE_SRC.match(e.get("source") or "")
            if m and int(m.group(1)) not in row["seen_in"]:
                row["seen_in"].append(int(m.group(1)))
        elif kind == "attended":
            # Discharges a pending Teach Beat and never creates one: a rating
            # covers every word a tape spoke, and hearing is not knowing. Dated
            # to the teaching. Attendance also implies exposure, which keeps the
            # rotation's coverage loop closed; `heard_times` counts presses only.
            row["spoken"] |= {"taught_on", "exposures", "heard_times"}
            row["taught_on"] = row["taught_on"] or row["taught_pending"]
            row["exposures"] += 1
            row["heard_times"] += 1
        elif kind == "exposed":
            row["exposures"] += 1
            row["spoken"].add("exposures")
        elif kind == "tested":
            # A watched test proves the learner was there for the word, and a
            # RIGHT recognition answer is first contact, proven — a word they
            # already know must not queue for a Teach Beat. A miss opens nothing.
            row["taught_on"] = (row["taught_on"] or row["taught_pending"]
                                or (day if axis == "recognition" and res == "right" else None))
            row["tests"] = row["reps"] = row["reps"] + 1
            row["spoken"].add("reps")
            if axis == "recognition":
                # The rung is what they KNOW; `heard_on` is what their EAR was
                # tested on, and a typed answer is no evidence of that.
                row["spoken"] |= {"recognition", "heard_on"} | ({"taught_on"} if row["taught_on"] else set())
                if observations.medium_of(e) == "audio":
                    row["heard_on"] = day or row["heard_on"]
                if res == "right":
                    row["recognition"] = RECOGNITION_NEXT.get(row["recognition"],
                                                              row["recognition"])
                elif res == "wrong":
                    row["recognition"] = DEMOTE.get(row["recognition"], "struggled")
                elif row["recognition"] == RECOGNITION_DEFAULT:
                    # A half-answer moves no rung, but it IS a test.
                    row["recognition"] = "struggled"
            elif axis == "production":
                row["spoken"].add("production")
                nxt = PRODUCTION_FOR.get(res or "")
                if nxt and PRODUCTION_RANK[nxt] > PRODUCTION_RANK[row["production"]]:
                    row["production"] = nxt
    return view


def rebuild(lexicon: dict, events, only=None) -> list[str]:
    """Fold the log onto the rows, in place; `only` limits it to words just
    written. Returns logged words with no row — reported, never minted."""
    orphans = []
    for word, row in derive(events).items():
        if only is not None and word not in only:
            continue
        rec = lexicon.get(word)
        if rec is None:
            orphans.append(word)
            continue
        for field in row["spoken"]:
            rec[field] = row[field]
        if row["seen_in"]:
            rec["seen_in"] = sorted(set(rec.get("seen_in") or []) | set(row["seen_in"]))
    return orphans


def observe(events, lexicon: dict | None = None) -> list[dict]:
    """THE write path for evidence: append, then fold onto the rows. With
    `lexicon` given it folds in place and the caller saves."""
    written = observations.record_many(events)
    own = lexicon is None
    lexicon = load_json(LEXICON_PATH) or {} if own else lexicon
    rebuild(lexicon, load_json(observations.OBSERVATIONS_PATH) or [],
            only={e["word"] for e in written})
    if own:
        save_json(LEXICON_PATH, lexicon)
    return written


def expose(keys, channel: str, source: str = "", *, taught=(), kind="exposed",
           mint: dict | None = None, lexicon: dict | None = None,
           at: str | None = None) -> list[str]:
    """A dose carrying these words went out — the delivery seam every lane calls.
    `taught` names the subset that was SHOWN (first contact); the rest merely
    appeared. Returns the keys that resolved. An unresolvable key is warned and
    never minted, unless the lane hands its static row in `mint`."""
    own = lexicon is None
    lex = (load_json(LEXICON_PATH) or {}) if own else lexicon
    if not lex or not keys:
        return []
    for k, row in (mint or {}).items():
        if k not in lex:
            lex[k] = {"recognition": RECOGNITION_DEFAULT, "production": "none",
                      "seen_in": [], "last_surfaced": None, **row}
            print(f"   + intake: '{k}' enters the lexicon")
    marked = []
    for k in keys:
        key = resolve(k, lex)
        if key is None:
            print(f"   ⚠ exposure: '{k}' not in lexicon — skipped")
        elif key not in marked:
            marked.append(key)
    shown = {resolve(k, lex) for k in taught}
    if marked:
        observe([dict(word=k, channel=channel, source=source, at=at,
                      kind="taught" if k in shown else kind) for k in marked], lexicon=lex)
        if own:
            save_json(LEXICON_PATH, lex)
            print(f"   Exposure stamped: {', '.join(marked)}")
    return marked


def remerge() -> Path:
    """Resolve a rebase conflict on `lexicon.json` (`publish.DERIVED`). Two
    writers never disagree about EVIDENCE — that is the fold of the log, already
    unioned on disk — so the static halves are unioned by key (upstream wins,
    ours fills its gaps) and the evidence is rebuilt. In a rebase, stage :2 is
    upstream and :3 is ours."""
    import subprocess

    def side(stage):
        r = subprocess.run(["git", "show", f":{stage}:progress/lexicon.json"],
                           cwd=LEXICON_PATH.parent.parent, capture_output=True,
                           text=True, encoding="utf-8")
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}

    theirs, ours = side(2), side(3)
    merged = {k: dict(v) for k, v in theirs.items()}
    for word, rec in ours.items():
        row = merged.setdefault(word, {})
        for field, value in rec.items():
            if field not in EVIDENCE and not row.get(field):
                row[field] = value
    orphans = rebuild(merged, load_json(observations.OBSERVATIONS_PATH) or [])
    save_json(LEXICON_PATH, merged)
    print(f"   ↳ lexicon re-merged: {len(theirs)} theirs + {len(ours)} ours -> {len(merged)} "
          f"rows, evidence rebuilt from the log"
          + (f"; {len(orphans)} logged words have no row" if orphans else ""))
    return LEXICON_PATH


def divergence(lexicon: dict, events) -> list[str]:
    """Every row whose evidence differs from the fold. Empty on a healthy tree;
    a name here means a writer set a field by hand."""
    view = derive(events)
    out = []
    for word, rec in lexicon.items():
        row = view.get(word)
        if not row:
            continue
        for field in row["spoken"]:
            if field == "seen_in":
                continue
            if (rec.get(field) or None) != (row[field] or None):
                out.append(f"{word}: {field} file={rec.get(field)!r} log={row[field]!r}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Check the lexicon against the observation log")
    ap.add_argument("--rebuild", action="store_true",
                    help="rewrite every evidence field from the log (a repair)")
    args = ap.parse_args()
    events = load_json(observations.OBSERVATIONS_PATH) or []
    lex = load_json(LEXICON_PATH) or {}
    if args.rebuild:
        orphans = rebuild(lex, events)
        save_json(LEXICON_PATH, lex)
        print(f"rebuilt {len(lex)} rows from {len(events)} events"
              + (f" · {len(orphans)} words in the log have no row: {orphans[:5]}" if orphans else ""))
    bad = divergence(lex, events)
    print(f"{len(lex)} rows · {len(events)} events · {len(bad)} divergent")
    for line in bad[:40]:
        print("  " + line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
