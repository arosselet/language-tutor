#!/usr/bin/env python3
"""
The soak loop — PASSIVE repetition for an ear on autopilot.

One of three listening channels, and the only one that demands nothing:

  episode (run_studio.py)   — a scene to follow. Comprehension work.
  drill   (render_drill.py) — a cue, a gap, and the learner SAYS IT OUT LOUD.
  soak    (this)            — nothing. The sounds repeat and iterate.

Commissioned when the learner is tired, walking, driving, or has no attention to
spend. Rhythm is Python's, never the model's: each item lands in the target
language FIRST (the sound before the meaning), the gloss once, then the sound
twice more with air around it; each cluster closes with a target-only echo of the
whole thread, so the endings iterate against each other. No response gaps — a
gap invites work, and this channel invites none.

  python scripts/render_soak.py --dry-run    # sheet only, no TTS
  python scripts/render_soak.py              # sheet -> render -> RSS + commit + phone push
  python scripts/render_soak.py --no-publish # render locally, no feed/commit/push

Secrets: OPENROUTER_API_KEY (the sheet, when no local agent), TTS credentials,
PUSH_WEBHOOK_URL (the push).
"""
import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path


BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from lanes import deliver_rendered
from publish import commit_and_push, load_env, push_to_phone
from pack import TUTOR_VOICE
from writer import STR, arr, ask_json, executor_name, obj, voice_canon

# What the soak sheet IS, for the agent executor. Every key SOAK_MANDATE names is
# declared, or the agent path silently drops it — an item without `say` fails
# the filter and the lane renders intro + outro over nothing.
SOAK_SCHEMA = obj(title=STR, intro=STR, outro=STR,
                  clusters=arr(thread=STR, items=arr(say=STR, en=STR)))
from render_audio import (generate_segment, get_raw_mp3_frames,
                          SILENCE_FRAME, clean_for_tts, tts_ready,
                          EXIT_NOT_CONFIGURED)
from mandates import BRIEF_IS_PRIVATE, SOAK_MANDATE
from state_io import LEXICON_PATH, load_json

SOAK_DIR = BASE / "published_audio"     # feed root — rebuild_rss picks up soak_*.mp3
SILENCE_PER_SEC = 41.666                # frames per second (matches render_audio)

def week_payload(days: int, max_items: int) -> list[dict]:
    """What the learner has actually been working this week: anything surfaced
    within `days`, mid-fight (hinted) items ahead of ones already cold."""
    lexicon = load_json(LEXICON_PATH) or {}
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rank = {"hinted": 0, "cold": 1, "none": 2}
    rows = []
    for key, rec in lexicon.items():
        seen = rec.get("last_surfaced")
        if not seen or seen < cutoff:
            continue
        rows.append({
            "word": key,
            "gloss": rec.get("gloss", ""),
            "production": rec.get("production", "none"),
            "last_surfaced": seen,
        })
    rows.sort(key=lambda r: (rank.get(r["production"], 3), r["last_surfaced"]),
              reverse=False)
    return rows[:max_items]


FOCUS_BRIEF = """\

FOCUS — this loop is a CAROUSEL, not a survey of the week:
{focus}

Build EVERY cluster on that focus; a week item that does not serve it stays out. \
Each cluster is one root or one ending, and the forms inside it differ only by the \
part being drilled — that contrast is the whole lesson. Inflect the focus roots \
freely into whatever forms the thread needs, including forms not on the list below: \
a conjugation carousel is unhearable if the endings are missing. The no-new-vocabulary \
rule still binds everything OUTSIDE the focus.
""" + BRIEF_IS_PRIVATE


def soak_brief() -> tuple[str | None, list[str]]:
    """The standing soak order, when addressed to THIS lane → (focus, payload).
    The payload matters: the order clears only when its words are delivered, so
    a lane that ignored it would re-dispatch forever."""
    order = (load_json(BASE / "progress" / "learner.json") or {}).get("soak_order") or {}
    if (order.get("channel") or "episode") != "soak":
        return None, []
    focus = (order.get("focus") or "").strip() or None
    return focus, [w for w in order.get("payload") or [] if w]


