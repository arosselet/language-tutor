#!/usr/bin/env python3
"""
Smoke test for the rep channel — the plumbing that carries knocks, judged
replies, and scheduled pushes. Drives the REAL production functions against a
sandbox copy of the repo with the outside-world boundaries stubbed: the LLM
call, the TTS render (audio scenarios only), push_to_phone, and
commit_and_push. No secrets, no network, no writes outside the sandbox. CI
runs it on any push that touches the machinery (smoke.yml); locally:

  python scripts/smoke_test.py

The sandbox always runs against config/tutor.json.example (a deterministic
fixture), so the test passes identically before and after bootstrap, in any
language. A fixed bug becomes a case here the day it's fixed — the numbered
regressions below are inherited from the reference implementation:
  #1  queue drain: oldest-due fires first, one non-forced per tick
  #2  prose-wrapped / single-quoted LLM JSON killed a knock tick
  #3  chained follow-up overwrote the original ask; chat lost chained replies
  #4  hinted-forever: reveal-capped fires now graduate cross-day
  #5  volley knock: binding targets + deterministic chain advance
  #6  eavesdrop dose: catch replies move recognition only, never production
  #7  stacked notifications: replies correlate by knock_id (KF-9)
  #8  transient delivery blip killed a logged knock — push retries, final failure raises
  #9  stale clone read yesterday's story; comma-joined soak payload never matched
  #10 chat mid-volley erased the open ask; Python re-presents it (KF-11)
  #11 [SFX] lines silently dropped by the renderer — now a beat of air
  #12 string-mission sidecar crashed the ticket sort; ticket smoke-runs end-to-end
  (The watchdog case in the reference impl does not port — the studio watchdog
  is local automation the template deliberately leaves out.)
"""
import argparse
import importlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REAL_BASE = Path(__file__).resolve().parent.parent
FAILURES: list[str] = []

# Fixture lexicon — matches the example config (script_regex null, so plain
# spellings are canonical keys).
WORD_A = "basta"                  # target word, unrevealed-ask fixture
WORD_B = "me encanta"             # second word, revealed-ask fixture
WORD_C = "ya me acostumbre"       # third word (capped/volley fixtures)
WORD_EAR = "sabes que"            # ear-only catch fixture


def check(name: str, cond: bool, detail: str = ""):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}" + ("" if cond else f" — {detail}"))
    if not cond:
        FAILURES.append(name)


class Recorder(list):
    """Stub for push_to_phone / commit_and_push — records instead of acting."""
    def __call__(self, *args, **kwargs):
        self.append(args)


# ── Sandbox ───────────────────────────────────────────────────────────────────

def make_sandbox(tmp: Path) -> Path:
    """Copy the repo (minus git/audio/secrets), reset progress/ to day-zero
    fixtures, and pin config to the example fixture so the test is
    deterministic regardless of how (or whether) this clone was bootstrapped."""
    sb = tmp / "repo"
    shutil.copytree(REAL_BASE, sb, ignore=shutil.ignore_patterns(
        ".git", ".env", "__pycache__", "audio", "published_audio",
        "*.mp3", "*.mp4", "*.ipynb", "*.jpg"))
    prog = sb / "progress"
    for ex in prog.glob("*.example"):
        shutil.copy(ex, prog / ex.name[: -len(".example")])
    (prog / "knock_log.json").write_text("[]", encoding="utf-8")
    (prog / "push_queue.json").write_text("[]", encoding="utf-8")
    shutil.copy(sb / "config" / "tutor.json.example", sb / "config" / "tutor.json")
    # persona.md may not exist pre-bootstrap; the knock/judge prompts read it.
    persona = sb / "protocol" / "persona.md"
    if not persona.exists():
        persona.write_text("# Persona: smoke fixture tutor\n", encoding="utf-8")
    return sb


def load_modules(sb: Path):
    """Import the SANDBOX copies of the scripts — their BASE resolves to the
    sandbox, so every path constant lands there without patching."""
    real_scripts = str(REAL_BASE / "scripts")
    sys.path = [p for p in sys.path if p != real_scripts]
    sys.path.insert(0, str(sb / "scripts"))
    mk = importlib.import_module("morning_knock")
    kr = importlib.import_module("knock_reply")
    pq = importlib.import_module("push_queue")
    check("modules imported from sandbox", mk.__file__.startswith(str(sb)),
          f"morning_knock loaded from {mk.__file__}")
    return mk, kr, pq


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Scenarios ─────────────────────────────────────────────────────────────────

def s1_parse_llm_json(mk):
    print("\n1. LLM response parsing (regression #2)")
    p = mk.parse_llm_json
    check("clean object", p('{"a": 1}') == {"a": 1})
    check("code fence", p('```json\n{"a": 1}\n```') == {"a": 1})
    check("prose-wrapped", p('My decision:\n{"a": {"b": 2}}\nHope that helps!')
          == {"a": {"b": 2}})
    # A model can return a single-quoted Python dict; the {..} slice fallback
    # finds braces but json.loads rejects single quotes. ast.literal_eval catches it.
    check("single-quoted keys", p("{'act': True, 'modality': 'text'}")
          == {"act": True, "modality": "text"})
    check("python-dict in prose", p("Here ya go: {'a': 1, 'b': False}")
          == {"a": 1, "b": False})
    try:
        p("no json here")
        check("garbage raises", False, "did not raise")
    except (json.JSONDecodeError, ValueError):
        check("garbage raises", True)


