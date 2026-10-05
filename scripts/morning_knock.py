#!/usr/bin/env python3
"""
The tutor's between-session outreach — an AGENT deciding whether, how and when to
reach out, not a fixed cron job. The schedule is the heartbeat; the POLICY is the
tutor's.

Division of labour:
  - Python owns the RAILS (hard) and the TICK: waking hours, a daily cap, a
    minimum gap, and the tutor's own `next_check` soft gate. It skips a tick
    cheaply (no model call) unless a reach is actually possible and due.
  - The tutor owns the POLICY: fire or silence, the move, the MODALITY, its own
    next check-in time, and a one-line rationale so its choices stay inspectable.

The reward is the LEARNER SHOWING UP, not taps. Outreach is READ-ONLY on the
learning brain except for declared exposures.

  python scripts/morning_knock.py --dry-run   # gate + decide + render only (no commit/push/notify)
  python scripts/morning_knock.py             # full: rails gate, then decide & (maybe) reach out
  python scripts/morning_knock.py --force     # skip the rails gate (manual one-off)

Secrets: OPENROUTER_API_KEY (when no local agent), PUSH_WEBHOOK_URL, TTS
credentials (only when an audio modality is chosen).
"""
import argparse
import asyncio
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from mandates import OUTREACH_MANDATE

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from pack import EAVESDROP_VOICE, LEARNER, REFERENT_NOUNS, TUTOR, TUTOR_VOICE
import world
from memo import render_memo
from push_queue import maybe_enqueue_schedule
from publish import (BODY_BUDGET, KNOCKS_DIR,
                     commit_and_push, jsdelivr_url, load_env, over_budget,
                     publish, push_to_phone)
from writer import (AGENT_MODEL, BOOL, INT, OPENROUTER_MODEL, STR, STRS, ask_json,
                    executor_name, have_agent, nullable, obj,
                    to_read_form, voice_canon)

# The budget lives in `rails.py` (two channels obey it); whether to WAKE the
# tutor is this lane's own policy, below.
from rails import (MAX_REACHES_PER_DAY, MIN_GAP_HOURS, WAKING_END_HOUR,
                   WAKING_START_HOUR, in_waking_window, last_fire, reaches_today)
from state_io import (KNOCK_LOG_PATH, LEARNER_PATH, LEXICON_PATH, LOCAL_TZ,
                      SESSION_LOG_PATH, STANCES, is_fire, is_give, load_json,
                      local_date)

NEXT_CHECK_CLAMP = (0.5, 24.0)   # the self-set next_check is clamped to this many hours

MODALITIES = {"text", "audio", "challenge", "volley", "eavesdrop", "fielding", "grace", "silence"}
VOLLEY_SIZE = 4   # menu items per volley knock — one per exchange, chained by Python


# ── The rails gate (no model call — runs every tick) ─────────────────────────

def rails_gate(force: bool, now: datetime | None = None) -> tuple[bool, str]:
    """Should this tick WAKE the tutor to decide? Only if a reach is genuinely
    possible: inside waking hours, under the daily cap, past the min gap, past
    the tutor's own next_check. `now` is injectable for testing."""
    if force:
        return True, "forced"
    now = now or datetime.now(timezone.utc)
    now_local = now.astimezone(LOCAL_TZ)

    # The transit bit, FIRST: it is the only rail meaning "cannot receive this at
    # all" (an unreachable phone keeps one queued push, so a dose fired into a
    # flight is destroyed). Skipped before anything is logged, so the stretch can
    # never be read as fading.
    quiet_until = (load_json(LEARNER_PATH) or {}).get("quiet_until") or ""
    if quiet_until and now_local.date() <= date.fromisoformat(quiet_until):
        return False, f"quiet_until {quiet_until} — in transit, not fading"

    if not in_waking_window(now):
        return False, f"quiet hours ({now_local:%H:%M} {now_local.tzname()})"

    klog = load_json(KNOCK_LOG_PATH) or []
    n_today = reaches_today(klog, now_local.date())
    if n_today >= MAX_REACHES_PER_DAY:
        return False, f"daily cap reached ({n_today}/{MAX_REACHES_PER_DAY})"

    lf = last_fire(klog)
    if lf:
        gap = (now - datetime.fromisoformat(lf["timestamp"])).total_seconds() / 3600
        if gap < MIN_GAP_HOURS:
            return False, f"min-gap not met ({gap:.1f}h < {MIN_GAP_HOURS}h)"

    # The tutor's own soft gate — its chosen cadence, set on the latest decision.
    if klog:
        nc = klog[-1].get("next_check")
        if nc and now < datetime.fromisoformat(nc):
            return False, f"{TUTOR}'s next_check not due (set for {nc})"

    return True, f"eligible ({n_today}/{MAX_REACHES_PER_DAY} today) — waking {TUTOR} to decide"