def with_payload(items: list[dict], payload: list[str]) -> list[dict]:
    """The ordered words lead the menu: they are why the dose was commissioned."""
    if not payload:
        return items
    lexicon = load_json(LEXICON_PATH) or {}
    have = {r["word"] for r in items}
    head = [{"word": w, "gloss": lexicon.get(w, {}).get("gloss", ""),
             "production": lexicon.get(w, {}).get("production", "none"),
             "last_surfaced": lexicon.get(w, {}).get("last_surfaced")}
            for w in payload if w in lexicon and w not in have]
    return head + items


def write_sheet(items: list[dict], focus: str | None = None) -> dict:
    canon = voice_canon()
    menu = "\n".join(
        f"- {r['word']} — {r['gloss'] or '[no gloss]'} [{r['production']}]"
        for r in items)
    mandate = SOAK_MANDATE + (FOCUS_BRIEF.format(focus=focus) if focus else "")
    print(f"   [soak sheet] {executor_name()}")
    sheet = ask_json(canon + "\n\n---\n\n" + mandate,
                     f"THIS WEEK'S ITEMS:\n{menu}", SOAK_SCHEMA)
    clean = []
    for c in sheet.get("clusters", []):
        kept = [i for i in c.get("items", [])
                if i.get("say", "").strip() and i.get("en", "").strip()]
        if kept and c.get("thread", "").strip():
            clean.append({"thread": c["thread"].strip(), "items": kept})
    sheet["clusters"] = clean
    return sheet


def silence(seconds: float) -> bytes:
    return SILENCE_FRAME * int(seconds * SILENCE_PER_SEC)