def s2_rails_gate(mk, klog_path: Path):
    print("\n2. Rails gate")
    noon_l = datetime.now(mk.LOCAL_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
    noon = noon_l.astimezone(timezone.utc)
    night = noon_l.replace(hour=3).astimezone(timezone.utc)
    today = noon_l.date().isoformat()

    def fired(hours_ago: float) -> dict:
        ts = noon - timedelta(hours=hours_ago)
        return {"date": today, "timestamp": ts.isoformat(), "acted": True,
                "modality": "text", "move": "smoke", "body": "x"}

    write_json(klog_path, [])
    ok, why = mk.rails_gate(False, now=noon)
    check("empty log at noon → eligible", ok, why)
    ok, why = mk.rails_gate(False, now=night)
    check("3am → quiet hours", not ok and "quiet" in why, why)
    ok, why = mk.rails_gate(True, now=night)
    check("--force overrides quiet hours", ok, why)

    write_json(klog_path, [fired(12 - 3 * i) for i in range(mk.MAX_REACHES_PER_DAY)])
    ok, why = mk.rails_gate(False, now=noon)
    check("daily cap blocks", not ok and "cap" in why, why)

    write_json(klog_path, [fired(1)])
    ok, why = mk.rails_gate(False, now=noon)
    check("min gap blocks a 1h-ago fire", not ok and "gap" in why, why)

    entry = fired(10)
    entry["next_check"] = (noon + timedelta(hours=2)).isoformat()
    write_json(klog_path, [entry])
    ok, why = mk.rails_gate(False, now=noon)
    check("tutor's future next_check blocks", not ok and "next_check" in why, why)
    write_json(klog_path, [])


def canned_decision(act: bool, body: str = "") -> dict:
    return {"act": act, "modality": "text" if act else "silence", "move": "smoke move",
            "rationale": "smoke", "next_check_hours": 3, "notification_body": body,
            "expected_target": "", "target_revealed": False, "schedule": None}


def s3_knock_paths(mk, sb: Path):
    print("\n3. Knock fire + silence paths")
    klog_path = sb / "progress" / "knock_log.json"
    chat_path = sb / "progress" / "chat.md"
    mk.rails_gate = lambda force, now=None: (True, "smoke-open")
    mk.build_digest = lambda: "SMOKE DIGEST"
    pushes, commits = Recorder(), Recorder()
    mk.push_to_phone, mk.commit_and_push = pushes, commits

    mk.decide = lambda digest, vt=None: canned_decision(False)
    sys.argv = ["morning_knock.py"]
    mk.main()
    log = read_json(klog_path)
    check("silence logs acted=false", len(log) == 1 and log[0]["acted"] is False,
          f"log={log}")
    check("silence pushes nothing", len(pushes) == 0)
    check("silence still commits the log", len(commits) == 1)

    body = "smoke dose — say it back"
    mk.decide = lambda digest, vt=None: canned_decision(True, body)
    mk.main()
    log = read_json(klog_path)
    check("fire logs acted=true with body", log[-1].get("acted") and log[-1]["body"] == body)
    check("fire pushes exactly once", len(pushes) == 1 and pushes[0][0] == body)
    check("fire commits knock_log + chat.md",
          len(commits) == 2 and any("chat.md" in str(p) for p in commits[-1][0]),
          f"paths={commits[-1][0] if commits else None}")
    check("chat.md carries the dose", body in chat_path.read_text(encoding="utf-8"))


def s4_normalize(kr):
    print("\n4. Verdict normalization")
    n = kr.normalize_verdict
    d = n({"verdict": "hinted", "fired": [WORD_A], "reply_line": "x"})
    check("flat legacy fired tolerated", d["fired"] == [{"word": WORD_A, "verdict": "hinted"}])
    d = n({"verdict": "hinted", "fired": [{"word": "a", "verdict": "cold"},
                                          {"word": "b", "verdict": "hinted"}]})
    check("overall verdict = best word", d["verdict"] == "cold")
    d = n({"verdict": "cold", "fired": []})
    check("scored-but-empty degrades to miss", d["verdict"] == "miss")
    d = n({"verdict": "??", "fired": [{"word": "a", "verdict": "cold"}]})
    check("junk verdict → chat, fired cleared", d["verdict"] == "chat" and d["fired"] == [])


def canned_verdict(fired: list, reply_line: str = "that's the one") -> dict:
    best = ("cold" if any(v in ("cold", "capped") for _, v in fired) else
            "hinted" if fired else "chat")
    return {"verdict": "cold" if best == "cold" else best,
            "reply_line": reply_line, "rationale": "smoke",
            "fired": [{"word": w, "verdict": v} for w, v in fired],
            "follow_up_ask": "", "follow_up_target": "",
            "follow_up_target_revealed": True, "meta_note": "", "schedule": None}


def s5_reply_judge(mk, kr, sb: Path):
    print("\n5. Reply judge → production axis")
    prog = sb / "progress"
    lex_path = prog / "lexicon.json"
    klog_path = prog / "knock_log.json"
    write_json(lex_path, {
        WORD_A: {"gloss": "Enough", "phonetic": [], "recognition": "solid",
                 "production": "none", "seen_in": [], "last_surfaced": "2026-07-01"},
        WORD_B: {"gloss": "I really like it", "phonetic": [],
                 "recognition": "solid", "production": "none",
                 "seen_in": [], "last_surfaced": "2026-07-01"},
    })
    kr.push_to_phone, kr.commit_and_push = Recorder(), Recorder()
    now = datetime.now(timezone.utc)

    def knock(body: str, target: str, revealed: bool) -> dict:
        return {"date": now.date().isoformat(), "timestamp": now.isoformat(),
                "acted": True, "modality": "challenge", "move": "smoke",
                "body": body, "expected_target": target, "target_revealed": revealed}

    def reply(text: str, verdict: dict):
        kr.judge = lambda k, r, t, h=None, rr=None: verdict
        sys.argv = ["knock_reply.py", text]
        kr.main()

    # unaided fire on an unrevealed target → cold lands, hinted word stays hinted
    log = read_json(klog_path)
    log.append(knock("say the line — go", WORD_B, False))
    write_json(klog_path, log)
    reply(f"{WORD_B}, {WORD_A}",
          canned_verdict([(WORD_B, "cold"), (WORD_A, "hinted")]))
    lex = read_json(lex_path)
    check("cold fire lands", lex[WORD_B]["production"] == "cold")
    check("hinted word records hinted", lex[WORD_A]["production"] == "hinted")
    entry = read_json(klog_path)[-1]
    check("cold pace credits the unrevealed word only",
          entry.get("reply_fired_cold") == [WORD_B],
          f"got {entry.get('reply_fired_cold')}")

    # revealed target → judge's 'cold' is capped deterministically (axis holds
    # at hinted on day 1 — the capped lane's graduation is s11's scenario)
    log = read_json(klog_path)
    log.append(knock(f"fire it back: {WORD_A} — one shot", WORD_A, True))
    write_json(klog_path, log)
    reply(WORD_A, canned_verdict([(WORD_A, "cold")]))
    lex = read_json(lex_path)
    check("revealed-cap holds production at hinted", lex[WORD_A]["production"] == "hinted")
    check("revealed-cap credits no cold pace",
          read_json(klog_path)[-1].get("reply_fired_cold") == [])

    # upgrades only — a hinted re-fire never demotes a cold word
    lex[WORD_B]["production"] = "cold"
    write_json(lex_path, lex)
    log = read_json(klog_path)
    log.append(knock("she just finished cooking — one line", WORD_B, False))
    write_json(klog_path, log)
    reply(WORD_B, canned_verdict([(WORD_B, "hinted")]))
    check("phone rep never demotes",
          read_json(lex_path)[WORD_B]["production"] == "cold")

    # chat verdict moves nothing
    before = lex_path.read_text(encoding="utf-8")
    log = read_json(klog_path)
    log.append(knock("debrief — how did it land?", "", False))
    write_json(klog_path, log)
    reply("it went great, talk tomorrow", canned_verdict([]))
    check("chat verdict leaves the lexicon untouched",
          lex_path.read_text(encoding="utf-8") == before)

    # meta-direction in a reply → feedback ledger
    flog_path = prog / "feedback_log.json"
    n_before = len(read_json(flog_path)) if flog_path.exists() else 0
    log = read_json(klog_path)
    log.append(knock("the gauntlet line — fire it", WORD_A, False))
    write_json(klog_path, log)
    v = canned_verdict([(WORD_A, "hinted")])
    v["meta_note"] = f"{WORD_A} is old muscle memory — stop teaching it"
    reply(f"{WORD_A} (old muscle memory, this one's mine)", v)
    flog = read_json(flog_path)
    check("meta_note lands in the feedback ledger",
          len(flog) == n_before + 1 and flog[-1]["note"].startswith("[phone]"),
          str(flog[-1:]))


def s6_queue_drain(mk, pq, sb: Path):
    print("\n6. Queue drain (regression #1)")
    prog = sb / "progress"
    klog_path, q_path = prog / "knock_log.json", prog / "push_queue.json"
    pushes, commits = Recorder(), Recorder()
    pq.push_to_phone, pq.commit_and_push = pushes, commits
    saved = (pq.WAKING_START_HOUR, pq.WAKING_END_HOUR, pq.MAX_REACHES_PER_DAY)
    now = datetime.now(timezone.utc)

    def q_entry(qid: str, due_hours: float, force: bool = False) -> dict:
        return {"id": qid, "due": (now + timedelta(hours=due_hours)).isoformat(),
                "body": f"dose {qid}", "expected_target": "", "target_revealed": True,
                "audio_url": None, "move": "smoke", "force": force,
                "queued_at": now.isoformat()}

    args = argparse.Namespace(dry_run=False, no_commit=False)
    try:
        pq.WAKING_START_HOUR, pq.WAKING_END_HOUR, pq.MAX_REACHES_PER_DAY = 0, 24, 99
        write_json(klog_path, [])
        write_json(q_path, [q_entry("qOLD", -2), q_entry("qNEW", -1), q_entry("qFUT", +6)])
        pq.cmd_drain(args)
        kept = [e["id"] for e in read_json(q_path)]
        check("one non-forced per tick, OLDEST first",
              len(pushes) == 1 and pushes[0][0] == "dose qOLD", f"pushes={list(pushes)}")
        check("newer + future entries deferred, not dropped", kept == ["qNEW", "qFUT"],
              f"kept={kept}")
        check("fired entry logged with queue_id",
              read_json(klog_path)[-1].get("queue_id") == "qOLD")
        pq.cmd_drain(args)
        check("next tick fires the deferred one",
              len(pushes) == 2 and pushes[1][0] == "dose qNEW")

        # quiet hours defer non-forced; --force punches through
        pq.WAKING_START_HOUR, pq.WAKING_END_HOUR = 0, 0
        write_json(q_path, [q_entry("qQUIET", -1), q_entry("qFORCE", -1, force=True)])
        pq.cmd_drain(args)
        check("quiet hours defers non-forced, fires forced",
              len(pushes) == 3 and pushes[2][0] == "dose qFORCE"
              and [e["id"] for e in read_json(q_path)] == ["qQUIET"])

        # daily cap defers non-forced; forced ignores it
        pq.WAKING_START_HOUR, pq.WAKING_END_HOUR, pq.MAX_REACHES_PER_DAY = 0, 24, 0
        write_json(q_path, [q_entry("qCAP", -1), q_entry("qFORCE2", -1, force=True)])
        pq.cmd_drain(args)
        check("cap defers non-forced, fires forced",
              len(pushes) == 4 and pushes[3][0] == "dose qFORCE2"
              and [e["id"] for e in read_json(q_path)] == ["qCAP"])
    finally:
        pq.WAKING_START_HOUR, pq.WAKING_END_HOUR, pq.MAX_REACHES_PER_DAY = saved


def s7_integrity(sb: Path):
    print("\n7. State integrity sweep")
    for f in sorted((sb / "progress").glob("*.json")):
        try:
            read_json(f)
            check(f"{f.name} valid JSON", True)
        except json.JSONDecodeError as e:
            check(f"{f.name} valid JSON", False, str(e))
    for e in read_json(sb / "progress" / "knock_log.json"):
        if not ("date" in e and "timestamp" in e):
            check("knock_log entries carry date+timestamp", False, str(e)[:80])
            break
    else:
        check("knock_log entries carry date+timestamp", True)


def s8_variety_and_decay(mk, kr, sb: Path):
    """Demand-streak surfaced to the digest, body budgets, continuity decay
    clock, UNSEEN teach-first flags."""
    print("\n8. Variety + decay helpers")
    now = datetime.now(timezone.utc)

    # demand streak counts trailing FIRES that carried an ask; silence skipped
    klog = [
        {"acted": True, "expected_target": "x"},
        {"acted": True, "expected_target": ""},
        {"acted": True, "expected_target": "y"},
        {"acted": False, "expected_target": ""},
        {"acted": True, "expected_target": "z"},
    ]
    check("demand_streak counts trailing asks", mk.demand_streak(klog) == 2,
          str(mk.demand_streak(klog)))
    check("demand_streak zero after a no-ask fire",
          mk.demand_streak([{"acted": True, "expected_target": ""}]) == 0)

    # the rails digest carries the no-ask directive once the streak hits 2
    fired = [{"acted": True, "expected_target": "x", "date": now.date().isoformat(),
              "timestamp": (now - timedelta(hours=5 - i)).isoformat()}
             for i in range(2)]
    room = mk.remaining_room(fired, now)
    check("digest carries the NO-ASK directive at streak 2", "NO-ASK" in room,
          room.splitlines()[-1])

    # lock-screen body budget
    check("over_budget flags a long body",
          mk.over_budget("x" * 200) and not mk.over_budget("x" * 100))

    # continuity decay clock (judge context)
    k = {"timestamp": (now - timedelta(hours=5)).isoformat()}
    h = kr.hours_since_exchange(k, now)
    check("hours_since_exchange reads the knock time", h is not None and 4.9 < h < 5.1, str(h))
    k["reply_at"] = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    h = kr.hours_since_exchange(k, now)
    check("last exchange (reply_at) wins over the knock time",
          h is not None and 0.9 < h < 1.1, str(h))
    check("missing timestamps → None", kr.hours_since_exchange({}, now) is None)

    # never-soaked deck items are flagged UNSEEN on the menu (teach before quiz)
    lex_path = sb / "progress" / "lexicon.json"
    write_json(lex_path, {
        WORD_A: {"gloss": "enough", "phonetic": [], "recognition": "struggled",
                 "production": "none", "seen_in": [], "last_surfaced": None,
                 "deck": "sprint", "direction": "fire"},
    })
    menu = mk.deck_due_list()
    check("never-soaked deck item flagged UNSEEN", "UNSEEN" in menu, menu)
    lex = read_json(lex_path)
    lex[WORD_A]["last_surfaced"] = "2026-07-01"
    write_json(lex_path, lex)
    check("soaked item loses the UNSEEN flag", "UNSEEN" not in mk.deck_due_list())


def s9_audio_knock_feed(mk, sb: Path):
    print("\n9. Audio knock refreshes the feed (all audio -> rss.xml)")
    mk.rails_gate = lambda force, now=None: (True, "smoke-open")
    mk.build_digest = lambda: "SMOKE DIGEST"
    pushes, commits = Recorder(), Recorder()
    mk.push_to_phone, mk.commit_and_push = pushes, commits

    async def fake_render(memo_script, out_path, voice=None):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"smoke-mp3")
    mk.render_memo = fake_render

    d = canned_decision(True, "smoke audio dose")
    d["modality"] = "audio"
    d["memo_script"] = "a one-paragraph smoke memo"
    mk.decide = lambda digest, vt=None: d
    sys.argv = ["morning_knock.py"]
    mk.main()

    paths = [str(p) for p in commits[-1][0]]
    check("audio knock commits the mp3", any("knocks" in p for p in paths), f"paths={paths}")
    check("audio knock commits rss.xml", any(p.endswith("rss.xml") for p in paths), f"paths={paths}")
    check("audio knock logs audio_url",
          bool(read_json(sb / "progress" / "knock_log.json")[-1].get("audio_url")))


