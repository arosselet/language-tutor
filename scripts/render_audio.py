#!/usr/bin/env python3
"""
Generate multi-voice podcast audio from a markdown script.

Usage:
    python scripts/render_audio.py <input_script.md> <output.mp3>

Reads dialogue lines prefixed with **Speaker Name:**, generates TTS segments with
Google (Chirp/WaveNet) or edge-tts, and stitches them into one MP3. A Voice Map
comment in the script assigns voices explicitly (`world.voice_map` writes it).
"""

import re
import os
import asyncio
import argparse
import base64
import random
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent.parent

# A host without TTS credentials is not a failure. Callers read this code as
# "skip, don't retry": retrying an absent secret just fills the log.
EXIT_NOT_CONFIGURED = 3

from publish import commit_and_push
from pack import TTS_PROVIDER, VOICE_POOLS, is_canonical, unmark, voice_locale

import edge_tts

try:
    from google.cloud import texttospeech
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False


def materialize_sa_key() -> str | None:
    """GCP_SA_KEY (the CI secret's name) → a file ADC can resolve, so a laptop
    whose .env carries the same secret can render too. Accepts raw JSON or base64
    (a .env value must survive on ONE line). Written outside the repo at 0600 so
    it can never be committed; an existing GOOGLE_APPLICATION_CREDENTIALS wins.
    Never logs the secret — only whether it parsed."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return None
    raw = (os.environ.get("GCP_SA_KEY") or "").strip()
    if not raw:
        return None
    doc = None
    try:
        doc = json.loads(raw)
    except ValueError:
        try:
            doc = json.loads(base64.b64decode(raw))
        except Exception:
            doc = None
    if not isinstance(doc, dict) or "private_key" not in doc:
        print(f"   ⚠ GCP_SA_KEY is set ({len(raw)} chars) but is not a service-account "
              f"key — expected JSON (or base64 of it) carrying private_key. Ignoring it.")
        return None
    path = Path(tempfile.gettempdir()) / "tutor-gcp.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass          # best-effort; Windows ACLs don't map onto POSIX modes
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
    return str(path)


def google_credentials_ready() -> str | None:
    """None when Google TTS can authenticate, else the reason. Local and cheap,
    checked ONCE before the render loop so a credential-less host skips in a
    second instead of burning retries on segment 0."""
    if not HAS_GOOGLE:
        return "google-cloud-texttospeech is not installed"
    materialize_sa_key()
    try:
        import google.auth
        google.auth.default()
    except Exception as e:
        return f"no Google application-default credentials ({type(e).__name__})"
    return None


def is_auth_error(e: Exception) -> bool:
    """Credential/permission failures are permanent — backoff cannot fix an
    absent secret. Everything else stays retryable."""
    name = type(e).__name__
    if name in ("DefaultCredentialsError", "Unauthenticated", "PermissionDenied",
                "Forbidden", "RefreshError"):
        return True
    return any(s in str(e).lower() for s in
               ("credential", "unauthenticated", "permission denied", "api key"))


def new_scratch_dir() -> str:
    """A fresh TTS scratch dir per render: two concurrent renders must never share one."""
    return tempfile.mkdtemp(prefix="tts_segments_")


def acquire_state_lock():
    """Serialize the state tail (episodes.json → rss.xml → commit/push) against
    other studio processes via `.studio.lock`; a child of a lock holder inherits
    (STUDIO_LOCK_HELD). The render itself is not covered — per-run temp dirs make
    concurrent renders safe, and locking ten minutes of TTS would serialize the
    slow part for nothing."""
    if os.environ.get("STUDIO_LOCK_HELD") == "1":
        return None
    try:
        import fcntl
    except ImportError:
        return None
    fd = open(BASE / ".studio.lock", "w")
    for attempt in range(60):  # up to ~60s: the tail is seconds long, not minutes
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except OSError:
            if attempt == 0:
                print("   ⏳ another studio process holds .studio.lock — waiting to publish…")
            time.sleep(1)
    fd.close()
    print("   ⚠️ gave up waiting for .studio.lock — publishing without it")
    return None


# Voice POOLS — the casting catalogue, from the pack. The pinned tutor and
# eavesdrop voices are choices from it (`pack.TUTOR_VOICE`, `pack.EAVESDROP_VOICE`).
def _pool(tier: str, sex: str) -> list[str]:
    return list(VOICE_POOLS.get(tier, {}).get(sex, []))


_CHIRP_POOL_MALE = _pool("chirp", "male")
_CHIRP_POOL_FEMALE = _pool("chirp", "female")
_CHIRP_POOL = _CHIRP_POOL_MALE + _CHIRP_POOL_FEMALE
_WAVENET_POOL_MALE = _pool("wavenet", "male")
_WAVENET_POOL_FEMALE = _pool("wavenet", "female")
_WAVENET_POOL = _WAVENET_POOL_MALE + _WAVENET_POOL_FEMALE
_EDGE_POOL_MALE = _pool("edge", "male")
_EDGE_POOL_FEMALE = _pool("edge", "female")
_EDGE_POOL = _EDGE_POOL_MALE + _EDGE_POOL_FEMALE

# Regex: matches "**Speaker:** text"
SPEAKER_RE = re.compile(
    r"^\s*(?:\*\s*)?\*\*\s*([^:]+)\s*:\s*(?:\*\*\s*)?(.*)", re.IGNORECASE
)
# Every pause form the scripts use: "[Pause: 1 sec]", "[Pause: 0.5 sec]", and a
# bare "[pause]" (one beat). `[^\]]*`, not `.*`: a greedy tail swallows the text
# BETWEEN two pauses on one line.
PAUSE_RE = re.compile(
    r"\[pause(?::\s*(\d+(?:\.\d+)?)\s*sec[^\]]*)?\]", re.IGNORECASE
)
SFX_RE = re.compile(r"^\[SFX\b", re.IGNORECASE)
EMBED_RE = re.compile(r"\[Intercept (audio )?plays\]", re.IGNORECASE)
VOICE_MAP_RE = re.compile(r"Voice Map\s*:\s*(\{.*?\})", re.DOTALL | re.IGNORECASE)

def pause_seconds(match: re.Match) -> float:
    """Seconds for a matched pause cue; a bare '[pause]' is one beat."""
    return float(match.group(1)) if match.group(1) else 1.0


def split_on_pauses(speaker: str, text: str) -> list[dict]:
    """One spoken line → speech / pause / speech in written order. A pause INSIDE
    a line is a beat within it, never a replacement for it."""
    items: list[dict] = []
    cursor = 0
    for match in PAUSE_RE.finditer(text):
        head = text[cursor:match.start()].strip()
        if head:
            items.append({"speaker": speaker, "text": head})
        items.append({"speaker": "PAUSE", "seconds": pause_seconds(match)})
        cursor = match.end()
    tail = text[cursor:].strip()
    if tail:
        items.append({"speaker": speaker, "text": tail})
    return items


def parse_script(file_path: str) -> tuple[list[dict], dict]:
    """Parse a markdown script for dialogue lines, pauses, and voice mapping."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    voice_map = {}
    map_match = VOICE_MAP_RE.search(content)
    if map_match:
        try:
            voice_map = json.loads(map_match.group(1))
            print(f"✅ Found explicit Voice Map: {voice_map}")
        except json.JSONDecodeError:
            print("⚠️ Warning: Failed to parse Voice Map JSON.")

    lines = content.splitlines()
    dialogue = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if SFX_RE.match(line):
            # No sound library — an SFX cue becomes a beat of air
            dialogue.append({"speaker": "PAUSE", "seconds": 1.5})
            continue

        if EMBED_RE.search(line):
            dialogue.append({"speaker": "EMBED_INTERCEPT"})
            continue

        if line == "---":
            dialogue.append({"speaker": "PAUSE", "seconds": 1})
            continue

        # The speaker question is asked BEFORE the pause question: a spoken line
        # that merely contains a pause must not become silence.
        match = SPEAKER_RE.match(line)
        if match:
            speaker = match.group(1).strip().upper()
            dialogue.extend(split_on_pauses(speaker, match.group(2).strip()))
            continue

        # Not speech, but it carries a pause cue: the line IS the pause.
        pause_match = PAUSE_RE.search(line)
        if pause_match:
            dialogue.append({"speaker": "PAUSE", "seconds": pause_seconds(pause_match)})

    final_dialogue = []
    for item in dialogue:
        if item["speaker"] == "PAUSE":
            if final_dialogue and final_dialogue[-1]["speaker"] == "PAUSE":
                final_dialogue[-1]["seconds"] += item["seconds"]
            else:
                final_dialogue.append(item)
        else:
            final_dialogue.append(item)

    return final_dialogue, voice_map


