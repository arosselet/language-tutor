#!/usr/bin/env python3
"""The state writer — the one script that records what the tutor observed.

Word-state lives in ONE place, progress/lexicon.json: a word-keyed map whose rows
carry a static half (gloss, type, register, direction) and an evidence half (both
axes, reps, dates). The evidence half is a VIEW: every observation is an event in
progress/observations.json and `lexicon_view` folds it onto the row. This script
records events; it never sets a rung by hand.

  progress/lexicon.json     → word-state
  progress/learner.json     → continuity: running story, soak order, status (thin, model-facing)
  progress/episodes.json    → episodes (audio artifacts)
  progress/session_log.json → momentum log, one entry per session-DAY

Usage:
    python scripts/sync_state.py update --produced-cold <key> --stuck-word <key>
    python scripts/sync_state.py status          # what the tutor reads at session start

Canonical-at-write: produced/recognized words resolve against the lexicon's own
keys. A produced word that resolves to no record is WARNED and SKIPPED rather than
poisoning state — production presupposes a recognition record.
"""

import argparse
import difflib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from pack import LANGUAGE, LEARNER, is_canonical
from dose_evidence import DOSE_CHANNELS
from slips import (append_slips, canon_tag, cmd_slips,
                   parse_slip_args, record_slip_commission, record_slip_test,
                   slip_patterns)
from publish import commit_and_push, publish
import audio_titles
from rebuild_rss import feed_items
import month as month_mod
import timeline as timeline_mod
import lexicon_view
import observations
from state_io import (BASE, DEFAULT_TZ, EPISODES_PATH, FEEDBACK_LOG_PATH,
                      canon_payload,
                      KNOCK_LOG_PATH, LEARNER_PATH, LEXICON_PATH, RECOGNITION_DEFAULT,
                      SESSION_LOG_PATH, SLIP_LOG_PATH,
                      load_json, local_today, resolve, save_json)


# Recognition ladder: comfortable or solid is RECOGNIZED; struggled means a test
# came back wrong; untested means no test yet.
RECOGNITION_LEVELS = ["untested", "struggled", "comfortable", "solid"]
RECOGNIZED = {"comfortable", "solid"}


def mark_soak_delivered(channel: str) -> bool:
    """The lane that RENDERED the standing order stamps it consumed. The episode
    lane clears itself through registration; soak and drill have nothing to
    register, and inferring delivery fails on exactly the brand-new payload words
    that have no row yet. Delivery is declared by the seam that ships the dose.
    False when there is no order; callers commit LEARNER_PATH when True."""
    learner = load_json(LEARNER_PATH)
    if not learner or not (learner.get("soak_order") or {}):
        return False
    learner["soak_order"]["delivered"] = {
        "channel": channel, "at": local_today().isoformat()}
    save_json(LEARNER_PATH, learner)
    print(f"   Soak order marked delivered by the {channel} lane")
    return True


def is_pattern(rec: dict) -> bool:
    """A pattern record is a generative structure, metered separately."""
    return rec.get("type") == "pattern"


def compute_floor(lexicon: dict) -> dict:
    """The viability floor: of the WORDS recognized, how many fire cold? Patterns
    (Engines) and ear-only rows (cleared on recognition) are excluded, or the
    meter lies."""
    recognized = [w for w, r in lexicon.items()
                  if not is_pattern(r) and r.get("direction") != "catch"
                  and r.get("recognition") in RECOGNIZED]
    cleared = [w for w in recognized if lexicon[w].get("production") == "cold"]
    total = len(recognized)
    pct = (len(cleared) / total * 100) if total else 0.0
    return {"cleared": len(cleared), "total": total, "pct": pct}


def compute_engines(lexicon: dict) -> dict:
    """The engine meter: of the tracked patterns, how many fire cold (a NOVEL
    instance produced unaided)? Ear-only patterns are excluded."""
    patterns = [w for w, r in lexicon.items()
                if is_pattern(r) and r.get("direction") != "catch"]
    online = [w for w in patterns if lexicon[w].get("production") == "cold"]
    total = len(patterns)
    pct = (len(online) / total * 100) if total else 0.0
    return {"online": len(online), "total": total, "pct": pct}


def is_heard(rec: dict) -> bool:
    """Solid on the ear AND an ear test actually observed it. `heard_on` is
    stamped only by a by-ear recognition test, so a typed answer cannot make a
    row heard."""
    return rec.get("recognition") == "solid" and bool(rec.get("heard_on"))


def compute_machines(lexicon: dict) -> dict:
    """The machines meter: of the tracked patterns, how many the learner HEARS.
    `tested` keeps the denominator honest — a denominator full of never-tested
    rows reports ignorance as failure. `pct` stays keyed to `total`, so the
    headline cannot flatter itself by dividing by what happened to be tested."""
    pats = [r for r in lexicon.values() if is_pattern(r)]
    heard = [r for r in pats if is_heard(r)]
    tested = [r for r in pats if r.get("heard_on")]
    total = len(pats)
    return {"heard": len(heard), "tested": len(tested), "total": total,
            "pct": (len(heard) / total * 100) if total else 0.0}


def compute_ear(lexicon: dict) -> dict:
    """The ear meter: of the `direction: "catch"` rows (ear-only), how many have
    reached heard-solid recognition."""
    catch = [r for r in lexicon.values() if r.get("direction") == "catch"]
    solid = [r for r in catch if is_heard(r)]
    return {"caught": len(solid), "total": len(catch),
            "untouched": sum(1 for r in catch if not r.get("last_surfaced"))}


def compute_status(learner: dict | None = None) -> str:
    """The status line. THE HEADLINE IS THE EAR: production meters can read high
    while the learner hears little. No countdown: this line is one of the tutor's
    inputs, and a winnable countdown is a pressure device. What lands is the LEAN.

    `learner` is passed in by the writer, which runs this before the merged dict
    reaches disk; re-reading the file would compose the line one write behind."""
    lexicon = load_json(LEXICON_PATH) or {}
    mach = compute_machines(lexicon)
    ears = (f"Machines heard {mach['heard']} · ear-tested "
            f"{mach['tested']}/{mach['total']}")
    floor = compute_floor(lexicon)
    ph = timeline_mod.phase(timeline_mod.load(learner))
    lean = f" · working {ph['direction']} ({ph['phase']})" if ph else ""
    return (f"{ears} · viability floor {floor['cleared']}/{floor['total']} "
            f"fire cold ({floor['pct']:.0f}%){lean}")