def s10_chain_history(mk, kr, sb: Path):
    """#3: a chained follow-up must move the PIN, not overwrite the original
    ask; every exchange lands in `exchanges`; chat.md renders the full chain;
    revealed_recently() computes reveals from the log, not model memory."""
    print("\n10. Chain history + grounded reveals (regression #3)")
    prog = sb / "progress"
    lex_path, klog_path = prog / "lexicon.json", prog / "knock_log.json"
    write_json(lex_path, {
        WORD_B: {"gloss": "I really like it", "phonetic": [],
                 "recognition": "solid", "production": "none", "seen_in": []},
        WORD_A: {"gloss": "Enough / no thanks", "phonetic": [],
                 "recognition": "solid", "production": "none", "seen_in": []},
    })
    kr.push_to_phone, kr.commit_and_push = Recorder(), Recorder()
    now = datetime.now(timezone.utc)
    log = read_json(klog_path)
    log.append({"date": now.date().isoformat(), "timestamp": now.isoformat(),
                "acted": True, "modality": "text", "move": "smoke chain",
                "body": "how do you like it? fire it back",
                "expected_target": WORD_B, "target_revealed": False})
    write_json(klog_path, log)

    # first reply fires cold; the judge chains a follow-up ask for a NEW target
    v = canned_verdict([(WORD_B, "cold")])
    v["follow_up_ask"] = "they pile more food — wave it off"
    v["follow_up_target"] = WORD_A
    v["follow_up_target_revealed"] = False
    kr.judge = lambda k, r, t, h=None, rr=None: v
    sys.argv = ["knock_reply.py", WORD_B]
    kr.main()
    entry = read_json(klog_path)[-1]
    check("original ask survives the chain",
          entry["expected_target"] == WORD_B,
          f"got {entry.get('expected_target')}")
    check("pin moved to the follow-up", entry.get("pinned_target") == WORD_A)

    # second reply is graded against the PIN, and both exchanges are on record
    kr.judge = lambda k, r, t, h=None, rr=None: canned_verdict([(WORD_A, "cold")])
    sys.argv = ["knock_reply.py", f"{WORD_A}!"]
    kr.main()
    entry = read_json(klog_path)[-1]
    check("both exchanges recorded", len(entry.get("exchanges", [])) == 2,
          f"got {len(entry.get('exchanges', []))}")
    check("second reply graded against the pin",
          read_json(lex_path)[WORD_A]["production"] == "cold")
    check("fired accumulates across the chain",
          entry.get("reply_fired") == [WORD_B, WORD_A],
          f"got {entry.get('reply_fired')}")

    # the chat record shows every turn of the chain, not just the last
    chat = (prog / "chat.md").read_text(encoding="utf-8")
    check("chat renders the full chain",
          WORD_B in chat and f"{WORD_A}!" in chat)

    # grounded reveals: only words actually printed in recent knock traffic list
    log = read_json(klog_path)
    log.append({"date": now.date().isoformat(), "timestamp": now.isoformat(),
                "acted": True, "modality": "text", "move": "smoke recap",
                "body": f"yesterday: {WORD_B} ✓ — solid",
                "expected_target": "", "target_revealed": False})
    write_json(klog_path, log)
    rr = kr.revealed_recently(read_json(klog_path), read_json(lex_path))
    check("revealed_recently sees the printed word", WORD_B in rr, f"got {rr}")


