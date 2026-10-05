#!/usr/bin/env python3
"""THE LANGUAGE AND LEARNER PACK — the only reader of `config/tutor.json`.

Every value a new learner or a new language changes is a key in that file, and
every lane reads it through this module. A port is therefore one JSON file plus
the `.template` prose listed in `PROSE_SLOTS`; nothing else in `scripts/` may hold
a learner name, a target-script character, or a config-owned literal.

Lanes ask the pack QUESTIONS (`is_canonical`, `has_target`, `target_runs`,
`stem`, `host_stem`, `needs_read_form`), never a regex. The same question has a
different answer for a distinct-script target (detected by `script_regex`) and a
shared-script one (declared: writers wrap target spans in ⟦ ⟧), and a lane that
held the regex itself would only ever be right for one of them.

Imports nothing from this repo. Everything may import from here.

    python scripts/pack.py check [config.json ...]   # validate; exit 1 on problems
"""
import json
import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
CONFIG_PATH = Path(os.environ.get("SOLLU_CONFIG") or BASE / "config" / "tutor.json")

# The prose a setup agent synthesizes, one file per slot. With config/tutor.json
# this list IS the port surface.
PROSE_SLOTS = (
    "protocol/persona.md", "protocol/user.md", "protocol/stake.md",
    "protocol/learner_contract.md", "protocol/language.md", "protocol/dialect.md",
    "protocol/exemplars.md", "content/world.md", "curriculum/word_pool.json",
)

# Example slots in the prompts (D11: at most 8). Each is one line in the target
# language, in the form named, spliced into a prompt that would otherwise need a
# worked example of its own.
EXAMPLE_SLOTS = {
    "repair_line": "what the learner can say instead of an answer ('didn't catch that — slower?'), voice form",
    "addressed_question": "a short question a family member fires at the learner, read form, plus a 2-4 word frame",
    "typed_spelling": "a typed spelling and the canonical form it counts as: '\"typed\" IS canonical'",
    "substitution": "a socially coherent substitute and what it stood in for: '\"X\" for \"Y\"', read form",
    "grammar_slip": "one clause naming a wrong form a native would flag, with the right one",
    "pattern_thread": "a soak thread label: a shared ending or frame, then what it does, in English",
    "contrast_title": "a soak title naming a contrast: 'A vs B · what differs'",
}

# Shared-script packs declare target spans in generated free text with these.
# They are mechanism, not config: no natural language uses them, so they clash
# with no format string, quotation convention, Markdown or SSML.
SPAN_OPEN, SPAN_CLOSE = "⟦", "⟧"
_SPAN = re.compile(f"{SPAN_OPEN}([^{SPAN_CLOSE}]*){SPAN_CLOSE}")
_L1_WORD = re.compile(r"[^\W\d_]+")

MODULES = ("audio", "phone", "timeline")
_TIERS = ("chirp", "wavenet", "edge")
_SCHEMA = {   # section -> {key: (types, required)}
    "learner": {"name": (str, True), "pronouns": (str, True), "native_language": (str, True)},
    "tutor": {"name": (str, True), "pronouns": (str, True), "relationship": (str, True)},
    "language": {
        "name": (str, True), "variety": (str, True), "audio_form": (str, True),
        "chat_form": (str, True), "weave_rule": (str, True),
        "script_regex": ((str, type(None)), False), "read_rewrite": (bool, False),
        "stem_tail": ((str, list, type(None)), False), "host_tail": ((str, list, type(None)), False),
        "tokenization": (str, False), "direction": (str, False), "referent_nouns": (list, False),
    },
    "examples": {k: (str, False) for k in EXAMPLE_SLOTS},
    "tts": {"provider": (str, False), "tutor_voice": (str, False),
            "eavesdrop_voice": (str, False), "pools": (dict, False)},
    "feed": {"repo": (str, False), "title": (str, False), "summary": (str, False),
             "caption_columns": (str, False)},
    "rails": {"waking_start_hour": (int, False), "waking_end_hour": (int, False),
              "max_reaches_per_day": (int, False), "min_gap_hours": (int, False)},
    "writer": {"model": (str, True), "agent_model": ((str, type(None)), False)},
    "modules": {m: (bool, False) for m in MODULES},
    "timeline": {"event": (str, False), "default_direction": (str, False),
                 "directions": (dict, False), "trails": (list, False), "phases": (list, False)},
}
_REQUIRED_SECTIONS = ("learner", "tutor", "language", "writer")
_PHASE_KEYS = {"name", "days", "event", "direction", "voices", "situation_given", "intake", "marker"}


