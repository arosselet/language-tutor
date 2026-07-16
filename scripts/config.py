#!/usr/bin/env python3
"""
The one config surface — config/tutor.json — that retargets the whole engine.

Everything language-, learner-, or deployment-specific that lives in *code*
(rather than in a protocol .md file) is a key in that one JSON file: the
learner's timezone, the target script's Unicode range, the TTS voice pools,
the feed identity, the outreach rails, the deck deadline, and the four short
prose fragments that parameterize the LLM prompts embedded in Python.

The setup agent writes config/tutor.json during bootstrap (see SETUP.md).
Until it exists, every script fails fast with a pointer to setup — a clone
is not a tutor yet.

Design rule: scripts read config through this module only. No other file
hardcodes a language, a voice, a timezone, or a repo URL.
"""
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).parent.parent
CONFIG_PATH = BASE / "config" / "tutor.json"

_DEFAULTS = {
    "outreach": {
        "model": "anthropic/claude-sonnet-4.6",
        "waking_start_hour": 8,
        "waking_end_hour": 21,
        "max_reaches_per_day": 5,
        "min_gap_hours": 3,
        "volley_size": 3,
    },
    "deck": {"name": "sprint", "label": "Sprint Deck",
             "deadline": None, "deadline_label": "deadline", "tiers": []},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(
            "config/tutor.json not found — this repo hasn't been bootstrapped yet.\n"
            "Open your agent in this repo and say \"set up my tutor\" (or run /setup).\n"
            "The setup protocol lives in SETUP.md."
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return _deep_merge(_DEFAULTS, cfg)


CONFIG = load_config()

# ── Convenience accessors (the names the engine actually uses) ────────────────

LEARNER = CONFIG["learner"]["name"]
LOCAL_TZ = ZoneInfo(CONFIG["learner"]["timezone"])
NATIVE_LANGUAGE = CONFIG["learner"].get("native_language", "English")

LANGUAGE = CONFIG["language"]["name"]
DIALECT = CONFIG["language"].get("dialect", "")
SCRIPT_NAME = CONFIG["language"].get("script_name", f"{LANGUAGE} script")

# The canonical-script check. When the target language uses a script distinct
# from the learner's native one, lexicon keys are canonical script and typed
# phonetics resolve against each record's phonetic list. When script_regex is
# null (Latin-script targets etc.), that split collapses: any spelling is
# canonical and the phonetic warnings are skipped.
_regex = CONFIG["language"].get("script_regex")
TARGET_RE = re.compile(_regex) if _regex else None
HAS_DISTINCT_SCRIPT = TARGET_RE is not None


def is_target(word: str) -> bool:
    """Is this token written in the target language's canonical script?
    Always True when the target shares the learner's script."""
    if TARGET_RE is None:
        return True
    return bool(TARGET_RE.search(word))


# Prompt fragments — the port surface of the LLM prompts embedded in Python
# (the knock decision, the reply judge, the drill sheet). Written at setup;
# see SETUP.md → "Derive the language rules".
CHAT_FORM = CONFIG["language"]["chat_form"]        # how the learner types the language in chat/replies
AUDIO_FORM = CONFIG["language"]["audio_form"]      # how the language must be written for TTS
WEAVE_RULE = CONFIG["language"]["weave_rule"]      # the scaffolding rule (native language vs payload)
REGISTER_NOTE = CONFIG["language"]["register_note"]  # the target spoken register, one line

TUTOR = CONFIG["tutor"]["name"]
TUTOR_PRONOUNS = CONFIG["tutor"].get("pronouns", "they/them")
TUTOR_VOICE = CONFIG["tutor"].get("voice_id", "")   # pinned: the tutor always sounds like the same someone

TTS = CONFIG.get("tts", {})
TTS_PROVIDER = TTS.get("provider", "edge")
TTS_LANGUAGE_CODE = TTS.get("language_code", "")
VOICES = TTS.get("voices", {})
# Pinned second voice for the eavesdrop knock (the overheard tape) — ear-training
# tracks a speaker, so it's one consistent someone, and never the tutor's voice.
# Empty ⇒ the eavesdrop modality is disabled (the knock never offers it).
EAVESDROP_VOICE = TTS.get("eavesdrop_voice", "")

FEED = CONFIG.get("feed", {})
REPO = FEED.get("repo", "")                         # "user/repo" — CDN + RSS URLs derive from this

OUTREACH = CONFIG["outreach"]
VOLLEY_SIZE = OUTREACH.get("volley_size", 3)   # deck items per volley knock
DECK = CONFIG["deck"]
DECK_NAME = DECK.get("name", "sprint")
DECK_LABEL = DECK.get("label", "Sprint Deck")

# Optional priority tiers — an ordered list the setup agent elaborates WITH the
# learner (SETUP.md Phase 5) when the deck's registers have a real pecking order:
#   "tiers": [{"name": "survival", "registers": ["antifreeze", "public"]}, ...]
# Position = priority. Absent/empty ⇒ flat ripeness ordering, no tier labels.
# Ordering only — nothing leaves the deck; the ambition is still to clear it whole.
DECK_TIERS = {reg: i for i, t in enumerate(DECK.get("tiers") or [])
              for reg in t.get("registers", [])}
TIER_NAMES = {i: t.get("name", "") for i, t in enumerate(DECK.get("tiers") or [])}


def deck_deadline():
    """The deck's deadline as a date, or None when the sprint has no clock."""
    from datetime import date
    d = DECK.get("deadline")
    return date.fromisoformat(d) if d else None


DECK_DEADLINE_LABEL = DECK.get("deadline_label", "deadline")