# ── The digest the tutor reads ───────────────────────────────────────────────

def outcome_memory(klog: list, now: datetime) -> str:
    """Recent reaches with their outcomes, framed around the real reward (did the
    learner SHOW UP?), plus the ignore-streak — what lets the policy adapt."""
    slog = load_json(SESSION_LOG_PATH) or []
    last_session = slog[-1].get("date") if slog else None
    fires = [k for k in klog if is_fire(k)]

    lines = []
    for k in fires[-5:]:
        modality = k.get("modality", "audio")
        move = k.get("move", "—")
        if k.get("reply"):
            # A typed reply carries real signal ("busy", "back off"): verbatim.
            detail = f'replied ({k.get("reply_verdict", "?")}): "{k["reply"][:60]}"'
        elif k.get("response"):
            detail = f"tapped ({k['response']})"
        else:
            detail = "no-tap"
        # The ask itself, not just the move name, so same-ask repeats are visible.
        ask = k.get("expected_target") or "no-ask"
        body_head = (k.get("body") or "").replace("\n", " ")[:48]
        lines.append(f"    {k.get('date','?')} · {modality}/{move} · "
                     f"asked: {ask} · “{body_head}…” · {detail}")

    # Ignore streak = trailing ASKS with no tap and no session since. Gifts are
    # worth an interruption "tapped or not", so they are counted on their own
    # line: counting them as ignored would make the default format read as
    # disengagement, and skipping them silently would hide gifts that never land.
    streak = gifts_untapped = 0
    for k in reversed(fires):
        after = local_date(k.get("timestamp", ""))
        session_after = last_session and after and last_session >= after.isoformat()
        if k.get("response") or session_after:
            break
        if is_give(k):
            gifts_untapped += 1
        else:
            streak += 1

    since = "never" if not last_session else last_session
    verdict = ""
    if streak >= 3:
        verdict = (f"  ⚠ {streak} asks in a row led to no session and no tap — the current "
                   "approach isn't converting. Change the move or modality — a gift next, then a "
                   "different ask; never a reason to stop asking.")
    elif gifts_untapped >= 4:
        verdict = (f"  ⚠ {gifts_untapped} gifts in a row untapped, no session between — the gifts "
                   "aren't landing. Change the vein and the notification's shape, or send a MISSION. "
                   "Not a reason for silence.")
    elif last_session and (now.astimezone(LOCAL_TZ).date() - date.fromisoformat(last_session)).days >= 3:
        verdict = "  ⚠ No session in 3+ days — pull, never nag: a gift that shows how close the next step is."

    body = "\n".join(lines) if lines else "    (no reaches logged yet)"
    return (f"OUTREACH MEMORY (reward = {LEARNER} showing up in chat, NOT taps):\n"
            f"  Last chat session: {since}\n"
            f"  Recent reaches (newest last):\n{body}\n"
            f"  Ignore-streak: {streak} unanswered asks ({gifts_untapped} untapped gifts "
            f"between).{verdict}")


def demand_streak(klog: list) -> int:
    """Trailing consecutive FIRES that wanted something (an ask or a lure). Only
    a GIVE breaks it (`state_io.is_give`). Python counts; the mandate owns the rule."""
    n = 0
    for k in reversed([k for k in klog if is_fire(k)]):
        if is_give(k):
            break
        n += 1
    return n


EAVESDROP_CADENCE_DAYS = 3  # catch items need an eavesdrop dose at least this often


def last_eavesdrop(klog: list) -> dict | None:
    """Most recent fired eavesdrop dose — catch items advance ONLY through it."""
    for k in reversed([k for k in klog if is_fire(k)]):
        if k.get("modality") == "eavesdrop":
            return k
    return None


