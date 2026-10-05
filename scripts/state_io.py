#!/usr/bin/env python3
"""The state layer's shared vocabulary: where the files are, how to read and
write them, the learner's clock, the two ladders, and how a token becomes a
canonical lexicon key.

Nothing here mutates learner state beyond the soak-order stamp; `sync_state.py`
is the writer. Imports only `pack`, and everything else may import from here.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pack import is_canonical

# Windows consoles default to cp1252, which cannot print most target scripts; a
# digest that dies mid-print invites the agent to improvise state.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent.parent
LEXICON_PATH = BASE / "progress" / "lexicon.json"
LEARNER_PATH = BASE / "progress" / "learner.json"
EPISODES_PATH = BASE / "progress" / "episodes.json"
SESSION_LOG_PATH = BASE / "progress" / "session_log.json"
FEEDBACK_LOG_PATH = BASE / "progress" / "feedback_log.json"
KNOCK_LOG_PATH = BASE / "progress" / "knock_log.json"
SLIP_LOG_PATH = BASE / "progress" / "slip_log.json"
# The phone's rating picker, plain text one row per line: raw.githubusercontent
# serves everything as text/plain + nosniff, so a phone shortcut cannot parse
# JSON from it. Rewritten by `rebuild_rss.write_recent_audio` only.
RECENT_AUDIO_PATH = BASE / "progress" / "recent_audio.txt"
# Audio lanes' public names, stem -> title (see `audio_titles.py`).
AUDIO_TITLES_PATH = BASE / "progress" / "audio_titles.json"


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── The two ladders ──────────────────────────────────────────────────────────
# Properties of the ledger, not of any lane that moves a rung. `untested` is the
# ABSENCE of a rung, not a low one: it ranks with `struggled` so no ordering
# moves, but `struggled` means a test came back wrong and nothing else does.
RECOGNITION_DEFAULT = "untested"
RECOGNITION_RANK = {"untested": 0, "struggled": 0, "comfortable": 1, "solid": 2}
RECOGNITION_NEXT = {"untested": "comfortable", "struggled": "comfortable", "comfortable": "solid"}
DEMOTE = {"solid": "comfortable", "comfortable": "struggled", "struggled": "struggled",
          "untested": "struggled"}
PRODUCTION_RANK = {"none": 0, "hinted": 1, "cold": 2}


# ── The learner's clock ──────────────────────────────────────────────────────
DEFAULT_TZ = "UTC"


def _resolve_local_tz() -> ZoneInfo:
    """The learner's zone, from `learner.json.timezone`, so it follows them when
    they travel. A bad name falls back loudly rather than raising: every
    unattended lane imports this, and a typo must not stop them all."""
    name = (load_json(LEARNER_PATH) or {}).get("timezone") or DEFAULT_TZ
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        print(f"⚠ learner.json names an unknown timezone {name!r} — falling back "
              f"to {DEFAULT_TZ}. Quiet hours and dates will be on that clock.",
              file=sys.stderr)
        return ZoneInfo(DEFAULT_TZ)


LOCAL_TZ = _resolve_local_tz()


def local_today() -> date:
    """Today on the LEARNER's clock, never the host's: a UTC runner in the
    evening is a day ahead, and the slip ledger compares dates across hosts."""
    return datetime.now(LOCAL_TZ).date()


def local_date(ts_iso: str):
    """An ISO stamp on the learner's clock, or None if unparseable."""
    try:
        return datetime.fromisoformat(ts_iso).astimezone(LOCAL_TZ).date()
    except (ValueError, TypeError):
        return None


def is_fire(entry: dict) -> bool:
    """Did this knock-log row actually reach the learner? Rows without `acted`
    predate the field and were all fires."""
    return entry.get("acted", True)


# What a dose wants back from the learner.
STANCES = {"give", "ask", "lure"}