def cold_fires_recent(days: int = 7) -> int:
    """COLD fires in the trailing window, across sessions and phone replies. Live
    from the logs, never stored."""
    cutoff = (local_today() - timedelta(days=days - 1)).isoformat()
    n = 0
    for s in load_json(SESSION_LOG_PATH) or []:
        if s.get("date", "") >= cutoff:
            n += len(s.get("cold", []))
    for k in load_json(KNOCK_LOG_PATH) or []:
        if k.get("reply_at", "") < cutoff:
            continue
        n += len(k.get("reply_fired_cold", []))
    return n


def trailing_pace(window: int = 7) -> str:
    """Cold/day actually happening. Python states the math; the tutor narrates."""
    return f"trailing {window}-day pace {cold_fires_recent(window) / window:.1f}/day"


def fires_today() -> int:
    """Words fired (cold or hinted) TODAY, across sessions and phone replies.
    Computed live, never stored (a stored counter is a meter that can lie)."""
    today = local_today().isoformat()
    n = 0
    for s in load_json(SESSION_LOG_PATH) or []:
        if s.get("date") == today:
            n += len(s.get("cold", [])) + len(s.get("hinted", []))
    for k in load_json(KNOCK_LOG_PATH) or []:
        if k.get("reply_at", "").startswith(today):
            n += len(k.get("reply_fired", []))
    return n


# Books this writer does NOT own: their writers persist them straight to disk, so
# the on-disk copy is fresher than any dict read before those writers ran.
FOREIGN_BOOKS = ("slip_closes", "slip_commissions")


def write_thin_learner(learner: dict):
    """MERGE-WRITE: read the file, overlay the keys the caller owns, recompute
    the derived status, leave everything else alone. A rebuild-from-a-key-list
    deletes any key it forgot, invisibly; merge-write lets an unknown key survive."""
    thin = load_json(LEARNER_PATH) or {}
    thin.update({k: v for k, v in learner.items() if k not in FOREIGN_BOOKS})
    # Shape floor for a fresh file: `timezone` feeds every clock-facing rule and
    # `quiet_until` is the transit bit the rails read.
    for key, default in (("learner", LEARNER), ("timezone", DEFAULT_TZ),
                         ("quiet_until", ""), ("last_debrief", ""),
                         ("next_engine", "")):
        thin.setdefault(key, default)
    for key in ("soak_order",) + FOREIGN_BOOKS:
        thin.setdefault(key, {})
    thin["status"] = compute_status(thin)
    save_json(LEARNER_PATH, thin)
    print(f"  Updated learner.json ({LEARNER_PATH.relative_to(BASE)})")


# --- Commands ----------------------------------------------------------------

