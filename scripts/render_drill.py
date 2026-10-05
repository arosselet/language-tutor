#!/usr/bin/env python3
"""
The drill track — a hands-free SPOKEN production volley from the pool's due list.

The tutor speaks a cue in the learner's language, silence while the learner SAYS
IT OUT LOUD in the target language, then the answer lands (twice). A walk or the
dishes becomes real reps.

The model writes the sheet (cues + answers); Python owns the menu (the due list),
the render, and the publish. Listening isn't producing: NO reps are logged here;
publishing records a declared EXPOSURE. Cold fires happen later, where a judge
hears them.

  python scripts/render_drill.py --dry-run     # write + print the sheet only
  python scripts/render_drill.py               # sheet → render → RSS + commit/push + phone push
  python scripts/render_drill.py --no-publish  # render to published_audio/ only

Secrets: OPENROUTER_API_KEY (when no local agent), TTS credentials,
PUSH_WEBHOOK_URL (the push).
"""
import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path


BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from lanes import deliver_rendered
from publish import commit_and_push, load_env, push_to_phone
from pack import TUTOR_VOICE
from writer import INT, STR, arr, ask_json, executor_name, obj, voice_canon

# The shapes this lane asks for. Every key the mandate names is declared, or the
# agent path drops it (a dropped `reason` makes every lint failure read "no reason").
DRILL_SCHEMA = obj(title=STR, intro=STR, outro=STR,
                   items=arr(cue=STR, answer=STR))
LINT_SCHEMA = obj(verdicts=arr(n=INT, verdict=STR, reason=STR))
from render_audio import (EXIT_NOT_CONFIGURED, SILENCE_FRAME, clean_for_tts,
                          generate_segment, get_raw_mp3_frames, tts_ready)
from suggest_targets import drill_menu
from mandates import BRIEF_IS_PRIVATE, DRILL_MANDATE, LINT_MANDATE
from state_io import LEXICON_PATH, load_json
from state_io import canon_payload

DRILLS_DIR = BASE / "published_audio"   # feed root — rebuild_rss picks up drill_*.mp3
SILENCE_PER_SEC = 41.666                # frames per second (matches render_audio)

# Appended when the standing order routed a REPAIR here. The commissioned item
# LEADS with three angles; the pool fills the rest — a whole drill built from one
# item is the slow repetitive loop this lane exists to escape.
COMMISSION_BRIEF = """

THE COMMISSION — the FIRST {n} item(s) of the DUE list are a REPAIR, not routine \
mouth reps. Give each of them THREE items instead of one: three different cues, three \
different everyday situations, the same target every time. Vary the situation, never the \
target — using it in context is the whole point of drilling it again. Everything after \
them is the ordinary drill and keeps its normal shape (one item per chunk, two per \
frame).{focus}
"""


def due_payload(max_entries: int) -> list[dict]:
    """The selector's order, interleaved frame/chunk: a slot-fill and a
    said-whole phrase are different work, and alternating them is a better drill."""
    menu = drill_menu(load_json(LEXICON_PATH) or {}, max_n=max(max_entries * 2, 12))
    if not menu:
        return []
    frames = [t for t in menu if t["kind"] == "frame"]
    chunks = [t for t in menu if t["kind"] != "frame"]
    out = []
    while len(out) < max_entries and (frames or chunks):
        if frames:
            out.append(frames.pop(0))
        if chunks and len(out) < max_entries:
            out.append(chunks.pop(0))
    return out