def s11_capped_graduation(kr, sb: Path):
    """#4: the reveal-cap's hinted-forever trap. Cold-quality fires the reveal
    window blocks are recorded CAPPED; capped fires on GRADUATION_DAYS distinct
    local days graduate the word to cold. Judge claims resolve against computed
    evidence: a 'capped' with no reveal on record upgrades to cold; a 'cold' on
    shown text downgrades to capped."""
    print("\n11. Capped lane + cross-day graduation (regression #4)")
    prog = sb / "progress"
    lex_path, klog_path = prog / "lexicon.json", prog / "knock_log.json"
    kr.push_to_phone, kr.commit_and_push = Recorder(), Recorder()
    now = datetime.now(timezone.utc)
    yday = now - timedelta(days=1)

    # (a) day 2 of capped fires → graduation to COLD, pace credited
    write_json(lex_path, {
        WORD_C: {"gloss": "I'm used to it", "phonetic": [],
                 "recognition": "solid", "production": "hinted",
                 "seen_in": [], "last_surfaced": "2026-07-01"},
    })
    day1 = {"date": yday.date().isoformat(), "timestamp": yday.isoformat(),
            "acted": True, "modality": "text", "move": "smoke lore",
            "body": f"{WORD_C} — 'used to it'. let it sit in your ear.",
            "expected_target": "", "target_revealed": False,
            "exchanges": [{"at": yday.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "reply": WORD_C, "verdict": "hinted",
                           "fired": [WORD_C], "fired_cold": [],
                           "fired_capped": [WORD_C], "graduated": [],
                           "reply_line": "that's the one"}]}
    day2 = {"date": now.date().isoformat(), "timestamp": now.isoformat(),
            "acted": True, "modality": "text", "move": "smoke ask",
            "body": "they warn the food is spicy — brush it off, you're used to it",
            "expected_target": WORD_C, "target_revealed": False}
    write_json(klog_path, [day1, day2])
    kr.judge = lambda k, r, t, h=None, rr=None: canned_verdict([(WORD_C, "capped")])
    sys.argv = ["knock_reply.py", WORD_C]
    kr.main()
    lex = read_json(lex_path)
    check("2nd distinct capped day graduates to COLD",
          lex[WORD_C]["production"] == "cold", lex[WORD_C]["production"])
    entry = read_json(klog_path)[-1]
    check("graduation credits the cold pace",
          entry.get("reply_fired_cold") == [WORD_C],
          str(entry.get("reply_fired_cold")))
    check("exchange records the graduation",
          entry["exchanges"][-1].get("graduated") == [WORD_C],
          str(entry["exchanges"][-1]))

    # (b) judge says 'capped' but nothing on record revealed the word → COLD
    write_json(lex_path, {
        WORD_A: {"gloss": "enough / no thanks", "phonetic": [],
                 "recognition": "solid", "production": "none",
                 "seen_in": [], "last_surfaced": "2026-07-01"},
    })
    write_json(klog_path, [{
        "date": now.date().isoformat(), "timestamp": now.isoformat(),
        "acted": True, "modality": "text", "move": "smoke ask",
        "body": "they pile more food — wave it off", "expected_target": WORD_A,
        "target_revealed": False}])
    kr.judge = lambda k, r, t, h=None, rr=None: canned_verdict([(WORD_A, "capped")])
    sys.argv = ["knock_reply.py", WORD_A]
    kr.main()
    check("unverifiable capped claim upgrades to COLD",
          read_json(lex_path)[WORD_A]["production"] == "cold")

    # (c) judge says 'cold' on text the knock itself printed → capped (day 1: hinted)
    write_json(lex_path, {
        WORD_B: {"gloss": "I really like it", "phonetic": [],
                 "recognition": "solid", "production": "none",
                 "seen_in": [], "last_surfaced": "2026-07-01"},
    })
    write_json(klog_path, [{
        "date": now.date().isoformat(), "timestamp": now.isoformat(),
        "acted": True, "modality": "text", "move": "smoke reveal",
        "body": f"fire it back: {WORD_B} — one shot", "expected_target": WORD_B,
        "target_revealed": True}])
    kr.judge = lambda k, r, t, h=None, rr=None: canned_verdict([(WORD_B, "cold")])
    sys.argv = ["knock_reply.py", WORD_B]
    kr.main()
    entry = read_json(klog_path)[-1]
    check("shown 'cold' lands as capped (axis holds at hinted on day 1)",
          read_json(lex_path)[WORD_B]["production"] == "hinted"
          and entry.get("reply_fired_capped") == [WORD_B],
          f"prod={read_json(lex_path)[WORD_B]['production']} capped={entry.get('reply_fired_capped')}")