def cmd_update(args):
    lexicon = load_json(LEXICON_PATH)
    learner = load_json(LEARNER_PATH)
    if lexicon is None or learner is None:
        print("Error: lexicon.json or learner.json missing. See SETUP.md.")
        sys.exit(1)

    today = local_today().isoformat()
    applied = {"cold": [], "hinted": [], "demoted": [], "recognized": []}  # for the session log

    # THE COMMISSION NOTICE — advisory, never a refusal. Commissioning nothing is
    # a first-class outcome: a gate that refuses the close turns a judgement into
    # a toll, and the close is the one command that must never become something
    # to dread. Surfacing the debt is the whole job. Runs BEFORE any write so the
    # close stays re-runnable.
    slip_rows = parse_slip_args(getattr(args, "slip", None) or [])
    declared = {canon_tag(t) for t in getattr(args, "slip_commissioned", None) or []}
    landed_now = {canon_tag(r.rpartition(":")[0])
                  for r in getattr(args, "slip_tested", None) or []
                  if r.strip().lower().endswith(":landed")}
    # A declared tag counts as covered only if an order will actually stand.
    order_stands = bool(args.soak_channel or args.soak_payload
                        or (learner.get("soak_order") or {}).get("channel"))
    sim = [{"tag": canon_tag(r["tag"]), "date": today} for r in slip_rows]
    owed = [p for p in slip_patterns(log=(load_json(SLIP_LOG_PATH) or []) + sim)
            if p["uncommissioned"] and p["tag"] not in landed_now
            and not (p["tag"] in declared and order_stands)]
    reason = getattr(args, "no_commission", None)
    if owed:
        print("  ⚠ live slip pattern(s) with no dose ever commissioned: "
              + ", ".join(f"{p['tag']} ({p['count']}× over {p['span_days']}d)"
                          for p in owed))
        print("     Commission one here if it has earned a dose:  --soak-payload … "
              "--soak-channel soak|episode|drill --slip-commissioned <tag>")
        if reason:
            print(f"     Closing without one, on the record: {reason}")

    # Every observation this close makes, folded onto the rows in one write below.
    events: list[dict] = []

    def ev(key, kind, **kw):
        return {"word": key, "channel": "session", "kind": kind,
                "source": f"session:{today}", **kw}

    def mint(word, gloss=""):
        """A row's STATIC half; the evidence half is the fold's."""
        lexicon[word] = {
            "gloss": gloss, "recognition": RECOGNITION_DEFAULT,
            "production": "none", "seen_in": [], "last_surfaced": None,
        }

    def key_for(word):
        """A logged token -> its row, or None, naming the nearest keys on a miss."""
        key = resolve(word, lexicon)
        if key is None:
            near = difflib.get_close_matches(word, list(lexicon), n=3, cutoff=0.6)
            hint = ", ".join(dict.fromkeys(near))
            print(f"  ! '{word}' resolves to no record{f' — nearest: {hint}' if hint else ''}. "
                  f"Re-log it as its lexicon key. Skipped.")
        return key

    def recognized(spec):
        """The tutor watched the learner recognize it — ONE observation, ONE rung."""
        word = spec.strip()
        key = resolve(word, lexicon)
        if key is None:
            if not is_canonical(word):
                print(f"  ! '{word}' can't be created — a new record needs its canonical {LANGUAGE} key. Skipped.")
                return
            mint(word)
            key = word
            print(f"  + New word '{word}' (gloss empty — fill in later)")
        events.append(ev(key, "tested", axis="recognition", result="right",
                         note="recognized in session"))
        applied["recognized"].append(key)
        print(f"  Recognized: {key} — one rung up on the ear")

    def demote_recognition(word):
        key = key_for(word)
        if key is None:
            return
        # A MISS IS EVIDENCE TOO — a tested failure must never read as untested.
        events.append(ev(key, "tested", axis="recognition", result="wrong",
                         note="failed cold recall"))
        applied["demoted"].append(key)
        print(f"  Recognition '{key}' — one rung down (tested, missed)")

    def set_production(word, level):
        key = key_for(word)
        if key is None:
            return
        events.append(ev(key, "tested", axis="production",
                         result=observations.FIRE_RESULT[level], note=f"fired {level}"))
        applied[level].append(key)
        print(f"  Produced {level.upper()}: {key}")

    def teach_word(spec):
        """A word taught in-session enters the lexicon at `untested`: a first
        contact is teaching, not a test, and production stays unset until it
        fires, so this can never inflate the floor. Accepts `WORD` or `WORD=gloss`."""
        word, _, gloss = spec.partition("=")
        word, gloss = word.strip(), gloss.strip()
        if not is_canonical(word):
            print(f"  ! '{word}' is not a canonical {LANGUAGE} key — teach it in its "
                  f"canonical form. Skipped.")
            return
        key = resolve(word, lexicon)
        if key is not None:
            if gloss and not lexicon[key].get("gloss"):
                lexicon[key]["gloss"] = gloss
            events.append(ev(key, "taught", note="re-taught; row already existed"))
            print(f"  Taught (already known): {key} — refreshed, recognition left "
                  f"at {lexicon[key].get('recognition', RECOGNITION_DEFAULT)}, "
                  f"gloss {lexicon[key].get('gloss') or 'STILL EMPTY'}")
            return
        mint(word, gloss)
        events.append(ev(word, "taught", note="first contact — row created untested"))
        print(f"  + Taught '{word}' → recognition untested"
              f"{', gloss: ' + gloss if gloss else ' (gloss empty — fill in later)'}")

    # Taught first, so a word taught and fired in one close resolves.
    for spec in args.teach:
        teach_word(spec)

    for w in args.recognized:
        recognized(w)
    for w in args.stuck_word:
        demote_recognition(w)

    for w in args.produced_cold:
        set_production(w, "cold")
    for w in args.produced_hinted:
        set_production(w, "hinted")

    if args.next_engine:
        learner["next_engine"] = args.next_engine
        print(f"  Next engine set: {args.next_engine}")

    # The transit bit. A DATE, not a boolean: a bare bit's failure is forgetting
    # to unset it, silently killing the channel. A date lapses on its own.
    if getattr(args, "quiet_until", None) is not None:
        # The clear path must be robust: a shell can eat a bare "".
        if args.quiet_until.strip().strip('"\'').lower() in ("", "off", "none", "clear"):
            args.quiet_until = ""
        if args.quiet_until:
            date.fromisoformat(args.quiet_until)   # raises on a typo, before it is stored
            learner["quiet_until"] = args.quiet_until
            print(f"  QUIET UNTIL {args.quiet_until} — knocks held; the rails skip "
                  f"before the LLM, so nothing logs and no silence reads as a fade.")
        else:
            learner["quiet_until"] = ""
            print("  Quiet window cleared — knocks resume on the next tick.")

    # Soak order — the intentional payload for the NEXT audio dose. A BRIEFING:
    # written per field, so setting one field never wipes another, and unnamed
    # keys survive.
    if (args.soak_payload or args.soak_seed or args.soak_focus
            or args.soak_channel or args.soak_form):
        order = dict(learner.get("soak_order") or {})
        if args.soak_payload:
            order["payload"] = [resolve(w, lexicon) or w
                                for w in canon_payload(args.soak_payload)]
        order.setdefault("payload", [])
        order["scene_seed"] = args.soak_seed or order.get("scene_seed", "")
        if args.soak_focus is not None:
            order["focus"] = args.soak_focus
        if args.soak_channel is not None:
            order["channel"] = args.soak_channel
        # FORM IS A CHOICE PER ORDER, NEVER A STANDING PREFERENCE. An inherited
        # channel is legible (every reader defaults it); an inherited form silently
        # disables the scene-spec gate forever. Clearing wrongly costs one rolled form.
        if args.soak_form is not None:
            order["form"] = args.soak_form
        else:
            order.pop("form", None)
        # A re-set order is a NEW order: drop any prior delivery stamp.
        order.pop("delivered", None)
        order["from"] = today
        learner["soak_order"] = order
        extra = "".join(f" · {k}: {order[k]}"
                        for k in ("channel", "form", "focus") if order.get(k))
        print(f"  Soak order set: {', '.join(order['payload']) or '(seed only)'}{extra}")

    if args.debrief:
        learner["last_debrief"] = args.debrief

    # The chat lane's half of the slip ledger: `last_debrief` is overwritten
    # every close, so a mistake recorded only there lasts as long as it is retyped.
    if slip_rows:
        channel = (learner.get("soak_order") or {}).get("channel", "")
        written = append_slips(slip_rows, lane="chat", modality="session",
                               dose_channel=channel)
        for row in written:
            print(f"  Slip logged: {row['tag']} — “{row['said']}” → “{row['want']}”")
        for p in slip_patterns():
            if p["pattern"] and p["live"] and p["tag"] in {r["tag"] for r in written}:
                print(f"  ⚠ {p['tag']} is now {p['count']}× over {p['span_days']}d "
                      f"— it is a pattern, not a one-off.")

    # Whether a deliberately tested slip healed.
    for tag, outcome, msg in record_slip_test(getattr(args, "slip_tested", None) or []):
        mark = {"landed": "✓", "missed": "✗", "bad": "!"}[outcome]
        print(f"  {mark} slip {tag}: {msg}")

    # Which debt the order just set pays — declared, never inferred. Reads the
    # order as mutated above, so set-and-declare works in one close.
    for tag, msg in record_slip_commission(getattr(args, "slip_commissioned", None) or [],
                                           learner.get("soak_order") or {}):
        mark = "✓" if msg.startswith("commissioned") else "!"
        print(f"  {mark} slip {tag}: {msg}")

    # THE ONE EVIDENCE WRITE: record, then fold onto the rows.
    if events:
        lexicon_view.observe(events, lexicon=lexicon)
    save_json(LEXICON_PATH, lexicon)
    write_thin_learner(learner)

    floor = compute_floor(lexicon)
    engines = compute_engines(lexicon)

    # Momentum log — ONE entry per session-day, merged by union: a second update
    # call in one close must not mint a session or double-count a fire.
    if any(applied.values()) or args.debrief:
        log = load_json(SESSION_LOG_PATH) or []
        entry = log[-1] if log and log[-1].get("date") == today else None
        if entry is None:
            entry = {"date": today, "cold": [], "hinted": [], "demoted": [], "note": ""}
            log.append(entry)
        for field, values in (("cold", applied["cold"]), ("hinted", applied["hinted"]),
                              ("demoted", applied["demoted"])):
            have = entry.setdefault(field, [])
            have.extend(v for v in values if v not in have)
        entry["floor_pct"] = round(floor["pct"], 1)
        entry["engines_pct"] = round(engines["pct"], 1)
        # A later debrief supersedes; an update without one never blanks it.
        if args.debrief:
            entry["note"] = args.debrief
        save_json(SESSION_LOG_PATH, log)
        print(f"  Logged session ({len(log)} total)")

    print(f"\nViability floor: {floor['cleared']}/{floor['total']} fire cold ({floor['pct']:.0f}%)")
    if engines["total"]:
        print(f"Engines online: {engines['online']}/{engines['total']} ({engines['pct']:.0f}%)")
    ear = compute_ear(lexicon)
    if ear["total"]:
        print(f"Ear-only: {ear['caught']}/{ear['total']} solid on recognition")
    print(f"Fired today: {fires_today()}")
    print("State updated.")


