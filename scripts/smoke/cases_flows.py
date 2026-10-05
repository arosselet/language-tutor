"""The lanes driven end to end, main() and all: only the model, TTS, git and the push
are stubbed. Each flow checks what the learner would see (no span markers, the read
form on the lock screen) and what the ledger would keep."""
import asyncio
import json
import os
import subprocess
import sys
from contextlib import contextmanager

from harness import ROOT, Recorder, check, marked, read, target_sample, write

SPOKEN: list[str] = []   # every text handed to the fake TTS


@contextmanager
def stubbed(*pairs):
    """Set (module, name, value) triples for the block, then restore them."""
    saved = [(m, n, getattr(m, n)) for m, n, _ in pairs]
    for m, n, v in pairs:
        setattr(m, n, v)
    try:
        yield
    finally:
        for m, n, v in saved:
            setattr(m, n, v)


async def fake_segment(text, voice, index, temp_dir):
    import render_audio
    SPOKEN.append(text)
    path = os.path.join(temp_dir, f"seg_{index}.mp3")
    with open(path, "wb") as f:
        f.write(render_audio.SILENCE_FRAME * 40)
    return path


def tts_stubs():
    import memo
    import render_audio
    import render_soak
    return [(render_audio, "generate_segment", fake_segment),
            (render_audio, "generate_segment_edge", fake_segment),
            (render_audio, "generate_segment_google", fake_segment),
            (render_audio, "tts_ready", lambda: None),
            (render_audio, "google_credentials_ready", lambda: None),
            (render_soak, "generate_segment", fake_segment),
            (render_soak, "tts_ready", lambda: None),
            (memo, "generate_segment", fake_segment)]


def read_form_stub():
    """The rewrite lane answers in plain letters, as the read form would."""
    import writer
    return [(writer, "ask_text", lambda *a, **k: "read form here")]


def seed_word() -> str:
    from state_io import local_today
    word = target_sample()
    write("progress/lexicon.json", {word: {"gloss": "a gloss", "recognition": "untested",
                                           "production": "none",
                                           "last_surfaced": local_today().isoformat()}})
    write("progress/observations.json", [])
    write("progress/knock_log.json", [])
    write("progress/learner.json", {"learner": "x"})
    return word


def no_marker(text: str) -> bool:
    import pack
    return pack.SPAN_OPEN not in text and pack.SPAN_CLOSE not in text


def case_a_knock_reaches_the_phone_in_the_read_form():
    """morning_knock: decide → render the tape → log → expose → push, read form only."""
    import morning_knock as mk
    import pack
    import world
    word = seed_word()
    who = max(world.names(), key=len)
    decision = {"act": True, "modality": "eavesdrop", "move": "overheard", "stance": "ask",
                "introduces": [], "notification_body": f"Who was {marked(word)} for?",
                "memo_script": f"{who}, at the door. {marked(word)}", "expected_target": word,
                "target_revealed": False, "next_check_hours": 3, "rationale": "smoke"}
    push, commit = Recorder(True), Recorder()
    SPOKEN.clear()
    with stubbed((mk, "ask_json", lambda *a, **k: dict(decision)), (mk, "push_to_phone", push),
                 (mk, "commit_and_push", commit), *tts_stubs(), *read_form_stub()):
        sys.argv = ["morning_knock.py", "--force"]
        mk.main()
    entry = (read("progress/knock_log.json") or [{}])[-1]
    check("the knock fired and was logged", entry.get("acted") and entry.get("modality") == "eavesdrop",
          f"{entry}")
    check("one push, one commit", len(push.calls) == 1 and len(commit.calls) == 1)
    body = push.calls[0][0][0] if push.calls else ""
    check("the lock screen carries no span marker", no_marker(body), body)
    check("…and no voice form the learner cannot read", not pack.needs_read_form(body), body)
    check("the tape was spoken without markers", SPOKEN and all(no_marker(t) for t in SPOKEN), f"{SPOKEN}")
    check("the overheard word is exposed in the ledger",
          any(o["word"] == word and o["kind"] == "exposed" for o in read("progress/observations.json")))


def case_a_reply_is_judged_and_credited():
    """knock_reply: a text knock, a reply that uses the word → a tested event, a push back."""
    import knock_reply as kr
    word = seed_word()
    ts = "2026-10-01T10:00:00+00:00"
    write("progress/knock_log.json", [{"timestamp": ts, "date": "2026-10-01", "acted": True,
                                       "modality": "text", "move": "ask", "stance": "ask",
                                       "body": "how would you ask it?", "body_script": "how would you ask it?",
                                       "expected_target": word, "target_revealed": False}])
    verdict = {"verdict": "cold", "fired": [{"word": word, "said": word, "verdict": "cold"}],
               "reply_line": f"{marked(word)} — yes.", "follow_up_ask": "", "follow_up_target": "",
               "follow_up_target_revealed": True, "meta_note": "", "rationale": "smoke",
               "voice_reply": "", "slips": [], "schedule": None}
    push, commit = Recorder(True), Recorder()
    with stubbed((kr, "ask_json", lambda *a, **k: json.loads(json.dumps(verdict))),
                 (kr, "push_to_phone", push), (kr, "commit_and_push", commit), *read_form_stub()):
        os.environ["REPLY_KNOCK_ID"] = ts
        sys.argv = ["knock_reply.py", f"I think it's {word}"]
        try:
            kr.main()
        finally:
            os.environ.pop("REPLY_KNOCK_ID", None)
    tested = [o for o in read("progress/observations.json") if o["word"] == word and o["kind"] == "tested"]
    check("the reply is a production test in the ledger", tested and tested[-1]["axis"] == "production",
          f"{tested}")
    check("the lexicon row moved", read("progress/lexicon.json")[word]["production"] != "none")
    body = push.calls[0][0][0] if push.calls else ""
    check("the push back reached the phone without markers", push.calls and no_marker(body), body)