def s12_volley(mk, kr, sb: Path):
    """#5: the standalone daily blitz. normalize_decision zips the tutor's asks
    with Python's BINDING targets; the reply judge advances the volley pin
    deterministically — even on a miss (recast-and-move), ignoring the judge's
    own chain — and the queue is finite."""
    print("\n12. Volley knock — binding targets + deterministic advance (regression #5)")
    prog = sb / "progress"
    lex_path, klog_path = prog / "lexicon.json", prog / "knock_log.json"
    w1, w2, w3 = WORD_A, WORD_B, WORD_C
    menu = [{"target": w, "gloss": "g"} for w in (w1, w2, w3)]

    # normalize_decision: binding zip + Python-composed body
    raw = {"act": True, "modality": "volley", "move": "daily volley",
           "rationale": "smoke", "next_check_hours": 3,
           "notification_body": "model's own body — must be overridden",
           "expected_target": "", "target_revealed": True,
           "volley_asks": ["ask one", "ask two", "ask three"], "schedule": None}
    d = mk.normalize_decision(dict(raw), menu)
    check("volley zips asks with Python's targets",
          d.get("volley") == [{"target": w1, "ask": "ask one"},
                              {"target": w2, "ask": "ask two"},
                              {"target": w3, "ask": "ask three"}], str(d.get("volley")))
    check("volley body is composed from ask 1, target unrevealed",
          d["notification_body"] == "⚡ volley 1/3 — ask one"
          and d["expected_target"] == w1 and d["target_revealed"] is False)
    d = mk.normalize_decision(dict(raw), [])
    check("volley without a binding menu degrades to text",
          d["modality"] == "text" and not d.get("volley"))

    # reply flow: cold → advance; MISS → still advance; queue exhausts
    write_json(lex_path, {
        w: {"gloss": "g", "phonetic": [], "recognition": "solid",
            "production": "none", "seen_in": [], "last_surfaced": "2026-07-01"}
        for w in (w1, w2, w3)})
    kr.push_to_phone, kr.commit_and_push = Recorder(), Recorder()
    now = datetime.now(timezone.utc)
    write_json(klog_path, [{
        "date": now.date().isoformat(), "timestamp": now.isoformat(),
        "acted": True, "modality": "volley", "move": "daily volley",
        "body": "⚡ volley 1/3 — ask one", "expected_target": w1,
        "target_revealed": False,
        "volley": [{"target": w1, "ask": "ask one"}, {"target": w2, "ask": "ask two"},
                   {"target": w3, "ask": "ask three"}],
        "volley_next": 1}])

    v = canned_verdict([(w1, "cold")])
    v["follow_up_ask"] = "judge's own chain — must be ignored"
    v["follow_up_target"] = w3
    kr.judge = lambda k, r, t, h=None, rr=None: v
    sys.argv = ["knock_reply.py", w1]
    kr.main()
    entry = read_json(klog_path)[-1]
    check("volley advance ignores the judge's chain and pins item 2",
          entry.get("pinned_target") == w2 and entry.get("volley_next") == 2,
          f"pin={entry.get('pinned_target')} next={entry.get('volley_next')}")
    check("push-back carries item 2's ask", "2/3 — ask two" in entry.get("reply_line", ""),
          entry.get("reply_line"))

    miss = canned_verdict([])
    miss["verdict"], miss["reply_line"] = "miss", "close — next time"
    kr.judge = lambda k, r, t, h=None, rr=None: miss
    sys.argv = ["knock_reply.py", "not quite the word"]
    kr.main()
    entry = read_json(klog_path)[-1]
    check("a MISS still advances the volley (recast-and-move)",
          entry.get("pinned_target") == w3 and entry.get("volley_next") == 3,
          f"pin={entry.get('pinned_target')} next={entry.get('volley_next')}")

    kr.judge = lambda k, r, t, h=None, rr=None: canned_verdict([(w3, "cold")])
    sys.argv = ["knock_reply.py", w3]
    kr.main()
    entry = read_json(klog_path)[-1]
    check("exhausted volley chains nothing further",
          entry.get("volley_next") == 3
          and entry["exchanges"][-1]["reply_line"] == "that's the one",
          f"next={entry.get('volley_next')} line={entry.get('reply_line')}")
    check("volley graded item 3 against its pin",
          read_json(lex_path)[w3]["production"] == "cold")
    check("original volley ask survives on record", entry.get("expected_target") == w1)


