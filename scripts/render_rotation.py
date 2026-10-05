#!/usr/bin/env python3
"""
The rotation tape — one press of play, movements on a cadence, nothing asked.

What makes this lane itself is the MOVEMENT: Python plans a cadence of mixed
shapes (machine, inventory, scene, eavesdrop, lore) and the recurrence schedule
is the pedagogical payload. It is not a long episode, and it is not a soak with
more passes — "never loop harder": a tired ear asking for longer wants more
structured recurrence, not more scene and not the same ten minutes four times.

THE RHYTHM IS PYTHON'S, AND THE CLOCK IS MEASURED, NOT GUESSED. No model is asked
for a long script (what it would write is a list). One small sheet per MOVEMENT,
written just in time, rendered, measured.

A TAPE IS AS LONG AS ITS MATERIAL; `--minutes` is a CEILING. Each spine draws only
on items its lead shape can teach from, so spines come out at different lengths.

THE MOVEMENT, NOT THE LINE, IS THE UNIT OF LANGUAGE MIX: movements of ~1-2
minutes with distinct centres of gravity, never two of a kind side by side, and
`scene`/`eavesdrop` movements draw ONLY on items earlier movements taught, so
comprehension is structural rather than hoped for.

  python scripts/render_rotation.py --plan-only   # the movement plan; no network at all
  python scripts/render_rotation.py --dry-run     # plan + the first sheet; no TTS, no publish
  python scripts/render_rotation.py               # render -> RSS + commit + push + notify
  python scripts/render_rotation.py --no-publish  # render locally, nothing leaves the machine

Secrets: OPENROUTER_API_KEY (when no local agent), TTS credentials,
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
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from lanes import deliver_rendered
import rails
import timeline
from publish import commit_and_push, load_env, push_to_phone
from pack import EAVESDROP_VOICE, TUTOR, TUTOR_VOICE
from render_audio import (generate_segment, get_raw_mp3_frames, SILENCE_FRAME,
                          clean_for_tts, tts_ready, EXIT_NOT_CONFIGURED,
                          _CHIRP_POOL_MALE, _CHIRP_POOL_FEMALE,
                          _EDGE_POOL_MALE, _EDGE_POOL_FEMALE)
from writer import STR, arr, ask_json, obj, voice_canon

# What one movement IS. `who` is declared: undeclared, the agent path drops it and
# a two-hander renders as one voice throughout.
MOVEMENT_SCHEMA = obj(frame=STR, beats=arr(say=STR, en=STR, who=STR))
from state_io import LEXICON_PATH, load_json
from state_io import canon_payload
from suggest_targets import WORD_POOL_PATH, intake_rows, inventory_hosts

ROTATION_DIR = BASE / "published_audio"   # feed root — rebuild_rss reads rotation_*.mp3
SILENCE_PER_SEC = 41.666                  # frames per second (matches render_audio)

# ── The rotation law ────────────────────────────────────────────────────────
# Variety on a fixed cycle, not by taste. `scene` and `eavesdrop` are RECALL
# shapes and consume no new items. INVARIANTS (smoke): no cadence places two
# identical shapes adjacently, including across the wrap (tapes are replayed);
# every cadence OPENS on a teaching shape (a recall in slot 1 has nothing to recall).
CADENCES = {
    "machines":  ("machine", "scene", "machine", "lore", "machine", "eavesdrop"),
    "inventory": ("inventory", "scene", "inventory", "lore", "inventory", "eavesdrop"),
    "room":      ("machine", "scene", "inventory", "eavesdrop", "scene", "lore"),
}
RECALL_SHAPES = {"scene", "eavesdrop"}
# The lanes whose whole contract is "press once, nothing asked" — the shelf the
# supply floor counts. An episode asks something, so it is not here.
PLEASURE_FORMATS = {"rotation", "soak", "payoff"}
# Pool items per shape; for recall shapes it is a look-back depth.
ITEMS = {"machine": 4, "inventory": 3, "scene": 6, "eavesdrop": 5, "lore": 2}
# Planning estimate ONLY — the render measures the real clock. Re-measure when the
# RHYTHM table or beat counts change.
MOVEMENT_MIN = 1.15
# The closing lap's two spoken lines — one home, read by the render AND the script.
LAP_IN, LAP_OUT = "Same sounds, one more lap.", "That's the lot."
CLOSING_LAP_MIN = 5.5
# (air after a target line, air after its gloss, air after the beat). Teaching
# shapes breathe; scenes run closer to speed.
RHYTHM = {
    "machine":   (0.9, 0.7, 1.4),
    "inventory": (1.0, 0.8, 1.6),
    "scene":     (0.6, 0.0, 0.9),
    "eavesdrop": (0.7, 0.0, 1.1),
    "lore":      (0.8, 0.0, 1.0),
}
# Section markers: Python owns the MODE word and the pause, the writer only the
# topic. Deterministic, because a label the ear learns to depend on must not be
# rephrased. Nouns, never imperatives — nothing on this tape asks.
MODE_LABEL = {"machine": "Drills", "inventory": "Phrases", "scene": "A scene",
              "eavesdrop": "Overheard", "lore": "A note"}
SHAPE_NAME = {"machine": ("drills", "more drills"), "inventory": ("phrases", "more phrases"),
              "scene": ("a scene", "another scene"), "lore": ("a note", "another note"),
              "eavesdrop": ("a phone call", "another phone call")}
# Air BEFORE a frame (a minimum including the previous tail), 1.2s after: long in,
# short out is the chapter cue.
PRE_FRAME = 2.0
# Past this many movements the roadmap names the cycle, not every round.
ROADMAP_MAX = 8
# The `room` spine's register order: the leads in timeline order, then the trails.
REGISTER_ORDER = list(dict.fromkeys(
    r for v in timeline.DIRECTIONS.values() for r in v.get("leads") or [])) + sorted(timeline.TRAILS)


def spoken_frame(shape: str, sheet: dict) -> str:
    """The header as said: mode label, then the writer's topic. A period, not a
    dash — the voice takes a period as a sentence break."""
    return f"{MODE_LABEL[shape]}. {(sheet.get('frame') or '').strip()}".strip()


def shape_names(shapes: list[str]) -> list[str]:
    return [SHAPE_NAME[s][s in shapes[:i]] for i, s in enumerate(shapes)]


def roadmap(shapes: list[str], lap: bool) -> str:
    """One line naming what the tape holds, built from the movements that PLAYED
    and spliced on after the render (the clock can stop a tape short of its plan).
    About the tape, never the listener."""
    n, short = len(shapes), len(shapes) <= ROADMAP_MAX
    names = shape_names(shapes) if short else [SHAPE_NAME[s][0] for s in dict.fromkeys(shapes)]
    joined = " and ".join(names) if len(names) < 3 else f"{', '.join(names[:-1])}, and {names[-1]}"
    return (f"{n} round{'s' * (n != 1)}{'' if short else ', turning through'}: {joined}."
            + (" Then one lap of everything." if lap else ""))


def closing_lap(sheets: list[tuple]) -> list[tuple[str, bool]]:
    """Every target line the tape spoke, once, grouped under the movement that
    introduced it -> [(text, is_header)], named in the roadmap's words."""
    out, seen = [], set()
    names = shape_names([mv["shape"] for mv, _ in sheets])
    for (mv, sheet), name in zip(sheets, names):
        new = [s for s in dict.fromkeys((b.get("say") or "").strip() for b in sheet["beats"])
               if s and s not in seen]
        seen |= set(new)
        if new:
            out += [(name[0].upper() + name[1:] + ".", True)] + [(s, False) for s in new]
    return out