def remaining_room(klog: list, now: datetime) -> str:
    now_local = now.astimezone(LOCAL_TZ)
    n_today = reaches_today(klog, now_local.date())
    lf = last_fire(klog)
    gap_str = "no reach yet today"
    if lf:
        gap = (now - datetime.fromisoformat(lf["timestamp"])).total_seconds() / 3600
        gap_str = f"last reach {gap:.1f}h ago"
    # Never the same gift vein twice running.
    gifts = [k.get("move", "") for k in klog if is_fire(k) and is_give(k)][-4:]
    lore_str = (f"\n  Recent gift veins (newest last — take a different one): {' · '.join(gifts)}"
                if gifts else "")
    # The template rail: sameness by rhetoric is invisible to a rail that reads
    # move labels, so Python counts the tease openers; the mandate owns the cap.
    teases = sum(bool(TEASE_RE.search(k.get("body") or "")) for k in
                 [k for k in klog if is_fire(k)][-6:])
    lore_str += f"\n  Progress-tease template in {teases} of the last 6 fires (cap: 1 in 3)."
    # Eavesdrop cadence: catch items advance ONLY through eavesdrop.
    eavesdrop_str = ""
    try:
        from suggest_targets import ear_targets
        _lex = load_json(LEXICON_PATH) or {}
        _catch_pending = ear_targets(_lex)["pending"]
        if _catch_pending and EAVESDROP_VOICE:
            le = last_eavesdrop(klog)
            if le is None:
                eavesdrop_str = (f"\n  ⚠ Eavesdrop: {len(_catch_pending)} catch item(s) pending, "
                                 f"NEVER fired — catch advances ONLY through eavesdrop; "
                                 f"this is the highest-value move right now.")
            else:
                ld = local_date(le.get("timestamp", ""))
                age = (now_local.date() - ld).days if ld else EAVESDROP_CADENCE_DAYS
                if age >= EAVESDROP_CADENCE_DAYS:
                    eavesdrop_str = (f"\n  ⚠ Eavesdrop: {len(_catch_pending)} catch item(s) pending, "
                                     f"last eavesdrop {age}d ago (cadence: every {EAVESDROP_CADENCE_DAYS}d) — "
                                     f"consider eavesdrop this tick.")
    except Exception:
        pass  # never let a cadence check kill a reach

    return (f"RAILS (hard — stay well inside; silence is free):\n"
            f"  Waking window {WAKING_START_HOUR}:00–{WAKING_END_HOUR}:00 {now_local.tzname()}; "
            f"now {now_local:%H:%M}.\n"
            f"  Reaches today: {n_today}/{MAX_REACHES_PER_DAY}. Min gap {MIN_GAP_HOURS}h ({gap_str})."
            f"{lore_str}{eavesdrop_str}")


def due_menu_block(max_fire: int = 6, max_catch: int = 2) -> str:
    """The pool's due items in the selector's own order (this lane never
    re-sorts). UNSEEN items are flagged: teach first, never cold-quiz."""
    from suggest_targets import ASK_COOLDOWN_DAYS, drill_menu, ear_targets
    lex = load_json(LEXICON_PATH) or {}
    menu = drill_menu(lex, max_n=max_fire)
    if not menu:
        return ""
    lines = ["DUE MENU (expected_target should usually come from here):"]
    for t in menu:
        state = "hinted→cold" if t["production"] == "hinted" else f"{t['recognition']}, cold-pending"
        if t["unseen"]:
            state += " · ⚠ UNSEEN — teach first (show dose), don't quiz"
        if t["retest"]:
            state += f" · GOING DARK, {t['staleness']}d silent since it was hinted"
        if t["asks"]:
            state += (f" · ⚠ asked/shown {t['asks']}× in last {ASK_COOLDOWN_DAYS}d — needs a genuinely "
                      f"new scene, or pick another item")
        lines.append(f"    [{t['kind']} · {t['lead']}] {t['word']} — {t['gloss'] or '[no gloss]'}  [{state}]")
    # One pattern and one catch row where both exist: a straight slice of the ear
    # queue would hand both slots to the patterns holding its reserved seats.
    _ear = ear_targets(lex)["pending"]
    _machines = [t for t in _ear if not t.get("ear_only")]
    _catch = [t for t in _ear if t.get("ear_only")]
    _picked = [q[0] for q in (_machines, _catch) if q][:max_catch]
    _picked += [t for t in _ear if t not in _picked][:max_catch - len(_picked)]
    for t in _picked:
        if t.get("pairs_with"):
            # The one ear-only case answered aloud: silence is the failure.
            lines.append(f"    [pair] {t['word']} — {t['gloss'] or '[no gloss]'}  "
                         f"→ the answer: {t['pairs_with']} — {t['response_gloss'] or '[no gloss]'}  "
                         f"(play HER line, let {LEARNER} answer — never quiz the catch half alone)")
        elif t.get("ear_only"):
            lines.append(f"    [ear-only] {t['word']} — {t['gloss'] or '[no gloss]'}  "
                         f"(soak/eavesdrop dose only — never ask {LEARNER} to fire it)")
        else:
            # A pattern, not a catch row: the catch law is a property of the ROW.
            lines.append(f"    [ear-behind] {t['word']} — {t['gloss'] or '[no gloss]'}  "
                         f"({LEARNER} FIRES this; the EAR is what is behind — eavesdrop/soak it, "
                         f"and a fire here earns no ear credit)")
    return "\n".join(lines)


