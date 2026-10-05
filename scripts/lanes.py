#!/usr/bin/env python3
"""WHAT THE LANES SHARE, once.

A lane declares what is DIFFERENT about it; what is the same for its whole family
lives here. The lanes are three families, not one shape, and flattening them
breaks a real invariant:

  write -> render -> publish    render_soak, render_drill, render_rotation,
                                run_studio — Python builds a menu, the writer
                                returns a sheet, Python renders and publishes.
  decide/judge -> maybe render  morning_knock, knock_reply — the model returns a
                                DECISION or a VERDICT, and rendering depends on modality.
  pure delivery, no writer      push_queue — zero model calls at fire time:
                                composed at add time, rendered at fire time.

THE SEAMS ARE ARGUMENTS. `commit` and `notify` reach outside the process (git
history, the learner's phone), so the caller names them: it states the contract,
and it keeps the suite's stubs (installed on the lane module) intercepting.
Both are keyword-only with no default — a default would silently reach past a
stub, and a test that stops intercepting `commit` writes real git history.
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import audio_titles
from publish import jsdelivr_url, publish
from lexicon_view import expose
from state_io import AUDIO_TITLES_PATH, LEARNER_PATH, LEXICON_PATH
from sync_state import mark_soak_delivered


def deliver_rendered(*, mp3: Path, lane: str, delivered: list, claimed: bool,
                     message: str, copy: str, noun: str, extra_paths=(),
                     taught=(), intake=None, title, commit, notify) -> bool:
    """The tail of every write -> render -> publish lane:

        exposure -> soak-order stamp -> name -> commit -> notify

    The lane owns `delivered`: which menu items are actually AUDIBLE in the
    finished artifact is a different question per family, and getting it wrong
    credits words that never played. `claimed` (did this run consume the
    standing order) is passed, not inferred: a stamp says a debt is PAID.
    `title` is the dose's public name, required — a forgotten name is invisible.
    `taught` is the subset a TEACHING shape gave (pending until a tap proves it
    reached the learner); `intake` rows become lexicon rows only if taught.

    Returns whether the notification left (False in quiet hours)."""
    intake = intake or {}
    born = {w: {"gloss": intake[w].get("gloss", "")} for w in taught if w in intake}
    exposed = expose(delivered, lane, source=mp3.stem, taught=taught, mint=born)
    stamped = mark_soak_delivered(lane) if claimed else False
    # The name and the aired words ride the dose's own commit: a soak leaves no
    # script, so this is the only moment its name exists, and a tap on it opens
    # what it carried.
    named = audio_titles.record(mp3.stem, title, delivered)
    commit(*publish([*extra_paths,
                     AUDIO_TITLES_PATH if named else None,
                     LEXICON_PATH if exposed else None,
                     LEARNER_PATH if stamped else None],
                    message, mp3=mp3))
    print("4. notify…")
    pushed = notify(copy, jsdelivr_url(mp3))
    print(f"done — {noun} on the feed{' and the lock screen' if pushed else ''}.")
    return pushed