def cmd_add_pattern(args):
    """Seed a generative pattern record. Movement afterward reuses `update`, e.g.
    `--produced-cold '<key>'` the day a NOVEL instance is produced unaided."""
    lexicon = load_json(LEXICON_PATH)
    if lexicon is None:
        print("Error: lexicon.json missing. See SETUP.md.")
        sys.exit(1)
    if args.key in lexicon:
        print(f"  ! '{args.key}' already exists — not overwriting. Move its axes with `update`.")
        return
    today = local_today().isoformat()
    lexicon[args.key] = {
        "type": "pattern",
        "gloss": args.gloss,
        "recognition": RECOGNITION_DEFAULT,
        "production": "none",
        "seen_in": [],
        "last_surfaced": today,
    }
    save_json(LEXICON_PATH, lexicon)
    print(f"  + Pattern '{args.key}' seeded — {args.gloss} (untested until something tests it)")
    print(f"    Log a cold novel instance later with:  update --produced-cold '{args.key}'")


def cmd_add_word(args):
    """Seed a word/chunk record with its gloss — the proper birth of a lexicon
    entry. The canonical key is the record's whole handle; read forms are
    generated for display, never stored."""
    lexicon = load_json(LEXICON_PATH)
    if lexicon is None:
        print("Error: lexicon.json missing. See SETUP.md.")
        sys.exit(1)
    if not is_canonical(args.key):
        print(f"  ! '{args.key}' isn't a canonical {LANGUAGE} key — records must be canonical.")
        sys.exit(1)
    key = resolve(args.key, lexicon)
    if key is not None:
        rec = lexicon[key]
        if args.gloss and not rec.get("gloss"):
            rec["gloss"] = args.gloss
        save_json(LEXICON_PATH, lexicon)
        same = "" if key == args.key else f" as '{key}' (same key, spelled differently)"
        print(f"  '{args.key}' already exists{same} — merged the gloss, learning state untouched.")
        return
    lexicon[args.key] = {
        "gloss": args.gloss,
        "recognition": RECOGNITION_DEFAULT,
        "production": "none",
        "seen_in": [],
        "last_surfaced": local_today().isoformat(),
    }
    save_json(LEXICON_PATH, lexicon)
    print(f"  + '{args.key}' — {args.gloss} (untested until something tests it)")


def _arc_inputs():
    """The books the month is a fold over, read HERE and passed down: `month.py`
    reads neither the registry nor the sidecars itself."""
    episodes = load_json(EPISODES_PATH) or {}
    sidecars = {}
    for p in (BASE / "content" / "scripts").glob("tier2_mission*.tags.json"):
        if (m := re.match(r"tier2_mission(\d+)\.tags\.json$", p.name)):
            try:
                sidecars[int(m.group(1))] = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                sidecars[int(m.group(1))] = {}   # loud via `standing`'s `unrecorded`
    return episodes, sidecars