def drill_brief() -> tuple[str | None, list[dict]]:
    """The standing soak order, when addressed to THIS lane → (focus, lead items).
    EAR-ONLY items are REFUSED, never demanded: a drill's silence is a production
    demand, and a catch row is never forced to fire. A catch commission routed
    here is reported and left standing for the soak or episode lane."""
    order = (load_json(BASE / "progress" / "learner.json") or {}).get("soak_order") or {}
    if (order.get("channel") or "episode") != "drill":
        return None, []
    focus = (order.get("focus") or "").strip() or None
    lexicon = load_json(LEXICON_PATH) or {}
    lead = []
    for w in canon_payload(order.get("payload") or []):
        rec = lexicon.get(w) or {}
        if rec.get("direction") == "catch":
            print(f"   ⚠ '{w}' is ear-only (direction: catch) — a drill demands "
                  f"production, so it is NOT drilled. Route it to soak or episode.")
            continue
        lead.append({
            "word": w, "gloss": rec.get("gloss", ""),
            "kind": "frame" if w.startswith("frame:") or rec.get("type") == "pattern"
                    else "chunk"})
    return focus, lead


def with_lead(pending: list[dict], lead: list[dict]) -> list[dict]:
    """The commissioned repair leads; the due menu fills the rest, without repeats."""
    if not lead:
        return pending
    have = {t["word"] for t in lead}
    return lead + [t for t in pending if t["word"] not in have]


def write_sheet(pending: list[dict], n_lead: int = 0, focus: str | None = None) -> dict:
    canon = voice_canon()
    menu = "\n".join(f"- [{t['kind']}] {t['word']} — {t['gloss'] or '[no gloss]'}"
                     for t in pending)
    mandate = DRILL_MANDATE
    if n_lead:
        mandate += COMMISSION_BRIEF.format(
            n=n_lead, focus=(f"\nWhat the repair is about: {focus}"
                             + BRIEF_IS_PRIVATE) if focus else "")
    print(f"   [drill sheet] {executor_name()}")
    sheet = ask_json(canon + "\n\n---\n\n" + mandate, f"DUE:\n{menu}",
                     DRILL_SCHEMA)
    sheet["items"] = [i for i in sheet.get("items", [])
                      if i.get("cue", "").strip() and i.get("answer", "").strip()]
    return sheet


def lint_sheet(sheet: dict) -> list[str]:
    """Answer-key gate. A drill answer IS the model the learner rehearses ten
    times, so a second call grades every answer against its cue and the caller
    stops on ANY fail. Fail-closed: a miscounted or errored verdict list raises,
    because unverified wrong forms are worse than a late drill."""
    items = sheet.get("items", [])
    if not items:
        return []
    listing = "\n".join(f"{n}. cue: {i['cue']}\n   answer: {i['answer']}"
                        for n, i in enumerate(items, 1))
    verdicts = ask_json(LINT_MANDATE, listing, LINT_SCHEMA,
                        answer_tokens=1200).get("verdicts", [])
    if len(verdicts) != len(items):
        raise ValueError(f"lint returned {len(verdicts)} verdicts for {len(items)} items")
    fails = []
    for v in verdicts:
        if str(v.get("verdict", "")).strip().upper() != "PASS":
            n = v.get("n")
            ans = items[n - 1]["answer"] if isinstance(n, int) and 1 <= n <= len(items) else "?"
            fails.append(f"item {n}: {ans} — {v.get('reason', '') or 'no reason given'}")
    return fails


def silence(seconds: float) -> bytes:
    return SILENCE_FRAME * int(seconds * SILENCE_PER_SEC)


async def render(sheet: dict, out_path: Path, gap: float):
    """The tutor's one pinned voice throughout, so the drill sounds like the same
    someone as the knocks."""
    audio = bytearray()
    tmp = tempfile.mkdtemp()
    idx = 0

    async def seg(text: str) -> bytes:
        nonlocal idx
        idx += 1
        f = await generate_segment(clean_for_tts(text), TUTOR_VOICE, idx, tmp)
        frames = get_raw_mp3_frames(f)
        os.remove(f)
        return frames

    print(f"   intro: {sheet['intro'][:60]}")
    audio.extend(await seg(sheet["intro"]))
    audio.extend(silence(1.5))
    for n, item in enumerate(sheet["items"], 1):
        print(f"   [{n}/{len(sheet['items'])}] {item['cue'][:40]} → {item['answer'][:30]}")
        audio.extend(await seg(item["cue"]))
        audio.extend(silence(gap))              # the learner's turn — out loud
        answer = await seg(item["answer"])
        audio.extend(answer)
        audio.extend(silence(0.9))
        audio.extend(answer)                    # the echo sets it
        audio.extend(silence(1.4))
    audio.extend(await seg(sheet["outro"]))
    os.rmdir(tmp)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio)
    print(f"   rendered -> {out_path} ({len(audio)/1024:.0f} KB)")


