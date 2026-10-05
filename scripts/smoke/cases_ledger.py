"""The ledger law: a rung is what watched tests support; the lexicon is a fold of
the observation log; reading is not hearing; declared channels never vote."""
import subprocess
import sys

from harness import ROOT, check, read, target_sample, write


def _fold(events):
    import lexicon_view
    return lexicon_view.derive([{"at": "2026-10-01T12:00:00Z", **e} for e in events])


def case_declared_channels_never_vote():
    """A seed claim speaks to its axis and moves nothing."""
    v = _fold([dict(word="w", channel="seed", kind="claimed", axis="recognition", result="right")])
    check("a seed claim leaves recognition at the default", v["w"]["recognition"] == "untested")
    check("…but the axis is spoken, so the fold writes the default", "recognition" in v["w"]["spoken"])


def case_tests_climb_and_misses_fall():
    """One rung per pass, one per miss; a half-answer is still a test."""
    v = _fold([dict(word="w", channel="session", kind="tested", axis="recognition", result="right")])
    check("a right answer climbs one rung", v["w"]["recognition"] == "comfortable")
    v = _fold([dict(word="w", channel="session", kind="tested", axis="recognition", result="wrong")])
    check("a wrong answer lands on struggled", v["w"]["recognition"] == "struggled")
    v = _fold([dict(word="w", channel="session", kind="tested", axis="recognition", result="partial")])
    check("a half-answer is not untested", v["w"]["recognition"] == "struggled")
    v = _fold([dict(word="w", channel="knock", kind="tested", axis="production", result="partial"),
               dict(word="w", channel="knock", kind="tested", axis="production", result="right")])
    check("production is the best grade ever fired", v["w"]["production"] == "cold")


def case_reading_is_not_hearing():
    """Only an ear test stamps heard_on."""
    v = _fold([dict(word="w", channel="check", kind="tested", axis="recognition",
                    result="right", medium="text")])
    check("a page answer moves the rung", v["w"]["recognition"] == "comfortable")
    check("…and never stamps the ear", v["w"]["heard_on"] is None)
    v = _fold([dict(word="w", channel="check", kind="tested", axis="recognition",
                    result="right", medium="audio")])
    check("an ear answer stamps heard_on", v["w"]["heard_on"])


def case_attendance_discharges_teaching_never_creates_it():
    """A render teaches nothing until a listen; a listen teaches nothing a render didn't."""
    v = _fold([dict(word="w", channel="episode", kind="taught", source="episode:M1")])
    check("a delivered Teach Beat is pending, not taught", v["w"]["taught_on"] is None)
    v = _fold([dict(word="w", channel="episode", kind="taught", source="episode:M1"),
               dict(word="w", channel="episode", kind="attended")])
    check("a listen discharges it", v["w"]["taught_on"])
    v = _fold([dict(word="w", channel="episode", kind="attended")])
    check("a listen alone never mints teaching", v["w"]["taught_on"] is None)
    v = _fold([dict(word="w", channel="session", kind="taught")])
    check("a live session's Teach Beat needs no listen", v["w"]["taught_on"])
    v = _fold([dict(word="w", channel="check", kind="tested", axis="recognition", result="right")])
    check("a right recognition answer proves first contact", v["w"]["taught_on"])


def case_the_writer_records_and_the_fold_agrees():
    """`sync_state update` writes events; the lexicon equals the fold afterwards."""
    word = target_sample() or "palabra"
    write("progress/lexicon.json", {})
    write("progress/observations.json", [])
    r = subprocess.run([sys.executable, str(ROOT / "scripts/sync_state.py"), "update",
                        "--teach", f"{word}=a test gloss", "--recognized", word,
                        "--debrief", "smoke"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8")
    check("update exits 0", r.returncode == 0, (r.stdout + r.stderr)[-300:])
    lex = read("progress/lexicon.json") or {}
    check("the taught word has a row with its gloss",
          lex.get(word, {}).get("gloss") == "a test gloss", f"{lex}")
    check("recognized in session climbed one rung", lex.get(word, {}).get("recognition") == "comfortable")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/lexicon_view.py")], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    check("the file equals the fold (no hand-set rung)", r.returncode == 0 and "0 divergent" in r.stdout,
          r.stdout[-200:])
    log = read("progress/session_log.json") or []
    check("one session-day row, not one per call", len(log) == 1)


def case_slips_escalate_only_after_a_listen():
    """A commissioned dose that nobody heard is `awaiting`, never a failure."""
    import dose_evidence
    c = [{"channel": "soak", "at": "2026-10-01", "payload": ["w"]}]
    state, _, after = dose_evidence.judge_dose(c, ["2026-10-03"], attended=[])
    check("no listen → awaiting", state == "awaiting" and not after)
    heard = [{"kind": "attended", "channel": "soak", "word": "w", "at": "2026-10-02T12:00:00Z"}]
    state, _, after = dose_evidence.judge_dose(c, ["2026-10-04"], attended=heard)
    check("a listen, then a slip a later day → heard and slipped after", state == "heard" and after)
    other = [{"kind": "attended", "channel": "rotation", "word": "w", "at": "2026-10-02T12:00:00Z"}]
    state, _, _ = dose_evidence.judge_dose(c, ["2026-10-04"], attended=other)
    check("a listen in another lane does not count as hearing this dose", state == "awaiting")
