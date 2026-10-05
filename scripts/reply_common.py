#!/usr/bin/env python3
"""What every inbound-message lane needs, whichever lane grades it: a way to
answer ALOUD, the backstops that make a direct audio or clock-bound request
stick, the one writer that files meta-direction in the feedback ledger, and the
conversation window the judges read.

knock_reply.py owns GRADING; none of that is needed to render a greeting or file
a complaint. Nothing here imports knock_reply, so knock_reply and knock_message
can both import this without a cycle.

The request detectors read the learner's own words, in their own language
(English as shipped; a learner who replies in another language widens them).
"""
import asyncio
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

from memo import render_memo
from publish import KNOCKS_DIR, jsdelivr_url
from pack import LEARNER, TUTOR_VOICE
from state_io import FEEDBACK_LOG_PATH, KNOCK_LOG_PATH, load_json, local_today, save_json

# A clock in the learner's words. Deliberately generous: a false positive costs
# one re-ask; a false negative costs a push that was asked for and never queued.
TIME_REQUEST_RE = re.compile(
    r"\b("
    r"\d{1,2}\s*(?::\d{2})?\s*(?:am|pm)"          # 9am, 9:15 pm
    r"|(?:at|by|around)\s+\d{1,2}(?::\d{2})?\b"   # at 9, by 9:15
    r"|in\s+(?:an?\s+)?(?:half\s+an?\s+)?(?:hour|minute|min)s?"
    r"|tomorrow|tonight|this\s+(?:morning|afternoon|evening)"
    r"|later\s+today|before\s+bed|first\s+thing"
    r")\b", re.I)

ASK_RE = re.compile(
    r"\b(send|ping|knock|remind|message|text|call|wake|greet\w*|give|do"
    r"|schedul\w*|queue|push|play|say|speak|sing|record|tell|wish)\b", re.I)

AUDIO_RE = re.compile(
    r"\b(audio|voice|voice[- ]?note|aloud|out\s+loud|say|speak|spoken|sing|sung"
    r"|pronounc\w*|record\w*|greeting|memo|hear|listen|sound)\b", re.I)


def wants_spoken_reply(text: str) -> bool:
    """True when the reply reads as 'let me HEAR this'. VOICE_MANDATE rations
    speaking hard, which is right for a recast and wrong for a direct request, so
    a mechanism enforces it. Wide on purpose; `said` and `tell` stay OUT because
    "tell me what she said" asks for a meaning, and a false positive would file a
    MISSED VOICE note for a request never made."""
    return bool(AUDIO_RE.search(text) and ASK_RE.search(text))


def ensure_voice(verdict: dict, reply_text: str, rejudge) -> dict:
    """The audio-request backstop: one forced re-ask (`rejudge` re-runs the
    caller's own judge with force_voice=True), then a LOUD miss — a lane that
    declines to speak looks exactly like a normal text reply, so the third outcome
    writes MISSED VOICE where the diagnosis pass reads."""
    if not wants_spoken_reply(reply_text) or verdict.get("voice_reply"):
        return verdict
    print("   🎧 direct audio request with no voice_reply — re-asking once, forced…")
    forced = rejudge()
    if forced.get("voice_reply"):
        print("   → speaking")
        return forced
    print("   ⚠ still silent — logging the miss to the ledger")
    verdict["meta_note"] = (verdict.get("meta_note") or "").strip() or (
        f"MISSED VOICE: {LEARNER} asked to HEAR something ({reply_text[:80]!r}) and "
        f"the push went out text-only — the judge declined twice. Check the voice lane.")
    return verdict


def wants_scheduled_push(text: str) -> bool:
    """True when the reply reads as 'do something for me at <time>'. The mandate
    says a clock-bound request MUST produce a schedule; this makes the rule real.
    The verb list is deliberately WIDE — widen on sight."""
    return bool(TIME_REQUEST_RE.search(text) and ASK_RE.search(text))


