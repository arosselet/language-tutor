#!/usr/bin/env python3
"""The session brief: what the tutor reads at the start of a session.

`sync_state status` — the agent-facing load: git sync banner, the local clock,
the soak order and its commission, what the last knocks asked and whether they
were answered, the meters, and the slip block. A READ surface: nothing here
mutates state. Not `show_status.py`, which is the learner's human dashboard.

Sits ABOVE the writer: it imports sync_state, which imports it back only inside
`main`'s subcommand dispatch.
"""

import subprocess
from datetime import date, datetime, timedelta

import audio_titles
from slips import format_slip_block, slip_patterns
from state_io import (BASE, EPISODES_PATH, FEEDBACK_LOG_PATH, KNOCK_LOG_PATH,
                      LEARNER_PATH, LEXICON_PATH, LOCAL_TZ, SESSION_LOG_PATH,
                      load_json, local_today)
from state_io import canon_payload, is_unseen, soak_pending, split_payload
from sync_state import (RECOGNITION_LEVELS, compute_ear, compute_engines,
                        compute_machines,
                        compute_floor, compute_status, fires_today, is_pattern)


def git_sync_counts() -> tuple[int, int] | None:
    """(behind, ahead) of origin/main after a fetch, or None when unknowable.
    The clone is one of several writers (the cloud knocks commit all day), so
    status must know whether it is reading today's story or yesterday's."""
    try:
        subprocess.run(["git", "fetch", "--quiet", "origin", "main"],
                       cwd=BASE, timeout=20, capture_output=True, check=True)
        out = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"],
            cwd=BASE, timeout=10, capture_output=True, text=True, encoding="utf-8", check=True).stdout
        ahead, behind = (int(x) for x in out.split())
        return behind, ahead
    except (subprocess.SubprocessError, FileNotFoundError, ValueError, OSError):
        return None


def sync_banner(counts: tuple[int, int] | None) -> str | None:
    """The staleness gate, printed ABOVE everything so no agent reads state past
    it: a session on a stale clone re-collects what was already answered."""
    if counts is None:
        return ("⚠ SYNC UNKNOWN — couldn't reach origin. If this machine has been "
                "offline or idle, this digest may be stale; reconnect and `git pull "
                "--ff-only` before trusting it.")
    behind, ahead = counts
    lines = []
    if behind:
        lines.append(f"⛔ STATE IS STALE — {behind} commit{'s' if behind != 1 else ''} "
                     f"behind origin/main. STOP: run `git pull --ff-only` (or rebase if "
                     f"diverged) and re-run status. Everything below may be yesterday's story.")
    if ahead:
        lines.append(f"⚠ {ahead} local commit{'s' if ahead != 1 else ''} not on origin — "
                     f"push after the session close, or the cloud knocks on stale state.")
    return "\n".join(lines) or None


def knocks_since(klog: list, last_session: str | None, cap: int = 6) -> list[dict]:
    """Knock-log entries on/after the last session date, newest last — the
    between-session story the debrief alone cannot carry."""
    if not klog:
        return []
    entries = [k for k in klog if not last_session or k.get("date", "") >= last_session]
    return entries[-cap:]


# The ALREADY ASKED block is capped like its siblings; one mention inside the
# window is the case the cooldown permits, not a repeat.
ASK_BLOCK_CAP = 8
ASK_REPEAT_FLOOR = 2