# ── Item selection ──────────────────────────────────────────────────────────

def _rank(spine: str, hosts: dict):
    """Ordering per spine; lower sorts first. Items not yet firing lead (a cold
    word is used, not drilled). The LAST key is staleness — never-aired first —
    which is why two tapes of one spine differ without any stored cursor."""
    unfired = {"none": 0, "hinted": 1, "cold": 2}

    def key(r):
        prod = unfired.get(r["production"], 3)
        seen = r["last_surfaced"] or ""
        if spine == "machines":
            return (0 if r["type"] == "pattern" else 1, 0 if r["register"] else 1,
                    prod, seen)
        if spine == "inventory":
            return (0 if r["word"] in hosts else 1, -len(hosts.get(r["word"], [])),
                    prod, seen)
        reg = r["register"]
        return (0 if reg else 1,
                REGISTER_ORDER.index(reg) if reg in REGISTER_ORDER else len(REGISTER_ORDER),
                prod, seen)
    return key


def build_pool(spine: str, payload: list[str]) -> list[dict]:
    """The whole lexicon is in scope, but only what the spine's shape can teach
    from is usable (`SPINE_QUALIFIES`): a longer ask must not buy worse items.
    The inventory spine leads with the intake quota (pool words with hosts and no
    row yet). Commissioned words lead regardless — a payload the lane ignored
    could never satisfy the order that dispatched it."""
    lexicon = load_json(LEXICON_PATH) or {}
    hosts = inventory_hosts(lexicon)
    intake = (intake_rows(lexicon, load_json(WORD_POOL_PATH) or [])
              if spine == "inventory" else [])
    rows = [{"word": k,
             "gloss": rec.get("gloss", ""),
             "production": rec.get("production", "none"),
             "direction": rec.get("direction", ""),
             "type": rec.get("type", ""),
             "register": rec.get("register", ""),
             "last_surfaced": rec.get("last_surfaced") or "",
             "hosts": hosts.get(k, [])}
            for k, rec in lexicon.items()]
    rows.sort(key=_rank(spine, hosts))
    want = canon_payload(payload)
    fits = SPINE_QUALIFIES[spine]
    head = [r for r in rows if r["word"] in want] + intake
    return head + [r for r in rows if r["word"] not in want and fits(r)]


