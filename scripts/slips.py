#!/usr/bin/env python3
"""The slip ledger: what the learner keeps getting wrong, and what to do about it.

A slip is a specific observed mistake (a wrong ending, the wrong verb) logged the
moment it happens. Once is noise; twice is a pattern, and a live pattern is the
primary signal for what to teach next. The ledger never forgets: a tag with no
recurrence RETIRES rather than disappearing, and a retired tag never confirmed
landed comes back as UNVERIFIED — the surface forgets, then asks again.

Imports `state_io` and `dose_evidence` only. `sync_state` imports from here.
"""

import re
from datetime import date, datetime

from dose_evidence import (attended_events, dose_note, dose_summary,
                           escalation_note, judge_dose)
from state_io import (LEARNER_PATH, LEXICON_PATH, LOCAL_TZ, SLIP_LOG_PATH,
                      load_json, local_today, resolve, save_json)

# After this many quiet days a tag retires: not "fixed", just no longer evidence.
# Matches `generate_callbacks.INTERVAL_DAYS["cold"]`, so patterns and cold words
# age on one recheck rhythm.
SLIP_RETIRE_DAYS = 21
# One is noise, two is signal — the same bar `diagnosis.md` sets for the system's bugs.
SLIP_PATTERN_COUNT = 2
_TAG_RE = re.compile(r"[^a-z0-9]+")


def canon_tag(s: str) -> str:
    """A slip tag as a stable slug. The judge names the pattern; Python only
    makes names comparable. Deliberately not a closed vocabulary: the ledger
    exists to show patterns nobody named in advance, and drift is visible and
    cheap to merge where a mislabelling enum is not."""
    return _TAG_RE.sub("-", (s or "").strip().casefold()).strip("-")


def parse_slip_args(raw_specs: list[str]) -> list[dict]:
    """CLI `--slip 'tag|said|want|note'` specs → ledger rows. Shared by the close
    and the commission gate, which must judge the rows the close will append."""
    rows = []
    for raw in raw_specs:
        parts = [p.strip() for p in raw.split("|")]
        if not parts or not parts[0]:
            print(f"  ! --slip {raw!r} has no tag before the first '|' — skipped")
            continue
        parts += [""] * (4 - len(parts))
        rows.append({"tag": parts[0], "said": parts[1],
                     "want": parts[2], "note": parts[3]})
    return rows


def append_slips(entries: list[dict], lane: str, modality: str = "",
                 dose_channel: str = "", when: str = "") -> list[dict]:
    """Append structured errors. THE LEDGER IS APPEND-ONLY, and crosses lanes:
    a mistake made in chat, a knock reply and a session is one record, so a
    correction repeated three times is something a mechanism can notice.

    `dose_channel` is the standing order's lane when the slip happened
    (provenance only). `when` is the date the mistake was MADE, not recorded: a
    late-evening reply judged on a UTC runner would otherwise file under tomorrow."""
    if not entries:
        return []
    log = load_json(SLIP_LOG_PATH) or []
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    today = when or datetime.now(LOCAL_TZ).date().isoformat()
    # `want` resolves to a key once, here; an ending-shaped slip often has none.
    lexicon = load_json(LEXICON_PATH) or {}
    written = []
    for e in entries:
        tag = canon_tag(e.get("tag", ""))
        if not tag:
            continue
        if not e.get("word"):
            e = dict(e, word=resolve(e.get("want", ""), lexicon) or "")
        row = {
            "at": now,
            "date": today,
            "lane": lane,
            "modality": modality,
            "tag": tag,
            "said": (e.get("said") or "").strip(),
            "want": (e.get("want") or "").strip(),
            "note": (e.get("note") or "").strip(),
            "word": (e.get("word") or "").strip(),
        }
        if dose_channel:
            row["dose_channel"] = dose_channel
        log.append(row)
        written.append(row)
    if written:
        save_json(SLIP_LOG_PATH, log)
    return written


def slip_closes() -> dict[str, str]:
    """tag → the date it was last observed LANDING. Dated, never a bare tag: a
    date can be voided by a later failure, a name cannot."""
    raw = (load_json(LEARNER_PATH) or {}).get("slip_closes") or {}
    return {canon_tag(k): v for k, v in raw.items() if v}


def slip_commissions() -> dict[str, list[dict]]:
    """tag → the doses built to pay that debt: [{channel, at, payload}, …]. A
    list, because trying a SECOND format is the event escalation needs to see."""
    raw = (load_json(LEARNER_PATH) or {}).get("slip_commissions") or {}
    return {canon_tag(k): list(v) for k, v in raw.items() if v}