def cmd_month(args):
    """THE MONTH — open an arc, read where it stands, or record its finale test.
    `month.py` owns the folds; this is the writer.

    With no flags it is a READ. `--open` takes a NAME and nothing else: the
    episodes decide what the month contains. `--finale N` marks the episode the
    ear test runs on; `--line right|partial|wrong` records one key line — what
    the learner PRODUCED as the meaning, never whether they say they got it."""
    lexicon = load_json(LEXICON_PATH)
    if lexicon is None:
        print("Error: lexicon.json missing. See SETUP.md.")
        sys.exit(1)
    learner = load_json(LEARNER_PATH) or {}
    rec = month_mod.load(learner)
    episodes, sidecars = _arc_inputs()

    if args.line:
        if not rec.get("finale"):
            print("  No finale is marked. `sync_state.py month --finale <mission>` first.")
            return 1
        # The test is evidence like any other; the verdict is a fold over it.
        for result in args.line:
            observations.record(f"finale:M{rec['finale']}", "check", "tested",
                                axis="recognition", result=result,
                                source=f"finale:M{rec['finale']}")
        print(f"  Recorded {len(args.line)} key line(s) on finale M{rec['finale']}.")
        return _print_month(rec, lexicon, episodes, sidecars)

    if args.finale is not None:
        if not rec:
            print("  No month is open. `sync_state.py month --open --name \"...\"`")
            return 1
        rec["finale"] = args.finale
        learner[month_mod.KEY] = rec
        write_thin_learner(learner)
        print(f"  Finale set to M{args.finale}. Test it with --line right/partial/wrong.")
        return _print_month(rec, lexicon, episodes, sidecars)

    if not args.open:
        return _print_month(rec, lexicon, episodes, sidecars)
    if rec and not month_mod.is_over(rec) and not args.force:
        print(f"  An arc is still open (closes {rec.get('closes')}). Re-cutting "
              f"mid-flight is allowed and is the point — pass --force and say "
              f"why in the commit.")
        return 1
    if rec:
        unmet = month_mod.carry(rec, lexicon, episodes, sidecars)
        print(f"  Closing arc '{rec.get('name') or 'unnamed'}': {len(unmet)} "
              f"still open, re-offered with no privilege and no debt.")
    new = month_mod.opened_record(args.name or "", local_today())
    _print_month(new, lexicon, episodes, sidecars)
    if args.dry_run:
        print("  (dry run — nothing written)")
        return
    learner[month_mod.KEY] = new
    write_thin_learner(learner)
    print("  learner.json updated.")


def cmd_timeline(args):
    """THE TIMELINE — open one against the stake's dates, or read where the
    phases stand. `timeline.py` owns the schedule; this is the writer.

    With no dates it is a READ. Three dates are stored and nothing else, so a
    moved date re-phases everything in one command and strands nothing. Dates may
    be tentative; that is why the boundaries are derived."""
    learner = load_json(LEARNER_PATH) or {}
    rec = timeline_mod.load(learner)
    if not (args.event_from or args.event_to):
        return _print_timeline(rec)
    if rec and not timeline_mod.is_over(rec) and not args.force:
        print(f"  A timeline is already open ({timeline_mod.EVENT} {rec.get('event_from')} → "
              f"{rec.get('event_to')}). Re-anchoring mid-flight is allowed and "
              f"cheap — pass --force and say why in the commit.")
        return 1
    new = timeline_mod.opened_record(args.opened, args.event_from, args.event_to, rec)
    # Refuse an unschedulable record: every selector would fall back to a flat
    # sort and nothing would say why.
    bad = timeline_mod.problem(new)
    if bad:
        print(f"  Refused — {bad}")
        return 1
    _print_timeline(new)
    if args.dry_run:
        print("  (dry run — nothing written)")
        return
    learner[timeline_mod.KEY] = new
    write_thin_learner(learner)
    print("  learner.json updated.")


def _print_timeline(rec: dict):
    """ENGINEERING SURFACE: the learner reads the table; no count reaches the
    tutor's mouth."""
    print("  " + timeline_mod.status_line(rec).replace("\n", "\n  "))
    print("\n".join("  " + ln for ln in timeline_mod.table(rec)))


def _print_month(rec: dict, lexicon: dict, episodes: dict, sidecars: dict):
    """The standing — an engineering surface the learner steers by, never the
    tutor's mouth."""
    if not rec:
        print("  No arc is open. `sync_state.py month --open --name \"...\"`")
        return
    st = month_mod.standing(rec, lexicon, episodes, sidecars)
    v = month_mod.verdict(rec, load_json(observations.OBSERVATIONS_PATH) or [])
    over = " ⏳ OVER — open the next one" if month_mod.is_over(rec) else ""
    print(f"  ARC: {rec.get('name') or 'unnamed'}  "
          f"({rec.get('opened')} → {rec.get('closes')}){over}")
    print(f"  {st['closed']}/{st['total']} of what it taught has closed "
          f"({st['ear']} on the ear) · {len(st['missions'])} episode(s)")
    # A month with no finale cannot be won, and its absence is loud.
    if not rec.get("finale"):
        print("  ⚠ no finale marked — this arc cannot be won. `--finale <mission>`")
    elif not v["run"]:
        print(f"  FINALE M{rec['finale']}: not yet tested (blind listen, then --line …)")
    else:
        print(f"  FINALE M{rec['finale']}: {v['score']:g}/{v['of']} key lines"
              + ("  ✅ WON" if v["won"] else ""))
    if st["missing"]:
        print(f"  ⚠ {len(st['missing'])} member(s) NOT IN THE LEXICON and can "
              f"never close: {', '.join(st['missing'])}")
    if st["unrecorded"]:
        print(f"  ⚠ episode(s) with no sidecar — what they taught is invisible "
              f"to this meter: {st['unrecorded']}")