# ── The plan ────────────────────────────────────────────────────────────────

def movement_count(minutes: float) -> int:
    """The CEILING `--minutes` implies; the material decides the real count."""
    return max(4, round((minutes - CLOSING_LAP_MIN) / MOVEMENT_MIN))


def pool_size(spine: str, count: int) -> int:
    """Items needed to cover `count` movements, sized one movement short: a tape
    the clock cuts drops a repeat, never a word's only airing."""
    cad = CADENCES[spine]
    return sum(ITEMS[cad[i % len(cad)]] for i in range(max(1, count - 1))
               if cad[i % len(cad)] not in RECALL_SHAPES)


def movements_for(spine: str, items: int) -> int:
    """The movements it takes to air `items` once — `pool_size` backwards, +1."""
    return next((c for c in range(4, 200) if pool_size(spine, c) >= items), 200) + 1


# What each spine's LEAD SHAPE needs of an item — what bounds an honest tape.
SPINE_QUALIFIES = {"inventory": lambda r: bool(r["hosts"]),
                   "machines": lambda r: (r["type"] == "pattern"
                                          or r["word"].startswith("frame:")),
                   "room": lambda r: bool(r["register"])}


def plan_movements(pool: list[dict], spine: str, count: int) -> list[dict]:
    """Round-robin the pool through the cadence: coverage first, recurrence
    second. INVARIANT (smoke): a recall movement only names items an earlier
    movement already taught."""
    cad = CADENCES[spine]
    plan: list[dict] = []
    taught: list[dict] = []
    cursor = 0
    for i in range(count):
        shape = cad[i % len(cad)]
        n = ITEMS[shape]
        if shape in RECALL_SHAPES:
            items = taught[-n:] if taught else []
        else:
            items = [pool[(cursor + j) % len(pool)] for j in range(min(n, len(pool)))]
            cursor += n
            taught.extend(items)
        plan.append({"shape": shape, "items": items})
    return plan


# ── The sheets: one small call per movement ─────────────────────────────────

from mandates import BASE_MANDATE, SHAPE_CLAUSES  # noqa: E402


def write_movement(mv: dict, spine: str, brief: str | None = None) -> dict:
    """One movement, one small call. `brief` is a commission's external guidance:
    it steers emphasis, never the spine's shape, and it CARRIES its state (the
    writer has no file access)."""
    canon = voice_canon()
    menu = "\n".join(
        f"- {i['word']} — {i['gloss'] or '[no gloss]'}"
        + (f"  HOSTS: {', '.join(i['hosts'])}" if i["hosts"] else "")
        for i in mv["items"])
    mandate = f"{BASE_MANDATE}\n{SHAPE_CLAUSES[mv['shape']]}"
    brief_block = f"COMMISSION BRIEF (external — what this tape is for, not what it teaches):\n{brief.strip()}\n\n" if (brief or "").strip() else ""
    sheet = ask_json(f"{canon}\n\n---\n\n{mandate}",
                     f"THE TAPE'S SPINE: {spine}\n\n{brief_block}ITEMS FOR THIS MOVEMENT:\n{menu}",
                     MOVEMENT_SCHEMA)
    sheet["beats"] = [b for b in sheet.get("beats", [])
                      if (b.get("say") or "").strip() or (b.get("en") or "").strip()]
    return sheet


