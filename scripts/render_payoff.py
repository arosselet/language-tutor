#!/usr/bin/env python3
"""The payoff — the tape the learner already heard, handed back with its meaning.

An eavesdrop tape is deliberately pitched below the coverage floor, and its drift
judge grades only the gist; without this lane nothing ever tells the learner what
a tape SAID, and a tape they could not parse moved nothing. The payoff replaces
the raw tape's residency in the feed: `rebuild_rss` drops `knock_<ts>.mp3` exactly
when `payoff_<ts>.mp3` is standing there. The raw mp3 is never deleted.

A NEW FILE, NOT AN OVERWRITE: the guid is the enclosure url is the filename, so
rewriting the tape in place would never reach a client that already downloaded it.

WHEN IT FIRES: when the tape's rep is CLOSED — answered, or the window ran out.
Earlier would hand over the answer key to a question not yet asked.

THE RHYTHM IS PYTHON'S:

    line · meaning · line       once per line (the soak rhythm)
    the tape, at speed          blind, at the END — the only place the tape is
                                heard CONNECTED with the meanings in mind

No speed pass up front: the knock was already the at-speed hearing. The closing
pass is the ORIGINAL mp3's frames, so what is re-heard is what was heard.

THE MODEL NEVER RETYPES THE TAPE. It gets numbered lines and returns a meaning
per number; Python holds the tape. Alignment is checked BY NUMBER, so a right
count of misaligned glosses is refused rather than rendered.

    python scripts/render_payoff.py --dry-run    # sheet only, no TTS
    python scripts/render_payoff.py              # sheet -> render -> feed + push
    python scripts/render_payoff.py --knock-id <timestamp>   # one tape, now

Secrets: OPENROUTER_API_KEY or `claude -p` (the sheet), TTS credentials,
PUSH_WEBHOOK_URL (the push).
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from lanes import deliver_rendered
from pack import EAVESDROP_VOICE, LEARNER, NATIVE_LANGUAGE, TUTOR_VOICE, has_target
from publish import (KNOCKS_DIR, commit_and_push, load_env, publish,
                     push_to_phone)
from rebuild_rss import MIN_PLAYABLE_BYTES
from render_audio import (EXIT_NOT_CONFIGURED, SILENCE_FRAME, clean_for_tts,
                          clean_memo_for_tts, generate_segment,
                          get_raw_mp3_frames, tts_ready)
from state_io import (FEEDBACK_LOG_PATH, KNOCK_LOG_PATH, load_json, local_today,
                      save_json)
from writer import INT, STR, arr, ask_json, executor_name, obj, voice_canon

SILENCE_PER_SEC = 41.666
# An unanswered tape closes after this: long enough to spoil no live rep, short
# enough that the meaning arrives while the hearing is remembered.
HOLD_HOURS = 24
# Only the eavesdrop tape is pitched below the coverage floor, which is what makes
# an unglossed one worthless afterwards. Widening this is a decision, not a constant.
TAPE_MODALITY = "eavesdrop"
# Two failed sheets and the tape is left alone: a retry that can never succeed is
# a warning that cannot be discharged.
MAX_TRIES = 2
REFUSED = "Payoff: refused (logged)"

# One sentence per line — the unit a gloss aligns to. Sentence-final punctuation
# is not a language fact.
SENTENCE = re.compile(r"[^.!?…。]+[.!?…。]*")

# Names no target language, script or morphology: it asks for meanings of
# numbered lines, the same request in any pack.
PAYOFF_BRIEF = f"""\
THE PAYOFF SHEET. {LEARNER} heard this tape on their phone and could not parse it. \
You are giving it back with its meaning attached, so it can be played again and \
actually followed. This is not a rep: nothing is graded and nothing is withheld — \
the question was answered, or the moment has passed.

The tape's lines are numbered below. Return ONE gloss per number: `n` is the \
line's number exactly as given, `en` is what that line MEANS in natural spoken \
{NATIVE_LANGUAGE} — what the speaker is saying, not a word-by-word decoding. One \
sentence each. No commentary, and never quote the original line back inside `en`.

`opener` — one short spoken {NATIVE_LANGUAGE} line naming what is about to be heard \
(who is talking, what the call is about) and saying the meaning comes after each \
line. `closer` — one short spoken {NATIVE_LANGUAGE} line giving the answer to the \
question that was asked about this tape, plainly, so the thing listened for is \
named out loud before the last playthrough.
"""

# `n` makes the alignment checkable; everything obj() names is REQUIRED.
PAYOFF_SHEET = obj(opener=STR, closer=STR, glosses=arr(n=INT, en=STR))


def _ts(raw: str | None) -> datetime | None:
    """A log timestamp as an aware datetime, or None (`+00:00` and `Z` both occur)."""
    try:
        when = datetime.fromisoformat((raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def stem_of(entry: dict) -> str:
    """The raw tape's filename stem — the join key between a knock, its payoff
    and the feed."""
    ref = entry.get("mp3") or entry.get("audio_url") or ""
    return os.path.basename(ref).removesuffix(".mp3") if ".mp3" in ref else ""


def payoff_path(stem: str) -> Path:
    """`knock_<ts>` -> `…/knocks/payoff_<ts>.mp3`; the timestamp pairs the two."""
    return KNOCKS_DIR / f"payoff_{stem.split('_', 1)[-1]}.mp3"


def tape_lines(memo_script: str) -> list[str]:
    """The tape as spoken sentences, within the paragraphs it was rendered with."""
    lines = []
    for para in (memo_script or "").split("\n\n"):
        lines += [m.group(0).strip() for m in SENTENCE.finditer(para.replace("\n", " "))
                  if m.group(0).strip()]
    return lines


def is_closed(entry: dict, now: datetime) -> bool:
    """Is this tape's rep over? Answered, or its window ran out."""
    if entry.get("response") or entry.get("reply_verdict"):
        return True
    when = _ts(entry.get("timestamp"))
    return bool(when and (now - when).total_seconds() >= HOLD_HOURS * 3600)


