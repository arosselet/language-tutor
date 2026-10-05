#!/usr/bin/env python3
"""The MESSAGE lane — the learner talking TO the tutor, not answering a knock.

Reached from knock_reply.py when the phone says `intent=message` and no
`knock_id` came with it. Nothing here grades: no axes, no chains, no volley, no
reveal caps. The job is to DO the thing asked. Without this lane a request typed
cold is graded as a reply to whatever knock happens to be open, and `chat` — a
correct and useless verdict — becomes the place requests go to die.

The last fired knock is a THREAD ANCHOR only: the exchange is appended to it
(tagged `intent: "message"`) so the chat record and `recent_exchanges` stay one
continuous conversation. This lane never sets `response`, `reply` or
`reply_verdict` on it — a nudge gate that believed a message answered a knock
would go quiet on outreach the learner never got.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

from mandates import (FORCE_SCHEDULE_ADDENDUM, FORCE_VOICE_ADDENDUM,
                      MESSAGE_MANDATE, REACH_MANDATE, THREAD_MANDATE,
                      VOICE_MANDATE)
from push_queue import maybe_enqueue_schedule
from publish import commit_and_push, load_env, publish, push_to_phone
from reply_common import (ensure_voice, recent_exchanges, record_meta_note,
                          speak, wants_scheduled_push)
from state_io import FEEDBACK_LOG_PATH, KNOCK_LOG_PATH, load_json, save_json
from pack import LEARNER
from writer import STR, ask_json, executor_name, obj, voice_canon

# Declared beside the lane that reads it. `schedule` is absent on purpose:
# obj() makes everything it names REQUIRED, which would force one onto every
# plain "thanks".
MESSAGE_SCHEMA = obj(reply_line=STR, meta_note=STR, rationale=STR, voice_reply=STR)


def judge_message(text: str, knock: dict, klog: list,
                  force_voice: bool = False, force_schedule: bool = False) -> dict:
    """The tutor reading a message. Same persona, same thread, no grading mandate."""
    canon = voice_canon()
    context = {"learner_said": text,
               "prior_exchanges": recent_exchanges(klog, knock) if knock else []}
    print(f"   [message] {executor_name()}")
    mandate = (MESSAGE_MANDATE + "\n" + VOICE_MANDATE + "\n" + REACH_MANDATE
               + "\n" + THREAD_MANDATE
               + (FORCE_VOICE_ADDENDUM if force_voice else "")
               + (FORCE_SCHEDULE_ADDENDUM if force_schedule else ""))
    d = ask_json(canon + "\n\n---\n\n" + mandate,
                 json.dumps(context, ensure_ascii=False, indent=2),
                 MESSAGE_SCHEMA, answer_tokens=900 if force_voice else 700)
    d["reply_line"] = (d.get("reply_line") or "").strip()
    d["meta_note"] = (d.get("meta_note") or "").strip()
    d["voice_reply"] = (d.get("voice_reply") or "").strip()
    return d


def handle_message(text: str, knock: dict | None, klog: list, dry_run: bool):
    """Answer, and act. A direct audio ask and a clock-bound ask each get one
    forced re-ask and then a LOUD ledger note: this lane has no verdict to fall
    back on, so an unanswered request would otherwise leave no trace."""
    print("1. MESSAGE — not a rep, nothing graded")
    verdict = judge_message(text, knock, klog)
    print(f"   → {verdict.get('rationale', '')}")

    verdict = ensure_voice(verdict, text,
                           lambda: judge_message(text, knock, klog, force_voice=True))

    if wants_scheduled_push(text) and not verdict.get("schedule"):
        print("   ⏰ time-bound request with no schedule — re-asking once, forced…")
        forced = judge_message(text, knock, klog, force_schedule=True)
        if forced.get("schedule"):
            verdict = forced
            print(f"   → scheduled: {forced['schedule'].get('at_local')}")
        else:
            print("   ⚠ still no schedule — logging the miss to the ledger")
            verdict["meta_note"] = (verdict.get("meta_note") or "").strip() or (
                f"MISSED SCHEDULE: {LEARNER} asked for something at a time "
                f"({text[:80]!r}) in a MESSAGE and no push was queued.")

    if dry_run:
        spoken = verdict.get("voice_reply") or ""
        print(f"[dry-run] would push: {verdict['reply_line']}"
              + (f"\n[dry-run] would speak: {spoken}" if spoken else ""))
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if knock is not None:
        # Thread anchor only; `intent` keeps this out of every rep count.
        knock.setdefault("exchanges", []).append(
            {"at": now, "reply": text, "intent": "message", "verdict": "chat",
             "fired": [], "reply_line": verdict["reply_line"]})
        save_json(KNOCK_LOG_PATH, klog)

    voice_url, vmp3 = speak(verdict, knock, klog) if knock is not None else (None, None)
    meta = record_meta_note(verdict)

    print("2. commit + push…")
    commit_and_push(*publish(
        [KNOCK_LOG_PATH, FEEDBACK_LOG_PATH if meta else None,
         maybe_enqueue_schedule(verdict)],
        "Message: answered" + (" (aloud)" if voice_url else ""),
        mp3=vmp3 if voice_url else None))
    print("3. push back…")
    # NO knock_id: it is judging correlation, and a reply to THIS notification
    # must come back to this lane, not be graded against the anchor knock.
    push_to_phone(verdict["reply_line"], voice_url, knock_id="", requested=True)
    print(f"done — message answered{' (aloud 🎧)' if voice_url else ''}.")


def main():
    parser = argparse.ArgumentParser(description="Answer a message from the learner")
    parser.add_argument("text")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_env()
    klog = load_json(KNOCK_LOG_PATH) or []
    fired = [k for k in klog if k.get("acted", True)]
    handle_message(args.text, fired[-1] if fired else None, klog, args.dry_run)


if __name__ == "__main__":
    main()