# ── The render: Python owns every second ────────────────────────────────────

def silence(seconds: float) -> bytes:
    return SILENCE_FRAME * int(seconds * SILENCE_PER_SEC)


def movement_voices(n: int) -> tuple[str, str]:
    """Two fresh character voices per movement, alternating which gender leads.
    The tutor and the overheard voice stay pinned; everyone else rotates."""
    male_pool = _CHIRP_POOL_MALE or _EDGE_POOL_MALE or [TUTOR_VOICE]
    female_pool = _CHIRP_POOL_FEMALE or _EDGE_POOL_FEMALE or [EAVESDROP_VOICE or TUTOR_VOICE]
    male = male_pool[n % len(male_pool)]
    female = female_pool[n % len(female_pool)]
    return (female, male) if n % 2 else (male, female)


class Tape:
    """The accumulating tape, and the only thing that knows what time it is."""

    def __init__(self, tmp: str):
        self.audio = bytearray()
        self.tmp = tmp
        self.cache: dict[tuple[str, str], bytes] = {}
        self.idx = 0
        self.spoken: list[str] = []      # every target line that actually played
        self.tail = 0                    # silence frames the tape currently ends on

    async def say(self, text: str, voice: str) -> bytes:
        """Cached per (line, voice): the tape repeats lines by design."""
        key = (text, voice)
        if key not in self.cache:
            self.idx += 1
            f = await generate_segment(clean_for_tts(text), voice, self.idx, self.tmp)
            self.cache[key] = get_raw_mp3_frames(f)
            os.remove(f)
        return self.cache[key]

    async def add(self, text: str, voice: str, gap: float, target: bool = False):
        self.audio.extend(await self.say(text, voice))
        if target:
            self.spoken.append(text)
        self.audio.extend(silence(gap))
        self.tail = int(gap * SILENCE_PER_SEC)

    async def header(self, text: str):
        """A section header, topped up to PRE_FRAME of air before (counted in
        frames), 1.2s after."""
        self.audio.extend(SILENCE_FRAME * max(0, int(PRE_FRAME * SILENCE_PER_SEC) - self.tail))
        await self.add(text, TUTOR_VOICE, 1.2)

    def minutes(self, path: Path) -> float:
        """MEASURED, never estimated from byte count."""
        path.write_bytes(self.audio)
        from rebuild_rss import audio_duration
        return (audio_duration(str(path)) or 0) / 60


SCRIPTS_DIR = BASE / "content" / "scripts"
# Who voices a beat, for the written page.
WHO = {"a": "FIRST", "b": "SECOND"}
TUTOR_LABEL = TUTOR.upper()