def record_slip_commission(tags: list[str], order: dict,
                           today: str = "") -> list[tuple[str, str]]:
    """Declare that the standing soak order pays off these slip tags. The seam
    that does the work declares it: payload words and slip tags are different
    vocabularies, so guessing the link from overlap would silently miss exactly
    the ending-shaped slips that hang off no single word."""
    today = today or datetime.now(LOCAL_TZ).date().isoformat()
    if not tags:
        return []
    channel = (order or {}).get("channel") or ""
    payload = list((order or {}).get("payload") or [])
    learner = load_json(LEARNER_PATH) or {}
    book = dict(learner.get("slip_commissions") or {})
    out = []
    known = {p["tag"] for p in slip_patterns()}
    for raw in tags:
        tag = canon_tag(raw)
        if not tag:
            out.append((raw, "expected a slip tag"))
            continue
        if not channel:
            out.append((tag, "no soak order is standing — set one in this same call"))
            continue
        # A tag with no history is a typo; booking it would mark a phantom debt paid.
        if tag not in known:
            out.append((tag, "no slip logged under that tag — check the spelling"))
            continue
        entries = list(book.get(tag) or [])
        entries.append({"channel": channel, "at": today, "payload": payload})
        book[tag] = entries
        out.append((tag, f"commissioned via the {channel} lane"))
    learner["slip_commissions"] = book
    save_json(LEARNER_PATH, learner)
    return out


def record_slip_test(results: list[str], today: str = "") -> list[tuple[str, str, str]]:
    """Log the outcome of testing a retired slip: 'tag:landed' or 'tag:missed'.
    A slip closes by firing right, unaided, later — never by being corrected.
    landed → a dated close. missed → a slip row, because a failed test IS a
    recurrence. This records an OBSERVATION the tutor reports, not a verdict."""
    today = today or datetime.now(LOCAL_TZ).date().isoformat()
    learner = load_json(LEARNER_PATH) or {}
    closes = dict(learner.get("slip_closes") or {})
    out, missed = [], []
    for raw in results:
        tag, _, outcome = (raw or "").rpartition(":")
        tag, outcome = canon_tag(tag), outcome.strip().lower()
        if not tag or outcome not in ("landed", "missed"):
            out.append((raw, "bad", "expected 'tag:landed' or 'tag:missed'"))
            continue
        if outcome == "landed":
            closes[tag] = today
            out.append((tag, "landed", f"closed as of {today} — revives if it comes back"))
        else:
            closes.pop(tag, None)
            missed.append({"tag": tag, "said": "", "want": "",
                           "note": "tested and missed — still not landed"})
            out.append((tag, "missed", "still live; the failed test is on the ledger"))
    if missed:
        append_slips(missed, lane="chat", modality="test", when=today)
    learner["slip_closes"] = closes
    save_json(LEARNER_PATH, learner)
    return out