def s13_eavesdrop(mk, kr, sb: Path):
    """#6: the catch-axis knock. An eavesdrop reply is judged on the drift
    mandate and moves RECOGNITION one rung per catch (upgrades only, solid =
    the deck win); production and the fire meters never move."""
    print("\n13. Eavesdrop dose — drift replies move the catch axis only (regression #6)")
    prog = sb / "progress"
    lex_path, klog_path = prog / "lexicon.json", prog / "knock_log.json"
    w = WORD_EAR

    # normalize_decision: a tape-less eavesdrop degrades to text; a real one
    # keeps the modality and never counts as a revealed production ask
    raw = {"act": True, "modality": "eavesdrop", "move": "gossip tape",
           "rationale": "smoke", "next_check_hours": 3, "memo_script": "",
           "notification_body": "who's the news about?", "expected_target": w,
           "target_revealed": True, "schedule": None}
    d = mk.normalize_decision(dict(raw))
    check("tape-less eavesdrop degrades to text", d["modality"] == "text")
    raw["memo_script"] = f"{w}… their daughter got a job in the city!"
    d = mk.normalize_decision(dict(raw))
    check("eavesdrop keeps modality, target unrevealed",
          d["modality"] == "eavesdrop" and d["target_revealed"] is False)
    # without a pinned eavesdrop voice the modality is never rendered
    saved_voice = mk.EAVESDROP_VOICE
    mk.EAVESDROP_VOICE = ""
    d = mk.normalize_decision(dict(raw))
    check("no eavesdrop_voice configured → degrades to text", d["modality"] == "text")
    mk.EAVESDROP_VOICE = saved_voice

    write_json(lex_path, {w: {
        "gloss": "you know?", "phonetic": [], "recognition": "struggled",
        "production": "none", "seen_in": [], "last_surfaced": "2026-07-01",
        "deck": "sprint", "direction": "catch", "type": "chunk"}})
    kr.push_to_phone, kr.commit_and_push = Recorder(), Recorder()
    now = datetime.now(timezone.utc)

    def eavesdrop_knock() -> dict:
        return {"date": now.date().isoformat(), "timestamp": now.isoformat(),
                "acted": True, "modality": "eavesdrop", "move": "gossip tape",
                "body": "who's the news about?", "memo_script": raw["memo_script"],
                "expected_target": w, "target_revealed": False}

    def reply(text: str, verdict: str):
        kr.judge_catch = lambda k, r: {"verdict": verdict, "reply_line": "you caught it 🎧",
                                       "meta_note": "", "rationale": "smoke"}
        sys.argv = ["knock_reply.py", text]
        kr.main()

    # caught → one rung; caught again → solid; production never moves
    log = read_json(klog_path); log.append(eavesdrop_knock()); write_json(klog_path, log)
    reply("their daughter got a job in the city", "caught")
    lex = read_json(lex_path)
    check("caught bumps recognition one rung", lex[w]["recognition"] == "comfortable")
    check("production untouched by a catch", lex[w]["production"] == "none")
    entry = read_json(klog_path)[-1]
    check("catch reply logs no production fire",
          entry.get("reply_fired") is None and entry["exchanges"][-1]["fired"] == [],
          str(entry.get("reply_fired")))
    check("catch verdict on record", entry.get("reply_verdict") == "caught")

    log = read_json(klog_path); log.append(eavesdrop_knock()); write_json(klog_path, log)
    reply("something about a wedding date", "caught")
    check("second catch reaches solid — the deck win",
          read_json(lex_path)[w]["recognition"] == "solid")

    # missed / chat move nothing
    log = read_json(klog_path); log.append(eavesdrop_knock()); write_json(klog_path, log)
    before = read_json(lex_path)[w]
    reply("no idea, too fast", "missed")
    after = read_json(lex_path)[w]
    check("missed drift moves no axis", after["recognition"] == before["recognition"])


def s14_reply_correlation(kr):
    """KF-9: notifications stack (unique tag per knock); taps and replies carry
    the knock's log timestamp back as knock_id. find_knock targets the exact
    entry; a missing/stale/empty id returns None so callers fall back to
    last-fired (pre-migration notifications stay judgeable)."""
    print("\n14. Reply correlation (stacked notifications)")
    klog = [
        {"acted": True, "timestamp": "2026-07-11T08:00:00+00:00", "move": "volley"},
        {"acted": False, "timestamp": "2026-07-11T10:00:00+00:00", "move": "silence"},
        {"acted": True, "timestamp": "2026-07-11T12:00:00+00:00", "move": "lore memo"},
    ]
    hit = kr.find_knock(klog, "2026-07-11T08:00:00+00:00")
    check("find_knock targets an older stacked knock by id",
          hit is not None and hit["move"] == "volley")
    check("unknown id → None (caller falls back to last-fired)",
          kr.find_knock(klog, "2026-07-13T00:00:00+00:00") is None)
    check("empty id → None (id-less events keep last-fired behavior)",
          kr.find_knock(klog, "") is None)
    check("silence entries never match (no notification existed)",
          kr.find_knock(klog, "2026-07-11T10:00:00+00:00") is None)


def s15_push_retry(mk):
    print("\n15. Push delivery retry (regression #8)")
    import os
    import urllib.error

    class FakeResp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    calls = {"n": 0}
    sleeps = []
    real_urlopen, real_sleep = mk.urllib.request.urlopen, mk.time.sleep
    os.environ["PUSH_WEBHOOK_URL"] = "https://smoke.invalid/hook"
    try:
        mk.time.sleep = sleeps.append

        def flaky(req, *a, **kw):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.URLError(OSError("Temporary failure in name resolution"))
            return FakeResp()
        mk.urllib.request.urlopen = flaky
        mk.push_to_phone("smoke", None, knock_id="smoke")
        check("two blips then success — delivered", calls["n"] == 3, f"{calls['n']} calls")
        check("backoff between attempts", sleeps == [5, 10], f"sleeps={sleeps}")

        calls["n"] = 0
        def dead(req, *a, **kw):
            calls["n"] += 1
            raise urllib.error.URLError(OSError("no route"))
        mk.urllib.request.urlopen = dead
        try:
            mk.push_to_phone("smoke", None, knock_id="smoke")
            check("unreachable webhook still raises", False, "did not raise")
        except OSError:
            check("unreachable webhook still raises", True)
        check("gave up after 3 attempts", calls["n"] == 3, f"{calls['n']} calls")
    finally:
        mk.urllib.request.urlopen, mk.time.sleep = real_urlopen, real_sleep
        os.environ.pop("PUSH_WEBHOOK_URL", None)


def s16_stale_clone_gates(sb: Path):
    print("\n16. Stale-clone gates + payload canon (regression #9)")
    # A session opened on a clone behind origin re-collects paid field missions
    # and misses the morning trailer; a comma-joined soak payload never matches
    # an episode's words. The pure halves of the fixes:
    ss = importlib.import_module("sync_state")

    check("behind origin → STALE banner", "STALE" in (ss.sync_banner((14, 0)) or ""))
    check("ahead only → unpushed warning", "not on origin" in (ss.sync_banner((0, 1)) or ""))
    check("in sync → no banner", ss.sync_banner((0, 0)) is None)
    check("sync unknown → soft warning", "SYNC UNKNOWN" in (ss.sync_banner(None) or ""))

    check("comma-joined payload splits",
          ss.canon_payload([f"frame:x,{WORD_A}"]) == ["frame:x", WORD_A])
    check("clean payload passes through",
          ss.canon_payload(["a", "b"]) == ["a", "b"])

    check("no record → unseen", ss.is_unseen({}))
    check("surfaced → not unseen", not ss.is_unseen({"last_surfaced": "2026-07-01"}))
    check("in an episode → not unseen", not ss.is_unseen({"seen_in": ["M60"]}))

    trailer = {"date": "2026-07-15", "move": "session bell trailer", "body": f"{WORD_A} today"}
    volley = {"date": "2026-07-15", "move": "afternoon volley", "body": "…"}
    check("newest-knock trailer with no session after → unpaid",
          ss.unpaid_trailer([volley, trailer], "2026-07-13") is trailer)
    check("session on/after trailer date → paid",
          ss.unpaid_trailer([trailer], "2026-07-15") is None)
    check("newest knock not a trailer → nothing owed",
          ss.unpaid_trailer([trailer, volley], "2026-07-13") is None)
    check("knocks_since filters to the gap",
          [k["date"] for k in ss.knocks_since([{"date": "2026-07-10"}, {"date": "2026-07-14"}],
                                              "2026-07-13")] == ["2026-07-14"])