def write_script(mp3: Path, spine: str, measured: float, sheets: list[tuple],
                 title: str | None = None) -> Path:
    """The written source text, saved beside the audio — from the sheets that
    actually PLAYED, with every spoken line (roadmap, mode labels, lap) built by
    the same functions the render calls, so it cannot drift from the audio."""
    lap = closing_lap(sheets)
    lines = [f"# Rotation — {title or spine} · {datetime.now():%Y-%m-%d}", "",
             "<!-- GENERATED by scripts/render_rotation.py — this is the source text",
             "     sent to the TTS, not a transcript. It is the story as written.",
             f"     AUDIO: published_audio/{mp3.name}",
             f"     MEASURED {measured:.1f} min over {len(sheets)} movements. -->", ""]
    if sheets:
        lines += ["## roadmap", "",
                  f"**{TUTOR_LABEL}:** {roadmap([mv['shape'] for mv, _ in sheets], bool(lap))}", ""]
    for n, (mv, sheet) in enumerate(sheets, 1):
        lines += [f"## {n}. {mv['shape']} — {sheet.get('frame') or '(no frame line)'}", "",
                  f"**{TUTOR_LABEL}:** {spoken_frame(mv['shape'], sheet)}", ""]
        for beat in sheet["beats"]:
            say, en = (beat.get("say") or "").strip(), (beat.get("en") or "").strip()
            who = WHO.get(beat.get("who"), TUTOR_LABEL) if mv["shape"] == "scene" else \
                ("OVERHEARD" if mv["shape"] == "eavesdrop" else TUTOR_LABEL)
            if say:
                lines.append(f"**{who}:** {say}")
            if en:
                lines.append(f"> {en}" if say else f"**{who}:** {en}")
            lines.append("")
    lines += ["## closing lap", ""]
    if lap:
        lines += [f"**{TUTOR_LABEL}:** {LAP_IN}", ""]
        for text, head in lap:
            lines += ["", f"**{TUTOR_LABEL}:** {text}", ""] if head else [f"**{TUTOR_LABEL}:** {text}"]
        lines.append("")
    lines += [f"**{TUTOR_LABEL}:** {LAP_OUT}", ""]
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / f"{mp3.stem}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def render_movement(tape: Tape, mv: dict, sheet: dict, n: int):
    """Teaching shapes get the soak law — the sound first, the gloss once, the
    sound again to settle. Scenes and eavesdrops run once, at speed."""
    after_say, after_en, after_beat = RHYTHM[mv["shape"]]
    voice_a, voice_b = movement_voices(n)
    await tape.header(spoken_frame(mv["shape"], sheet))
    for beat in sheet["beats"]:
        say, en = (beat.get("say") or "").strip(), (beat.get("en") or "").strip()
        if mv["shape"] == "lore":
            if en:
                await tape.add(en, TUTOR_VOICE, after_say if say else after_beat)
            if say:
                await tape.add(say, TUTOR_VOICE, after_beat, target=True)
            continue
        if mv["shape"] == "eavesdrop":
            await tape.add(say, EAVESDROP_VOICE or voice_b, after_beat, target=True)
            continue
        if mv["shape"] == "scene":
            await tape.add(say, voice_b if beat.get("who") == "b" else voice_a,
                           after_beat, target=True)
            continue
        await tape.add(say, TUTOR_VOICE, after_say, target=True)
        if en:
            await tape.add(en, TUTOR_VOICE, after_en)
        await tape.add(say, TUTOR_VOICE, after_say)
        await tape.add(say, TUTOR_VOICE, after_beat)


async def render(plan: list[dict], spine: str, out: Path, minutes: float,
                 writer=write_movement) -> tuple[float, int, list[str], list[tuple]]:
    """Sheets are written JUST IN TIME and the tape stops when the measured clock
    reaches the target: nothing is written that does not play. The played sheets
    come back out so the written story can be saved beside the audio."""
    tmp = tempfile.mkdtemp(prefix="rotation_")
    tape = Tape(tmp)
    sheets: list[tuple] = []
    try:
        for n, mv in enumerate(plan):
            elapsed = tape.minutes(out)
            if elapsed >= minutes:
                break
            print(f"   [{n+1}/{len(plan)}] {mv['shape']:<9} "
                  f"({elapsed:.1f}/{minutes:.0f} min)")
            sheet = writer(mv, spine)
            await render_movement(tape, mv, sheet, n)
            sheets.append((mv, sheet))
        # The closing lap: target only, no glosses, one pass — a recap of lines
        # placed in context earlier on this tape, not a list taught cold. Its
        # spoken lines say nothing about the listener.
        lap = closing_lap(sheets)
        if lap:
            await tape.add(LAP_IN, TUTOR_VOICE, 1.5)
            for text, head in lap:
                await (tape.header(text) if head else tape.add(text, TUTOR_VOICE, 1.0))
        await tape.add(LAP_OUT, TUTOR_VOICE, 0.5)
        # The roadmap goes on last, at the front: only now is it known what played.
        if sheets:
            tape.audio[0:0] = await tape.say(
                roadmap([mv["shape"] for mv, _ in sheets], bool(lap)), TUTOR_VOICE)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return tape.minutes(out), len(sheets), tape.spoken, sheets


# ── CLI ─────────────────────────────────────────────────────────────────────