def _tail(spec) -> str | None:
    """A stem rule as one end-anchored pattern: a regex, a suffix list, or None."""
    if not spec:
        return None
    if isinstance(spec, list):
        return "(?:" + "|".join(re.escape(s) for s in sorted(spec, key=len, reverse=True)) + ")$"
    return spec if spec.endswith("$") else spec + "$"


def _timeline_problems(t: dict) -> list[str]:
    out, phases = [], t.get("phases") or []
    dirs = t.get("directions") or {}
    if not phases:
        return ["timeline.phases: empty — turn modules.timeline off instead"]
    events = [p for p in phases if p.get("event")]
    if len(events) != 1:
        out.append(f"timeline.phases: exactly one phase must be the event (found {len(events)})")
    after = False
    for i, p in enumerate(phases):
        where = f"timeline.phases[{i}]"
        if extra := set(p) - _PHASE_KEYS:
            out.append(f"{where}: unknown keys {sorted(extra)}")
        if not p.get("name") or not p.get("marker"):
            out.append(f"{where}: needs a name and a behavioural marker")
        if p.get("direction") not in dirs:
            out.append(f"{where}: direction {p.get('direction')!r} is not in timeline.directions")
        if p.get("event"):
            after = True
            if p.get("days") is not None:
                out.append(f"{where}: the event spans its dates; days must be null")
        elif p.get("days") is None and after:
            out.append(f"{where}: only phases before the event may share the run-up (days null)")
        elif p.get("days") is not None and not (isinstance(p["days"], int) and p["days"] > 0):
            out.append(f"{where}: days must be a positive integer or null")
        if p.get("intake") is not None and not isinstance(p["intake"], int):
            out.append(f"{where}: intake is an integer override or null")
    if t.get("default_direction", next(iter(dirs), None)) not in dirs:
        out.append("timeline.default_direction is not in timeline.directions")
    return out


def check(cfg: dict) -> list[str]:
    """Every problem with a config, as sentences. [] means it will load."""
    out = [f"missing section {s!r}" for s in _REQUIRED_SECTIONS if s not in cfg]
    for section, body in cfg.items():
        if section.startswith("_"):
            continue
        if section not in _SCHEMA:
            out.append(f"unknown section {section!r}")
            continue
        if not isinstance(body, dict):
            out.append(f"{section}: must be an object")
            continue
        for key, (types, required) in _SCHEMA[section].items():
            if key not in body:
                out += [f"{section}.{key}: required"] if required else []
            elif not isinstance(body[key], types) or (types is int and isinstance(body[key], bool)):
                out.append(f"{section}.{key}: wrong type {type(body[key]).__name__}")
        out += [f"{section}.{k}: unknown key" for k in body if k not in _SCHEMA[section]]
    if out:
        return out
    lang = cfg["language"]
    for key in ("script_regex", "stem_tail", "host_tail"):
        try:
            pat = lang.get(key) if key == "script_regex" else _tail(lang.get(key))
            pat and re.compile(pat)
        except re.error as e:
            out.append(f"language.{key}: does not compile ({e})")
    if lang.get("read_rewrite") and not lang.get("script_regex"):
        out.append("language.read_rewrite needs script_regex: a rewrite is triggered by detecting the script")
    if lang.get("tokenization", "spaces") not in ("spaces", "characters"):
        out.append("language.tokenization: 'spaces' or 'characters'")
    if lang.get("direction", "ltr") not in ("ltr", "rtl"):
        out.append("language.direction: 'ltr' or 'rtl'")
    if not all(isinstance(n, str) and n for n in lang.get("referent_nouns", [])):
        out.append("language.referent_nouns: a list of non-empty strings")
    tts = cfg.get("tts", {})
    if tts.get("provider", "google") not in ("google", "edge"):
        out.append("tts.provider: 'google' or 'edge'")
    for tier, sexes in tts.get("pools", {}).items():
        if tier not in _TIERS or not isinstance(sexes, dict) or set(sexes) - {"male", "female"}:
            out.append(f"tts.pools.{tier}: a tier in {_TIERS} mapping male/female to voice lists")
    rails = {**_RAILS, **cfg.get("rails", {})}
    if not 0 <= rails["waking_start_hour"] < rails["waking_end_hour"] <= 24:
        out.append("rails: waking_start_hour must come before waking_end_hour, both 0-24")
    if "/" not in cfg.get("feed", {}).get("repo", "owner/repo"):
        out.append("feed.repo: 'owner/name'")
    mods = _modules(cfg)
    if mods["audio"] and not tts.get("tutor_voice"):
        out.append("modules.audio is on but tts.tutor_voice is empty — list the real voices and pin one")
    if mods["timeline"]:
        out += _timeline_problems(cfg.get("timeline", {}))
    return out