def record_meta_note(verdict: dict) -> bool:
    """Meta-direction lands in the feedback ledger (what the diagnosis pass
    reads). One writer for every lane; returns whether anything was written."""
    note = (verdict.get("meta_note") or "").strip()
    if not note:
        return False
    flog = load_json(FEEDBACK_LOG_PATH) or []
    flog.append({"date": local_today().isoformat(), "note": f"[phone] {note}"})
    save_json(FEEDBACK_LOG_PATH, flog)
    print(f"   meta → ledger: {note}")
    return True


def speak(verdict: dict, knock: dict, klog: list) -> tuple[str | None, Path | None]:
    """Render the tutor's spoken answer and attach it to the knock; (url, mp3).
    Written on the EXCHANGE too (the top-level field is only the latest view).
    On a render failure `spoke` is cleared: a record claiming audio that never
    arrived teaches the thread a promise that was not kept."""
    if not verdict.get("voice_reply"):
        return None, None
    print("2b. render voice reply…")
    mp3, url = render_voice_reply(verdict["voice_reply"])
    if url:
        knock["reply_audio_url"] = url
        knock["exchanges"][-1].update(audio_url=url)
        save_json(KNOCK_LOG_PATH, klog)
    else:
        knock["exchanges"][-1].update(spoke="", audio_failed=True)
    return url, mp3


def render_voice_reply(spoken: str) -> tuple[Path | None, str | None]:
    """Render a spoken answer for THIS push-back; (mp3, url). Best-effort: a TTS
    failure still delivers the text. It costs a wait at the lock screen, which is
    why the mandate rations it to answers where the sound IS the answer."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    mp3 = KNOCKS_DIR / f"reply_{stamp}.mp3"
    try:
        asyncio.run(render_memo(spoken, mp3, TUTOR_VOICE))
    except Exception as exc:                       # noqa: BLE001 — text must still land
        print(f"   ⚠ voice reply failed to render ({exc}) — pushing the text alone")
        return None, None
    return mp3, jsdelivr_url(mp3)


RECENT_WINDOW_HOURS = 24.0
RECENT_WINDOW_TURNS = 8


def _ts(raw: str | None) -> datetime | None:
    """A log timestamp as an aware datetime, or None. One parser for every window."""
    try:
        dt = datetime.fromisoformat((raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def recent_exchanges(klog: list, knock: dict,
                     hours: float = RECENT_WINDOW_HOURS,
                     limit: int = RECENT_WINDOW_TURNS) -> list[dict]:
    """The conversation the tutor is actually in — across knocks, not just this
    one — and what the tutor DID on each turn (`tutor_sent_audio`,
    `tutor_queued_push`), so a promise with no matching field reads as unkept.

    Continuity only: cold-fire accounting never reads this window
    (`revealed_recently` owns that evidence). The current knock's own last four
    turns are always carried, however old."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    keep = {id(x) for x in (knock.get("exchanges") or [])[-4:]}   # never regress
    sources = list(klog) + ([] if any(k is knock for k in klog) else [knock])
    rows, seen = [], set()
    for k in sources:
        for x in k.get("exchanges", []):
            at = _ts(x.get("at"))
            if at is None or id(x) in seen or (at < cutoff and id(x) not in keep):
                continue
            seen.add(id(x))
            rows.append((at, k, x))
    rows.sort(key=lambda r: r[0])
    out = []
    for _, k, x in rows[-limit:]:
        row = {"learner_said": x.get("reply", ""),
               "tutor_said": x.get("reply_line", "")}
        if k is not knock:
            row["earlier_thread"] = k.get("move", "") or k.get("modality", "")
        row.update({out_key: x[src_key] for src_key, out_key in
                    (("spoke", "tutor_sent_audio"), ("scheduled", "tutor_queued_push"))
                    if x.get(src_key)})
        out.append(row)
    return out
