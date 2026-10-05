#!/usr/bin/env python3
"""Scheduled pushes — the durable "ping me at X" layer of the tutor's outreach.

The knock decides WHETHER to reach out; this queue delivers pushes already
decided on, at a chosen TIME. Entries are fully composed at add-time (no model
call at fire time), live in progress/push_queue.json on main, and are drained at
the start of every wake-up — whoever gets there first; the queue is the single
source of truth.

COMPOSED at add-time is not RENDERED at add-time: an entry carrying `memo_script`
is a VOICE dose whose words are frozen when written and whose TTS runs in the
drain, off the reply path where the learner is waiting at the lock screen.

Every fired entry is logged into knock_log.json exactly like a knock, so a reply
is judged against its expected_target and the rails SEE scheduled pushes.

Quiet hours: a non-forced entry due in the sleep window waits for the first
waking tick. --force marks a ping the learner asked for (the rails protect
against UNrequested pushes, not requested ones).

  python scripts/push_queue.py add --in 60 --body "<line>" --expected-target "<key>" [--force]
  python scripts/push_queue.py add --at 2026-07-02T08:15 --body "..."
  python scripts/push_queue.py list
  python scripts/push_queue.py drain [--dry-run]
  python scripts/push_queue.py cancel <id>

Secrets: PUSH_WEBHOOK_URL (delivery); TTS credentials only when a due entry
carries a memo_script. No model key needed.
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from memo import render_memo
from publish import (KNOCKS_DIR, commit_and_push, jsdelivr_url,
                     load_env, publish, push_to_phone)
from rails import MAX_REACHES_PER_DAY, in_waking_window, reaches_today
from state_io import KNOCK_LOG_PATH, LOCAL_TZ, load_json
from pack import TUTOR_VOICE

QUEUE_PATH = BASE / "progress" / "push_queue.json"


def save_queue(queue: list):
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_due(at: str | None, in_minutes: float | None) -> datetime:
    """--in N minutes, or --at as 'HH:MM' (today local; tomorrow if past),
    'YYYY-MM-DDTHH:MM' (local), or full ISO with offset. Returns aware UTC."""
    now = datetime.now(timezone.utc)
    if in_minutes is not None:
        return now + timedelta(minutes=in_minutes)
    if not at:
        raise SystemExit("Need --at or --in.")
    if ":" in at and "T" not in at and "-" not in at:  # bare HH:MM
        h, m = map(int, at.split(":"))
        local = now.astimezone(LOCAL_TZ).replace(hour=h, minute=m, second=0, microsecond=0)
        if local < now.astimezone(LOCAL_TZ):
            local += timedelta(days=1)
        return local.astimezone(timezone.utc)
    dt = datetime.fromisoformat(at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc)


def needs_render(entry: dict) -> bool:
    """A voice dose that hasn't been rendered yet. `audio_url` already set means
    a local session handed over a finished mp3 — nothing to do."""
    return bool(entry.get("memo_script")) and not entry.get("audio_url")


def render_entry(entry: dict) -> Path | None:
    """Render a queued voice dose to a tracked mp3 and fill in its `audio_url`;
    the mp3 path to commit, or None. A render failure must not swallow the dose:
    the text still fires, and the log records that the voice was lost."""
    if not needs_render(entry):
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    mp3 = KNOCKS_DIR / f"queued_{entry['id']}_{stamp}.mp3"
    try:
        asyncio.run(render_memo(entry["memo_script"], mp3, TUTOR_VOICE))
    except Exception as exc:                       # noqa: BLE001 — text must still fire
        print(f"  ⚠ {entry['id']}: TTS failed ({exc}) — firing the text without voice")
        entry["render_failed"] = str(exc)[:200]
        return None
    entry["audio_url"] = jsdelivr_url(mp3)
    return mp3


def enqueue(body: str, due: datetime, *, expected_target: str = "",
            target_revealed: bool = True, audio_url: str | None = None,
            memo_script: str = "", move: str = "scheduled push",
            force: bool = False, body_script: str = "") -> dict:
    """Append one composed push to the queue (no commit — callers own that, so a
    knock/judge run can land the queue write in its existing commit).

    `memo_script` makes it a VOICE dose: the drain renders it at fire time and
    fills `audio_url` itself. `audio_url` stays available for an already-rendered
    mp3 (a local session can hand one over pre-made)."""
    entry = {
        "id": f"q{int(time.time())}",
        "due": due.astimezone(timezone.utc).isoformat(),
        "body": body, "body_script": body_script or "",
        "expected_target": expected_target or "",
        "target_revealed": bool(target_revealed),
        "audio_url": audio_url or None,
        "memo_script": memo_script or "",
        "move": move,
        "force": bool(force),
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    queue = load_json(QUEUE_PATH) or []
    queue.append(entry)
    queue.sort(key=lambda e: e["due"])
    save_queue(queue)
    local = due.astimezone(LOCAL_TZ)
    print(f"Queued {entry['id']} → fires {local:%Y-%m-%d %H:%M %Z}"
          + ("" if entry["force"] or in_waking_window(due)
             else "  (quiet hours — will defer to the next waking tick)"))
    return entry


def maybe_enqueue_schedule(decision: dict) -> Path | None:
    """If a decision or verdict planted a scheduled push, land it in the queue
    (a voice dose keeps its `memo_script`); it fires on the next wake-up. Returns
    the queue path for the commit, or None. The knock, the judge and the message
    lane all call this — the queue owns its own write."""
    s = decision.get("schedule")
    if not isinstance(s, dict) or not s.get("at_local") or not s.get("body"):
        return None
    try:
        due = datetime.fromisoformat(s["at_local"])
        if due.tzinfo is None:
            due = due.replace(tzinfo=LOCAL_TZ)
    except ValueError:
        print(f"   ! schedule.at_local unparseable ({s.get('at_local')!r}) — dropped")
        return None
    if due <= datetime.now(timezone.utc):
        print(f"   ! schedule.at_local is in the past ({s['at_local']}) — dropped")
        return None
    # The planted body is drafted in the voice form like every knock body, so its
    # read form is made HERE, inside a model-backed lane — the drain fires with
    # zero model calls by design. The draft rides as body_script.
    from writer import to_read_form
    enqueue(to_read_form(s["body"], label="scheduled body"), due, body_script=s["body"],
            expected_target=s.get("expected_target", ""),
            target_revealed=bool(s.get("target_revealed", True)),
            memo_script=(s.get("memo_script") or "").strip(),
            move=s.get("move", "scheduled follow-up"))
    return QUEUE_PATH


def cmd_add(args):
    due = parse_due(args.at, getattr(args, "in"))
    entry = enqueue(args.body, due, expected_target=args.expected_target,
                    target_revealed=args.target_revealed, audio_url=args.audio_url,
                    memo_script=args.memo_script, move=args.move, force=args.force)
    if not args.no_commit:
        local = due.astimezone(LOCAL_TZ)
        commit_and_push([QUEUE_PATH], f"Queue push {entry['id']} for {local:%m-%d %H:%M}")


def cmd_list(_args):
    queue = load_json(QUEUE_PATH) or []
    if not queue:
        print("Queue empty.")
        return
    for e in queue:
        local = datetime.fromisoformat(e["due"]).astimezone(LOCAL_TZ)
        flags = "".join([" ⚡force" if e.get("force") else "",
                         " 🎧" if e.get("audio_url") else "",
                         " 🎙" if needs_render(e) else ""])
        print(f"  {e['id']} · {local:%m-%d %H:%M %Z} · {e.get('move','')}{flags}\n"
              f"      {e['body'][:90]}")


def cmd_cancel(args):
    queue = load_json(QUEUE_PATH) or []
    kept = [e for e in queue if e["id"] != args.id]
    if len(kept) == len(queue):
        print(f"No entry {args.id}.")
        return
    save_queue(kept)
    print(f"Cancelled {args.id}.")
    if not args.no_commit:
        commit_and_push([QUEUE_PATH], f"Cancel queued push {args.id}")


def cmd_drain(args):
    """Fire everything due. Non-forced entries also need the waking window and
    room under the daily reach cap — otherwise they stay queued and fire on the
    first eligible tick (deferred, never dropped)."""
    queue = load_json(QUEUE_PATH) or []
    if not queue:
        print("Queue empty — nothing to drain.")
        return
    now = datetime.now(timezone.utc)
    klog = load_json(KNOCK_LOG_PATH) or []
    # count today's reaches the same way the rails do
    n_today = reaches_today(klog, now.astimezone(LOCAL_TZ).date())

    fired, kept = [], []
    non_forced_fired = False
    for e in queue:
        due = datetime.fromisoformat(e["due"])
        if due > now:
            kept.append(e)
            continue
        if not e.get("force") and not in_waking_window(now):
            kept.append(e)
            print(f"  {e['id']} due but quiet hours — deferred.")
            continue
        if not e.get("force") and n_today >= MAX_REACHES_PER_DAY:
            kept.append(e)
            print(f"  {e['id']} due but daily cap ({n_today}/{MAX_REACHES_PER_DAY}) — deferred.")
            continue
        if not e.get("force") and non_forced_fired:
            # One non-forced fire per drain: two doses in one minute reads as spam.
            kept.append(e)
            print(f"  {e['id']} due but another non-forced push already fired this tick — deferred to next tick.")
            continue
        fired.append(e)
        n_today += 1
        if not e.get("force"):
            non_forced_fired = True

    if not fired:
        print("Nothing eligible to fire.")
        return

    for e in fired:
        voice = " 🎙 render" if needs_render(e) else ""
        print(f"  fire {e['id']} · {e.get('move','')}{voice} · {e['body'][:70]}")

    if args.dry_run:
        print(f"[dry-run] would fire {len(fired)}, keep {len(kept)}.")
        return

    # Render, then COMMIT the mp3s alone before any notification: the CDN serves
    # only paths on main. A separate commit keeps the retry property — a failed
    # push leaves the entry queued against an mp3 already published. The feed
    # rebuild belongs with the knock-log write below.
    rendered = [p for p in (render_entry(e) for e in fired) if p is not None]
    if rendered and not args.no_commit:
        commit_and_push(rendered,
                        f"Scheduled voice dose rendered ({', '.join(e['id'] for e in fired if e.get('memo_script'))})")

    for e in fired:
        # per-entry stamp, not the batch's `now` — it doubles as the reply
        # correlation id, so same-tick fires must never share one
        fired_at = datetime.now(timezone.utc).isoformat()
        # `force` is the learner asking for it — the chokepoint's exemption.
        push_to_phone(e["body"], e.get("audio_url"), knock_id=fired_at,
                      requested=bool(e.get("force")))
        klog.append({
            "date": now.date().isoformat(),
            "timestamp": fired_at,
            "acted": True,
            "scheduled": True,
            "queue_id": e["id"],
            "modality": "audio" if e.get("audio_url") else "text",
            "move": e.get("move", "scheduled push"),
            "rationale": f"scheduled at {e['queued_at'][:16]} for {e['due'][:16]}",
            "body": e["body"], "body_script": e.get("body_script", ""),
            "expected_target": e.get("expected_target", ""),
            "target_revealed": bool(e.get("target_revealed", True)),
            # the reply judge reads what was HEARD, exactly as for an audio knock
            **({"audio_url": e["audio_url"]} if e.get("audio_url") else {}),
            **({"memo_script": e["memo_script"]} if e.get("memo_script") else {}),
        })

    KNOCK_LOG_PATH.write_text(json.dumps(klog, ensure_ascii=False, indent=2), encoding="utf-8")
    save_queue(kept)
    # A revealed target is a declared exposure, stamped at the seam that fired it.
    from state_io import LEXICON_PATH
    from lexicon_view import expose
    exposed = expose([e["expected_target"] for e in fired
                      if e.get("expected_target") and e.get("target_revealed", True)],
                     "knock", source=f"queue:{','.join(e['id'] for e in fired)}")
    if not args.no_commit:
        # feed=True with no mp3: the mp3s went out above, but the rebuild
        # belongs after the knock-log write (publish.publish owns the order).
        commit_and_push(*publish(
            [QUEUE_PATH, KNOCK_LOG_PATH, LEXICON_PATH if exposed else None],
            f"Scheduled push fired ({', '.join(e['id'] for e in fired)})", feed=True))
    print(f"done — fired {len(fired)}, {len(kept)} still queued.")


def main():
    ap = argparse.ArgumentParser(description="The tutor's scheduled-push queue")
    sub = ap.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="queue a push")
    add.add_argument("--at", help="fire time: HH:MM (local), YYYY-MM-DDTHH:MM (local), or ISO+offset")
    add.add_argument("--in", type=float, dest="in", help="fire in N minutes")
    add.add_argument("--body", required=True, help="the notification line (the whole dose)")
    add.add_argument("--expected-target", default="", help="lexicon word/chunk/frame a good reply fires")
    # One default for every reader: True, the conservative end (caps credit at
    # hinted), so an unstated flag can never over-credit.
    add.add_argument("--target-revealed", action=argparse.BooleanOptionalAction,
                     default=True,
                     help="the body shows the target (reply caps at hinted). "
                          "Default true; --no-target-revealed lets a reply score cold.")
    add.add_argument("--audio-url", default="", help="optional already-rendered mp3 URL")
    add.add_argument("--memo-script", default="",
                     help="spoken words for a VOICE dose — the drain renders it at fire time")
    add.add_argument("--move", default="scheduled push", help="2-4 word label for the log")
    add.add_argument("--force", action="store_true",
                     help="the learner asked for this — fire even in quiet hours / over the cap")
    add.add_argument("--no-commit", action="store_true")
    add.set_defaults(func=cmd_add)

    ls = sub.add_parser("list", help="show the queue")
    ls.set_defaults(func=cmd_list)

    cancel = sub.add_parser("cancel", help="remove a queued push")
    cancel.add_argument("id")
    cancel.add_argument("--no-commit", action="store_true")
    cancel.set_defaults(func=cmd_cancel)

    drain = sub.add_parser("drain", help="fire everything due (CI tick / local)")
    drain.add_argument("--dry-run", action="store_true")
    drain.add_argument("--no-commit", action="store_true")
    drain.set_defaults(func=cmd_drain)

    args = ap.parse_args()
    load_env(BASE / ".env")
    args.func(args)


if __name__ == "__main__":
    main()