def pending(klog: list, now: datetime) -> list[dict]:
    """Closed tapes with no payoff yet, NEWEST FIRST — the tape still remembered is
    worth more than the one that waited longest. A tape whose mp3 is not on disk
    is skipped: a re-synthesised approximation is a different tape."""
    out = []
    for e in klog:
        stem = stem_of(e)
        if e.get("modality") != TAPE_MODALITY or not e.get("acted") or not stem:
            continue
        if e.get("payoff_mp3") or e.get("payoff_tries", 0) >= MAX_TRIES:
            continue
        if not (e.get("memo_script") or "").strip() or not is_closed(e, now):
            continue
        if (KNOCKS_DIR / f"{stem}.mp3").exists():
            out.append(e)
    return sorted(out, key=lambda e: e.get("timestamp") or "", reverse=True)


def write_sheet(entry: dict, lines: list[str]) -> dict:
    """The gloss pass. The tape goes down numbered; only meanings come back."""
    numbered = "\n".join(f"{i}. {ln}" for i, ln in enumerate(lines, 1))
    context = (f"THE TAPE ({entry.get('move', '')}):\n{numbered}\n\n"
               f"WHAT {LEARNER.upper()} WAS ASKED ABOUT IT: {entry.get('body', '')}\n"
               f"WHAT {LEARNER.upper()} ANSWERED: {entry.get('reply') or '— no reply —'}")
    print(f"   [payoff sheet] {executor_name()}")
    return ask_json(voice_canon() + "\n\n---\n\n" + PAYOFF_BRIEF, context,
                    PAYOFF_SHEET, answer_tokens=900)


def align(lines: list[str], sheet: dict) -> tuple[list[str], str]:
    """Glosses in tape order, or ([], why-not). BY NUMBER, not by count: meanings
    against the wrong lines would teach the tape wrong with every instrument green.
    A gloss that echoes the target back is refused too (for a shared-script pack
    only a declared span is detectable)."""
    by_n: dict[int, str] = {}
    for g in sheet.get("glosses") or []:
        try:
            n = int(g.get("n"))
        except (TypeError, ValueError):
            continue
        en = " ".join((g.get("en") or "").split())
        if en and 1 <= n <= len(lines) and n not in by_n:
            by_n[n] = en
    missing = [i for i in range(1, len(lines) + 1) if i not in by_n]
    if missing:
        return [], f"no meaning for line {missing[:6]} of {len(lines)}"
    echoed = sorted(n for n, en in by_n.items() if has_target(en))
    if echoed:
        return [], f"line {echoed[:6]} came back in the tape's own language, unglossed"
    return [by_n[i] for i in range(1, len(lines) + 1)], ""


def silence(seconds: float) -> bytes:
    return SILENCE_FRAME * int(seconds * SILENCE_PER_SEC)


async def render(tape: bytes, lines: list[str], glosses: list[str],
                 sheet: dict, out_path: Path):
    """The tutor's frame, the walk, the answer, then the tape blind."""
    audio = bytearray()
    tmp = tempfile.mkdtemp(prefix="payoff_segments_")
    idx = 0
    cache: dict[tuple, bytes] = {}
    overheard = EAVESDROP_VOICE or TUTOR_VOICE

    async def say(text: str, voice: str) -> bytes:
        """One segment, cached (a line is spoken twice in the walk). The tape's
        lines take the memo cleaner they were first rendered with."""
        nonlocal idx
        key = (voice, text)
        if key not in cache:
            idx += 1
            clean = clean_memo_for_tts if voice == overheard else clean_for_tts
            seg = await generate_segment(clean(text), voice, idx, tmp)
            cache[key] = get_raw_mp3_frames(seg)
            os.remove(seg)
        return cache[key]

    try:
        audio.extend(await say(sheet["opener"], TUTOR_VOICE))
        audio.extend(silence(1.4))
        for line, en in zip(lines, glosses):
            print(f"   [walk] {en[:56]}")
            spoken = await say(line, overheard)
            audio.extend(spoken)                            # sound first
            audio.extend(silence(0.8))
            audio.extend(await say(en, TUTOR_VOICE))        # meaning, once
            audio.extend(silence(0.6))
            audio.extend(spoken)                            # and settle
            audio.extend(silence(1.4))
        audio.extend(silence(0.8))
        audio.extend(await say(sheet["closer"], TUTOR_VOICE))
        audio.extend(silence(1.8))
        audio.extend(tape)                                  # blind, the win
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio)
    from rebuild_rss import audio_duration        # measured, never estimated
    secs = audio_duration(str(out_path)) or 0
    print(f"   rendered -> {out_path} ({len(audio)/1024:.0f} KB, {secs/60:.1f} min, "
          f"{idx} segments)")