def volley_targets(n: int = VOLLEY_SIZE) -> list[dict]:
    """The BINDING item list for a volley — Python picks, so coverage stays
    honest. `drill_menu`'s head only (the focus set IS the rotation budget);
    UNSEEN excluded. Returns short when the head is mostly unseen, and the volley
    then degrades — correct: an unseen-heavy head wants a teach dose."""
    from suggest_targets import drill_menu  # lazy: keeps module import light
    lex = load_json(LEXICON_PATH) or {}
    out = []
    for t in drill_menu(lex):
        if t["unseen"]:
            continue  # UNSEEN — teach first (show dose), never cold-quiz
        out.append({"target": t["word"], "gloss": t.get("gloss", "")})
        if len(out) == n:
            break
    return out


def campaign_block() -> str:
    """The live ARC from profile.md's `## The Arc` section — the month's
    situation in the world, which the knocks steer by. It names no items (the
    ticket owns those). Matched on the HEADING prefix, never its title, which
    changes with every arc."""
    try:
        text = (BASE / "progress" / "profile.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    marker = "## The Arc"
    heading = next((l for l in text.splitlines() if l.startswith(marker)), None)
    if heading is None:
        return ""
    body = text.split(heading, 1)[1].split("\n## ", 1)[0]
    # Drop the standing contract blockquote; the mandate already carries the rules.
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith(">")).strip()
    if not body or "no arc live" in body:
        return ""
    # Cut at a paragraph break, never mid-word; no break within the cap falls back
    # to the raw slice, never to an empty campaign.
    return "CAMPAIGN (the live week plan — steer by it):\n" + (body[:1500].rsplit("\n\n", 1)[0] if len(body) > 1500 else body)


# The progress-tease openers the template rail counts (see remaining_room).
TEASE_RE = re.compile(r"you already|you own|you'?re (one|1)\b|\bone\b.{0,40}\baway\b|"
                      r"\ba\b.{0,40}\baway from\b", re.I)

# Question words in the learner's language (as shipped, English).
QUESTION_RE = re.compile(r"\b(what|why|how|which|break (it )?down|root|mean|difference)\b", re.I)


def last_fired_on(klog: list) -> dict:
    """key -> the last date the learner PRODUCED it (sessions and judged
    replies). A tease on month-old evidence reads as pressure, not pull. Not
    `last_surfaced`, which is a delivery stamp."""
    out = {}
    for e in load_json(SESSION_LOG_PATH) or []:
        for k in (e.get("cold") or []) + (e.get("hinted") or []):
            out[k] = max(out.get(k, ""), e.get("date") or "")
    for e in klog:
        for k in e.get("reply_fired") or []:
            out[k] = max(out.get(k, ""), (e.get("reply_at") or e.get("timestamp") or "")[:10])
    return out