def slip_patterns(log: list | None = None, today=None) -> list[dict]:
    """Aggregate the ledger by tag, newest recurrence first. The MENU, not the
    choice: Python counts and groups, the tutor decides what it means.

    One row per tag: how often, over how long, in which lanes, through which
    declared doses, and whether it is live, unverified, uncommissioned or due
    to ESCALATE (a dose was HEARD and the learner slipped anyway)."""
    log = load_json(SLIP_LOG_PATH) if log is None else log
    log = log or []
    today = today or local_today()
    closes = slip_closes()
    commissions = slip_commissions()
    attended = attended_events()
    by_tag: dict[str, dict] = {}
    for row in log:
        tag = row.get("tag")
        if not tag:
            continue
        agg = by_tag.setdefault(tag, {
            "tag": tag, "count": 0, "first": row.get("date"), "last": row.get("date"),
            "lanes": [], "channels": [], "words": [], "examples": [], "notes": [],
            "dosed_rows": [], "days": [],
        })
        agg["days"].append(row.get("date") or "")
        if row.get("dose_channel"):
            agg["dosed_rows"].append((row.get("date") or "", row["dose_channel"],
                                      row.get("lane") or ""))
        agg["count"] += 1
        # MIN/MAX, not first/last seen: append-only is not date-ordered (`when`
        # backdates), and a last-seen `last` would retire a live slip early.
        if row.get("date") and row["date"] > (agg["last"] or ""):
            agg["last"] = row["date"]
        if row.get("date") and row["date"] < (agg["first"] or row["date"]):
            agg["first"] = row["date"]
        # `channels` is filled below from DECLARED commissions only. A row's
        # `dose_channel` is whatever order stood for some other payload; feeding
        # it in would disarm both the uncommissioned and the escalate gates.
        for key, field in (("lanes", "lane"), ("words", "word")):
            v = row.get(field)
            if v and v not in agg[key]:
                agg[key].append(v)
        if row.get("said") or row.get("want"):
            agg["examples"].append((row.get("date"), row.get("said", ""), row.get("want", "")))
        if row.get("note") and row["note"] not in agg["notes"]:
            agg["notes"].append(row["note"])

    out = []
    for agg in by_tag.values():
        try:
            days_quiet = (today - date.fromisoformat(agg["last"])).days
        except (TypeError, ValueError):
            days_quiet = 0
        agg["days_quiet"] = days_quiet
        agg["span_days"] = _span_days(agg["first"], agg["last"])
        # A close is a claim about its date; a later slip voids it and the tag
        # is live again with its history — the most informative event there is.
        closed_on = closes.get(agg["tag"], "")
        agg["closed_on"] = closed_on if closed_on and closed_on >= (agg["last"] or "") else ""
        agg["closed"] = bool(agg["closed_on"])
        agg["reopened"] = bool(closed_on) and not agg["closed"]
        agg["live"] = not agg["closed"] and days_quiet <= SLIP_RETIRE_DAYS
        agg["pattern"] = agg["count"] >= SLIP_PATTERN_COUNT
        # Quiet but never confirmed: learned, or never asked — the ledger cannot
        # tell which, so it asks for a CHECK rather than vanishing.
        agg["unverified"] = (agg["pattern"] and not agg["live"]
                             and not agg["closed"])
        agg["commissions"] = sorted(commissions.get(agg["tag"], []),
                                    key=lambda c: c.get("at") or "")
        for c in agg["commissions"]:
            if c.get("channel") and c["channel"] not in agg["channels"]:
                agg["channels"].append(c["channel"])
        # NEVER COMMISSIONED: corrected in passing, nothing ever built — owed a dose.
        agg["uncommissioned"] = agg["pattern"] and agg["live"] and not agg["channels"]
        (agg["dose_state"], agg["heard_at"],
         agg["slipped_after_heard"]) = judge_dose(agg["commissions"], agg["days"], attended)
        # ESCALATE: a declared dose was heard and the learner slipped on a later day.
        agg["escalate"] = (agg["pattern"] and agg["live"]
                           and bool(agg["channels"])
                           and agg["slipped_after_heard"])
        out.append(agg)
    out.sort(key=lambda a: (a["live"] and a["pattern"], a["unverified"],
                            a["last"] or "", a["count"]), reverse=True)
    return out


def _span_days(first: str, last: str) -> int:
    try:
        return (date.fromisoformat(last) - date.fromisoformat(first)).days
    except (TypeError, ValueError):
        return 0


