#!/usr/bin/env python3
"""THE WORLD CANON — the reader and the one appender for `content/world.md`.

The canon is for continuity. Disposable scenes cannot teach shared context, and
shared context — who someone is, why they are sulking, what happened last
holiday — is most of what makes a real table hard. A recurring cast teaches it.

THE VOICES ARE PINNED IN THE CANON AND PYTHON COPIES THEM; the writer never
transcribes them. The ear tracks a SPEAKER before it tracks a word, so a
character whose voice drifts quietly undoes earlier listening. The model writes
the scene; Python writes the Voice Map.

Not owned here: what happens in the world (the tutor writes the arc premise, the
Architect the scene), which words a scene carries (the ticket), or whether the
canon is any good (the learner approves the cast).
"""
import re
from datetime import date

from state_io import BASE, local_today


CANON_PATH = BASE / "content" / "world.md"

# A cast row: `| **Grandma** (<target-form name>) | … | `<voice-id>` |`
# The name is the first bold span, its target-language form the parenthesised
# span after it, the voice the last backticked span — anchored to the row so a
# paragraph mentioning a name cannot mint a character.
_ROW_RE = re.compile(
    r"^\|\s*\*\*(?P<name>[^*|]+?)\*\*\s*(?:\((?P<target>[^)|]+)\))?.*?"
    r"`(?P<voice>[\w-]+)`\s*\|\s*$", re.MULTILINE)
_BEAT_HEAD = "### Beat log"
_ARC_HEAD = "## 4. This arc"
_EMPTY = "*(empty)*"


def load() -> str:
    """The canon's text, or "" when there is none."""
    return CANON_PATH.read_text(encoding="utf-8") if CANON_PATH.exists() else ""


def cast(text: str | None = None) -> dict[str, str]:
    """name -> pinned TTS voice. {} when there is no table, and every caller
    treats that as LOUD (`problem`): a silently empty cast means voices assigned
    at random per episode, a feed that sounds almost right for a month."""
    return {m["name"].strip(): m["voice"] for m in _ROW_RE.finditer(text or load())}


def names(text: str | None = None) -> set[str]:
    """Every string that names a cast member, in both languages. The target-form
    half is load-bearing: an eavesdrop tape is refused unless its opening names
    who it is about, and the tape is in the target language. A cast list is a
    fact about the learner's pack, so the knock lane asks here."""
    out = set()
    for m in _ROW_RE.finditer(text or load()):
        out.add(m["name"].strip())
        if m["target"]:
            out.add(m["target"].strip())
    return out


def problem(text: str | None = None) -> str:
    """Why the canon cannot be used, in one sentence, or "". Each failure here
    is otherwise indistinguishable from success: episodes keep coming, set
    nowhere and remembered by nothing."""
    text = load() if text is None else text
    if not text.strip():
        return f"no canon at {CANON_PATH.relative_to(BASE)} — the studio has nowhere to set a scene"
    if not cast(text):
        return "the canon has no cast table — no character has a pinned voice"
    if _BEAT_HEAD not in text:
        return f"the canon has no `{_BEAT_HEAD}` section — a rendered beat has nowhere to land"
    return ""


def voice_map(script: str, text: str | None = None) -> dict[str, str]:
    """SPEAKER TAG -> pinned voice for one script, keyed as `render_audio`
    looks names up: uppercased, the whole tag including its `(F)`/`(M)`."""
    out = {}
    for tag in set(re.findall(r"^\s*(?:\*\s*)?\*\*\s*([^:]+?)\s*:", script, re.MULTILINE)):
        for name, voice in cast(text).items():
            if re.match(rf"{re.escape(name)}\b", tag, re.IGNORECASE):
                out[tag.upper()] = voice
    return out


def render_voice_map(vmap: dict[str, str]) -> str:
    """The block `render_audio.VOICE_MAP_RE` reads, as an HTML comment."""
    import json
    return f"<!-- Voice Map: {json.dumps(vmap, ensure_ascii=False)} -->"


def arc_name(text: str | None = None) -> str:
    """This month's arc, as the canon's arc heading states it, or ""."""
    body = (text or load()).split(_ARC_HEAD, 1)
    if len(body) < 2:
        return ""
    head = body[1].split(_BEAT_HEAD, 1)[0]
    m = re.search(r"^\s*\*\*(.+?)\*\*", head, re.MULTILINE)
    return m.group(1).strip() if m else ""


def append_beat(mission: int, beat: str, today: date | None = None) -> bool:
    """Append ONE beat line to the log; False if it could not land. Python's
    append, from the Producer's sidecar, so continuity is a fact about what
    rendered. A render that does not grow the log is a red run."""
    text = load()
    if not text or _BEAT_HEAD not in text or not beat.strip():
        return False
    line = f"- {(today or local_today()).isoformat()} · M{mission} — {beat.strip()}"
    head, tail = text.split(_BEAT_HEAD, 1)
    tail = tail.replace(_EMPTY, line, 1) if _EMPTY in tail else _insert(tail, line)
    CANON_PATH.write_text(head + _BEAT_HEAD + tail, encoding="utf-8", newline="\n")
    return True


def _insert(tail: str, line: str) -> str:
    """`line` at the END of the beat log, before whatever section follows — not
    the end of the file, which would file it under past arcs."""
    stop = next((i for i, ln in enumerate(tail.splitlines())
                 if ln.startswith("---") or ln.startswith("## ")), None)
    lines = tail.splitlines()
    at = len(lines) if stop is None else stop
    while at and not lines[at - 1].strip():
        at -= 1
    return "\n".join(lines[:at] + [line] + lines[at:]) + ("\n" if tail.endswith("\n") else "")