def case_a_soak_tape_renders_and_publishes():
    """render_soak: sheet → TTS → feed → exposure; markers never reach the voice."""
    import render_soak as rs
    word = seed_word()
    sheet = {"title": "Smoke soak", "intro": "Here we go.", "outro": "That's it.",
             "clusters": [{"thread": "one thread", "items": [{"say": marked(word), "en": "a gloss"}]}]}
    push, commit = Recorder(True), Recorder()
    SPOKEN.clear()
    with stubbed((rs, "ask_json", lambda *a, **k: json.loads(json.dumps(sheet))),
                 (rs, "push_to_phone", push), (rs, "commit_and_push", commit), *tts_stubs()):
        sys.argv = ["render_soak.py", "--focus", word]
        rs.main()
    mp3s = sorted((ROOT / "published_audio").glob("soak_*.mp3"))
    check("a soak mp3 was written", mp3s and mp3s[-1].stat().st_size > 0)
    check("the voice never spoke a span marker", SPOKEN and all(no_marker(t) for t in SPOKEN), f"{SPOKEN}")
    check("committed and pushed once", len(commit.calls) == 1 and len(push.calls) == 1)
    check("the aired word is exposed",
          any(o["word"] == word and o["kind"] == "exposed" for o in read("progress/observations.json")))


def _episode(word: str, cast_name: str) -> str:
    """A Producer answer that passes the lint: an H1, a narrator in the learner's
    language, and a cast voice that carries the scene in the target."""
    host = [f"**HOST:** Tonight we are back in the kitchen, and somebody is late again ({i})."
            for i in range(10)]
    scene = [f"**{cast_name.upper()}:** {marked(word)} {marked(word)}, {marked(word)}." for i in range(10)]
    script = "\n\n".join(["# The late dinner"] + [x for pair in zip(host, scene) for x in pair])
    tags = {"mission": 1, "register": "across", "dramatic_ingredient": "a delay",
            "episode_form": "scene", "new_words_landed": {word: 1}, "beat": "dinner ran late"}
    return f"```markdown\n{script}\n```\n\n```json\n{json.dumps(tags, ensure_ascii=False)}\n```"


def case_an_episode_runs_from_passes_to_the_feed():
    """run_studio's passes, lint and claims, then render_audio's render and register."""
    import render_audio as ra
    import run_studio as st
    import world
    word = seed_word()
    write("curriculum/word_pool.json", [{"word": word, "gloss": "a gloss", "cluster": "c", "priority": 1}])
    git = ["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.invalid"]
    subprocess.run([*git, "add", "-A"], cwd=ROOT, check=True)
    subprocess.run([*git, "commit", "-qm", "base", "--no-verify"], cwd=ROOT, check=True)
    for d in ("content/lessons", "content/captions"):   # a fresh clone has neither
        check(f"{d}/ does not exist yet", not (ROOT / d).exists())
    cast_name = next(iter(world.cast()))
    answers = {"Director": "the plan", "Architect": "the draft",
               "Producer": _episode(word, cast_name), "Captions": "```markdown\n# captions\n```"}
    n = st.next_mission()
    baseline = st.git_dirty()
    ok = st.write_episode(n, lambda label, prompt: answers[label])
    check("the passes persisted the episode", ok)
    problems = st.lint(n, baseline)
    check("the first episode in a fresh clone passes the lint", not problems, f"{problems}")
    st.claim_payload(n)
    st.claim_spec(n)
    check("the beat reached the canon", "dinner ran late" in world.load())
    script = st.episode_paths(n)["script"]
    mp3 = ROOT / "published_audio" / f"tier2_mission{n}.mp3"
    commit = Recorder()
    SPOKEN.clear()
    with stubbed((ra, "commit_and_push", commit), *tts_stubs()):
        sys.argv = ["render_audio.py", str(script), str(mp3)]
        cwd = os.getcwd()
        os.chdir(ROOT)
        try:
            asyncio.run(ra.main())
        finally:
            os.chdir(cwd)
    check("the episode mp3 exists", mp3.exists() and mp3.stat().st_size > 0)
    check("the voice never spoke a span marker", SPOKEN and all(no_marker(t) for t in SPOKEN), f"{SPOKEN[:3]}")
    eps = read("progress/episodes.json") or {}
    check("the episode is registered", str(n) in json.dumps(eps), f"{str(eps)[:200]}")
    check("the commit carries the canon's beat",
          commit.calls and any(str(p).endswith("world.md") for p in commit.calls[0][0][0]),
          f"{commit.calls[:1]}")