def main():
    ap = argparse.ArgumentParser(description="Spoken production drill from the pool's due list")
    ap.add_argument("--entries", type=int, default=8,
                    help="menu entries to drill (frames expand to 2 items; default 8)")
    ap.add_argument("--gap", type=float, default=3.5,
                    help="seconds of silence for the out-loud attempt (default 3.5)")
    ap.add_argument("--dry-run", action="store_true", help="write + print the sheet; no TTS or publish")
    ap.add_argument("--no-publish", action="store_true", help="render only; skip RSS/commit/push/notify")
    args = ap.parse_args()

    load_env(BASE / ".env")

    # The commission is read FIRST: a repair routed here gets its tape even on a
    # day nothing else is due.
    focus, lead = drill_brief()
    pending = with_lead(due_payload(args.entries), lead)
    if not pending:
        print("No due fire-side items — nothing to drill.")
        return

    print(f"1. sheet… ({len(pending)} menu entries"
          f"{f' · {len(lead)} COMMISSIONED, leading' if lead else ''}"
          f"{' · FOCUS: ' + focus if focus else ''})")
    sheet = write_sheet(pending, len(lead), focus)
    print(f"   → '{sheet.get('title', 'Drill')}' · {len(sheet['items'])} items")

    # THE FLOOR — AN EMPTY SHEET IS NOT A DOSE, and the lint passes an empty
    # sheet, so this sits above it: no grader, no TTS, no exposure booked for a
    # tape that said nothing.
    if not sheet["items"]:
        sys.exit("✗ EMPTY SHEET — no items survived; this drill is intro + outro over "
                 "silence. Nothing linted, rendered or published, order left STANDING. "
                 "--dry-run it: items all gone means DRILL_SCHEMA lacks a key "
                 "DRILL_MANDATE names, and the agent path ate it.")

    # Lint before the dry-run gate: a dry run prints the verdict a real run acts on.
    try:
        fails = lint_sheet(sheet)
    except Exception as e:
        sys.exit(f"✗ answer-key lint could not run ({e}) — unverified sheet; not rendering.")
    if fails:
        for line in fails:
            print(f"   ✗ {line}")
        sys.exit("✗ answer key failed lint — stopped for inspection, nothing rendered. "
                 "Re-run for a fresh sheet.")
    print(f"   ✓ lint: {len(sheet['items'])} answers pass")

    if args.dry_run:
        print(json.dumps(sheet, ensure_ascii=False, indent=2))
        return

    reason = tts_ready()
    if reason:
        print(f"⏭️  Skipping render — {reason}. This host cannot produce audio.")
        sys.exit(EXIT_NOT_CONFIGURED)

    now = datetime.now()
    mp3 = DRILLS_DIR / f"drill_{now.strftime('%Y-%m-%d_%H%M')}.mp3"
    print("2. render…")
    asyncio.run(render(sheet, mp3, args.gap))

    if args.no_publish:
        return

    print("3. publish…")
    # The due menu the sheet was built from is what went out the door.
    deliver_rendered(
        mp3=mp3, lane="drill", delivered=[t["word"] for t in pending],
        claimed=bool(focus or lead),
        message=f"Drill track: {sheet.get('title', mp3.stem)}",
        title=sheet.get("title", ""),
        copy=f"drill's up — {len(sheet['items'])} out loud, gaps are yours 🎧",
        noun="drill", commit=commit_and_push, notify=push_to_phone)


if __name__ == "__main__":
    main()