def format_slip_block(patterns: list[dict], limit: int = 6) -> list[str]:
    """Repeated slips for a reader surface — one renderer for status, the knock
    context and the ticket. LIVE earns a dose; UNVERIFIED earns a test."""
    live = [p for p in patterns if p["live"] and p["pattern"]]
    unverified = [p for p in patterns if p["unverified"]]
    if not live and not unverified:
        return []
    lines = []
    if not live:
        lines.append("No live slips — nothing repeated recently.")
    else:
        lines += ["REPEATED SLIPS — mistakes the learner has made more than once, newest first.",
                  "  These name what to TEACH next, not what to quiz: an explanation, a tape, or the",
                  "  learner volunteering it is what closes one — never being asked again.",
                  "  Explain the machine; the probe comes later, unannounced — a slip is still closed by firing right, unaided, and a recast never closes it."]
        if summary := dose_summary(live):
            lines.append("  " + summary)
    for p in live[:limit]:
        when = (f"{p['count']}× over {p['span_days']}d" if p["span_days"]
                else f"{p['count']}×")
        quiet = f", last {p['days_quiet']}d ago" if p["days_quiet"] else ", today"
        lines.append(f"  ⚠ {p['tag']} — {when}{quiet}")
        for d, said, want in p["examples"][-2:]:
            lines.append(f"      {d}: said “{said}” → wanted “{want}”")
        if p["notes"]:
            lines.append(f"      pattern: {p['notes'][-1]}")
        if p.get("commissions"):
            c = p["commissions"][-1]
            lines.append(f"      ✓ dose commissioned {c.get('at','')} "
                         f"({c.get('channel','?')} lane"
                         + (f": {', '.join(c['payload'])}" if c.get("payload") else "")
                         + ") — don't re-order it; test whether it landed.")
        if p["uncommissioned"]:
            # The instruction names the exact flag, because the flag is the only
            # thing that turns this warning off and prose gets walked past.
            lines.append("      ⚠ NEVER COMMISSIONED — corrected in passing every "
                         "time and no dose was ever built for it. This one is owed "
                         "a dose, not another recast.")
            lines.append(f"        → order it, then DECLARE it in the same close: "
                         f"--soak-payload … --soak-channel <lane> "
                         f"--slip-commissioned {p['tag']}")
        elif p["escalate"]:
            lines.append(f"      ⚠ ESCALATE — a dose was heard ({p['heard_at'][:10]}) and "
                         f"the learner slipped again: {escalation_note(p['channels'])}. "
                         f"audio_channels.md: change the format, never loop harder.")
        elif note := dose_note(p):
            lines.append(f"      {note}")
    if len(live) > limit:
        lines.append(f"  … {len(live) - limit} more live slip(s) behind these")
    if unverified:
        lines.append("")
        lines.append("RETIRED BUT UNVERIFIED — quiet, and never once confirmed landed.")
        lines.append("  Silence here has two causes and the ledger cannot tell them apart:")
        lines.append("  it was learned, or nothing ever asked. Worth a CHECK, not a dose —")
        lines.append("  slip it into a scene and see. Report with --slip-tested tag:landed|missed.")
        for p in unverified[:limit]:
            ago = f"{p['days_quiet']}d quiet" if p["days_quiet"] else "today"
            lines.append(f"  ○ {p['tag']} — {p['count']}× to {p['last']}, {ago}"
                         + ("  · came back after a close" if p["reopened"] else ""))
            for d, said, want in p["examples"][-1:]:
                lines.append(f"      {d}: said “{said}” → wanted “{want}”")
            if p["notes"]:
                lines.append(f"      pattern: {p['notes'][-1]}")
        if len(unverified) > limit:
            lines.append(f"  … {len(unverified) - limit} more unverified behind these")
    return lines


def cmd_slips(args):
    """Read the slip ledger, or record test outcomes. Capture is not here: the
    judge that saw the mistake and `update --slip` both go through append_slips."""
    if args.tested:
        for tag, outcome, msg in record_slip_test(args.tested):
            mark = {"landed": "✓", "missed": "✗", "bad": "!"}[outcome]
            print(f"  {mark} {tag}: {msg}")
        return

    patterns = slip_patterns()
    if not patterns:
        print("No slips logged yet.")
        return
    live = [p for p in patterns if p["live"] and p["pattern"]]
    unver = [p for p in patterns if p["unverified"]]
    print(f"SLIP LEDGER ({sum(p['count'] for p in patterns)} slips, "
          f"{len(patterns)} patterns, {len(live)} live, {len(unver)} awaiting a check):")
    for p in patterns[:args.n]:
        state = ("LIVE" if p["live"] and p["pattern"] else
                 f"closed {p['closed_on']}" if p["closed"] else
                 "UNVERIFIED" if p["unverified"] else
                 "quiet" if not p["live"] else "once")
        print(f"\n  [{state}] {p['tag']} — {p['count']}× "
              f"({p['first']} → {p['last']}, {p['span_days']}d span)")
        if p["lanes"]:
            print(f"        lanes: {', '.join(p['lanes'])}"
                  + (f" · dose channels tried: {', '.join(p['channels'])}"
                     if p["channels"] else " · no dose ever commissioned for it"))
        for d, said, want in p["examples"][-3:]:
            print(f"        {d}: “{said}” → “{want}”")
        if p["notes"]:
            print(f"        pattern: {p['notes'][-1]}")
        for c in p.get("commissions", []):
            print(f"        ✓ dose commissioned {c.get('at','')} via the "
                  f"{c.get('channel','?')} lane"
                  + (f" — {', '.join(c['payload'])}" if c.get("payload") else ""))
        if p.get("dosed_rows"):
            print(f"        · slipped while an order stood: "
                  f"{', '.join(f'{d} ({ch})' for d, ch, _ in p['dosed_rows'][-3:])}")
        if p["uncommissioned"]:
            print("        ⚠ NEVER COMMISSIONED — owed a dose, not another recast.")
        elif p["escalate"]:
            print(f"        ⚠ ESCALATE — heard {p['heard_at'][:10]}, slipped since: "
                  f"{escalation_note(p['channels'])}.")
        elif note := dose_note(p):
            print(f"        {note}")
        if p["unverified"]:
            print("        ○ never confirmed landed — test it, then --tested "
                  f"{p['tag']}:landed|missed")
        if p["reopened"]:
            print("        ⚠ CAME BACK after being closed — the loudest signal here.")