def progress_block(klog: list, now: datetime, max_n: int = 6) -> str:
    """What the push HOOKS on: what the learner owns, is one step from, and has
    not met — so pushes tease progress instead of leaning on the world or on
    misses. Rows only — no new state."""
    lex = load_json(LEXICON_PATH) or {}
    by_recent = sorted(lex.items(), key=lambda kv: kv[1].get("last_surfaced") or "", reverse=True)
    fired = last_fired_on(klog)
    def rows(pred, n, dated=True):
        when = lambda k: f" (last fired: {fired.get(k, 'no dated evidence')})" if dated else ""
        return [f"    {k} — {(v.get('gloss') or '')[:70]}{when(k)}" for k, v in by_recent if pred(k, v)][:n]
    frame = lambda k: k.startswith("frame:")
    owned = rows(lambda k, v: frame(k) and v.get("production") == "cold", max_n)
    ahead = rows(lambda k, v: frame(k) and v.get("production") == "none", 3, dated=False)
    close = rows(lambda k, v: not frame(k) and v.get("production") == "hinted", max_n)
    since = (now - timedelta(days=14)).isoformat()
    asked = []
    for e in klog:
        if (e.get("timestamp") or "") < since:
            continue
        for x in e.get("exchanges") or []:
            r = (x.get("reply") or "").strip()
            if r and QUESTION_RE.search(r):
                asked.append(f'    {(x.get("at") or e["timestamp"])[:10]}: "{r[:140]}"')
    out = [f"PROGRESS (the hook — what {LEARNER} owns, is one step from, has not met):",
           "  Patterns fired unaided:", *owned,
           "  One step away (fired with a hint, not yet alone):", *close,
           "  Patterns not met yet:", *ahead]
    if asked:
        out += ["RECENT QUESTIONS (answer each with a gift, once; skip any a recent "
                "gift vein already took):", *asked[-4:]]
    return "\n".join(out)


def build_digest() -> str:
    """Everything the tutor needs for a policy call: learning state, the live
    arc, progress, the due menu, outcome memory, and the room the rails leave."""
    out = subprocess.run([sys.executable, str(BASE / "scripts" / "sync_state.py"), "status"],
                         capture_output=True, text=True, encoding="utf-8")
    status = out.stdout.strip()
    klog = load_json(KNOCK_LOG_PATH) or []
    now = datetime.now(timezone.utc)
    parts = [status, campaign_block(), progress_block(klog, now), due_menu_block(),
             outcome_memory(klog, now), remaining_room(klog, now)]
    return "\n\n".join(p for p in parts if p)


# ── The decision (model — only reached when the rails gate opened) ───────────

def knock_exposures(decision: dict) -> list[str]:
    """The DECLARED exposure of a knock — never mined from its prose:
      - `introduces` keys (a show dose is a knock-sized Teach Beat),
      - a revealed `expected_target`,
      - an eavesdrop's target (the tape SPEAKS it; it is unrevealed only
        because the ask is comprehension).
    A hidden target is an ASK — spend, not exposure — and stamps nothing."""
    keys = list(decision.get("introduces") or [])
    target = (decision.get("expected_target") or "").strip()
    if target and (decision.get("target_revealed") or decision.get("modality") == "eavesdrop"):
        keys.append(target)
    return keys


# How much of a tape's opening must name its subject: a fact about how a phone
# call is structured (a greeting before the news), so it lives with this lane.
REFERENT_WINDOW = 2  # paragraphs


def tape_names_a_referent(memo_script: str) -> bool:
    """Does the tape name who it is about, up front? A tape about an unnamed
    "they" cannot be asked "who?". The WINDOW is what discriminates: a tape can
    name someone later as the source rather than the subject. Kinship nouns come
    from the pack; the cast's own names (including their target-form spellings)
    from the world canon — a cast list is a fact about the learner, not the language."""
    opening = "\n\n".join((memo_script or "").split("\n\n")[:REFERENT_WINDOW])
    return any(n in opening for n in (*REFERENT_NOUNS, *world.names()))


