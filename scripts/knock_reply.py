#!/usr/bin/env python3
"""The reply half of the knock loop — the micro-session on the lock screen.

The learner types a reply into the knock notification; the receiver routes it
here (the tutor workflow). The tutor judges the reply against what that knock
asked for, moves the production axis, and pushes one line back — the recast (or
the celebration) plus a count of today's fires. An EAVESDROP knock takes its own
lane: the reply is a drift answer, judged for comprehension, and moves the
RECOGNITION axis.

Judge philosophy: the recast across the table, not an exam. Generous in spirit,
honest on the axis — each fired word graded on its OWN merits — and Python
re-enforces the one hard rule per word: target language the notification SHOWED
scores at most "hinted"; "cold" is unaided production only. The release valve: a
cold-quality fire the reveal window blocks is recorded CAPPED, and capped fires
on GRADUATION_DAYS distinct local days graduate the word to cold, or a word knocked
on daily could never escape hinted through the channel drilling it.

The routing is deterministic: a sort-tape answer (numbers) goes to render_sort; an
untagged message to the message lane unless it answers the open ask; an eavesdrop
knock to the catch judge; everything else to the production judge.

  python scripts/knock_reply.py "<reply>"            # judge, write state, commit+push, notify
  python scripts/knock_reply.py --dry-run "<reply>"  # judge + print only (no writes)

The tutor may answer ALOUD when the sound IS the answer (`voice_reply`), rationed
by the mandate because the render costs a wait at the lock screen.

Secrets: OPENROUTER_API_KEY (when no local agent), PUSH_WEBHOOK_URL, TTS
credentials (only when answering aloud).
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import lexicon_view
from observations import CATCH_RESULT, FIRE_RESULT, HEARD_RESULT


BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from knock_message import handle_message
import render_sort
from push_queue import maybe_enqueue_schedule
from publish import commit_and_push, load_env, publish, push_to_phone
# The lane-neutral half of answering (shared with the message lane).
from reply_common import (_ts, ensure_voice, recent_exchanges,
                          record_meta_note, speak, wants_scheduled_push)
from pack import LEARNER
from writer import (BOOL, STR, arr, ask_json, executor_name, nullable, obj,
                    to_read_form, voice_canon)

# Each judge declares its OWN top-level shape, beside itself. If a mandate names
# a key, the schema MUST name it too: the agent path DROPS undeclared keys, and a
# dropped `voice_reply` reads exactly like a decision not to speak.
JUDGE_SCHEMA = obj(verdict=STR, fired=arr(word=STR, said=STR, verdict=STR),
                   reply_line=STR, follow_up_ask=STR, follow_up_target=STR,
                   follow_up_target_revealed=BOOL, meta_note=STR, rationale=STR,
                   voice_reply=STR,
                   slips=arr(tag=STR, said=STR, want=STR, note=STR),
                   # Only this lane's mandate offers a scheduled dose a voice.
                   schedule=nullable(obj(
                       at_local=STR, body=STR, memo_script=STR, expected_target=STR,
                       target_revealed=BOOL, move=STR)))
CATCH_SCHEMA = obj(verdict=STR, reply_line=STR, meta_note=STR, rationale=STR,
                   voice_reply=STR,
                   # Same shape as `fired`: name a key, quote the span, rule on it.
                   heard=arr(key=STR, said=STR, verdict=STR))
from state_io import PRODUCTION_RANK  # L0 owns the ladders
from state_io import FEEDBACK_LOG_PATH, KNOCK_LOG_PATH, LEARNER_PATH, LEXICON_PATH, SLIP_LOG_PATH, load_json, local_today, resolve, save_json
from slips import append_slips, slip_patterns
from sync_state import fires_today

from mandates import (CATCH_JUDGE_MANDATE, FORCE_SCHEDULE_ADDENDUM, JUDGE_MANDATE,
                      FORCE_VOICE_ADDENDUM, OPEN_ASK_MANDATE, REACH_MANDATE,
                      SLIP_MANDATE, THREAD_MANDATE, VOICE_MANDATE)


VERDICTS = {"cold", "hinted", "miss", "chat"}
CHAIN_CAP = 3  # max chained follow-up asks per knock — momentum, not a treadmill

CATCH_VERDICTS = {"caught", "half-caught", "missed", "chat"}








def catch_context(knock: dict, reply_text: str, klog: list | None = None) -> dict:
    """What the drift judge is shown — testable without the model call. The
    thread is included so a later turn knows the drift was already caught."""
    context = {
        "tape_memo_script": knock.get("memo_script", ""),
        "drift_question": knock.get("body", ""),
        "ear_only_target": knock.get("expected_target", ""),
        "learner_reply": reply_text,
    }
    prior = recent_exchanges(klog if klog is not None else [knock], knock)
    if prior:
        context["prior_exchanges"] = prior
    return context


def judge_catch(knock: dict, reply_text: str, klog: list | None = None,
                force_voice: bool = False) -> dict:
    """The comprehension judge for an eavesdrop dose — a deliberately separate,
    smaller mandate so the production judge's rules (reveal caps, chains,
    per-word grades) never leak into a drift grade."""
    canon = voice_canon()
    context = catch_context(knock, reply_text, klog)
    print(f"   [catch judge] {executor_name()}")
    # Both judges can answer aloud: which judge runs must not decide whether
    # the tutor has a voice.
    d = ask_json(canon + "\n\n---\n\n" + CATCH_JUDGE_MANDATE + "\n" + THREAD_MANDATE
                 + "\n" + VOICE_MANDATE + (FORCE_VOICE_ADDENDUM if force_voice else ""),
                 json.dumps(context, ensure_ascii=False, indent=2),
                 CATCH_SCHEMA, answer_tokens=700 if force_voice else 550)
    if d.get("verdict") not in CATCH_VERDICTS:
        d["verdict"] = "chat"
    d["reply_line"] = (d.get("reply_line") or "").strip()
    d["meta_note"] = (d.get("meta_note") or "").strip()
    d["voice_reply"] = (d.get("voice_reply") or "").strip()
    return d


def apply_catch_verdict(verdict: dict, knock: dict, lexicon: dict) -> list[str]:
    """The dose's declared ear target, judged: one `tested` event on the
    recognition axis — caught climbs a rung, missed falls one, half-caught is
    recorded and moves nothing. `chat` is not a test and records nothing."""
    key = resolve(knock.get("expected_target", ""), lexicon)
    if key is None:
        return [f"! eavesdrop target {knock.get('expected_target')!r} resolves to no lexicon record — not scored"]
    res = CATCH_RESULT.get(verdict["verdict"])
    if res is None:
        return [f"{key}: '{verdict['verdict']}' is not a test of the ear — nothing recorded"]
    before = lexicon[key].get("recognition", "untested")
    lexicon_view.observe([dict(word=key, channel="eavesdrop", kind="tested", axis="recognition",
                               result=res, source=f"knock:{knock.get('timestamp', '')}",
                               note=f"declared target, {verdict['verdict']}")], lexicon=lexicon)
    return [f"{key} tested by ear ({verdict['verdict']}) — recognition {before} → "
            f"{lexicon[key]['recognition'].upper()}"]


def apply_heard_words(verdict: dict, knock: dict, lexicon: dict,
                      reply_text: str) -> list[str]:
    """THE WORDS THE LEARNER PICKS OUT OF THE TAPE. The eavesdrop runs below the
    coverage floor on purpose, so catching two words of eight is the designed
    outcome — and those two are real ear evidence. This does NOT widen the
    grade (the verdict is still the drift); it records a word the learner
    named that the tape actually spoke. Three guards, none optional:
      (1) the key resolves to a real lexicon row,
      (2) the quoted span is ACTUALLY in the reply (`said_in_reply`),
      (3) the key is ACTUALLY in the tape.
    A misread is a `wrong` and moves the rung down, like every other miss."""
    tape = json.dumps(knock.get("memo_script", ""), ensure_ascii=False)
    declared = resolve((knock.get("expected_target") or ""), lexicon)
    lines, events = [], []
    for item in (verdict.get("heard") or []):
        if not isinstance(item, dict):
            continue
        named = (item.get("key") or "").strip()
        said = (item.get("said") or "").strip()
        key = resolve(named, lexicon)
        if key is None:
            lines.append(f"! heard {named!r} resolves to no lexicon record — not scored")
            continue
        if key == declared:
            continue  # apply_catch_verdict already owns the declared target
        if not said_in_reply(said, reply_text):
            lines.append(f"! {key}: judge quoted {said!r}, which is not in the reply — not scored")
            continue
        if key not in tape:
            lines.append(f"! {key}: the tape never said it — not scored")
            continue
        res = HEARD_RESULT.get((item.get("verdict") or "").strip().casefold(), "wrong")
        events.append(dict(word=key, channel="eavesdrop", kind="tested", axis="recognition",
                           result=res, source=f"knock:{knock.get('timestamp', '')}",
                           note=f"named unprompted, {item.get('verdict')}"))
        lines.append(f"{key} named unprompted — {'heard' if res == 'right' else 'MISREAD'}")
    if events:
        lexicon_view.observe(events, lexicon=lexicon)
    return lines


def handle_catch_reply(knock: dict, reply_text: str, klog: list,
                       lexicon: dict, dry_run: bool):
    """The eavesdrop counterpart of the production flow: judge the drift, move
    recognition, log the exchange in the same shape, push one line back. No
    chains, no volley, no production meters."""
    print(f"1. judging DRIFT reply against eavesdrop knock {knock.get('timestamp', '?')[:16]}…")
    verdict = judge_catch(knock, reply_text, klog)
    print(f"   → {verdict['verdict']} | {verdict.get('rationale', '')}")
    verdict = ensure_voice(verdict, reply_text, lambda: judge_catch(
        knock, reply_text, klog, force_voice=True))

    if dry_run:
        print(f"[dry-run] would apply, then push: {verdict['reply_line']}")
        return

    print("2. state…")
    for line in apply_catch_verdict(verdict, knock, lexicon):
        print(f"   {line}")
    for line in apply_heard_words(verdict, knock, lexicon, reply_text):
        print(f"   {line}")

    knock["response"] = "reply"
    knock["reply"] = reply_text
    knock["reply_verdict"] = verdict["verdict"]
    # The same read-surface law as every push-back: the lock screen gets the
    # read form, and the draft rides as `reply_line_script`.
    knock["reply_line_script"] = verdict["reply_line"]
    knock["reply_line"] = to_read_form(verdict["reply_line"], label="catch push-back")
    knock["reply_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    knock.setdefault("exchanges", []).append({
        "at": knock["reply_at"], "reply": reply_text,
        "verdict": verdict["verdict"], "fired": [],
        "reply_line": knock["reply_line"], "reply_line_script": knock["reply_line_script"],
    })
    save_json(LEXICON_PATH, lexicon)
    save_json(KNOCK_LOG_PATH, klog)

    voice_url, vmp3 = speak(verdict, knock, klog)
    meta = record_meta_note(verdict)

    print("3. commit + push…")
    # The line only — no meter tail: a fraction recited on the lock screen is a
    # scoreboard. `requested`: an answer to a reply is not an interruption.
    commit_and_push(*publish(
        [LEXICON_PATH, KNOCK_LOG_PATH, FEEDBACK_LOG_PATH if meta else None],
        f"Knock reply: {verdict['verdict']} (eavesdrop)",
        mp3=vmp3 if voice_url else None))
    print("4. push back…")
    # The LOGGED line, not the draft: the log records what was actually sent.
    push_to_phone(knock["reply_line"], voice_url,
                  knock_id=knock.get("timestamp", ""), requested=True)
    print(f"done — drift judged, catch axis scored, "
          f"answered{' (aloud 🎧)' if voice_url else ''}.")


def last_fired_knock(klog: list) -> dict | None:
    fired = [k for k in klog if k.get("acted", True)]
    return fired[-1] if fired else None


OPEN_ASK_SCHEMA = obj(answers=BOOL)


def answers_the_open_ask(text: str, knock: dict, lexicon: dict) -> bool:
    """Does this line attempt what the open knock asked for? The escalation net
    under the intent tag: an answer is a REP whichever button was pressed. It can
    only pull something INTO grading, never push a request out. A model decides
    (it reads any spelling); a failed call is a MESSAGE, loudly — the safe side."""
    target, _ = current_pin(knock)
    if not target or not text.strip():
        return False
    ask = (f"THE OPEN ASK: {target} — {(lexicon.get(target) or {}).get('gloss', '')}\n"
           f"THE KNOCK: {knock.get('body_script') or knock.get('body', '')}\n\nTHE LEARNER'S LINE: {text}")
    try:
        return bool(ask_json(OPEN_ASK_MANDATE, ask, OPEN_ASK_SCHEMA, answer_tokens=60).get("answers"))
    except Exception as e:
        print(f"   ⚠ open-ask check failed ({type(e).__name__}: {e}) — treating it as a message")
        return False


def is_message(knock_id: str, intent: str, text: str,
               knock: dict | None, lexicon: dict) -> bool:
    """Reply to be judged, or message to be acted on? Deterministic, from the tag
    the phone sends (docs/phone_loop.md):

      knock_id present   → a reply to THAT knock
      intent == "reply"  → a reply to the last fired knock
      otherwise          → a MESSAGE

    Untagged is a message: grading a request costs a refusal and a corrupted
    ledger row, while a rep treated as a message costs one uncredited fire, which
    the open-ask net mostly recovers. It says so, loudly."""
    if knock_id or intent == "reply":
        return False
    if not intent:
        print("   ⚠ no intent tag — assuming message")
    if knock and answers_the_open_ask(text, knock, lexicon):
        print("   ↩ it answers the open ask — grading it as a reply")
        return False
    return True


def find_knock(klog: list, knock_id: str) -> dict | None:
    """The knock a reply belongs to, by its log timestamp (the notification's
    `knock_id`, round-tripped by the receiver). Notifications stack, so answering
    an older one is legal; last-fired is only the fallback for id-less events."""
    if not knock_id:
        return None
    for k in reversed(klog):
        if k.get("acted", True) and k.get("timestamp") == knock_id:
            return k
    return None


def scoreboard(lexicon: dict) -> str:
    """The per-day reward appended to a push-back: fires today, live from the
    logs. A COUNT OF WHAT WAS DONE, never a fraction of what is left or a
    countdown — on the lock screen that is a scoreboard."""
    n = fires_today()
    return f"{n} fired today" if n else ""


def hours_since_exchange(knock: dict, now: datetime) -> float | None:
    """Hours since this knock last spoke — the later of the knock and its last
    judged exchange. The judge decays scenario continuity on it: past ~3h a reply
    is to a lock-screen line, not a continuing scene."""
    ts = knock.get("reply_at") or knock.get("timestamp")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600


def volley_open_ask(knock: dict) -> str | None:
    """The CURRENT volley ask as 'N/M — <ask>', or None outside a volley. Python
    owns this string: the logged body stays frozen at ask 1 while the pin walks,
    so the raw body would make every later item read as a mis-target."""
    vq = knock.get("volley")
    if not vq:
        return None
    cur = min(knock.get("volley_next", 1), len(vq))
    return f"{cur}/{len(vq)} — {vq[cur - 1]['ask']}"











def judge(knock: dict, reply_text: str, target_record: dict | None,
          hours_since: float | None = None,
          revealed_recent: list | None = None,
          force_schedule: bool = False,
          force_voice: bool = False,
          klog: list | None = None) -> dict:
    canon = voice_canon()
    pin, pin_revealed = current_pin(knock)
    open_ask = volley_open_ask(knock)
    context = {
        "knock": {
            "modality": knock.get("modality"),
            "move": knock.get("move"),
            "notification_body": f"volley {open_ask}" if open_ask else knock.get("body", ""),
            "memo_script": knock.get("memo_script", ""),
            "expected_target": pin,
            "target_revealed": pin_revealed,
        },
        "hours_since_last_exchange": round(hours_since, 1) if hours_since is not None else None,
        "expected_target_lexicon_record": target_record,
        "revealed_recently": revealed_recent or [],
        "learner_reply": reply_text,
        # Tags on the ledger (live AND retired-unverified), so the judge reuses
        # one instead of coining a synonym — counting is by exact string, and a
        # returning pattern is only visible under its old tag.
        "slip_tags_in_use": [
            {"tag": p["tag"], "seen": p["count"], "means": p["notes"][-1] if p["notes"] else "",
             "state": "live" if p["live"] else "retired — reuse this tag if it returns"}
            for p in slip_patterns() if p["live"] or p["unverified"]][:12],
    }
    if knock.get("volley"):
        context["knock"]["volley_in_progress"] = (
            f"item {min(knock.get('volley_next', 1), len(knock['volley']))} of {len(knock['volley'])}")
    # The recent thread across knocks, with what the tutor DID. Reveals are judged
    # by revealed_recent/shown_in_knock, which are Python-owned.
    prior = recent_exchanges(klog if klog is not None else [knock], knock)
    if prior:
        context["prior_exchanges"] = prior
    mandate = (JUDGE_MANDATE + "\n" + SLIP_MANDATE + "\n" + REACH_MANDATE
               + "\n" + THREAD_MANDATE + "\n" + VOICE_MANDATE
               + (FORCE_SCHEDULE_ADDENDUM if force_schedule else "")
               + (FORCE_VOICE_ADDENDUM if force_voice else ""))
    # 1600 is what the ARTIFACT needs; the thinking room belongs to the model
    # (`writer.budget`), never to a call site.
    print(f"   [judge] {executor_name()}")
    d = ask_json(canon + "\n\n---\n\n" + mandate,
                 json.dumps(context, ensure_ascii=False, indent=2),
                 JUDGE_SCHEMA, answer_tokens=1600)
    return normalize_verdict(d, reply_text)


_FLATTEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def flatten_for_match(s: str) -> str:
    """Casefold, punctuation → space, runs collapsed: loose enough that a quote
    with a capital and a full stop matches the reply, strict enough that the
    letters must actually be there."""
    return _FLATTEN_RE.sub(" ", (s or "").casefold()).strip()


def said_in_reply(said: str, reply_text: str) -> bool:
    """Did the learner actually type this? The credit-side twin of
    shown_in_knock: without it the judge is free to credit the target it wanted
    rather than the word that was used. Python owns the honesty check, not the
    matching — the judge names the canonical key AND quotes the span (no
    deterministic match survives every spelling); this verifies the span."""
    flat_reply = flatten_for_match(reply_text)
    flat_said = flatten_for_match(said)
    return bool(flat_said) and bool(flat_reply) and flat_said in flat_reply



def normalize_verdict(d: dict, reply_text: str = "") -> dict:
    """Guard the judge's JSON into the shape Python relies on. Each fired item
    carries its own grade; the overall verdict is DERIVED (best word wins), and a
    scored verdict with no fired words degrades to "miss". A fire whose span is
    not in the reply is DROPPED (the word itself counts as its own evidence) and
    lands on d["unverified"], loud in the run log."""
    if d.get("verdict") not in VERDICTS:
        d["verdict"] = "chat"
    fired, unverified = [], []
    for item in d.get("fired", []):
        if isinstance(item, str):  # tolerate the pre-per-word flat shape
            item = {"word": item, "verdict": d["verdict"]}
        if not isinstance(item, dict):
            continue
        w = (item.get("word") or "").strip()
        if not w:
            continue
        said = (item.get("said") or "").strip()
        if reply_text and not (said_in_reply(said, reply_text)
                               or said_in_reply(w, reply_text)):
            unverified.append(f"{w} (claimed {said!r})" if said else f"{w} (no span)")
            continue
        v = item.get("verdict") if item.get("verdict") in ("cold", "capped") else "hinted"
        fired.append({"word": w, "said": said or w, "verdict": v})
    # Slips: the structured error record. Guard the shape here so a judge that
    # returns junk cannot poison the ledger — a tag is mandatory (Python counts
    # by it), everything else is best-effort prose.
    slips = []
    for s in d.get("slips", []) or []:
        if not isinstance(s, dict):
            continue
        tag = (s.get("tag") or "").strip()
        if not tag:
            continue
        slips.append({"tag": tag, "said": (s.get("said") or "").strip(),
                      "want": (s.get("want") or "").strip(),
                      "note": (s.get("note") or "").strip()})
    d["slips"] = slips

    # A word the judge corrected cannot also be a word it credited. Matched on the
    # flattened `want` against both the fired key and the typed span.
    corrected = {flatten_for_match(s["want"]) for s in slips if s["want"]}
    if corrected:
        kept = []
        for item in fired:
            hit = next((c for c in corrected
                        if c and (c == flatten_for_match(item["word"])
                                  or c == flatten_for_match(item["said"]))), None)
            if hit:
                unverified.append(f"{item['word']} (corrected in the same breath — "
                                  f"slipped, not fired)")
                continue
            kept.append(item)
        fired = kept

    d["unverified"] = unverified
    d["fired"] = fired if d["verdict"] in ("cold", "hinted") else []
    if d["fired"]:
        d["verdict"] = ("cold" if any(i["verdict"] == "cold" for i in d["fired"])
                        else "hinted")
    elif d["verdict"] in ("cold", "hinted"):
        d["verdict"] = "miss"
    d["reply_line"] = (d.get("reply_line") or "").strip()
    d["meta_note"] = (d.get("meta_note") or "").strip()
    d["follow_up_ask"] = (d.get("follow_up_ask") or "").strip()
    d["follow_up_target"] = (d.get("follow_up_target") or "").strip()
    d["follow_up_target_revealed"] = bool(d.get("follow_up_target_revealed", True))
    d["voice_reply"] = (d.get("voice_reply") or "").strip()
    d["schedule"] = d.get("schedule") if isinstance(d.get("schedule"), dict) else None
    return d


def shown_in_knock(key: str, knock: dict) -> bool:
    """The hard rule, deterministically: did the knock's own text — or a recast
    already pushed back on this chain — show this key? Shown ⇒ the reply caps at
    'hinted'. The `*_script` drafts are exact; the read surfaces are scanned too,
    because a failed read-form rewrite falls back to the voice form."""
    parts = [knock.get(f, "") for f in ("body", "body_script", "memo_script",
                                        "reply_line", "reply_line_script")]
    parts += [x.get(f, "") for x in knock.get("exchanges", [])
              for f in ("reply_line", "reply_line_script")]
    shown = " ".join(p for p in parts if p).lower()
    return key.lower() in shown


def current_pin(knock: dict) -> tuple[str, bool]:
    """What this knock is asking for RIGHT NOW: the chained pin, else the
    original ask. A chain moves the pin; expected_target stays on record."""
    if knock.get("pinned_target") is not None:
        return knock["pinned_target"], bool(knock.get("pinned_revealed", True))
    return knock.get("expected_target", ""), bool(knock.get("target_revealed", True))


def revealed_recently(klog: list, lexicon: dict, hours: float = 48.0) -> list[str]:
    """Lexicon keys that actually appeared in the last `hours` of knock traffic.
    The judge may deny a cold as "recently handed over" ONLY for these: Python
    owns the evidence of what was shown, never the model's memory."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    texts = []
    for k in klog:
        ts = _ts(k.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        texts += [k.get(f, "") for f in ("body", "body_script", "memo_script", "reply_line", "reply_line_script")]
        texts += [x.get(f, "") for x in k.get("exchanges", []) for f in ("reply_line", "reply_line_script")]
    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return []
    return sorted(key for key in lexicon if key.lower() in blob)


GRADUATION_DAYS = 2  # distinct local days of capped-quality fires that prove a word cold


def capped_fire_days(key: str, klog: list) -> set:
    """Local dates on which `key` fired CAPPED (cold-quality, reveal-blocked) in
    judged knock traffic — the graduation evidence, computed from the log the
    same way revealed_recently() computes reveals (never from model memory)."""
    from state_io import LOCAL_TZ
    days = set()
    for k in klog:
        for x in k.get("exchanges", []):
            dt = _ts(x.get("at")) if key in x.get("fired_capped", []) else None
            if dt is not None:
                days.add(dt.astimezone(LOCAL_TZ).date())
    return days


def apply_verdict(verdict: dict, knock: dict, lexicon: dict, klog: list,
                  revealed_recent: list | None = None,
                  ) -> tuple[list[str], list[str], list[str], list[str]]:
    """Move the production axis for what fired — each word on its OWN grade.
    Upgrades only: a phone rep never demotes. Python resolves every cold/capped
    grade against the computed reveal evidence (a shown "cold" becomes capped; a
    "capped" with no reveal on record becomes cold), and capped fires on
    GRADUATION_DAYS distinct days graduate the word to cold.

    Returns (summary lines, cold-credited keys, capped keys, graduated keys)."""
    today_local = local_today()
    pin, pin_revealed = current_pin(knock)
    revealed_key = resolve(pin, lexicon) if pin_revealed else None
    revealed_recent = revealed_recent or []
    summary, cold_credited, capped_keys, graduated, events = [], [], [], [], []
    for item in verdict["fired"]:
        key = resolve(item["word"], lexicon)
        if key is None:
            summary.append(f"! '{item['word']}' resolves to no lexicon record — not scored")
            continue
        rec = lexicon[key]
        grade = item["verdict"]
        shown = key == revealed_key or shown_in_knock(key, knock)
        if grade == "cold" and shown:
            grade = "capped"  # the hard rule, enforced deterministically per word
        elif grade == "capped" and not (shown or key in revealed_recent):
            grade = "cold"  # the judge invented a reveal — the computed evidence says unaided
        target = grade
        if grade == "capped":
            capped_keys.append(key)
            days = capped_fire_days(key, klog) | {today_local}
            if len(days) >= GRADUATION_DAYS:
                target = "cold"  # graduation: unaided-quality fires across distinct days
                if rec.get("production") != "cold":
                    graduated.append(key)
            else:
                target = "hinted"  # capped rides the hinted rung until it graduates
        if target == "cold":
            cold_credited.append(key)  # a re-fire of an already-cold word still counts as pace
        cur = rec.get("production", "none")
        if PRODUCTION_RANK[target] > PRODUCTION_RANK.get(cur, 0):
            grad = " 🎓 graduated — capped fires on ≥2 days" if key in graduated else ""
            summary.append(f"{key} → {target.upper()}{grad}")
        else:
            summary.append(f"{key} already {cur} — kept ({grade} fire)")
        # Every fired word is a DECLARED production event, any verdict.
        events.append(dict(word=key, channel=knock.get("modality") or "knock", kind="tested",
                           axis="production", result=FIRE_RESULT[target],
                           source=f"knock:{knock.get('timestamp', '')}", note=f"{grade} fire"))
    if events:
        lexicon_view.observe(events, lexicon=lexicon)
    return summary, cold_credited, capped_keys, graduated






def main():
    ap = argparse.ArgumentParser(description="Judge a phone reply to the last knock")
    ap.add_argument("reply", help="the learner's reply text, from the notification")
    ap.add_argument("--dry-run", action="store_true",
                    help="judge + print only; no state writes, commit, or push-back")
    args = ap.parse_args()

    load_env(BASE / ".env")
    reply_text = args.reply.strip()
    if not reply_text:
        print("Empty reply — nothing to judge.")
        return

    klog = load_json(KNOCK_LOG_PATH) or []
    knock_id = os.environ.get("REPLY_KNOCK_ID", "").strip()
    knock = find_knock(klog, knock_id) or last_fired_knock(klog)
    if knock is None:
        print("No fired knock to judge a reply against — logging nothing.")
        return
    if knock_id and knock.get("timestamp") != knock_id:
        print(f"   ⚠ knock_id {knock_id!r} not in the log — falling back to last fired")

    lexicon = load_json(LEXICON_PATH) or {}

    # A SORT TAPE ANSWER IS NUMBERS, parsed by Python — checked before the message
    # test, because it often arrives untagged after another knock has fired.
    sort = render_sort.claim_reply(klog, knock_id, reply_text)
    if sort is not None:
        render_sort.handle_reply(sort, reply_text, klog, lexicon, args.dry_run,
                                 commit=commit_and_push, notify=push_to_phone)
        return

    if is_message(knock_id, os.environ.get("REPLY_INTENT", "").strip().lower(),
                  reply_text, knock, lexicon):
        handle_message(reply_text, knock, klog, args.dry_run)
        return

    if knock.get("modality") == "eavesdrop":
            # Comprehension dose: the CATCH axis, on its own smaller mandate.
        handle_catch_reply(knock, reply_text, klog, lexicon, args.dry_run)
        return

    target, _ = current_pin(knock)
    target_key = resolve(target, lexicon) if target else None
    target_record = None
    if target_key:
        target_record = {"key": target_key,
                         "gloss": lexicon[target_key].get("gloss", "")}

    hours = hours_since_exchange(knock, datetime.now(timezone.utc))
    hours_str = f", {hours:.1f}h since last exchange" if hours is not None else ""
    print(f"1. judging reply against knock {knock.get('timestamp', '?')[:16]} "
          f"({knock.get('modality')}/{knock.get('move')}{hours_str})…")
    revealed = revealed_recently(klog, lexicon)
    verdict = judge(knock, reply_text, target_record, hours, revealed, klog=klog)
    fired_str = ", ".join(f"{i['word']}:{i['verdict']}" for i in verdict["fired"]) or "—"
    print(f"   → {verdict['verdict']} | fired: {fired_str} | {verdict.get('rationale', '')}")
    for claim in verdict.get("unverified", []):
        print(f"   ⚠ dropped — not in the reply: {claim}")

    # The clock-request backstop: one forced re-ask, then a loud ledger note.
    if wants_scheduled_push(reply_text) and not verdict.get("schedule"):
        print("   ⏰ time-bound request with no schedule — re-asking once, forced…")
        forced = judge(knock, reply_text, target_record, hours, revealed,
                       force_schedule=True, klog=klog)
        if forced.get("schedule"):
            verdict = forced
            print(f"   → scheduled: {forced['schedule'].get('at_local')} "
                  f"· {forced['schedule'].get('body', '')[:60]}")
        else:
            print("   ⚠ still no schedule — logging the miss to the ledger")
            verdict["meta_note"] = (verdict.get("meta_note") or "").strip() or (
                f"MISSED SCHEDULE: {LEARNER} asked for something at a time "
                f"({reply_text[:80]!r}) and no push was queued — the judge "
                f"declined twice. Check the schedule lane.")

    verdict = ensure_voice(verdict, reply_text, lambda: judge(
        knock, reply_text, target_record, hours, revealed,
        force_voice=True, klog=klog))

    # Momentum chain: on a scored reply the push-back may carry the NEXT micro-ask,
    # and the pin moves to it. A VOLLEY chains DETERMINISTICALLY instead: Python
    # hands the next item on any judged verdict and ignores the judge's follow_up.
    follow, volley_pin = "", None
    vq = knock.get("volley")
    # `represent`: a deterministic re-present of the still-open ask. `held`: "chat"
    # holds the pin, so one mislabelled answer could re-present an item forever —
    # the hold is capped at ONE re-present, read off Python's own "still open · "
    # prefix on the prior turn (never the verdict, never model memory).
    represent, held = None, "still open · " in ((knock.get("exchanges") or [{}])[-1].get("reply_line") or "")
    if vq:
        # A capped advance keeps "chat": nothing is credited; it only refuses to
        # ask the same question a third time.
        if verdict["verdict"] != "chat" or held:
            nxt = knock.get("volley_next", 1)
            if nxt < len(vq):
                volley_pin = vq[nxt]
                follow = f"{nxt + 1}/{len(vq)} — {volley_pin['ask']}"
            else:
                knock["volley_done"] = True  # last item judged — chain closed
        elif not knock.get("volley_done"):
            # A chat reply mid-volley must never let the open ask vanish.
            represent = f"still open · {volley_open_ask(knock)}"
    elif (verdict["verdict"] in ("cold", "hinted") and verdict["follow_up_ask"]
            and knock.get("chained", 0) < CHAIN_CAP):
        follow = verdict["follow_up_ask"]

    if args.dry_run:
        chain_str = f" ↪ chain: {follow}" if follow else ""
        print(f"[dry-run] would apply, then push: {verdict['reply_line']} · {scoreboard(lexicon)}{chain_str}")
        return

    print("2. state…")
    summary, cold_credited, capped_keys, graduated = apply_verdict(
        verdict, knock, lexicon, klog, revealed)
    for line in summary:
        print(f"   {line}")

    # Top-level reply fields are the LATEST-exchange view; history is `exchanges`.
    knock["response"] = "reply"  # the strongest "landed" signal there is
    knock["reply"] = reply_text
    knock["reply_verdict"] = verdict["verdict"]
    # Accumulated across a chain: fires_today reads reply_fired; the pace meter
    # reads reply_fired_cold (the effective grade after the reveal cap).
    fired_words = [i["word"] for i in verdict["fired"]]
    knock["reply_fired"] = knock.get("reply_fired", []) + fired_words
    knock["reply_fired_cold"] = knock.get("reply_fired_cold", []) + cold_credited
    knock["reply_fired_capped"] = knock.get("reply_fired_capped", []) + capped_keys
    # The FULL push-back (recast + chained ask), in the read form; the draft is
    # kept, because the reveal check reads it exactly.
    knock["reply_line_script"] = " · ".join(p for p in (verdict["reply_line"], follow or represent) if p)
    knock["reply_line"] = to_read_form(knock["reply_line_script"], label="push-back")
    knock["reply_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sched = verdict.get("schedule") or {}
    knock.setdefault("exchanges", []).append({
        "at": knock["reply_at"], "reply": reply_text,
        "verdict": verdict["verdict"], "fired": fired_words,
        "fired_cold": cold_credited, "fired_capped": capped_keys,
        "graduated": graduated, "reply_line": knock["reply_line"],
        "reply_line_script": knock["reply_line_script"],
        "slips": [s["tag"] for s in verdict.get("slips") or []],
        # What the tutor DID this turn, so a later turn can tell a delivered
        # artifact from a promise. `audio_url` is backfilled after the render.
        "spoke": verdict.get("voice_reply") or "",
        "scheduled": " · ".join(v for v in (sched.get("at_local", ""),
                                            sched.get("move", "")) if v),
    })

    # The phone lane's half of the slip ledger: a correction made here reaches
    # the next lesson's selection.
    if verdict.get("slips"):
        learner_now = load_json(LEARNER_PATH) or {}
        from state_io import LOCAL_TZ
        written = append_slips(
            verdict["slips"], lane="knock", modality=knock.get("modality", ""),
            dose_channel=(learner_now.get("soak_order") or {}).get("channel", ""),
            when=datetime.now(timezone.utc).astimezone(LOCAL_TZ).date().isoformat())
        for row in written:
            print(f"   slip: {row['tag']} — “{row['said']}” → “{row['want']}”")
        repeated = {p["tag"]: p for p in slip_patterns() if p["pattern"] and p["live"]}
        for row in written:
            p = repeated.get(row["tag"])
            if p:
                print(f"   ⚠ {p['tag']} is {p['count']}× over {p['span_days']}d "
                      f"— pattern, not a one-off"
                      + ("; NEVER COMMISSIONED" if p["uncommissioned"]
                         else f"; ESCALATE past {p['channels'][0]}" if p["escalate"]
                         else ""))
    if volley_pin is not None:
        # Volley advance is Python's; expected_target stays the first ask.
        knock["chained"] = knock.get("chained", 0) + 1
        knock["volley_next"] = knock.get("volley_next", 1) + 1
        knock["pinned_target"] = volley_pin["target"]
        knock["pinned_revealed"] = False
    elif follow:
        # The chain moves the PIN; expected_target stays the original ask.
        knock["chained"] = knock.get("chained", 0) + 1
        knock["pinned_target"] = verdict["follow_up_target"]
        knock["pinned_revealed"] = verdict["follow_up_target_revealed"]

    save_json(LEXICON_PATH, lexicon)
    save_json(KNOCK_LOG_PATH, klog)

    # Rendered before the commit: the CDN serves only paths already on main.
    voice_url, vmp3 = speak(verdict, knock, klog)

    # Meta-direction lands in the feedback ledger — the diagnosis pass reads it.
    meta = record_meta_note(verdict)

    print("3. commit + push…")
    score = scoreboard(lexicon)
    body = " · ".join(p for p in (knock["reply_line"], score) if p)
    if len(body) > 240:
        print(f"   ⚠ push-back is {len(body)} chars — the lock screen will cut the tail (chained ask at risk)")
    # The slip ledger is written on the runner; unpushed it dies with it.
    commit_and_push(*publish(
        [LEXICON_PATH, KNOCK_LOG_PATH,
         SLIP_LOG_PATH if verdict.get("slips") else None,
         FEEDBACK_LOG_PATH if meta else None,
         maybe_enqueue_schedule(verdict)],
        f"Knock reply: {verdict['verdict']} ({', '.join(fired_words) or 'no fire'})",
        mp3=vmp3 if voice_url else None))
    print("4. push back…")
    push_to_phone(body, voice_url, knock_id=knock.get("timestamp", ""), requested=True)
    print(f"done — reply judged, scored, answered{' (aloud 🎧)' if voice_url else ''}.")


if __name__ == "__main__":
    main()