def s17_campaign_digest(mk, sb: Path):
    print("\n17. Campaign block in the knock digest")
    # The campaign is learner-initiated prose in profile.md; the digest carries
    # it so the cloud tutor steers by it. No section / placeholder / missing ⇒ "".
    profile = sb / "progress" / "profile.md"
    original = profile.read_text(encoding="utf-8")
    # The day-zero example profile ships the section with the placeholder line.
    check("day-zero placeholder → no campaign block", mk.campaign_block() == "")

    profile.write_text(
        original.split("## The Campaign — This Week", 1)[0]
        + "## The Campaign — This Week\n\n"
        "> Contract: see daily_session.md.\n\n"
        f"**Ask-machine week** (07-20 → 07-26): {WORD_A}, {WORD_B}.\n"
        "- Mon: teach day\n\n## After The Campaign\n\nunrelated\n",
        encoding="utf-8")
    block = mk.campaign_block()
    check("live campaign lands in the digest", "Ask-machine week" in block)
    check("contract blockquote stripped", "Contract" not in block)
    check("next section not swept in", "unrelated" not in block)

    profile.write_text(profile.read_text(encoding="utf-8").replace(
        f"**Ask-machine week** (07-20 → 07-26): {WORD_A}, {WORD_B}.\n"
        "- Mon: teach day",
        "_(no campaign live yet — kick one off at the next session)_"),
        encoding="utf-8")
    check("placeholder → no campaign block", mk.campaign_block() == "")
    profile.write_text(original, encoding="utf-8")


# Word budgets for the prose surfaces (from the reference impl, 2026-07-16): every
# incident lands as a paragraph, and prose only accumulates — "earn its place"
# doesn't enforce itself. Growth past a budget is a red run; raising a budget must
# ride the same diff as the growth, and the commit names the lines it retired
# (/extend Gate 4). A file that keeps hitting its ceiling is carrying crud or
# doing two jobs — a split-or-retire signal, never a bump-the-number reflex.
PROSE_BUDGETS = {
    "protocol/persona.md.template": 1800,
    "protocol/constitution.md": 1950,
    "protocol/daily_session.md": 1350,
    "OUTREACH_MANDATE": 2100,
    "JUDGE_MANDATE": 1500,
    "CATCH_JUDGE_MANDATE": 300,
}


def s18_prose_budgets(mk, kr, sb: Path):
    print("\n18. Protocol prose word budgets (the subtraction mechanism)")
    strings = {"OUTREACH_MANDATE": mk.OUTREACH_MANDATE,
               "JUDGE_MANDATE": kr.JUDGE_MANDATE,
               "CATCH_JUDGE_MANDATE": kr.CATCH_JUDGE_MANDATE}
    for rel, budget in PROSE_BUDGETS.items():
        words = (len(strings[rel].split()) if rel in strings
                 else len((sb / rel).read_text(encoding="utf-8").split()))
        check(f"{rel}: {words}/{budget} words", words <= budget,
              f"over by {words - budget} — retire lines, or raise the budget in this "
              f"same diff and name what it retired")


def s20_fielding(mk, kr, sb: Path):
    """The fielding dose: a target-language question fired AT the learner, reply
    graded as production by the NORMAL judge — never the catch judge. The
    stimulus half of the exchange has its own channel."""
    print("\n20. Fielding dose — heard question in, produced answer out")
    prog = sb / "progress"
    lex_path, klog_path = prog / "lexicon.json", prog / "knock_log.json"

    raw = {"act": True, "modality": "fielding", "move": "field the FAQ",
           "rationale": "smoke", "next_check_hours": 3, "memo_script": "",
           "notification_body": "they're asking you something — answer",
           "expected_target": WORD_A, "target_revealed": True, "schedule": None}
    d = mk.normalize_decision(dict(raw))
    check("question-less fielding degrades to text", d["modality"] == "text")
    raw["memo_script"] = "¿ya comiste?"
    d = mk.normalize_decision(dict(raw))
    check("fielding keeps modality, answer unrevealed",
          d["modality"] == "fielding" and d["target_revealed"] is False)

    mk.rails_gate = lambda force, now=None: (True, "smoke-open")
    mk.build_digest = lambda: "SMOKE DIGEST"
    mk.push_to_phone, mk.commit_and_push = Recorder(), Recorder()

    async def fake_render(memo_script, out_path, voice=None):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"smoke-mp3")
        fake_render.voice = voice
    mk.render_memo = fake_render
    mk.decide = lambda digest, vt=None: dict(d)
    sys.argv = ["morning_knock.py"]
    mk.main()
    entry = read_json(klog_path)[-1]
    check("fielding renders audio and logs the url", bool(entry.get("audio_url")))
    check("fielding speaks in the second voice, not the tutor's",
          fake_render.voice == mk.EAVESDROP_VOICE)

    write_json(lex_path, {WORD_A: {
        "gloss": "enough", "phonetic": [], "recognition": "comfortable",
        "production": "none", "seen_in": ["M1"], "last_surfaced": "2026-07-01",
        "deck": "trip", "direction": "fire", "type": "chunk"}})
    kr.push_to_phone, kr.commit_and_push = Recorder(), Recorder()
    catch_calls = Recorder()
    kr.judge_catch = catch_calls
    kr.judge = lambda k, r, t, h=None, rr=None: canned_verdict([(WORD_A, "cold")])
    sys.argv = ["knock_reply.py", WORD_A]
    kr.main()
    check("fielding reply routes to the PRODUCTION judge", len(catch_calls) == 0)
    check("fielded answer moves the production axis",
          read_json(lex_path)[WORD_A]["production"] == "cold")