def normalize_decision(d: dict, volley_menu: list | None = None) -> dict:
    """Guard the decision into the shape Python relies on. A volley zips the
    tutor's asks with PYTHON's binding targets — the model writes the situations,
    never the picks — and the body is composed from ask 1."""
    d["modality"] = d.get("modality") if d.get("modality") in MODALITIES else "text"
    if d["modality"] == "silence":
        d["act"] = False
    lo, hi = NEXT_CHECK_CLAMP
    try:
        d["next_check_hours"] = max(lo, min(hi, float(d.get("next_check_hours", 3))))
    except (TypeError, ValueError):
        d["next_check_hours"] = 3.0
    # Unstated target_revealed defaults True: a reply caps at hinted, so the cold
    # axis stays honest.
    d["expected_target"] = (d.get("expected_target") or "").strip()
    d["target_revealed"] = bool(d.get("target_revealed", True))
    d["introduces"] = [k for k in (d.get("introduces") or []) if isinstance(k, str) and k.strip()]
    # An absent stance is LOUD and defaults to ASK: "give" would silently reset
    # the demand brake. Silence never reaches the streak.
    if d.get("stance") not in STANCES:
        if d.get("act"):
            print(f"   ⚠ dose declared no stance ({d.get('stance')!r}) — counting it as ASK")
        d["stance"] = "ask"
    d["schedule"] = d.get("schedule") if isinstance(d.get("schedule"), dict) else None
    if d["modality"] == "eavesdrop":
        # A defective eavesdrop is REFUSED, never degraded to text: its body is a
        # question about a tape, and a text degrade asks about audio that never
        # ships. A lost dose is cheaper than a wrong one.
        if not EAVESDROP_VOICE:
            print("   ⚠ eavesdrop with no overheard voice configured — refused")
            d["modality"], d["act"] = "silence", False
        elif not (d.get("memo_script") or "").strip():
            print("   ⚠ eavesdrop with no tape — refused (text eavesdrops are "
                  "banned; the drift question's audio would never ship)")
            d["modality"], d["act"] = "silence", False
        elif not tape_names_a_referent(d["memo_script"]):
            print("   ⚠ eavesdrop tape names nobody in its opening — refused "
                  "(the drift question would have no answer in the audio)")
            d["modality"], d["act"] = "silence", False
        else:
            d["target_revealed"] = False  # the tape plays target language; the ask is comprehension
    if d["modality"] == "fielding":
        if (d.get("memo_script") or "").strip():
            d["target_revealed"] = False  # the question plays; the ANSWER was never shown
        else:
            d["modality"] = "text"  # no question to render — plain dose
    if d["modality"] == "volley":
        asks = [a.strip() for a in (d.get("volley_asks") or [])
                if isinstance(a, str) and a.strip()]
        items = [{"target": t["target"], "ask": a}
                 for t, a in zip(volley_menu or [], asks)]
        if len(items) >= 2:
            d["volley"] = items
            d["expected_target"] = items[0]["target"]
            d["target_revealed"] = False  # volley asks are situations by contract
            d["notification_body"] = f"⚡ volley 1/{len(items)} — {items[0]['ask']}"
        else:
            d["modality"] = "text"  # no binding menu / no usable asks — plain dose
    return d


# The knock's shape, declared beside the lane that reads it. Conditional keys
# are declared `nullable`: undeclared means DELETED on the agent path.
DECIDE_SCHEMA = obj(act=BOOL, modality=STR, move=STR, stance=STR,
                    introduces=STRS, notification_body=STR, memo_script=STR,
                    expected_target=STR, target_revealed=BOOL,
                    next_check_hours=INT, rationale=STR,
                    volley_asks=nullable(STRS),
                    # No `memo_script`: an outreach-scheduled dose is text.
                    schedule=nullable(obj(
                        at_local=STR, body=STR, expected_target=STR,
                        target_revealed=BOOL, move=STR)))


def decide(digest: str, volley_menu: list | None = None) -> dict:
    """Ask the tutor what to do this tick, on the host's executor. The world
    canon rides in (an eavesdrop tape is a cast member on the phone); it is not in
    `voice_canon()` because most lanes have no world in them. The model used is
    stamped on every entry, so a writer change stays auditable."""
    canon = voice_canon() + "\n\n---\n\n" + world.load()
    model = AGENT_MODEL if have_agent() else OPENROUTER_MODEL
    print(f"   [decide] {executor_name()} · {model}")
    d = ask_json(canon + "\n\n---\n\n" + OUTREACH_MANDATE,
                 f"TODAY'S DIGEST:\n\n{digest}", DECIDE_SCHEMA, answer_tokens=1600,
                 model=None if have_agent() else model)
    d = normalize_decision(d, volley_menu)
    d["decide_model"] = model
    return d


# ── Orchestration ─────────────────────────────────────────────────────────────

def log_decision(now: datetime, decision: dict, *, acted: bool,
                 audio_url: str | None = None, mp3: Path | None = None) -> Path:
    """Record every WAKE — fire or silence — so next_check and the rationale
    persist across stateless runs and the outcome memory grows."""
    klog = load_json(KNOCK_LOG_PATH) or []
    entry = {
        "date": now.date().isoformat(),
        "timestamp": now.isoformat(),
        "acted": acted,
        "modality": decision.get("modality"),
        "move": decision.get("move"),
        "rationale": decision.get("rationale"),
        "decide_model": decision.get("decide_model"),
        "next_check": (now + timedelta(hours=decision["next_check_hours"])).isoformat(),
    }
    if acted:
        entry["body"], entry["body_script"] = decision.get("notification_body"), decision.get("body_script", "")
        entry["expected_target"] = decision.get("expected_target", "")
        entry["stance"] = decision.get("stance", "ask")   # what it wanted; is_give reads this
        entry["target_revealed"] = decision.get("target_revealed", True)
        if decision.get("volley"):
            # the reply judge walks this queue deterministically (knock_reply.py)
            entry["volley"] = decision["volley"]
            entry["volley_next"] = 1
        if audio_url:
            entry["audio_url"] = audio_url
            entry["memo_script"] = decision.get("memo_script", "")  # the judge reads what was heard
        if mp3:
            entry["mp3"] = str(mp3.relative_to(BASE))
    klog.append(entry)
    KNOCK_LOG_PATH.write_text(json.dumps(klog, ensure_ascii=False, indent=2), encoding="utf-8")
    return KNOCK_LOG_PATH