def refuse(entry: dict, klog: list, why: str):
    """A payoff that cannot be made counts its attempts (committed — a cloud
    runner forgets an uncommitted count) and, on the LAST try only, says so in
    the feedback ledger: a note every wake-up is walked past; none at all leaves
    a tape silently unglossed forever."""
    entry["payoff_tries"] = entry.get("payoff_tries", 0) + 1
    print(f"   ⚠ no payoff for {stem_of(entry)}: {why} "
          f"(try {entry['payoff_tries']}/{MAX_TRIES})")
    paths = [KNOCK_LOG_PATH]
    if entry["payoff_tries"] >= MAX_TRIES:
        flog = load_json(FEEDBACK_LOG_PATH) or []
        flog.append({"date": local_today().isoformat(),
                     "note": f"[payoff] the {entry.get('date')} tape "
                             f"({entry.get('move')}) has no payoff and will not be "
                             f"retried — {why}. It was heard and its meaning never given."})
        save_json(FEEDBACK_LOG_PATH, flog)
        paths.append(FEEDBACK_LOG_PATH)
    save_json(KNOCK_LOG_PATH, klog)
    return paths


def main():
    ap = argparse.ArgumentParser(description="Re-cut a heard tape with its meaning")
    ap.add_argument("--knock-id", help="one tape by its log timestamp, closed or not")
    ap.add_argument("--dry-run", action="store_true", help="sheet only; no TTS, no publish")
    ap.add_argument("--no-publish", action="store_true", help="render only; no feed/commit/push")
    args = ap.parse_args()

    load_env(BASE / ".env")
    klog = load_json(KNOCK_LOG_PATH) or []
    now = datetime.now(timezone.utc)
    if args.knock_id:
        due = [e for e in klog if e.get("timestamp") == args.knock_id]
    else:
        due = pending(klog, now)
    if not due:
        print("No closed tape is waiting for a payoff.")
        return
    # ONE PER RUN, freshest first: a backlog drains at the rate it can be heard.
    entry = due[0]
    stem = stem_of(entry)
    lines = tape_lines(entry.get("memo_script", ""))
    print(f"1. sheet… ({entry.get('date')} · {entry.get('move')} · {len(lines)} lines)")
    def refused(why: str) -> None:
        # A dry run reports the refusal and counts nothing: the try counter and
        # the feedback note are state, and committing them is the run's job.
        if args.dry_run:
            print(f"[dry-run] would refuse {stem}: {why} — nothing counted or committed.")
            return
        commit_and_push(*publish(refuse(entry, klog, why), REFUSED))

    if not lines:
        return refused("the tape has no lines")

    sheet = write_sheet(entry, lines)
    glosses, why = align(lines, sheet)
    if why:
        return refused(why)
    if args.dry_run:
        print(json.dumps({"opener": sheet["opener"], "closer": sheet["closer"],
                          "walk": list(zip(lines, glosses))},
                         ensure_ascii=False, indent=2))
        return

    reason = tts_ready()
    if reason:
        print(f"⏭️  Skipping render — {reason}. This host cannot produce audio.")
        sys.exit(EXIT_NOT_CONFIGURED)

    mp3 = payoff_path(stem)
    print("2. render…")
    tape = get_raw_mp3_frames(str(KNOCKS_DIR / f"{stem}.mp3"))
    asyncio.run(render(tape, lines, glosses, sheet, mp3))
    if args.no_publish:
        return
    # THE STAMP FOLLOWS THE ARTIFACT: a stamp over a render that did not survive
    # would retire a tape whose payoff nobody can play.
    if not (mp3.exists() and mp3.stat().st_size >= MIN_PLAYABLE_BYTES):
        commit_and_push(*publish(refuse(entry, klog, "the render produced nothing playable"),
                                 REFUSED))
        return
    entry["payoff_mp3"] = mp3.relative_to(BASE).as_posix()
    save_json(KNOCK_LOG_PATH, klog)

    print("3. publish…")
    # `delivered` is EMPTY by law: the eavesdrop's exposures were stamped when the
    # tape went out, and re-stamping would double-count. A payoff answers no order.
    deliver_rendered(
        mp3=mp3, lane="payoff", delivered=[], claimed=False,
        extra_paths=[KNOCK_LOG_PATH],
        message=f"Payoff: {entry.get('date')} tape ({entry.get('move')})",
        title=entry.get("move", ""),
        copy=f"🎧 that tape from {entry.get('date')} — same call, with the meaning "
             f"after every line.",
        noun="payoff", commit=commit_and_push, notify=push_to_phone)


if __name__ == "__main__":
    main()