def is_give(entry: dict) -> bool:
    """Did this fire hand something over and close? Only a GIVE resets the
    anti-demand streak; a lure withholds its payoff and is not a break. A row
    with no stance falls back to "carried no expected target" — never read a
    missing field as a give."""
    stance = entry.get("stance")
    return stance == "give" if stance in STANCES else not entry.get("expected_target")


# ── Lexicon keys ─────────────────────────────────────────────────────────────

def resolve(word: str, lexicon: dict) -> str | None:
    """A token's canonical lexicon key, or None. One resolver is the contract
    every writer is canonical-at-write against; read forms are generated for
    display and never stored, so the match is key to key."""
    return word if word in lexicon else None


def canon_payload(items: list[str]) -> list[str]:
    """Split comma-joined payload elements into a flat word list, at write AND
    read, so a stored blob still matches an episode's words."""
    return [p.strip() for item in items for p in item.split(",") if p.strip()]


def resolve_soak_item(token: str, lexicon: dict) -> str | None:
    """A soak-payload token → its key, or None. Wider than `resolve`: the tutor
    writes a bare headword where the key is the whole chunk, so a canonical
    token also matches a key it prefixes."""
    exact = resolve(token, lexicon)
    if exact is not None:
        return exact
    if is_canonical(token):
        for key in lexicon:
            if key.startswith(token):
                return key
    return None


def split_payload(items: list[str], lexicon: dict) -> tuple[list[str], list[str]]:
    """(resolved keys, tokens that resolve to nothing). A canonical or `frame:`
    token absent from the lexicon is a new word its episode will register, so it
    counts as resolved. Callers treat the unresolved list as a WARNING, never as
    'still pending': an unverifiable item is a broken order, not unfinished work."""
    resolved, unresolved = [], []
    for token in canon_payload(items):
        key = resolve_soak_item(token, lexicon)
        if key:
            resolved.append(key)
        elif is_canonical(token) or token.startswith("frame:"):
            resolved.append(token)
        else:
            unresolved.append(token)
    return resolved, unresolved


def soak_pending() -> bool:
    """Has the standing soak order not been carried yet, on any channel?

    The episode channel clears an order when the newest episode's word list holds
    every verifiable payload item; soak and drill register no episode, so they
    stamp `delivered`. Either way a stamp older than the order does not count.
    A recorded render attempt also clears it, which bounds the dispatch loop at
    one render when the script used a form the stem rule cannot match."""
    soak = (load_json(LEARNER_PATH) or {}).get("soak_order") or {}
    raw = [w for w in soak.get("payload", []) if w]
    if not raw:
        return False
    channel = soak.get("channel") or "episode"
    if channel != "episode":
        deliv = soak.get("delivered") or {}
        return not (deliv.get("channel") == channel
                    and (deliv.get("at") or "") >= (soak.get("from") or ""))
    resolved, unresolved = split_payload(raw, load_json(LEXICON_PATH) or {})
    if unresolved:
        print(f"  ⚠ soak payload unresolvable, ignored for the produced-check: "
              f"{', '.join(unresolved)} — fix the soak order")
    if not resolved:
        return False
    episodes = load_json(EPISODES_PATH) or {}
    newest = episodes[max(episodes, key=int)].get("words", []) if episodes else []
    if all(w in newest for w in resolved):
        return False
    return not ((soak.get("attempted") or {}).get("at", "") >= (soak.get("from") or ""))


def mark_soak_attempted(episode: str, unclaimed: list[str]) -> None:
    """Record that a SUCCESSFUL render ran against the standing order."""
    learner = load_json(LEARNER_PATH) or {}
    if not (learner.get("soak_order") or {}):
        return
    learner["soak_order"]["attempted"] = {
        "at": local_today().isoformat(), "episode": str(episode),
        "unclaimed": list(unclaimed)}
    save_json(LEARNER_PATH, learner)


def is_unseen(rec: dict) -> bool:
    """Never TAUGHT. An unseen item may be taught (shown with its meaning) but
    never cold-quizzed. Reads `taught_on`, the fold's answer to "was the learner
    there", not a render or delivery stamp, which are facts about the machine."""
    return not rec.get("taught_on")