def audible(pool: list[dict], spoken: list[str], sheets: list[tuple]) -> list[str]:
    """What this tape actually delivered — only what was AUDIBLE is claimed. A
    chunk is claimed when its text was spoken; a FRAME is a label for a pattern
    realised across beats and is never spoken by name, so it is claimed when the
    movement holding it played and produced beats."""
    blob = " ".join(spoken)
    ran = {i["word"] for mv, sheet in sheets if sheet.get("beats") for i in mv["items"]}
    return [i["word"] for i in pool
            if (i["word"] in ran if i["word"].startswith("frame:") else i["word"] in blob)]


def rotation_brief() -> tuple[str | None, list[str]]:
    """The standing soak order, when addressed to THIS lane -> (focus, payload)."""
    order = (load_json(BASE / "progress" / "learner.json") or {}).get("soak_order") or {}
    if (order.get("channel") or "episode") != "rotation":
        return None, []
    return (order.get("focus") or "").strip() or None, [w for w in order.get("payload") or [] if w]


def brief_reach(brief: str, sheets: list[tuple]) -> str:
    """Which of the brief's NAMES (capitalised words not opening a sentence)
    reached the played sheets — an observation for the log, never a gate."""
    names = list(dict.fromkeys(m.group(1) for m in re.finditer(
        r"(?<=\s)(?<![.:!?]\s)([A-Z][a-z]{2,})", brief)))
    text = " ".join([sh.get("frame") or "" for _, sh in sheets] + [
        f"{b.get('say')} {b.get('en')}" for _, sh in sheets for b in sh["beats"]]).lower()
    hit = [n for n in names if n.lower() in text]
    return (f"{len(hit)}/{len(names)} brief names reached the sheets: {', '.join(hit) or 'none'}"
            f" · absent: {', '.join(n for n in names if n not in hit) or 'none'}")


def expected_min(count: int) -> float:
    """What `count` movements should measure — a prediction to check the
    measured number against."""
    return count * MOVEMENT_MIN + CLOSING_LAP_MIN


def describe(plan: list[dict], pool: list[dict], minutes: float):
    est = expected_min(len(plan))
    capped = est > minutes
    print(f"\nPLAN — {len(plan)} movements, ~{est:.0f} min expected"
          + (f", CAPPED at the {minutes:.0f} min ceiling" if capped
             else f" (under the {minutes:.0f} min ceiling — this spine's material)"))
    for n, mv in enumerate(plan, 1):
        words = ", ".join(i["word"] for i in mv["items"]) or "(nothing taught yet)"
        print(f"  {n:>2}. {mv['shape']:<9} {words[:88]}")
    print(f"\nPOOL — {len(pool)} items"
          f" · {sum(1 for i in pool if i['register'])} ranked"
          f" · {sum(1 for i in pool if i['production'] == 'none')} never fired"
          f" · {sum(1 for i in pool if i['hosts'])} with inventory hosts"
          f" · {sum(1 for i in pool if i.get('intake'))} intake (no row yet)")