def defang_hyphens(text: str) -> str:
    """A hyphen glued to a word is voiced as 'minus'."""
    return re.sub(r"-(?=\w)|(?<=\w)-", " ", text)


def clean_memo_for_tts(text: str) -> str:
    """Clean a narrated memo paragraph for TTS: span brackets out, markdown out,
    periods kept (prose needs them), internal newlines collapsed (a single-\\n
    list in one TTS call confuses the voice)."""
    text = defang_hyphens(unmark(text))
    text = re.sub(r"[*_#`]", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def clean_for_tts(text: str) -> str:
    """Clean a script dialogue line for TTS. Periods are kept: they are the
    sentence breaks the voice needs for prosody."""
    text = unmark(text)
    text = re.sub(r"\s*\(.*?\)\s*", " ", text)
    text = re.sub(r"\s*\[.*?\]\s*", " ", text)
    replacements = {"JSON": "jay-son", "CLI": "C-L-I"}
    for word, phonetic in replacements.items():
        text = re.sub(rf"\b{word}\b", phonetic, text, flags=re.IGNORECASE)
    text = re.sub(r"[*_#`]", "", text)
    text = defang_hyphens(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def generate_segment_edge(text: str, voice: str, index: int, temp_dir: str) -> str:
    """Generate a single audio segment using edge-tts."""
    communicate = edge_tts.Communicate(text, voice)
    filename = os.path.join(temp_dir, f"segment_{index:04d}.mp3")
    await communicate.save(filename)
    return filename


async def generate_segment_google(text: str, voice: str, index: int, temp_dir: str, max_retries: int = 5) -> str:
    """Generate a single audio segment using Google Cloud TTS with exponential backoff."""
    client = texttospeech.TextToSpeechClient()
    input_text = texttospeech.SynthesisInput(text=text)
    voice_params = texttospeech.VoiceSelectionParams(
        language_code=voice_locale(voice), name=voice)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, sample_rate_hertz=24000)
    for attempt in range(max_retries):
        try:
            response = client.synthesize_speech(input=input_text, voice=voice_params, audio_config=audio_config)
            filename = os.path.join(temp_dir, f"segment_{index:04d}.mp3")
            with open(filename, "wb") as out:
                out.write(response.audio_content)
            return filename
        except Exception as e:
            if is_auth_error(e):
                raise  # permanent — no amount of backoff conjures a credential
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt + random.random()
            print(f"   ⚠️ Retry {attempt+1}/{max_retries} after {wait:.1f}s — {e}")
            time.sleep(wait)


async def generate_segment(text: str, voice: str, index: int, temp_dir: str) -> str:
    """One segment on the CONFIGURED provider — what every lane calls."""
    if TTS_PROVIDER == "edge":
        return await generate_segment_edge(text, voice, index, temp_dir)
    return await generate_segment_google(text, voice, index, temp_dir)


def tts_ready() -> str | None:
    """None when the configured provider can synthesize here, else the reason.
    edge-tts needs no credential; Google needs application-default credentials."""
    return None if TTS_PROVIDER == "edge" else google_credentials_ready()


def get_raw_mp3_frames(filepath: str) -> bytes:
    """Extract raw MPEG audio chunk."""
    with open(filepath, "rb") as f:
        data = f.read()
    offset = 0
    if data.startswith(b"ID3"):
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        offset = 10 + size
    if offset < len(data) - 1 and data[offset] == 0xFF and (data[offset+1] & 0xE0) == 0xE0:
        padding = (data[offset+2] & 0x02) >> 1
        frame_len = 144 + padding
        frame_data = data[offset:offset+frame_len]
        if b"Xing" in frame_data or b"Info" in frame_data:
            offset += frame_len
    end_offset = len(data)
    if end_offset >= 128 and data[-128:].startswith(b"TAG"):
        end_offset -= 128
    return data[offset:end_offset]


SILENCE_FRAME_B64 ="//NkxJoiPA4Vgc1AAVXPcXO05CbzflKqdX8LXO/PQy7v6mbnkYz3BsVdxH7xI1psbFEYzt6Fxl0w17Szht3EmOWRKhJANxpojDXhk+E+3qNp+0+oomHuYca0xPxKUOihtdfcvPB+yzd2o2Sbh5zuLHVDDK9juB8rHhbq9lYT0XEdvYWKCGEeTvz8YP2XWipB"
SILENCE_FRAME = base64.b64decode(SILENCE_FRAME_B64)

def assign_voices(dialogue, voice_map, provider, voice_type):
    """Assign a voice to every speaker: the explicit map first, then a random
    pick from the pool, honouring (M)/(F) in the speaker tag."""
    speakers = set(d["speaker"] for d in dialogue if d["speaker"] != "PAUSE" and d["speaker"] != "EMBED_INTERCEPT")

    assigned = {}
    for speaker, voice in voice_map.items():
        assigned[speaker.upper()] = voice

    if provider == "google":
        pool_male = list(_CHIRP_POOL_MALE if voice_type == "chirp" else _WAVENET_POOL_MALE)
        pool_female = list(_CHIRP_POOL_FEMALE if voice_type == "chirp" else _WAVENET_POOL_FEMALE)
        pool_any = list(_CHIRP_POOL if voice_type == "chirp" else _WAVENET_POOL)
    else:
        pool_male = list(_EDGE_POOL_MALE)
        pool_female = list(_EDGE_POOL_FEMALE)
        pool_any = list(_EDGE_POOL)

    available_male = [v for v in pool_male if v not in assigned.values()]
    if not available_male: available_male = list(pool_male)
    random.shuffle(available_male)

    available_female = [v for v in pool_female if v not in assigned.values()]
    if not available_female: available_female = list(pool_female)
    random.shuffle(available_female)

    available_any = [v for v in pool_any if v not in assigned.values()]
    if not available_any: available_any = list(pool_any)
    random.shuffle(available_any)

    for s in sorted(list(speakers)):
        s_upper = s.upper()
        if s_upper not in assigned:
            if "(M)" in s_upper or "(MALE)" in s_upper:
                assigned[s_upper] = available_male.pop() if available_male else random.choice(pool_male)
            elif "(F)" in s_upper or "(FEMALE)" in s_upper:
                assigned[s_upper] = available_female.pop() if available_female else random.choice(pool_female)
            else:
                assigned[s_upper] = available_any.pop() if available_any else random.choice(pool_any)

    return assigned

def register_mission_in_state(script_path: Path, mp3_path: Path):
    """Register a new mission in progress/episodes.json and record its exposure.
    Paths are absolute off BASE, so a test importing a sandbox copy can never
    write into the real progress/ files."""
    from pathlib import Path
    EPISODES_PATH = BASE / "progress" / "episodes.json"
    LEXICON_PATH = BASE / "progress" / "lexicon.json"

    def load_json(path: Path):
        if not path.exists(): return {}
        with open(path, "r", encoding="utf-8") as f: return json.load(f)

    def save_json(path: Path, data):
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

    def get_duration(p: Path) -> float:
        """Measured, or LOUD — never a plausible fiction: an invented length
        corrupts the meter the learner judges an episode by. 0.0 with a warning
        is the honest floor."""
        from rebuild_rss import audio_duration
        try:
            return (audio_duration(str(p)) or 0) / 60
        except Exception as e:
            print(f"   ⚠ could not measure {p.name} ({e}) — registering 0.0, not a guess")
            return 0.0

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    title_match = re.search(r"^# Tier 2, Mission \d+ — (.*)$", content, re.M)
    title = title_match.group(1) if title_match else f"Mission {script_path.stem}"
    # The structured .tags.json sidecar is the vocab source (new words +
    # callbacks). Canonical-at-write: every key must resolve to a lexicon record
    # or be a genuinely new canonical payload word — an annotation like
    # "frame:x (…)" credits frame:x, never a ghost.
    lexicon = load_json(LEXICON_PATH)

    def canonical(w: str) -> str | None:
        """A sidecar key → its lexicon key, tolerating a trailing ' (…)'."""
        for cand in (w, re.sub(r"\s*\([^)]*\)\s*$", "", w).strip()):
            if cand in lexicon:
                return cand
        return None

    cleaned_words = []
    new_word_keys = set()
    tags_path = script_path.with_suffix(".tags.json")
    sidecar_broken = False
    if tags_path.exists():
        try:
            tags = json.loads(tags_path.read_text(encoding="utf-8"))
            for bucket in ("new_words_landed", "callbacks_used"):
                for w in tags.get(bucket, {}):
                    key = canonical(w)
                    if key is None:
                        base = re.sub(r"\s*\([^)]*\)\s*$", "", w).strip()
                        if base.startswith("frame:"):
                            # Frames are seeded, never born in a render.
                            print(f"   ! sidecar frame '{w}' resolves to no lexicon pattern — skipped")
                            continue
                        key = base  # may be a brand-new payload word (created below)
                    if key not in cleaned_words:
                        cleaned_words.append(key)
                        if bucket == "new_words_landed":
                            new_word_keys.add(key)
        except (json.JSONDecodeError, OSError) as e:
            # A sidecar that EXISTS but cannot be parsed is broken, and the
            # scrape fallback would INVENT a word list from the wrong source.
            # Under-claim, loudly, rather than invent.
            sidecar_broken = True
            print(f"   ! {tags_path.name} EXISTS BUT COULD NOT BE READ "
                  f"({type(e).__name__}: {e})")
            print("     Not scraping the script instead — that would credit words "
                  "this episode never taught. Fix the sidecar and re-run.")
    if not cleaned_words and not sidecar_broken:
        for w in re.findall(r"\*\*([^\*]+)\*\*", content):
            head = re.split(r"[\(\s]", w)[0]
            if head and is_canonical(head) and head not in cleaned_words:
                cleaned_words.append(head)

    mission_match = re.search(r"mission(\d+)", script_path.name)
    if not mission_match: return
    mission_num = mission_match.group(1)

    episodes = load_json(EPISODES_PATH)
    duration = get_duration(mp3_path)

    if mission_num not in episodes:
        episodes[mission_num] = {
            "title": title, "words": cleaned_words, "duration_min": duration,
            # The unattended-production cap counts these dates.
            "produced": date.today().isoformat(),
        }
        print(f"✅ Registered Mission {mission_num} in episodes.json")
    else:
        episodes[mission_num].update({
            "title": title, "words": cleaned_words, "duration_min": duration
        })
        print(f"✅ Updated Mission {mission_num} metadata in episodes.json")

    save_json(EPISODES_PATH, episodes)

    # Record the attempt against the standing episode order, naming what it
    # could not carry: without this, an order whose payload the script said
    # another way stays NOT YET PRODUCED and every session open re-dispatches.
    from state_io import RECOGNITION_DEFAULT, mark_soak_attempted, split_payload
    order = (load_json(BASE / "progress" / "learner.json") or {}).get("soak_order") or {}
    if (order.get("channel") or "episode") == "episode" and order.get("payload"):
        wanted, _ = split_payload(order["payload"], lexicon)
        mark_soak_attempted(mission_num, [w for w in wanted if w not in cleaned_words])

    # The episode going out the door is the delivery: `new_words_landed` is a
    # Teach Beat (pending until a listen), a callback is an exposure only.
    if lexicon:
        import lexicon_view
        mnum = int(mission_num)
        src = f"episode:M{mnum}"
        events, created, unresolved = [], 0, []
        for w in cleaned_words:
            key = w if w in lexicon else None
            if key is None and w in new_word_keys and is_canonical(w):
                # Brand-new payload word: the STATIC half only; the fold owns the rest.
                lexicon[w] = {"gloss": "", "recognition": RECOGNITION_DEFAULT,
                              "production": "none", "seen_in": [], "last_surfaced": None}
                key = w
                created += 1
            if key:
                events.append(dict(word=key, channel="episode", source=src,
                                   kind="taught" if key in new_word_keys else "exposed"))
            else:
                # A callback claims the word exists: report, never mint a duplicate.
                unresolved.append(w)
        if unresolved:
            print(f"   ! sidecar callback(s) resolve to no lexicon word — NOT registered, "
                  f"NOT exposed: {unresolved}")
            print(f"     → if one is genuinely new, move it to new_words_landed in "
                  f"{tags_path.name} and re-run; if it is a variant, fix the sidecar spelling.")
        if events:
            lexicon_view.observe(events, lexicon=lexicon)
            save_json(LEXICON_PATH, lexicon)
            msg = f"   ↳ exposed {len(events)} lexicon words via M{mnum} (taught + delivery, as events)"
            if created:
                msg += f"; +{created} NEW words registered (gloss empty — backfill later)"
            print(msg)

async def main():
    parser = argparse.ArgumentParser(description="Generate multi-voice podcast audio")
    parser.add_argument("input_file", help="Input markdown script")
    parser.add_argument("output_file", help="Output MP3 file")
    parser.add_argument("--provider", choices=["edge", "google"], default=TTS_PROVIDER,
                        help=f"TTS provider (default: {TTS_PROVIDER}, from config)")
    parser.add_argument("--voice-type", choices=["chirp", "wavenet"], default="chirp", help="Google voice tier (default: chirp)")
    args = parser.parse_args()

    # .env for GCP_SA_KEY, inside main(): this module is also imported by cloud
    # lanes that get secrets from the workflow, and load_env never overrides.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from publish import load_env
    load_env(Path(__file__).resolve().parent.parent / ".env")

    print(f"📖 Parsing {args.input_file}...")
    dialogue, voice_map = parse_script(args.input_file)
    if not dialogue:
        print("❌ No dialogue lines found!")
        return

    if args.provider == "google":
        reason = google_credentials_ready()
        if reason:
            print(f"⏭️  Skipping render — {reason}.\n"
                  f"    This host is not set up to produce audio; set GCP_SA_KEY in .env "
                  f"(see SETUP.md) or render on a host that has it.")
            sys.exit(EXIT_NOT_CONFIGURED)

    speaker_assignments = assign_voices(dialogue, voice_map, args.provider, args.voice_type)
    print("🎭 Cast Assignments:")
    for s, v in speaker_assignments.items():
        print(f"   - {s}: {v}")

    temp_dir = new_scratch_dir()
    os.makedirs(os.path.dirname(args.output_file) or ".", exist_ok=True)

    print("🎙️ Generating audio segments...")
    final_audio_data = bytearray()

    try:
        for i, line in enumerate(dialogue):
            speaker = line["speaker"]
            if speaker == "PAUSE":
                seconds = line.get("seconds", 1)
                final_audio_data.extend(SILENCE_FRAME * int(seconds * 41.666))
                continue

            if speaker == "EMBED_INTERCEPT":
                print(f"   [{i+1}/{len(dialogue)}] ⚠️ Skipping [Intercept audio plays] — deprecated in single-script mode")
                continue

            voice = speaker_assignments.get(speaker)
            clean_text = clean_for_tts(line["text"])
            if not clean_text: continue

            print(f"   [{i+1}/{len(dialogue)}] {speaker} ({voice}): {clean_text[:40]}...")

            if args.provider == "google":
                seg_file = await generate_segment_google(clean_text, voice, i, temp_dir)
            else:
                seg_file = await generate_segment_edge(clean_text, voice, i, temp_dir)

            final_audio_data.extend(get_raw_mp3_frames(seg_file))
            final_audio_data.extend(SILENCE_FRAME * 21) # ~500ms breath between lines
            os.remove(seg_file)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    for folder in ["audio", "published_audio"]:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, os.path.basename(args.output_file))
        with open(path, "wb") as f:
            f.write(final_audio_data)
        print(f"💾 Saved → {path}")

    print(f"✅ Success! ({len(final_audio_data)/(1024*1024):.1f} MB)")

    # The state tail, under .studio.lock so two studio processes never
    # interleave episodes.json / rss.xml / the commit.
    lock = acquire_state_lock()
    try:
        register_mission_in_state(Path(args.input_file), Path(args.output_file))

        subprocess.run([sys.executable, str(BASE / "scripts" / "rebuild_rss.py")],
                       cwd=BASE, check=True)

        # Stage THIS mission's files by name: a commit must only ever carry the
        # episode it rendered, never a concurrently written draft.
        stem = Path(args.input_file).stem
        candidates = [
            Path("rss.xml"),
            Path("progress/episodes.json"),
            Path("progress/lexicon.json"),
            Path("published_audio") / os.path.basename(args.output_file),
            Path("content/lessons") / f"{stem}_brief.md",
            Path("content/captions") / f"{stem}.md",
            # The beat the studio appended to the canon: continuity rides the
            # episode's own commit, or the world remembers nothing in git.
            Path("content/world.md"),
            Path(args.input_file),
            Path(args.input_file).with_suffix(".tags.json"),
        ]
        paths = [BASE / p for p in candidates if (BASE / p).exists()]

        # Through the same rebase net every writer uses; a re-render that changed
        # no bytes is a no-op line, not a crash.
        subprocess.run(["git", "add", "--", *[str(p.relative_to(BASE)) for p in paths]],
                       cwd=BASE, check=True)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=BASE).returncode == 0:
            print("   nothing staged — no commit")
        else:
            commit_and_push(
                paths,
                f"Add lesson: {os.path.basename(args.output_file)} and update state")

    finally:
        if lock is not None:
            lock.close()

if __name__ == "__main__":
    asyncio.run(main())
