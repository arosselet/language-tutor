"""The lanes, driven with every outward call stubbed: rails, the referent rule,
modality on/off, the weave branches, the publish order, the reply judge's law."""
from datetime import datetime, timedelta, timezone

from harness import ROOT, Recorder, check, marked, read, target_sample, write


def case_the_rails_hold():
    """Waking window from the pack; the cap, the gap and the transit bit gate the knock."""
    import morning_knock as mk
    import pack
    import rails
    from state_io import LOCAL_TZ
    day = datetime.now(LOCAL_TZ).replace(hour=pack.WAKING_START_HOUR, minute=30)
    night = day.replace(hour=(pack.WAKING_END_HOUR) % 24, minute=5)
    check("inside the waking window", rails.in_waking_window(day))
    check("outside it at the end hour", not rails.in_waking_window(night))
    write("progress/learner.json", {"learner": pack.LEARNER, "quiet_until": "2999-01-01"})
    ok, why = mk.rails_gate(False, day.astimezone(timezone.utc))
    check("the transit bit holds every knock, before anything is logged", not ok and "quiet_until" in why, why)
    write("progress/learner.json", {"learner": pack.LEARNER})
    fired = [{"acted": True, "timestamp": (day - timedelta(minutes=10 * i)).astimezone(timezone.utc).isoformat()}
             for i in range(pack.MAX_REACHES_PER_DAY)]
    write("progress/knock_log.json", fired)
    ok, why = mk.rails_gate(False, day.astimezone(timezone.utc))
    check("the daily cap holds", not ok and "cap" in why, why)
    write("progress/knock_log.json", fired[:1])
    ok, why = mk.rails_gate(False, day.astimezone(timezone.utc))
    check("the min gap holds", not ok and "min-gap" in why, why)
    write("progress/knock_log.json", [])


def case_an_overheard_tape_must_name_its_subject():
    """The referent rule: kinship nouns from the pack, names from the world canon."""
    import morning_knock as mk
    import pack
    names = sorted(__import__("world").names())
    check("the world canon yields names (both forms)", "Gran" in names and "Granny" in names, f"{names}")
    check("a tape opening on a cast name passes", mk.tape_names_a_referent("Granny called.\n\nShe said…"))
    if pack.REFERENT_NOUNS:
        check("a tape opening on a kinship noun passes",
              mk.tape_names_a_referent(f"{pack.REFERENT_NOUNS[0]} called."))
    check("a tape that names nobody up front fails",
          not mk.tape_names_a_referent("Someone called.\n\nThey said…\n\nGranny, later."))
    d = mk.normalize_decision({"act": True, "modality": "eavesdrop", "stance": "ask",
                               "memo_script": "Someone called.\n\nNothing named."})
    check("an eavesdrop with no named referent is refused, never degraded to text",
          d["modality"] == "silence" and not d["act"])
    d = mk.normalize_decision({"act": True, "modality": "text"})
    check("an undeclared stance counts as an ASK, never a free give", d["stance"] == "ask")


def case_the_read_form_lane():
    """The rewrite runs only when the pack needs it; it never fires otherwise."""
    import pack
    import writer
    word = target_sample() or "x"
    calls = Recorder(ret=lambda sys_, body, **kw: body.replace(word, "romanized"))
    writer.ask_text, saved = calls, writer.ask_text
    try:
        out = writer.to_read_form(f"say {marked(word)}")
    finally:
        writer.ask_text = saved
    if pack.READ_REWRITE:
        check("a voice-form body is rewritten for the reader", calls.calls and word not in out, out)
    else:
        check("no rewrite call is made", not calls.calls)
        check("…and span brackets never reach a reader", pack.SPAN_OPEN not in out, out)


def case_the_weave_tripwire_and_the_carrying_voice():
    """run_studio measures the native-language share with the pack's own questions."""
    import run_studio as rs
    word = target_sample() or "palabra"
    t = marked(word)
    scaffolded = "\n".join([f"**Narrator (M):** so they walk to the market and {t} is said"] * 6
                           + [f"**Gran (F):** {t} {t} {t}"] * 6)
    pure = "\n".join([f"**Gran (F):** {t} {t} {t} {t}"] * 6)
    check("a scaffolded episode clears the native-share floor",
          rs.native_share(scaffolded) >= rs.MIN_NATIVE_SHARE, f"{rs.native_share(scaffolded):.2f}")
    check("near-pure target dialogue trips it", rs.native_share(pure) < rs.MIN_NATIVE_SHARE,
          f"{rs.native_share(pure):.2f}")
    check("a voice that lives in the target carries the scene", rs.carrying_voice(scaffolded) >= rs.VOICE_CARRIES)
    # Every host narrating, the target only quoted now and then: nobody is IN the scene.
    narrated = "\n".join([f"**Host A (F):** they said {t} at lunch, you see"] * 2
                         + ["**Host A (F):** and nobody answered for a while"] * 4
                         + [f"**Host B (M):** then {t}, apparently"]
                         + ["**Host B (M):** and then they all went home"] * 5)
    check("a script where every host narrates fails the carrying voice",
          rs.carrying_voice(narrated) < rs.VOICE_CARRIES, f"{rs.carrying_voice(narrated):.2f}")