def main():
    ap = argparse.ArgumentParser(description="A press-once listening tape — nothing asked")
    ap.add_argument("--spine", choices=sorted(CADENCES), default="inventory",
                    help="the tape's centre of gravity (default: inventory)")
    ap.add_argument("--minutes", type=float, default=15,
                    help="CEILING on measured length; a spine with less material stops sooner (default 15; a long journey is --minutes 45)")
    ap.add_argument("--plan-only", action="store_true",
                    help="print the movement plan and stop — no network at all")
    ap.add_argument("--dry-run", action="store_true",
                    help="plan + write the first sheet; no TTS, no publish")
    ap.add_argument("--no-publish", action="store_true",
                    help="render only; skip RSS/commit/push/notify")
    ap.add_argument("--if-short", action="store_true",
                    help="only build when the week's authored supply is under the floor (rails)")
    ap.add_argument("--brief", default="",
                    help="commission brief threaded into each movement's writer prompt "
                    "(from a commission file); empty for the standing shelf runs")
    # A brief cannot change the spine, so a commissioned title makes a mismatch
    # between brief and tape visible in the feed.
    ap.add_argument("--title", default="",
                    help="the feed title (from a commission file); default: the spine")
    args = ap.parse_args()
    title = args.title.strip() or args.spine

    # THE SHELF, NOT THE LEARNER: `--if-short` asks whether the WEEK PRODUCED
    # enough audio, never whether anyone listened (that would be a streak).
    if args.if_short:
        from rebuild_rss import feed_items
        from state_io import local_today
        from datetime import date as _date, timedelta as _td
        today = local_today()
        window = (today - _td(days=rails.SUPPLY_WINDOW_DAYS - 1)).isoformat()
        items = [i for i in feed_items() if (i.get("date") or "") >= window]
        produced = sum(i.get("minutes") or 0 for i in items)
        last = [i.get("date") for i in feed_items()
                if (i.get("format") or "").split("/")[0] in PLEASURE_FORMATS
                and i.get("date")]
        gap = ((today - _date.fromisoformat(max(last))).days) if last else None
        if why := rails.pleasure_due(produced, gap):
            print(f"   [supply] no tape — {why}")
            return
        print(f"   [supply] {produced:.0f} min produced in "
              f"{rails.SUPPLY_WINDOW_DAYS}d, under the {rails.SUPPLY_FLOOR_MIN} floor — building")

    load_env(BASE / ".env")
    writer = lambda mv, spine, _b=(args.brief or "").strip() or None: write_movement(mv, spine, _b)
    focus, payload = rotation_brief()
    pool = build_pool(args.spine, payload)
    if not pool:
        sys.exit(f"No material for the '{args.spine}' spine — nothing to build a tape from.")
    # The material sets the length; `--minutes` only caps it (+2 slack so the
    # measured clock, not an exhausted plan, ends a long-enough tape).
    count = min(movements_for(args.spine, len(pool)), movement_count(args.minutes) + 2)
    plan = plan_movements(pool, args.spine, count)
    print(f"1. plan… (spine: {args.spine}"
          f"{f' · {len(payload)} commissioned' if payload else ''}"
          f"{' · FOCUS: ' + focus if focus else ''})")
    describe(plan, pool, args.minutes)

    if args.plan_only:
        return
    if args.dry_run:
        print("\n2. first sheet…")
        print(json.dumps(writer(plan[0], args.spine), ensure_ascii=False, indent=2))
        return

    reason = tts_ready()
    if reason:
        print(f"⏭️  Skipping render — {reason}. This host cannot produce audio.")
        sys.exit(EXIT_NOT_CONFIGURED)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    mp3 = ROTATION_DIR / f"rotation_{args.spine}_{stamp}.mp3"
    mp3.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n2. render… (target {args.minutes:.0f} min)")
    measured, played, spoken, sheets = asyncio.run(
        render(plan, args.spine, mp3, args.minutes, writer=writer))
    print(f"   rendered -> {mp3} ({measured:.1f} min, {played} movements)")
    # Before the publish gate, so a local render still leaves the story on disk.
    script = write_script(mp3, args.spine, measured, sheets, title)
    print(f"   script   -> {script}")
    if args.brief.strip():
        print(f"   [brief] {brief_reach(args.brief, sheets)}")
    # Stopping under --minutes is the honest length; what is flagged is the
    # calibration drifting from the rhythm table.
    predicted = expected_min(played)
    if played and abs(measured - predicted) > max(3.0, predicted * 0.25):
        print(f"   ⚠ {measured:.1f} min against {predicted:.1f} predicted for {played} "
              f"movements — MOVEMENT_MIN ({MOVEMENT_MIN}) has drifted from the rhythm "
              f"table. Re-measure it; the tape itself is fine.")

    if args.no_publish:
        return

    print("3. publish…")
    delivered = audible(pool, spoken, sheets)
    print(f"   {len(delivered)}/{len(pool)} pool items audible on the tape")
    # Only teaching shapes hand a word over with its meaning (a Teach Beat), read
    # off the sheets that rendered. The script rides the mp3's commit.
    gave = {i["word"] for mv, sheet in sheets
            if sheet.get("beats") and mv["shape"] not in RECALL_SHAPES
            for i in mv["items"]}
    deliver_rendered(
        mp3=mp3, lane="rotation", delivered=delivered,
        taught=[w for w in delivered if w in gave],
        intake={r["word"]: r for r in pool if r.get("intake")},
        claimed=bool(focus or payload), extra_paths=[script],
        message=f"Rotation tape: {title} ({measured:.0f} min)",
        title=title,
        copy=f"rotation tape's up — {measured:.0f} min, {title}. press once 🎧",
        noun="tape", commit=commit_and_push, notify=push_to_phone)


if __name__ == "__main__":
    main()