def cmd_seed(args):
    """Idempotently load a curated set into the lexicon — setup's intake, or any
    curated list the learner vets. The file is CONTENT; this lands it.

    Each entry: {"word", "gloss", "type": "chunk"|"frame", "register"?,
    "direction"?: "fire"|"catch", "pairs_with"?}. A frame becomes a `pattern`; a
    "catch" row is ear-only; "pairs_with" names the chunk that answers it and must
    resolve inside the same file, or the whole seed refuses before any write — a
    split pair is the failure the field exists to prevent.

    Static fields only: a `recognition` in the file is ignored, because a curated
    file cannot observe and a claim does not vote. Seeded rows are `untested`; the
    Receptive Check is what tests them."""
    path = Path(args.file)
    if not path.is_absolute():
        path = BASE / path
    entries = load_json(path)
    if entries is None:
        print(f"Error: seed file not found: {path}")
        sys.exit(1)
    lexicon = load_json(LEXICON_PATH)
    if lexicon is None:
        print("Error: lexicon.json missing. See SETUP.md.")
        sys.exit(1)
    in_file = {e.get("word") for e in entries}
    split = [(e.get("word"), e.get("pairs_with")) for e in entries
             if e.get("pairs_with") and e["pairs_with"] not in in_file]
    if split:
        for word, pair in split:
            print(f"  ✗ '{word}' pairs_with '{pair}', which is not in this file — split pair.")
        print("  Error: seed refused, nothing written. A pair must resolve inside the file.")
        sys.exit(1)
    created = updated = 0
    for e in entries:
        word = e.get("word")
        if not word:
            print(f"  ! seed entry missing 'word' — skipped: {e}")
            continue
        pair = e.get("pairs_with")
        lex_type = "pattern" if e.get("type") == "frame" else e.get("type", "chunk")
        # Frames use the `frame:...` key convention, exempt from the canonical check.
        if lex_type != "pattern" and not is_canonical(word):
            print(f"  ! '{word}' isn't a canonical {LANGUAGE} key — chunks must be canonical. Skipped.")
            continue
        key = resolve(word, lexicon) if lex_type != "pattern" else (word if word in lexicon else None)
        if key is not None:
            if key != word:
                print(f"  ~ '{word}' is the existing key '{key}', spelled differently — updated that row.")
            rec = lexicon[key]
            rec["direction"] = e.get("direction", "fire")
            if e.get("register"):
                rec["register"] = e["register"]
            rec.setdefault("type", lex_type)
            if pair:
                rec["pairs_with"] = pair
            else:
                rec.pop("pairs_with", None)  # the file is the source of truth
            if e.get("gloss"):
                rec["gloss"] = e["gloss"]  # the curated file's gloss wins
            updated += 1
        else:
            lexicon[word] = {
                "type": lex_type,
                "gloss": e.get("gloss", ""),
                "recognition": RECOGNITION_DEFAULT,
                "production": "none",
                "seen_in": [],
                "last_surfaced": None,
                "direction": e.get("direction", "fire"),
                **({"register": e["register"]} if e.get("register") else {}),
                **({"pairs_with": pair} if pair else {}),
            }
            created += 1
    save_json(LEXICON_PATH, lexicon)
    ear = compute_ear(lexicon)
    print(f"  Seeded {path.name}: +{created} new, {updated} updated.")
    floor = compute_floor(lexicon)
    print(f"  Floor now: {floor['cleared']}/{floor['total']} fire cold ({floor['pct']:.0f}%)"
          + (f" · ear-only {ear['caught']}/{ear['total']} solid" if ear["total"] else ""))


# The knock tap: "got it" — the knock landed, no learning write. A second tap on
# the same knock is a no-op.
KNOCK_RESPONSES = {"ack"}