def case_the_renderer_never_speaks_a_bracket():
    """TTS cleaning strips span markers and stage directions."""
    import render_audio as ra
    word = target_sample() or "palabra"
    clean = ra.clean_for_tts(f"Well, {marked(word)} [laughs] *right*")
    check("no span marker, no stage direction, no markdown",
          "⟦" not in clean and "[" not in clean and "*" not in clean and word in clean, clean)


def case_publish_owns_the_order():
    """The mp3 leads; the observation log rides along; chat.md follows the knock log."""
    import publish
    from state_io import KNOCK_LOG_PATH
    write("progress/observations.json", [])
    mp3 = ROOT / "published_audio" / "x.mp3"
    publish.refresh_feed, saved = Recorder(ret=None), publish.refresh_feed
    try:
        paths, _ = publish.publish([KNOCK_LOG_PATH], "m", mp3=mp3)
    finally:
        publish.refresh_feed = saved
    names = [p.name for p in paths]
    check("the mp3 leads the commit", names[0] == "x.mp3", f"{names}")
    check("the observation log rides every dose", "observations.json" in names)
    check("a commit carrying the knock log carries a fresh chat.md", "chat.md" in names)


def case_the_judge_cannot_credit_what_was_not_said():
    """Credit needs the span in the reply; a revealed target caps at hinted."""
    import knock_reply as kr
    import pack
    word = target_sample() or "palabra"
    v = kr.normalize_verdict({"verdict": "cold", "fired": [
        {"word": word, "said": "something else", "verdict": "cold"}]}, "nothing like it")
    check("a fire whose span is not in the reply is dropped", not v["fired"] and v["unverified"])
    v = kr.normalize_verdict({"verdict": "cold", "fired": [{"word": word, "said": word, "verdict": "cold"}],
                              "slips": [{"tag": "t", "said": "x", "want": word}]}, f"I said {word}")
    check("a word corrected in the same breath is slipped, not fired", not v["fired"])
    write("progress/lexicon.json", {word: {"gloss": "g", "recognition": "untested", "production": "none"}})
    write("progress/observations.json", [])
    lex = read("progress/lexicon.json")
    knock = {"timestamp": "2026-10-01T10:00:00+00:00", "modality": "text", "expected_target": word,
             "target_revealed": True, "body": f"say {word}"}
    v = {"fired": [{"word": word, "said": word, "verdict": "cold"}]}
    summary, cold, capped, _ = kr.apply_verdict(v, knock, lex, [])
    check("a revealed target scores at most hinted (capped)", capped == [word] and not cold, f"{summary}")
    check("…and moves production to hinted, never cold", lex[word]["production"] == "hinted")


def case_the_sort_reply_is_parsed_by_python():
    """Numbers name the misses; nothing countable records nothing."""
    import render_sort as rs
    check("'missed 4, 9' names two misses", rs.parse_reply("missed 4, 9", 20) == {4, 9})
    check("'got them all' misses none", rs.parse_reply("got them all", 20) == set())
    check("'got 1 and 2' inverts to the rest", rs.parse_reply("got 1 and 2", 3) == {3})
    check("an uncountable reply is None, never an empty score", rs.parse_reply("hmm", 20) is None)


def case_a_dry_run_payoff_refuses_without_writing():
    """A refusal under --dry-run counts no try, writes no note, commits nothing."""
    import sys
    import render_payoff as rp
    ts = "2026-10-01T10:00:00+00:00"
    write("progress/knock_log.json", [{"timestamp": ts, "modality": rp.TAPE_MODALITY, "acted": True,
                                       "mp3": "knock_2026-10-01T10-00.mp3",
                                       "memo_script": "One line here. Another line there."}])
    write("progress/feedback_log.json", [])
    commits = Recorder()
    saved = rp.commit_and_push, rp.write_sheet, rp.align, sys.argv
    rp.commit_and_push = commits
    rp.write_sheet = lambda entry, lines: {"opener": "", "closer": "", "glosses": []}
    rp.align = lambda lines, sheet: ([], "the glosses do not line up")
    sys.argv = ["render_payoff.py", "--knock-id", ts, "--dry-run"]
    try:
        rp.main()
    finally:
        rp.commit_and_push, rp.write_sheet, rp.align, sys.argv = saved
    check("nothing committed", not commits.calls, f"{commits.calls}")
    check("no try counted", "payoff_tries" not in read("progress/knock_log.json")[0])
    check("no feedback note", read("progress/feedback_log.json") == [])