_RAILS = {"waking_start_hour": 8, "waking_end_hour": 21, "max_reaches_per_day": 3, "min_gap_hours": 3}


def _modules(cfg: dict) -> dict:
    """Explicit flags win; otherwise audio follows a pinned voice, timeline follows
    phases, and phone stays off until setup wires a receiver (D4)."""
    given = cfg.get("modules", {})
    return {"audio": given.get("audio", bool(cfg.get("tts", {}).get("tutor_voice"))),
            "phone": given.get("phone", False),
            "timeline": given.get("timeline", bool(cfg.get("timeline", {}).get("phases")))}


def load(path: Path = CONFIG_PATH) -> dict:
    """The config, validated. No file means an uninitialized clone: say so and stop."""
    if not path.exists():
        sys.exit(f"{path.relative_to(BASE) if path.is_relative_to(BASE) else path} not found — "
                 "this repo has not been set up yet.\nOpen your agent here and say "
                 "\"set up my tutor\". The protocol is SETUP.md.")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if problems := check(cfg):
        sys.exit(f"{path}: invalid config\n  " + "\n  ".join(problems))
    return cfg


def _cli(argv: list[str]) -> int:
    if argv[:1] != ["check"]:
        print(__doc__.strip().splitlines()[-1].strip())
        return 2
    bad = 0
    for p in [Path(a) for a in argv[1:]] or [CONFIG_PATH]:
        problems = check(json.loads(p.read_text(encoding="utf-8")))
        print(f"{'✗' if problems else '✓'} {p}" + "".join(f"\n    {x}" for x in problems))
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))

CONFIG = load()
_lang, _tts, _feed = CONFIG["language"], CONFIG.get("tts", {}), CONFIG.get("feed", {})

# ── Who ──────────────────────────────────────────────────────────────────────
LEARNER = CONFIG["learner"]["name"]
LEARNER_PRONOUNS = CONFIG["learner"]["pronouns"]
NATIVE_LANGUAGE = CONFIG["learner"]["native_language"]
TUTOR = CONFIG["tutor"]["name"]
TUTOR_PRONOUNS = CONFIG["tutor"]["pronouns"]
TUTOR_RELATIONSHIP = CONFIG["tutor"]["relationship"]

# ── The language ─────────────────────────────────────────────────────────────
LANGUAGE = _lang["name"]
VARIETY = _lang["variety"]
DIRECTION = _lang.get("direction", "ltr")
REFERENT_NOUNS = tuple(_lang.get("referent_nouns", ()))
EXAMPLES = dict(CONFIG.get("examples", {}))
_SCRIPT = re.compile(_lang["script_regex"]) if _lang.get("script_regex") else None
_RUN = re.compile(f"(?:{_lang['script_regex']})+") if _SCRIPT else None
_STEM = re.compile(_tail(_lang.get("stem_tail"))) if _lang.get("stem_tail") else None
_HOST = re.compile(_tail(_lang.get("host_tail"))) if _lang.get("host_tail") else None
_BY_CHAR = _lang.get("tokenization", "spaces") == "characters"
READ_REWRITE = bool(_lang.get("read_rewrite"))
DISTINCT_SCRIPT = _SCRIPT is not None

# The two surfaces as prompt fragments (D13). A shared-script pack's audio form
# also carries the span rule, because nothing else can tell its target from L1.
CHAT_FORM = _lang["chat_form"]
AUDIO_FORM = _lang["audio_form"] + ("" if DISTINCT_SCRIPT else (
    f"; wrap every {LANGUAGE} span in {SPAN_OPEN} {SPAN_CLOSE} so the engine can tell it "
    f"from {NATIVE_LANGUAGE} — the brackets are never spoken"))