def s21_volley_represent(kr, sb: Path):
    """KF-11: a chat/meta reply mid-volley let the open ask vanish and the judge
    improvised the chain surface. Python re-presents the pinned ask on chat
    verdicts and marks the chain closed after the last judged item."""
    print("\n21. Volley re-present on chat replies (KF-11)")
    prog = sb / "progress"
    klog_path = prog / "knock_log.json"
    write_json(prog / "lexicon.json", {})
    kr.commit_and_push = Recorder()

    def volley_knock(nxt: int) -> dict:
        return {"date": "2026-07-18", "timestamp": f"2026-07-18T15:0{nxt}:00+00:00",
                "acted": True, "modality": "volley", "move": "smoke volley",
                "body": "⚡ volley 1/3 — ask one", "expected_target": "t1",
                "target_revealed": False, "volley_next": nxt,
                "pinned_target": f"t{min(nxt, 3)}", "pinned_revealed": False,
                "volley": [{"target": "t1", "ask": "ask one"},
                           {"target": "t2", "ask": "ask two"},
                           {"target": "t3", "ask": "ask three"}]}

    def reply(text: str, verdict: dict):
        kr.judge = lambda k, r, t, h=None, rr=None: verdict
        kr.push_to_phone = pushes = Recorder()
        sys.argv = ["knock_reply.py", text]
        kr.main()
        return pushes[-1][0]

    chat = {"verdict": "chat", "reply_line": "ha, all good", "rationale": "smoke",
            "fired": [], "follow_up_ask": "", "follow_up_target": "",
            "follow_up_target_revealed": True, "meta_note": "", "schedule": None}

    # the one owner of "the current ask" — judge context and re-presents both read it
    check("volley_open_ask names the current item",
          kr.volley_open_ask(volley_knock(nxt=2)) == "2/3 — ask two")
    check("volley_open_ask starts at ask one",
          kr.volley_open_ask(volley_knock(nxt=1)) == "1/3 — ask one")
    check("volley_open_ask clamps past the end",
          kr.volley_open_ask(volley_knock(nxt=3)) == "3/3 — ask three")
    check("no volley → no open ask", kr.volley_open_ask({"body": "x"}) is None)

    # chat mid-volley → the pinned ask is re-presented; pin and chain untouched
    write_json(klog_path, [volley_knock(nxt=2)])
    body = reply("wait, which one are we on?", dict(chat))
    entry = read_json(klog_path)[-1]
    check("chat mid-volley re-presents the open ask", "still open · 2/3 — ask two" in body, body)
    check("pin does not move on chat", entry["volley_next"] == 2 and entry["pinned_target"] == "t2")
    check("chat does not count as a chain step", entry.get("chained", 0) == 0)

    # judged reply on the LAST item closes the chain
    write_json(klog_path, [volley_knock(nxt=3)])
    miss = dict(chat); miss["verdict"] = "miss"; miss["reply_line"] = "that one is 'ask three'"
    body = reply("no idea", miss)
    entry = read_json(klog_path)[-1]
    check("last judged item marks the volley done", entry.get("volley_done") is True)
    check("no re-present after the chain closes", "still open" not in body, body)

    # chat AFTER the volley is done stays a plain chat
    body = reply("thanks!", dict(chat))
    check("chat on a finished volley adds no ask", "still open" not in body, body)


def s22_sfx_pause(sb: Path):
    print("\n22. [SFX] cues render as air, never dropped (regression #11)")
    ra = importlib.import_module("render_audio")
    script = sb / "content" / "scripts" / "smoke_sfx.md"
    script.write_text(
        "# Tier 2, Mission 99 — Smoke\n\n"
        "[SFX: A phone rings in the dark.]\n\n"
        "**HOST (M):** Three fourteen in the morning.\n\n"
        "[SFX: Sheets rustle.]\n"
        "[Pause: 2 sec]\n", encoding="utf-8")
    dialogue, _ = ra.parse_script(str(script))
    check("SFX cue becomes a pause",
          dialogue[0]["speaker"] == "PAUSE" and dialogue[0]["seconds"] == 1.5,
          f"got {dialogue[0]}")
    check("SFX text never reaches a voice",
          not any("phone rings" in d.get("text", "") for d in dialogue))
    check("adjacent SFX + pause coalesce",
          dialogue[-1] == {"speaker": "PAUSE", "seconds": 3.5}, f"got {dialogue[-1]}")


def s23_ticket_end_to_end(sb: Path):
    print("\n23. suggest_targets: the ticket runs end-to-end (regression #12)")
    import contextlib
    import io
    st = importlib.import_module("suggest_targets")
    # Bootstrap-shaped curriculum fixture: the live files a /setup would create.
    cur = sb / "curriculum"
    for ex in cur.glob("*.example"):
        shutil.copy(ex, cur / ex.name[: -len(".example")])
    # The proven crash class: a reference sidecar carrying a STRING mission must
    # never enter (or crash) the integer mission sort.
    (sb / "content" / "scripts" / "real_ep.tags.json").write_text(
        json.dumps({"mission": 3, "register": "domestic"}), encoding="utf-8")
    (sb / "content" / "scripts" / "special_smoke.tags.json").write_text(
        json.dumps({"mission": "smoke reference tape", "register": "neutral"}),
        encoding="utf-8")
    cars = st.load_recent_sidecars()
    check("string-mission sidecar never enters the rotation",
          all(isinstance(c.get("mission"), int) for c in cars))
    check("integer-mission sidecar survives the filter",
          any(c.get("mission") == 3 for c in cars))

    argv, out = sys.argv, io.StringIO()
    try:
        sys.argv = ["suggest_targets.py"]
        with contextlib.redirect_stdout(out):
            st.main()
        ran = True
    except Exception as e:  # noqa: BLE001 — the check IS "it doesn't raise"
        ran, out = False, io.StringIO(f"raised {e!r}")
    finally:
        sys.argv = argv
    text = out.getvalue()
    check("ticket runs end-to-end on day-zero state", ran, text[:200])
    check("ticket prints the menu header", "SESSION TICKET" in text)
    check("day-zero ticket still serves new candidates",
          "not found" not in text, text[:200])


def s24_intake_status_refresh(sb: Path):
    print("\n24. Intake meter honesty: word entry outside a session refreshes the status line")
    from types import SimpleNamespace
    ss = importlib.import_module("sync_state")
    learner_path = sb / "progress" / "learner.json"
    # Stamp the current truth, then grow the floor's denominator outside a session —
    # the intake-sweep shape that left a stale "100%" in the first cold elaboration.
    ss.refresh_learner_status()
    before = read_json(learner_path)["status"]
    ss.cmd_add_word(SimpleNamespace(key="palabra de humo", gloss="smoke word",
                                    phonetic=[], recognition="solid"))
    after = read_json(learner_path)["status"]
    check("add-word recomputes the stored status line",
          before != after and "fire cold" in after, f"{before!r} -> {after!r}")


def main():
    with tempfile.TemporaryDirectory(prefix="tutor-smoke-") as tmp:
        sb = make_sandbox(Path(tmp))
        print(f"sandbox: {sb}")
        mk, kr, pq = load_modules(sb)
        s1_parse_llm_json(mk)
        s2_rails_gate(mk, sb / "progress" / "knock_log.json")
        s15_push_retry(mk)   # needs the real push_to_phone — s3+ stub it out
        s3_knock_paths(mk, sb)
        s4_normalize(kr)
        s5_reply_judge(mk, kr, sb)
        s6_queue_drain(mk, pq, sb)
        s7_integrity(sb)
        s8_variety_and_decay(mk, kr, sb)
        s9_audio_knock_feed(mk, sb)
        s10_chain_history(mk, kr, sb)
        s11_capped_graduation(kr, sb)
        s12_volley(mk, kr, sb)
        s13_eavesdrop(mk, kr, sb)
        s14_reply_correlation(kr)
        s16_stale_clone_gates(sb)
        s17_campaign_digest(mk, sb)
        s18_prose_budgets(mk, kr, sb)
        s20_fielding(mk, kr, sb)
        s21_volley_represent(kr, sb)
        s22_sfx_pause(sb)
        s23_ticket_end_to_end(sb)
        s24_intake_status_refresh(sb)

    print(f"\n{'ALL GREEN' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