async def render(sheet: dict, out_path: Path, passes: int):
    """Python owns the rhythm. Per item: sound, gloss, sound, sound. Per cluster:
    a target-only echo of the whole thread. Whole-sheet passes repeat the loop."""
    audio = bytearray()
    tmp = tempfile.mkdtemp(prefix="soak_segments_")
    idx = 0
    cache: dict[str, bytes] = {}

    async def seg(text: str) -> bytes:
        """Cached: the same line is spoken many times in one loop."""
        nonlocal idx
        if text in cache:
            return cache[text]
        idx += 1
        f = await generate_segment(clean_for_tts(text), TUTOR_VOICE, idx, tmp)
        frames = get_raw_mp3_frames(f)
        os.remove(f)
        cache[text] = frames
        return frames

    try:
        audio.extend(await seg(sheet["intro"]))
        audio.extend(silence(2.0))

        for p in range(passes):
            if p:
                audio.extend(silence(2.5))
            for c in sheet["clusters"]:
                print(f"   [pass {p+1}] {c['thread'][:52]}")
                audio.extend(await seg(c["thread"]))
                audio.extend(silence(1.2))
                for item in c["items"]:
                    said = await seg(item["say"])
                    audio.extend(said)                  # sound first
                    audio.extend(silence(0.9))
                    audio.extend(await seg(item["en"]))  # meaning, once
                    audio.extend(silence(0.7))
                    audio.extend(said)
                    audio.extend(silence(0.9))
                    audio.extend(said)                  # and settle
                    audio.extend(silence(1.5))
                audio.extend(silence(0.8))
                for item in c["items"]:                 # the thread, target only
                    audio.extend(await seg(item["say"]))
                    audio.extend(silence(1.0))
                audio.extend(silence(1.8))

        audio.extend(await seg(sheet["outro"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio)
    # Measure, never estimate from byte count (speech frames dwarf silence frames).
    from rebuild_rss import audio_duration
    secs = audio_duration(str(out_path)) or 0
    print(f"   rendered -> {out_path} ({len(audio)/1024:.0f} KB, "
          f"{secs/60:.1f} min, {idx} unique segments)")


def main():
    ap = argparse.ArgumentParser(description="Passive soak loop from this week's items")
    ap.add_argument("--days", type=int, default=7, help="how far back 'this week' reaches (default 7)")
    ap.add_argument("--items", type=int, default=16, help="max items to draw from (default 16)")
    ap.add_argument("--passes", type=int, default=2, help="times through the whole loop (default 2)")
    ap.add_argument("--focus", type=str, default=None,
                    help="Carousel brief — what to permute (an ending over two verbs). "
                         "Defaults to the soak order's `focus` when its channel is 'soak'.")
    ap.add_argument("--dry-run", action="store_true", help="write + print the sheet; no TTS or publish")
    ap.add_argument("--no-publish", action="store_true", help="render only; skip RSS/commit/push/notify")
    args = ap.parse_args()

    load_env(BASE / ".env")

    items = week_payload(args.days, args.items)
    if not items:
        print(f"Nothing surfaced in the last {args.days} days — nothing to soak.")
        return

    ordered_focus, payload = soak_brief()
    focus = args.focus or ordered_focus
    items = with_payload(items, payload)
    print(f"1. sheet… ({len(items)} items from the last {args.days} days"
          f"{f' + {len(payload)} ordered' if payload else ''}"
          f"{' · FOCUS: ' + focus if focus else ''})")
    sheet = write_sheet(items, focus)
    n = sum(len(c["items"]) for c in sheet["clusters"])
    print(f"   → '{sheet.get('title', 'Soak')}' · {len(sheet['clusters'])} threads, {n} items")

    if args.dry_run:
        print(json.dumps(sheet, ensure_ascii=False, indent=2))
        return

    # THE FLOOR — AN EMPTY SHEET IS NOT A DOSE. Without it an empty sheet renders
    # intro + outro, publishes, pushes, and stamps the order DELIVERED: every
    # instrument green, the repair gone. It sits before the spend, the feed entry,
    # the push and the stamp. Non-zero, so the order can be re-dispatched.
    if n == 0:
        sys.exit("❌ EMPTY SHEET — no clusters, so this loop is intro + outro over "
                 "silence. Nothing rendered, published or pushed, and the soak order "
                 "is left STANDING to be re-dispatched. Inspect it with --dry-run: "
                 "clusters present but items gone means a key SOAK_MANDATE names is "
                 "missing from SOAK_SCHEMA, and the agent path ate it.")

    reason = tts_ready()   # rendering needs TTS even with --no-publish
    if reason:
        print(f"⏭️  Skipping render — {reason}. This host cannot produce audio.")
        sys.exit(EXIT_NOT_CONFIGURED)

    now = datetime.now()
    mp3 = SOAK_DIR / f"soak_{now.strftime('%Y-%m-%d_%H%M')}.mp3"
    print("2. render…")
    asyncio.run(render(sheet, mp3, args.passes))

    if args.no_publish:
        return

    print("3. publish…")
    # Under a FOCUS the menu is a candidate pool: stamp only what is audible in
    # the finished sheet, or the ledger books delivery for words that never
    # played. `frame:` keys have no surface form and are left out — under-claim.
    if focus:
        spoken = " ".join(i["say"] for c in sheet["clusters"] for i in c["items"])
        delivered = [r["word"] for r in items if r["word"] in spoken]
        print(f"   focused run — {len(delivered)}/{len(items)} menu items audible in the sheet")
    else:
        delivered = [r["word"] for r in items]
    deliver_rendered(
        mp3=mp3, lane="soak", delivered=delivered, claimed=bool(focus or payload),
        message=f"Soak loop: {sheet.get('title', mp3.stem)}",
        title=sheet.get("title", ""),
        copy=f"soak loop's up — {n} sounds, nothing to do but listen 🎧",
        noun="soak loop", commit=commit_and_push, notify=push_to_phone)


if __name__ == "__main__":
    main()