def main():
    ap = argparse.ArgumentParser(description="The tutor's agentic between-session outreach")
    ap.add_argument("--dry-run", action="store_true",
                    help="gate + decide + render only; no commit, push, or notification")
    ap.add_argument("--force", action="store_true",
                    help="skip the rails gate entirely — waking hours, cap, gaps (manual one-off)")
    args = ap.parse_args()

    load_env(BASE / ".env")

    should_wake, reason = rails_gate(args.force)
    if not should_wake:
        print(f"[rails] skip — {reason}")
        return
    print(f"[rails] wake — {reason}")

    now = datetime.now(timezone.utc)
    print("1. digest…")
    digest = build_digest()
    print(f"2. {TUTOR} decides…")
    decision = decide(digest, volley_targets())
    print(f"   → act={decision.get('act')} modality={decision['modality']} "
          f"move={decision.get('move')!r} next_check={decision['next_check_hours']}h")
    print(f"   rationale: {decision.get('rationale')}")

    acting = bool(decision.get("act")) and decision["modality"] != "silence"

    if not acting:
        print(f"   {TUTOR} chose silence.")
        if args.dry_run:
            print("[dry-run] would log the silence + next_check; stopping.")
            return
        # A silence reaches nobody, but its log entry still commits (and chat.md
        # follows the log through `publish`).
        commit_and_push(*publish(
            [log_decision(now, decision, acted=False),
             maybe_enqueue_schedule(decision)],
            f"Knock: silence ({decision.get('rationale','')[:50]})"))
        print("done — silence logged, next_check set.")
        return

    # The body is READ; memo_script is SPOKEN and keeps the voice form. The draft
    # rides as `body_script`: exact evidence of what the knock showed, which the
    # reveal check and the ask counts read.
    decision["body_script"] = decision.get("notification_body", "")
    decision["notification_body"] = body = to_read_form(decision["body_script"])
    mp3 = audio_url = None
    if decision["modality"] in ("audio", "eavesdrop", "fielding"):
        print("3. render…")
        mp3 = KNOCKS_DIR / f"knock_{now.strftime('%Y-%m-%dT%H-%M')}.mp3"
        # fielding speaks in the family voice too — the question comes AT the learner
        voice = (EAVESDROP_VOICE or TUTOR_VOICE) if decision["modality"] in ("eavesdrop", "fielding") else TUTOR_VOICE
        asyncio.run(render_memo(decision.get("memo_script", ""), mp3, voice))
        audio_url = jsdelivr_url(mp3)

    print("\n--- notification body ---\n" + body + "\n")
    if over_budget(body):
        print(f"   ⚠ body is {len(body)} chars (budget {BODY_BUDGET}) — the lock screen will cut it")

    if args.dry_run:
        print(f"[dry-run] would push ({decision['modality']}) + log; stopping.", mp3 or "")
        return

    # LOG and EXPOSURE are this lane's; the shared tail is `publish`'s.
    path = log_decision(now, decision, acted=True, audio_url=audio_url, mp3=mp3)
    from lexicon_view import expose
    exposed = expose(knock_exposures(decision), decision["modality"],
                     source=f"knock:{now.isoformat()}", taught=decision.get("introduces") or [])
    print("4. commit + push…")
    commit_and_push(*publish(
        [path, LEXICON_PATH if exposed else None,
         maybe_enqueue_schedule(decision)],
        f"Knock ({decision['modality']}/{decision.get('move')})", mp3=mp3))
    print("5. notify…")
    push_to_phone(body, audio_url, knock_id=now.isoformat())
    print("\ndone — reached out & logged.")


if __name__ == "__main__":
    main()