WEAVE_RULE = _lang["weave_rule"]


def is_canonical(word: str) -> bool:
    """Is this token in lexicon-key form? A distinct-script key is written in the
    script, so a romanized token never mints a record. Shared script: any spelling."""
    return bool(_SCRIPT.search(word)) if _SCRIPT else bool(word.strip())


def has_target(text: str) -> bool:
    """Does this text carry any target language? Distinct script: detected.
    Shared script: only declared spans count — undeclared text answers False."""
    return bool(_SCRIPT.search(text)) if _SCRIPT else bool(_SPAN.search(text))


def target_runs(text: str) -> list[str]:
    """The target-language units in this text, in order — what a meter counts.
    A unit is a space-delimited run, or one character when the language does not
    space its words (`tokenization: characters`)."""
    if _SCRIPT:
        runs = _RUN.findall(text)
    else:
        runs = [w for span in _SPAN.findall(text) for w in span.split()]
    return [c for r in runs for c in r if c.strip()] if _BY_CHAR else runs


def l1_runs(text: str) -> list[str]:
    """The learner's-language words in this text: letters left once target units go."""
    rest = _RUN.sub(" ", text) if _SCRIPT else _SPAN.sub(" ", text)
    return _L1_WORD.findall(rest)


def unmark(text: str) -> str:
    """The text as spoken or shown — span brackets removed. Identity when none."""
    return text.replace(SPAN_OPEN, "").replace(SPAN_CLOSE, "")


def needs_read_form(text: str) -> bool:
    """Does a surface the learner READS need the rewrite lane? Only when the read
    form differs from the voice form and this text carries the voice form."""
    return READ_REWRITE and has_target(text)


def stem(word: str) -> str:
    """The word minus what inflection replaces, so an inflected form still
    matches. No rule: verbatim. The minimum-length guard is the caller's."""
    return _STEM.sub("", word) if _STEM else word


def host_stem(word: str) -> str:
    """The form a word takes inside a longer phrase that hosts it. Narrower than
    `stem` on purpose: it widens every substring host net. No rule: verbatim."""
    return _HOST.sub("", word) if _HOST else word


# ── The voices ───────────────────────────────────────────────────────────────
TTS_PROVIDER = _tts.get("provider", "google")
TUTOR_VOICE = _tts.get("tutor_voice", "")
EAVESDROP_VOICE = _tts.get("eavesdrop_voice", "")   # "" ⇒ no overheard-voice modality
VOICE_POOLS = {tier: {"male": list(p.get("male", [])), "female": list(p.get("female", []))}
               for tier, p in _tts.get("pools", {}).items()}


def voice_locale(voice: str) -> str:
    """'ta-IN-Chirp3-HD-Orus' → 'ta-IN'. Derived, so the locale moves with the voice."""
    return "-".join(voice.split("-")[:2])


# ── The feed ─────────────────────────────────────────────────────────────────
REPO = _feed.get("repo", "")
RAW_BASE_URL = f"https://raw.githubusercontent.com/{REPO}/main"
SITE_URL = f"https://github.com/{REPO}"
FEED_TITLE = _feed.get("title", f"{TUTOR} — {LANGUAGE}")
FEED_SUMMARY = _feed.get("summary", f"AI-generated {LANGUAGE} lessons for {LEARNER}.")
CAPTION_COLUMNS = _feed.get("caption_columns", f"{LANGUAGE} · {NATIVE_LANGUAGE}")

# ── Rails, writer, modules, timeline ─────────────────────────────────────────
_r = {**_RAILS, **CONFIG.get("rails", {})}
WAKING_START_HOUR, WAKING_END_HOUR = _r["waking_start_hour"], _r["waking_end_hour"]
MAX_REACHES_PER_DAY, MIN_GAP_HOURS = _r["max_reaches_per_day"], _r["min_gap_hours"]
WRITER_MODEL = CONFIG["writer"]["model"]
AGENT_MODEL = CONFIG["writer"].get("agent_model")
ENABLED = _modules(CONFIG)
TIMELINE = CONFIG.get("timeline", {}) if ENABLED["timeline"] else {}


def module_on(name: str) -> bool:
    """Core is always on; the others are config flags (§5.2)."""
    return name == "core" or ENABLED.get(name, False)