def _answered_targets(klog: list, days: int) -> set:
    """Targets that got a reply inside the window. An answered ask means the item
    was worked; an unanswered one means nothing, and silence quietly makes an item
    MORE eligible — re-commissioning on it is the loop being closed."""
    cutoff = datetime.now(LOCAL_TZ).timestamp() - days * 86400
    out = set()
    for k in klog:
        if not k.get("acted", True) or not (k.get("reply") or k.get("exchanges")):
            continue
        try:
            ts = datetime.fromisoformat((k.get("timestamp") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.timestamp() >= cutoff and k.get("expected_target"):
            out.add(k["expected_target"])
    return out


def knock_line(k: dict) -> str:
    """One digest line per knock: what went out, what came back, what was
    CORRECTED — so the same recast cannot ship three times looking like progress."""
    body = (k.get("body") or "").replace("\n", " ")
    if len(body) > 90:
        body = body[:87] + "…"
    if k.get("reply"):
        n = len(k.get("exchanges", [])) or 1
        reply = k["reply"].replace("\n", " ")
        if len(reply) > 40:
            reply = reply[:37] + "…"
        back = f"→ {n} repl{'ies' if n != 1 else 'y'}, last: '{reply}' ({k.get('reply_verdict', '?')})"
        fired = k.get("reply_fired_cold") or []
        if fired:
            back += f" · fired COLD: {', '.join(fired)}"
        recasts = [x.get("reply_line", "") for x in k.get("exchanges", [])] or \
                  [k.get("reply_line", "")]
        recasts = [r.split(" · ")[0].strip() for r in recasts if r]
        if recasts:
            back += "\n      corrected: " + " | ".join(r[:88] for r in recasts[-2:])
    elif k.get("response"):
        back = f"→ {k['response']}"
    else:
        back = "→ (no response yet)"
    return f"  {k.get('date', '?')} [{k.get('modality', '?')}] {k.get('move', '?')} — \"{body}\" {back}"


HEARD_TAG = "[heard]"


def heard_in_the_wild(cap: int = 5) -> list[str]:
    """What the learner heard OUT THERE and could not place — the highest-yield
    input the system gets. A reader, not a store: a `[heard]` prefix on an
    ordinary feedback note (`sync_state.py feedback "[heard] …"`).

    The tutor DECODES it, never grades it: a line whose words the learner owns
    is an ear problem (eavesdrop dose); a genuinely new word is a Teach Beat.
    Cleared by `[heard-worked] …`. It does not claim the session's opening slot:
    the open belongs to `daily_session.md`."""
    log = load_json(FEEDBACK_LOG_PATH) or []
    worked = {e.get("note", "")[len("[heard-worked]"):].strip().lower()
              for e in log if e.get("note", "").startswith("[heard-worked]")}
    body = [f"   {e.get('date', '?')} · {e['note'][len(HEARD_TAG):].strip()}"
            for e in log if e.get("note", "").startswith(HEARD_TAG)
            and e["note"][len(HEARD_TAG):].strip().lower() not in worked]
    return ["", "👂 HEARD IN THE WILD, NOT YET WORKED — work one of these into "
            "the session; decode it, never grade it. Close with "
            "`feedback \"[heard-worked] <line>\"`."] + body[-cap:] if body else []


def unpaid_trailer(klog: list, last_session: str | None) -> dict | None:
    """The newest knock, if it is a lure whose promised teach no session has paid
    off yet. Its payoff opens the session."""
    if not klog:
        return None
    k = klog[-1]
    if k.get("stance") != "lure":
        return None
    if last_session and last_session >= k.get("date", ""):
        return None
    return k


def cmd_status(_args):
    lexicon = load_json(LEXICON_PATH)
    learner = load_json(LEARNER_PATH)
    if not learner:
        print("No learner.json found.")
        return

    banner = sync_banner(git_sync_counts())
    if banner:
        print(banner)
        print()

    # The tutor is time-aware: "ping me in an hour" becomes a real scheduled push.
    # The zone is NAMED, so a forgotten switch after travel is visible.
    print(f"Now: {datetime.now(LOCAL_TZ):%a %Y-%m-%d %H:%M %Z} ({LOCAL_TZ.key})")
    print(f"Learner: {learner.get('learner')}")
    # A held channel must SAY it is held, or it reads as the learner going quiet.
    quiet_until = learner.get("quiet_until") or ""
    if quiet_until:
        lapsed = local_today() > date.fromisoformat(quiet_until)
        print(f"⏸ KNOCKS HELD through {quiet_until}"
              + (" — LAPSED, knocks resume; clear it with `--quiet-until \"\"`"
                 if lapsed else " (silence here is not a fade)"))
    # No streak theatre — the honest signal is recency.
    slog = load_json(SESSION_LOG_PATH) or []
    last = slog[-1].get("date") if slog else None
    gap = (local_today() - date.fromisoformat(last)).days if last else None
    if last:
        gap_str = "today" if not gap else f"{gap} day{'s' if gap != 1 else ''} ago"
        print(f"Last logged session: {last} ({gap_str})")
    print(f"Status: {compute_status()}")
    print(f"Story so far: {learner.get('last_debrief', '')}")
    next_engine = learner.get("next_engine", "")
    if next_engine and lexicon:
        r = lexicon.get(next_engine, {})
        prod = r.get("production", "none")
        if prod != "cold":
            gloss = r.get("gloss", "")
            unseen = is_unseen(r)
            tag = "UNSEEN — teach first" if unseen else f"production: {prod}"
            print(f"Next engine: {next_engine} — {gloss}  [{tag}]")

    soak = learner.get("soak_order", {})
    if soak.get("payload") or soak.get("scene_seed"):
        items = canon_payload(soak.get("payload", []))
        soak_from = soak.get("from")
        soak_age = (local_today() - date.fromisoformat(soak_from)).days if soak_from else None
        stale = " ⚠ stale — chat hasn't fed the Director lately" if soak_age and soak_age > 7 else ""
        # The session-open auto-drain answer, computed with the ONE resolver the
        # dispatch uses, so the two doors onto the same dispatch cannot disagree.
        _, unresolved = split_payload(soak.get("payload", []), lexicon)
        channel = soak.get("channel") or "episode"
        lane = {"soak": "python scripts/render_soak.py",
                "drill": "python scripts/render_drill.py"}.get(
                    channel, "python scripts/run_studio.py")
        produced = not soak_pending()
        # STALLED reads before produced: a render ran and could not carry the
        # payload, which answers the dispatch question like a carried order does.
        att = soak.get("attempted") or {}
        stalled = (att.get("unclaimed") and (att.get("at") or "") >= (soak_from or ""))
        if unresolved:
            drain = (f" · ⚠ payload unverifiable ({', '.join(unresolved)}) — fix the soak "
                     f"order; NOT dispatching on an item that can never match")
        elif stalled:
            drain = (f" · ⚠ STALLED — M{att['episode']} rendered against this order on "
                     f"{att['at']} but could not carry {', '.join(att['unclaimed'])} "
                     f"(the script said it another way). NOT re-dispatching. Re-order "
                     f"the payload in the form the script can carry, or take the next item.")
        elif produced:
            drain = f" · produced ✓ (the {channel} lane carried it — no dispatch needed)"
        else:
            drain = (f" · ⚠ NOT YET PRODUCED — dispatch `{lane}` in the background now "
                     f"(session-open auto-drain)")
        focus = f" · focus: {soak['focus']}" if soak.get("focus") else ""
        print(f"Soak order [{channel}]: [{', '.join(items)}] — {soak.get('scene_seed', '')}"
              f"{focus} (from {soak.get('from', '?')}){stale}{drain}")
    else:
        print("Soak order: ⚠ none set — chat hasn't handed anything to the Director.")

    # The between-session story: re-collecting something answered here is the bug.
    klog = load_json(KNOCK_LOG_PATH) or []
    since = knocks_since(klog, last)
    if since:
        print(f"\nKnocks since last logged session ({len(since)} shown — replies here are already judged; don't re-collect):")
        for k in since:
            print(knock_line(k))
    # THE COOLDOWN, on the surface the tutor reads when writing the soak order.
    # Advisory by construction: the order is the tutor's prose, so Python cannot
    # block it — it can only say so. Unanswered repeats sort first.
    from suggest_targets import ASK_COOLDOWN_DAYS, recent_ask_counts
    asked = recent_ask_counts(klog, lexicon or {})
    answered = _answered_targets(klog, ASK_COOLDOWN_DAYS)
    repeats = sorted(((w, n) for w, n in asked.items() if n >= ASK_REPEAT_FLOOR),
                     key=lambda kv: (-kv[1], kv[0] in answered, kv[0]))
    if repeats:
        print(f"\nALREADY ASKED (last {ASK_COOLDOWN_DAYS}d — do NOT re-commission these; "
              f"a repeat needs a genuinely new angle, or take another item):")
        for w, n in repeats[:ASK_BLOCK_CAP]:
            tail = "" if w in answered else " · UNANSWERED — silence is not a reason to re-ask"
            print(f"  - {w} — asked/shown {n}×{tail}")
        rest = len(repeats) - ASK_BLOCK_CAP
        if rest > 0:
            print(f"  (…{rest} more at {repeats[ASK_BLOCK_CAP][1]}× or fewer — not shown)")
    trailer = unpaid_trailer(klog, last)
    if trailer:
        body = (trailer.get("body") or "").replace("\n", " ")
        print(f"🎬 UNPAID TRAILER: \"{body}\" — its promised teach OPENS the session (pay it off in the first two exchanges).")

    for line in heard_in_the_wild():
        print(line)

    # The error memory, ahead of the meters: a slip says HOW a rep keeps failing.
    slip_block = format_slip_block(slip_patterns())
    if slip_block:
        print()
        for line in slip_block:
            print(line)
    print()

    if lexicon:
        by_level = {lvl: 0 for lvl in RECOGNITION_LEVELS}
        cold = hinted = 0
        for r in lexicon.values():
            if is_pattern(r):
                continue  # patterns are metered separately, on both axes
            by_level[r.get("recognition", "untested")] = by_level.get(r.get("recognition", "untested"), 0) + 1
            if r.get("production") == "cold":
                cold += 1
            elif r.get("production") == "hinted":
                hinted += 1
        # Steering data, never narration: a scoreboard read aloud to a
        # mastery-driven learner predicts withdrawal when the number is slow.
        print("↓ ENGINEERING NUMBERS — they steer what Python picks. Never recite a "
              "fraction, percentage, countdown or streak at the learner (persona.md); the "
              "close names what got clearer.")
        # `untested` is the absence of evidence, never a grade: a large count says
        # the picture is guesswork — run the sweep, don't re-teach.
        print(f"Recognition — solid: {by_level['solid']}, comfortable: {by_level['comfortable']}, "
              f"struggled: {by_level['struggled']}, untested: {by_level['untested']} (no test yet)")
        print(f"Production — cold: {cold}, hinted: {hinted}")
        floor = compute_floor(lexicon)
        print(f"Viability floor: {floor['cleared']}/{floor['total']} recognized words fire cold ({floor['pct']:.0f}%)")
        engines = compute_engines(lexicon)
        if engines["total"]:
            print(f"Engines online: {engines['online']}/{engines['total']} patterns fire cold ({engines['pct']:.0f}%)")
        mach = compute_machines(lexicon)
        if mach["total"]:
            # The untested count said out loud: a blank is not a miss.
            print(f"Machines heard: {mach['heard']} of {mach['tested']} ever ear-tested "
                  f"({mach['total']} tracked; {mach['total'] - mach['tested']} NEVER tested "
                  f"— blanks, not misses) — PRIMARY STEER")
        ear = compute_ear(lexicon)
        if ear["total"]:
            print(f"Ear-only: {ear['caught']}/{ear['total']} solid on recognition "
                  f"— the win is comprehension; never forced to fire.")
            if ear["untouched"]:
                print(f"  ⚠ Coverage: {ear['untouched']} ear item(s) never worked — "
                      f"catch advances ONLY through eavesdrop. See the ticket for the "
                      f"register breakdown.")
                print("    ENGINEERING NUMBER — steers what Python picks; never narrated to the learner "
                      "(a global deficit recited in a warm voice is guilt machinery).")
        print(f"Fired today: {fires_today()}")
        # A rating is the one proof a dose was heard, so rating days are ear-block
        # days. Cue and meter only — no streak, no deficit narrated.
        week = (local_today() - timedelta(days=6)).isoformat()
        heard = {e["date"] for e in load_json(FEEDBACK_LOG_PATH) or []
                 if e.get("date", "") >= week and "[audio rating]" in e.get("note", "")}
        print(f"Ear block: rated on {len(heard)} of the last 7 days"
              + ("" if heard else " — cue it at the second anchor; a rating is how it is seen"))
        # Minutes PLAYED: a floor for what to commission, never a debt.
        dose = audio_titles.dose_minutes(7)
        warn = " — ⚠ presses with NO duration behind them: plumbing, not a quiet week" if dose["unmeasured"] else ""
        print(f"Dose: {dose['minutes']:.0f} min played over 7d "
              f"({dose['per_day']:.1f}/day, {dose['taps']} presses){warn}")

    episodes = load_json(EPISODES_PATH) or {}
    if episodes:
        recent = sorted(episodes.items(), key=lambda x: int(x[0]), reverse=True)[:6]
        print("\nRecent episodes (immersion tank — no listen bookkeeping; each is a self-contained dose):")
        for m, ep in recent:
            dur = ep.get("duration_min")
            dur_str = f" ({dur:.1f} min)" if dur else ""
            print(f"  M{m}: {ep.get('title', m)}{dur_str}")