def cmd_knock_response(args):
    """Record the learner's tap against its knock. Idempotent."""
    from datetime import datetime
    response = args.response.strip().lower()
    if response not in KNOCK_RESPONSES:
        print(f"  Unknown knock response '{response}' (expected one of {sorted(KNOCK_RESPONSES)}). Skipping.")
        return
    log = load_json(KNOCK_LOG_PATH) or []
    # Only FIRED reaches carry a notification to tap.
    fired = [k for k in log if k.get("acted", True)]
    if not fired:
        print("No fired knocks in knock_log.json to respond to.")
        sys.exit(1)
    # Notifications stack: a tap carries its knock's timestamp as knock_id, so an
    # old notification acks the right entry. No id → last fired.
    kid = (getattr(args, "knock_id", "") or "").strip()
    last = next((k for k in reversed(fired) if k.get("timestamp") == kid), None) if kid else None
    if last is None:
        if kid:
            print(f"  ⚠ knock_id {kid!r} not in the log — marking the most recent knock")
        last = fired[-1]
    if last.get("response") is not None:
        print(f"  Knock ({last['date']}) already '{last['response']}'; '{response}' adds nothing. Skipping.")
        return

    last["response"] = response
    last["response_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    save_json(KNOCK_LOG_PATH, log)
    print(f"  Knock {last['date']} marked '{response}'")

    if getattr(args, "commit", False):
        # Through `publish`, so the union net and the derived re-render apply.
        commit_and_push(*publish([KNOCK_LOG_PATH], f"Knock response: {response}", feed=False))


# A versioned re-render (`tier2_mission74_v2`) is still mission 74, so no `$`.
MISSION_STEM_RE = re.compile(r"^tier2_mission(\d+)")

# THE THREE BUTTONS. A tap reports a FACT, never a mood. Quality moves to the
# PLAY COUNT, which costs no tap.
#   attends -> the learner was there for the whole tape, so pending Teach Beats
#              open. `stopped early` cannot say WHERE, so it opens nothing.
VERDICTS = {
    "finished": ("finished it", True, ""),
    "stopped early": ("stopped early", False, ""),
    "lost the thread": ("lost the thread", True,
                        " ← COVERAGE BROKE HERE: the learner stayed with the tape and "
                        "could not follow it. This is the 95%-known-words rule "
                        "failing on a specific artifact."),
}


def cmd_rate_episode(args):
    """Record a listen from the phone into the feedback ledger.

    Every bad input is LOUD (exit non-zero): this lane is unattended, and a
    mis-filed rating steers the diagnosis pass while looking like a real one.
    Resolves against the FEED by the exact title the picker offered — the title
    the podcast app shows — and refuses rather than guesses.

    A RATING IS A LISTEN and the ATTENDANCE SIGNAL: `kind="attended"` on the
    words the artifact aired discharges their pending Teach Beats (and never
    mints one). Words come from `episodes.json` by mission number for a numbered
    mission, else from the artifact registry; none recorded is said out loud."""
    raw = (getattr(args, "verdict", None) or "").strip().lower()
    verdict = next((v for v in VERDICTS if raw.startswith(v)), None)
    if verdict is None:
        print(f"  ! Unknown verdict {raw!r}. The picker offers exactly: "
              f"{', '.join(sorted(VERDICTS))}.")
        sys.exit(1)
    label, attends, diagnostic = VERDICTS[verdict]
    wanted = (args.episode or "").strip()
    item = next((d for d in feed_items() if d["title"] == wanted), None)
    if item is None:
        print(f"  ! {wanted!r} is not in the feed — nothing to rate. "
              f"Pick a row from progress/recent_audio.txt.")
        sys.exit(1)
    note = f"[audio rating] [{item['format']}] {item['title']} — {label}.{diagnostic}"
    log = load_json(FEEDBACK_LOG_PATH) or []
    # The play row freezes its own minutes, so the dose meter is a sum, never a join.
    log.append({"date": local_today().isoformat(), "note": note,
                "id": item["id"], "minutes": item.get("minutes", 0.0)})
    save_json(FEEDBACK_LOG_PATH, log)
    print(f"  Logged feedback ({len(log)} total): {note}")
    mission = MISSION_STEM_RE.match(str(item["id"]))
    ep = (load_json(EPISODES_PATH) or {}).get(mission.group(1), {}) if mission else {}
    words = ep.get("words") or audio_titles.words_for(item["id"])
    if not words:
        print(f"   ⚠ no words recorded for {item['id']} — the play is logged, "
              f"but it can open no Teach Beat")
    exposed = lexicon_view.expose(words, item["format"].split("/")[0],
                                  source=f"rating:{item['id']}",
                                  kind="attended" if attends else "exposed")
    if getattr(args, "commit", False):
        commit_and_push(*publish([FEEDBACK_LOG_PATH, LEXICON_PATH if exposed else None],
                                 f"Audio listen: {item['id']} {label}", feed=False))


def cmd_check(args):
    """CLI facade; recognition recording lives in receptive_check."""
    import receptive_check
    code, changed = receptive_check.run(args)
    if changed:
        write_thin_learner(load_json(LEARNER_PATH) or {})
    return code


def cmd_feedback(args):
    """Capture (append a dated note) or read (list recent) the feedback ledger,
    which feeds the Diagnosis pass: fixes come from REPRODUCED patterns, never
    one-offs — capture is cheap, change is not."""
    log = load_json(FEEDBACK_LOG_PATH) or []
    if args.note:
        log.append({"date": local_today().isoformat(), "note": args.note})
        save_json(FEEDBACK_LOG_PATH, log)
        print(f"  Logged feedback ({len(log)} total): {args.note}")
        return
    if not log:
        print("No feedback logged yet.")
        return
    print(f"FEEDBACK LEDGER ({len(log)} entries) — diagnose patterns, not one-offs:")
    for e in log[-args.n:]:
        print(f"  {e['date']}  {e['note']}")


def main():
    parser = argparse.ArgumentParser(description=f"{LANGUAGE} tutor state management")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="Show current state")

    up = sub.add_parser("update", help="Update state after a session")
    up.add_argument("--soak-payload", type=str, action="append", default=[],
                    help="Word(s) to soak in the next audio dose (the Director's payload)")
    up.add_argument("--soak-seed", type=str, default=None,
                    help="One-line scene seed for the next audio soak")
    up.add_argument("--soak-focus", type=str, default=None,
                    help="What the next dose PERMUTES, free text (an ending over two "
                         "verbs) — a carousel brief, not a word list")
    up.add_argument("--soak-channel", type=str, default=None,
                    choices=list(DOSE_CHANNELS),
                    help="Which lane renders the order (default: episode). Capacity "
                         "routes this, never the curriculum — protocol/audio_channels.md")
    # Deferred: suggest_targets imports THIS module.
    from suggest_targets import ALL_FORMS, COMMISSIONED_FORMS
    up.add_argument("--soak-form", type=str, default=None, choices=ALL_FORMS,
                    help=f"Commission an episode FORM instead of letting the divergence "
                         f"gate roll one. {'/'.join(COMMISSIONED_FORMS)} can ONLY arrive "
                         f"this way; the rest are normally spec-rotated and this pins them.")
    up.add_argument("--teach", type=str, action="append", default=[],
                    metavar="WORD[=GLOSS]",
                    help="Word(s) TAUGHT this session — creates the lexicon record at "
                         "`untested` recognition, production unset. The canonical key "
                         "is the whole handle.")
    up.add_argument("--recognized", dest="recognized",
                    type=str, action="append", default=[], metavar="WORD",
                    help="Word(s) RECOGNIZED unaided this session — one observation, "
                         "one rung up on the ear. A key the lexicon lacks is minted from it.")
    up.add_argument("--stuck-word", type=str, action="append", default=[],
                    help="Word(s) that failed cold recall — demotes recognition one level")
    up.add_argument("--produced-cold", type=str, action="append", default=[],
                    help="Word(s) produced COLD — no hint (production axis)")
    up.add_argument("--produced-hinted", type=str, action="append", default=[],
                    help="Word(s) produced only after a hint (production axis)")
    up.add_argument("--debrief", type=str, default=None,
                    help="Running 'story so far' — rewrite cumulatively (carry what matters, prune what resolved); the tutor's persistent narrative memory, not a one-line log")
    up.add_argument("--next-engine", type=str, default=None,
                    help="Frame key to set as the engine to unlock next (e.g. 'frame:polite-request')")
    up.add_argument("--quiet-until", type=str, default=None, metavar="YYYY-MM-DD|''",
                    help="TRANSIT BIT: hold every knock through this local date "
                         "(the rails skip before the LLM, so nothing is logged and "
                         "no silence reads as a fade). Pass '' to clear it and resume.")
    up.add_argument("--slip", type=str, action="append", default=[],
                    help="A mistake worth remembering: 'tag|what was said|what it should be|the pattern in one clause'. "
                         "Repeatable. Appends to the slip ledger — never overwrites. The knock judge writes these "
                         "itself; this is the chat lane's half.")
    up.add_argument("--slip-tested", type=str, action="append", default=[], metavar="TAG:landed|missed",
                    help="Report an UNVERIFIED slip you deliberately tested this session. 'landed' closes it as of "
                         "today (a later miss revives it); 'missed' logs the failure and keeps it live. Only for a "
                         "slip actually produced unaided — it asserts an observation, not a verdict.")
    up.add_argument("--slip-commissioned", type=str, action="append", default=[], metavar="TAG",
                    help="Declare that the soak order set in THIS call pays off that slip tag. Repeatable. "
                         "Without it a dose cannot clear NEVER COMMISSIONED. It says a debt was ordered, "
                         "never that it landed (that is --slip-tested).")
    up.add_argument("--no-commission", type=str, default=None, metavar="REASON", dest="no_commission",
                    help="Put on the record why this close commissions nothing despite a live "
                         "uncommissioned slip pattern. The notice is advisory; the close always lands.")

    ap = sub.add_parser("add-pattern", help="Seed a generative pattern record (tracked as an Engine)")
    ap.add_argument("key", help="Canonical key, e.g. 'frame:present-future-toggle'")
    ap.add_argument("--gloss", required=True,
                    help="Human description of the engine, e.g. 'the now vs later ending on any verb'")

    aw = sub.add_parser("add-word", help="Seed a word/chunk record (gloss) — a word without a record can't be resolved or scored")
    aw.add_argument("key", help=f"The canonical {LANGUAGE} key")
    aw.add_argument("--gloss", required=True, help="Gloss in the learner's language")

    sd = sub.add_parser("seed", help="Load a curated set (chunks/frames) into the lexicon — static fields only, rows untested")
    sd.add_argument("file", help="Path to the set's JSON, absolute or repo-relative")

    kr = sub.add_parser("knock-response", help="Log the learner's tap against its knock (by --knock-id; most recent if absent)")
    kr.add_argument("response", help="The tap value: 'ack' (got it)")
    kr.add_argument("--knock-id", default="", dest="knock_id",
                    help="The knock's log timestamp (from the notification payload); empty → most recent")
    kr.add_argument("--commit", action="store_true",
                    help="Land the tap via commit_and_push (union merge + derived re-render)")

    ck = sub.add_parser("check", help="The Receptive Check — draw a never-tested sample, or record its answers")
    ck.add_argument("--draw", type=int, default=0, metavar="N",
                    help="Print N never-tested rows, deterministic for the month; writes nothing")
    ck.add_argument("--heard", action="append", default=[], metavar="WORD:right|wrong|partial",
                    help="Record one item answered BY EAR (repeatable) — stamps the ear, re-bases the cue")
    ck.add_argument("--read", action="append", default=[], metavar="WORD:right|wrong|partial",
                    help="Record one item worked ON THE PAGE (repeatable) — moves the rung, never the ear")
    ck.add_argument("--session", action="store_true",
                    help="Record unaided lesson recognition, without resetting the monthly check cue")
    ck.add_argument("--source", default="", help="Clip path/URL or text reference; required with --session")
    ck.add_argument("--note", default="", help="Actual reply and support supplied; required with --session")

    fb = sub.add_parser("feedback", help="Append a feedback note (capture), or list recent (diagnosis)")
    fb.add_argument("note", nargs="?", default=None, help="The feedback to log; omit to list recent")
    fb.add_argument("-n", type=int, default=20, help="How many recent entries to show when listing")

    re_ = sub.add_parser("rate-episode", help="Record a listen from the phone (feed title + one of the three buttons)")
    re_.add_argument("--episode", required=True, help="Feed title, exactly as the picker offered it")
    re_.add_argument("--verdict", required=True,
                     help="finished | stopped early | lost the thread")
    re_.add_argument("--commit", action="store_true", help="Commit and push the ledger (CI lane)")

    tl = sub.add_parser("timeline", help="The phase schedule — read it, or anchor it to the stake's dates")
    tl.add_argument("--from", dest="event_from", default="", metavar="DATE", help="First day of the event")
    tl.add_argument("--to", dest="event_to", default="", metavar="DATE", help="Last day of the event")
    tl.add_argument("--opened", default="", metavar="DATE", help="Day the first phase starts (default today)")
    tl.add_argument("--force", action="store_true", help="Re-anchor while a timeline is still open")
    tl.add_argument("--dry-run", action="store_true", help="Print the schedule and write nothing")

    mo = sub.add_parser("month", help="The arc — read the standing, --open a new one, or record its finale")
    mo.add_argument("--open", action="store_true", help="Open a new arc of the world's life")
    mo.add_argument("--name", default="", help="What is happening in the world — never a word count")
    mo.add_argument("--finale", type=int, default=None, metavar="N", help="Mark the arc's finale episode")
    mo.add_argument("--line", action="append", default=[], choices=["right", "partial", "wrong"],
                    help="Record ONE key line of the finale ear test (repeatable)")
    mo.add_argument("--force", action="store_true", help="Re-cut while an arc is still open")
    mo.add_argument("--dry-run", action="store_true", help="Print the arc and write nothing")

    sl = sub.add_parser("slips", help="Read the slip ledger (what keeps going wrong), or report a test")
    sl.add_argument("-n", type=int, default=15, help="How many patterns to show")
    sl.add_argument("--tested", action="append", default=[], metavar="TAG:landed|missed",
                    help="Report the outcome of putting a slip to the test. 'landed' closes it AS OF TODAY "
                         "(a later miss revives it, history intact); 'missed' logs the failure and keeps it live. "
                         "This asserts an observation — fired right unaided — not a verdict.")

    args = parser.parse_args()
    if args.command == "update":
        cmd_update(args)
    elif args.command == "status":
        # Deferred: session_brief sits ABOVE this module and imports it.
        from session_brief import cmd_status
        cmd_status(args)
    elif args.command == "add-pattern":
        cmd_add_pattern(args)
    elif args.command == "add-word":
        cmd_add_word(args)
    elif args.command == "seed":
        cmd_seed(args)
    elif args.command == "check":
        return cmd_check(args)
    elif args.command == "feedback":
        cmd_feedback(args)
    elif args.command == "rate-episode":
        cmd_rate_episode(args)
    elif args.command == "timeline":
        return cmd_timeline(args)
    elif args.command == "month":
        return cmd_month(args)
    elif args.command == "slips":
        cmd_slips(args)
    elif args.command == "knock-response":
        cmd_knock_response(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    # A subcommand that reports an unresolvable row returns non-zero; without
    # this the loud absence is invisible to CI.
    sys.exit(main() or 0)
