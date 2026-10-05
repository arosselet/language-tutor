#!/usr/bin/env python3
"""
Studio dispatch — the writer passes + the local Python renderer.

The writer runs each studio pass as a READ-ONLY, PRINT-ONLY call — Director →
Architect → Producer, one invocation per pass (collapsing them produces flat,
off-canon scripts). The writer never writes a file, runs a command or sees git:
Python captures each pass's stdout, writes the artifacts, LINTS them
deterministically, and hands the script to render_audio.py, which owns TTS,
registration, the feed and the commit.

TWO EXECUTORS: `claude -p` where an agent exists (no cash cost, reads the canon
off disk), the OpenRouter API where one does not (`inline_canon` carries the
canon instead). The host decides (`writer.have_agent`).

Exit 0 = episode rendered and published. Any other exit = the caller falls back
to the studio subagent (.claude/agents/studio.md). Failed artifacts stay in
place, untracked, for inspection.

  python scripts/run_studio.py            # full: three passes, lint, render, publish
  python scripts/run_studio.py --dry-run  # passes + lint only; no render

Needs: claude on PATH (or OPENROUTER_API_KEY), TTS credentials for the render.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from pack import (AUDIO_FORM, CHAT_FORM, LANGUAGE, LEARNER, NATIVE_LANGUAGE, WEAVE_RULE,
                  has_target, l1_runs, stem, target_runs)
import world

# A caller reads this as "this host lacks the secrets" — skip, never retry.
EXIT_NOT_CONFIGURED = 3

SCRIPTS_DIR = BASE / "content" / "scripts"
LESSONS_DIR = BASE / "content" / "lessons"
CAPTIONS_DIR = BASE / "content" / "captions"
AUDIO_DIR = BASE / "published_audio"

PASS_TIMEOUT_S = 900   # 15 min per pass — each is one print turn

# READ-ONLY BY CONSTRUCTION: the PREAMBLE says each pass is print-only and
# `--allowedTools` enforces it. Python is the only thing that touches disk.
WRITER_TOOLS = ["Read", "Glob", "Grep"]
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

SPEAKER_RE = re.compile(r"^\s*(?:\*\s*)?\*\*[^:]+:")
REQUIRED_TAGS = {"mission", "register", "dramatic_ingredient", "episode_form",
                 "new_words_landed", "beat"}

PREAMBLE = """\
You are ONE pass of the Studio pipeline (protocol/studio/studio.md) for the
""" + LANGUAGE + """ tutor repo in the current directory. You are print-only: PRINT
your artifact as your response. Write NO files, run NO commands, touch NO git —
Python persists your output and runs the next pass. You never address the
learner; the fourth wall stays up (protocol/studio/hosts.md).
"""

DIRECTOR = PREAMBLE + """
THIS PASS: the DIRECTOR. Read protocol/studio/director.md and follow it
exactly. Read progress/profile.md — its Calibration Notes are LAW — and the
soak-order in progress/learner.json. The ticket + scene spec below are
already computed; the spec is a GATE, not a suggestion.

Read content/world.md — THE CANON. This episode is the next beat in that
world's life, with those people, in that place. It is not a fresh invented
scenario: the cast recurs, the standing facts are binding, and the beat log is
what the scene may call back to. Variety comes from the scene spec (register /
form / ingredient), never from changing who these people are. The Scenario
section of your plan must name which cast members are in it and what is
happening to them.

{ticket}

PRINT the complete Master Lesson Plan and nothing else.
"""

ARCHITECT = PREAMBLE + """
THIS PASS: the ARCHITECT. Read protocol/studio/architect.md and follow it
exactly (including the Listenability Gate). Calibration from
progress/profile.md is LAW — the weave: """ + WEAVE_RULE + """; density is an
OUTPUT of the 95% known-word coverage rule, never a target. All """ + LANGUAGE + """
is """ + AUDIO_FORM + """. Here is the Master Lesson Plan:

{plan}

PRINT the full episode script and nothing else. The VERY FIRST LINE must be
the title as an H1 — `# Tier 2, Mission {n} — <Title>` — because the feed reads
the episode's public name off that one line and nothing else. Then speaker
lines as `**Name:** text`, with [SFX] / [Pause] craft per the role file.
"""

PRODUCER = PREAMBLE + """
THIS PASS: the PRODUCER. Read protocol/studio/producer.md,
protocol/dialect.md and protocol/constitution.md and follow them exactly:
dialect transformation, integrity checks (send-backs become fixes you make
yourself here), and the sidecar. All """ + LANGUAGE + """ stays """ + AUDIO_FORM + """.
Here is the Master Lesson Plan the draft was built from — the Vocabulary Fence
in it is the SOURCE for `fence_size` and `unfenced_words`; count against it,
never eyeball them:

{plan}

PAYLOAD FIDELITY is a hard rule the dialect pass must not violate: a CHUNK the
sidecar claims must appear EXACTLY as seeded — the learner drills these precise
forms and a mutated anchor poisons the rep. A single WORD may carry the
sentence's own inflection, but its stem must survive (Python rejects the script
on either failure). Here is the Architect's draft:

{draft}

PRINT exactly two fenced blocks and nothing else:
1. a ```markdown fence with the final production script
2. a ```json fence with the .tags.json sidecar — "mission": {n}, schema per
   the existing content/scripts/*.tags.json files, PLUS a "beat" key: ONE
   plain sentence saying what happened in the world this episode, as the
   beat log would record it ("The cousin says the scooter is fine. It is not.").
   Python appends it to content/world.md — you write no files.
"""

CAPTIONS = PREAMBLE + """
THIS PASS: the CAPTION SHEET (the follow-along the learner reads while
listening; see protocol/studio/studio.md). Below is the FINAL production
script. Transcribe it into a markdown sheet:
- Open with `# Captions — Ep {n} · <title>` and this blockquote how-to:
  "**Follow-along sheet** — the line as *sound* · what it means." /
  "Passes 1–2: listen with this open. Pass 3+: put it away — **blind is the
  win.**"
- Then ONE blockquote per spoken line, two `<br>`-separated rows:
  `**<speaker letter/name>:** *<the full line as SOUND — """ + NATIVE_LANGUAGE + """
  words as written, """ + LANGUAGE + """ words in """ + CHAT_FORM + """>*`
  then the plain """ + NATIVE_LANGUAGE + """ meaning.
- Skip the meaning row when a line is already mostly """ + NATIVE_LANGUAGE + """.
- Keep [SFX]/[Pause] as short italic position cues between blockquotes.

{script}

PRINT one ```markdown fence with the caption sheet and nothing else.
"""


def next_mission() -> int:
    nums = [int(m.group(1)) for p in SCRIPTS_DIR.glob("tier2_mission*.md")
            if (m := re.match(r"tier2_mission(\d+)\.md$", p.name))]
    return max(nums, default=0) + 1


def episode_paths(n: int) -> dict[str, Path]:
    return {"brief": LESSONS_DIR / f"tier2_mission{n}_brief.md",
            "script": SCRIPTS_DIR / f"tier2_mission{n}.md",
            "tags": SCRIPTS_DIR / f"tier2_mission{n}.tags.json",
            "captions": CAPTIONS_DIR / f"tier2_mission{n}.md"}


def claude_print(label: str, prompt: str) -> str | None:
    """One read-only, print-only pass on the local agent; stdout or None. Runs in
    BASE so the pass reads the canon off disk."""
    from writer import AGENT_MODEL
    print(f"   [{label}] claude ({AGENT_MODEL or 'default model'})…")
    try:
        r = subprocess.run(
            ["claude", "-p", *(["--model", AGENT_MODEL] if AGENT_MODEL else []),
             "--allowedTools", *WRITER_TOOLS, "--", prompt],
            cwd=BASE, timeout=PASS_TIMEOUT_S, capture_output=True,
            encoding="utf-8", errors="replace")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"   ✗ {label}: {e}")
        return None
    out = (r.stdout or "").strip()
    if r.returncode != 0 or len(out) < 200:
        print(f"   ✗ {label}: exit {r.returncode}, {len(out)} chars — "
              f"{(r.stderr or out)[-200:]}")
        return None
    print(f"   [{label}] {len(out)} chars")
    return out


CANON_REF_RE = re.compile(r"(?:(?:protocol|progress)/[\w/-]+|content/world)\.(?:md|json)")
CANON_SKIP = {
    # Raw rows the ticket already distills; inlining it would re-send what the
    # ticket chose from. Skipped LOUDLY below.
    "progress/lexicon.json",
}
CANON_DEPTH = 2   # the prompt names a file; that file names its canon. No further.


def newest_tags_sample() -> str | None:
    """The freshest real sidecar, as the schema example for the cloud Producer."""
    tags = sorted(SCRIPTS_DIR.glob("tier2_mission*.tags.json"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    return tags[0].read_text(encoding="utf-8").strip() if tags else None


def inline_canon(prompt: str) -> str:
    """Carry the protocol INTO the prompt for the filesystem-less cloud writer.
    The prompt's own file references are the manifest, followed transitively to
    CANON_DEPTH (role files cite the constitution), deduped. Anything referenced
    and NOT carried is printed, so a blind spot announces itself."""
    seen, blocks, queue, skipped = [], [], list(CANON_REF_RE.findall(prompt)), []
    for _ in range(CANON_DEPTH):
        nxt = []
        for ref in queue:
            if ref in seen:
                continue
            seen.append(ref)
            if ref in CANON_SKIP:
                skipped.append(ref)
                continue
            p = BASE / ref
            if not p.exists():
                blocks.append(f"===== {ref} (referenced but missing) =====")
                continue
            text = p.read_text(encoding="utf-8").strip()
            blocks.append(f"===== {ref} =====\n{text}")
            nxt.extend(CANON_REF_RE.findall(text))
        queue = nxt
    if skipped:
        print(f"   [canon] referenced but NOT carried: {', '.join(skipped)}")
    if ".tags.json" in prompt:
        sample = newest_tags_sample()
        if sample:
            blocks.append("===== EXAMPLE .tags.json — match THIS schema exactly "
                          f"(your content, its keys) =====\n{sample}")
    if not blocks:
        return prompt
    return ("CANON — the files this pass refers to, inlined because you have no "
            "filesystem. Follow them exactly:\n\n"
            + "\n\n".join(blocks)
            + "\n\n===== YOUR TASK =====\n" + prompt)


def openrouter_pass(label: str, prompt: str) -> str | None:
    """One writer pass through OpenRouter — same contract as `claude_print`, with
    `inline_canon` supplying what a filesystem would."""
    from openai import OpenAI
    from writer import OPENROUTER_MODEL, budget
    print(f"   [{label}] openrouter ({OPENROUTER_MODEL})…")
    try:
        client = OpenAI(base_url=OPENROUTER_BASE, api_key=os.environ["OPENROUTER_API_KEY"])
        resp = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            max_tokens=budget(8000),
            messages=[{"role": "user", "content": inline_canon(prompt)}],
            timeout=PASS_TIMEOUT_S,
        )
        out = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"   ✗ {label}: {type(e).__name__}: {str(e)[:200]}")
        return None
    if len(out) < 200:
        print(f"   ✗ {label}: {len(out)} chars — too short")
        return None
    print(f"   [{label}] {len(out)} chars")
    return out


def resolve_writer(prefer: str = "auto"):
    """Pick the pass executor: the host rule for 'auto', or force one (A/B)."""
    if prefer == "claude":
        return claude_print
    if prefer == "openrouter":
        return openrouter_pass
    from writer import have_agent
    return claude_print if have_agent() else openrouter_pass


def payload_present(word: str, script: str, lexicon: dict) -> bool:
    """Is a claimed payload item really in the script? VERBATIM FOR CHUNKS (a
    fixed phrase is drilled whole, so a mutation poisons the rep), STEM-TOLERANT
    FOR WORDS (the sentence inflects a word). A stem under 3 characters is no
    evidence and falls back to verbatim."""
    if word in script:
        return True
    if " " in word or (lexicon.get(word) or {}).get("type") == "chunk":
        return False
    root = stem(word)
    return len(root) >= 3 and root in script


def fenced_block(text: str, lang: str) -> str | None:
    m = re.findall(rf"```{lang}\s*\n(.*?)```", text, re.DOTALL)
    return m[-1].strip() if m else None


def write_episode(n: int, write_pass=claude_print) -> bool:
    """Run the passes; persist the artifacts. Python is the only thing that
    touches disk.

    THE CANON IS A PRECONDITION: without it an episode is set nowhere, and that
    state is indistinguishable from a working world. The Producer gets the PLAN
    as well as the draft: it counts the fence, and the brief is not on disk yet."""
    if bad := world.problem():
        print(f"   ✗ world canon unusable — {bad}")
        return False
    ticket = subprocess.run([sys.executable, str(BASE / "scripts" / "suggest_targets.py"), "--fence"],
                            capture_output=True, encoding="utf-8", errors="replace",
                            cwd=BASE, check=True).stdout
    plan = write_pass("Director", DIRECTOR.format(ticket=ticket))
    if not plan:
        return False
    draft = write_pass("Architect", ARCHITECT.format(plan=plan, n=n))
    if not draft:
        return False
    final = write_pass("Producer", PRODUCER.format(plan=plan, draft=draft, n=n))
    if not final:
        return False

    script = fenced_block(final, "markdown")
    tags = fenced_block(final, "json")
    if not script or not tags:
        print("   ✗ Producer output missing the markdown/json fences")
        return False
    # PYTHON PINS THE VOICES; the writer never transcribes them. The map goes
    # AFTER the H1: the feed reads the public title off line 1 and nothing else,
    # and the renderer finds the map anywhere.
    vmap = world.voice_map(script)
    if vmap:
        head, _, body = script.partition("\n")
        script = f"{head}\n{world.render_voice_map(vmap)}\n{body}"
    paths = episode_paths(n)
    paths["brief"].parent.mkdir(parents=True, exist_ok=True)
    paths["brief"].write_text(plan + "\n", encoding="utf-8")
    paths["script"].write_text(script + "\n", encoding="utf-8")
    paths["tags"].write_text(tags + "\n", encoding="utf-8")

    # THE CANON REMEMBERS THIS EPISODE, or the run is not finished.
    try:
        beat = str(json.loads(tags).get("beat") or "")
    except json.JSONDecodeError:
        beat = ""          # lint() reports the unparseable sidecar itself
    if not world.append_beat(n, beat):
        print(f"   ✗ beat did not reach the canon's log (beat={beat!r})")
        return False

    # Caption sheet — a companion, never a gate.
    sheet_out = write_pass("Captions", CAPTIONS.format(n=n, script=script))
    sheet = fenced_block(sheet_out, "markdown") if sheet_out else None
    if sheet:
        paths["captions"].parent.mkdir(parents=True, exist_ok=True)
        paths["captions"].write_text(sheet + "\n", encoding="utf-8")
    else:
        print("   ⚠ caption sheet pass failed — episode ships without captions")
    return True


def git_dirty() -> set[str]:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=BASE,
                         capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    return {ln[3:].strip() for ln in out if ln[3:].strip()}


# The speaker label and stage directions are not spoken payload.
LINE_CRAFT_RE = re.compile(r"\[.*?\]")
# SPEAKER_RE is match-only and other readers depend on that; the name is captured
# by a second pattern.
SPEAKER_NAME_RE = re.compile(r"^\s*(?:\*\s*)?\*\*\s*([^:]+?)\s*:\s*(?:\*\*)?\s*(.*)")


def native_share(script: str) -> float:
    """The learner's-language word share of the spoken lines — the weave
    tripwire. Density is an OUTPUT, never a target, so this is not a dial: it
    trips only on near-pure target dialogue, which cannot hold live comprehension."""
    spoken = "\n".join(LINE_CRAFT_RE.sub(" ", m.group(2))
                       for ln in script.splitlines() if (m := SPEAKER_NAME_RE.match(ln)))
    native = len(l1_runs(spoken))
    target = len(target_runs(spoken))
    return native / (native + target) if native + target else 0.0


MIN_NATIVE_SHARE = 0.15  # tripwire, not a dial — well under every healthy episode


def voice_lines(script: str) -> dict[str, tuple[int, int]]:
    """speaker -> (lines carrying target language, lines spoken)."""
    out: dict[str, tuple[int, int]] = {}
    for ln in script.splitlines():
        m = SPEAKER_NAME_RE.match(ln)
        if not m:
            continue
        said = LINE_CRAFT_RE.sub(" ", m.group(2)).strip()
        if not said:
            continue
        who = m.group(1).strip().upper()
        tgt, spoken = out.get(who, (0, 0))
        out[who] = (tgt + has_target(said), spoken + 1)
    return out


def carrying_voice(script: str) -> float:
    """The most-target VOICE in the episode — is anybody actually in the scene?

    NOT A DENSITY MEASURE. Scaffolded in the learner's language is not the same
    as mostly in it: a healthy scaffolded episode splits the ROLES (a narrator
    carrying logistics, a voice living the scene), so its overall ratio can be
    low and still sound. The failure is an episode where every host narrates and
    the target is only quoted inside the narration. A voice needs
    MIN_VOICE_LINES to count: a two-line walk-on is not a scene."""
    return max((tgt / spoken for tgt, spoken in voice_lines(script).values()
                if spoken >= MIN_VOICE_LINES), default=0.0)


MIN_VOICE_LINES = 5   # below this a voice is a walk-on, not the scene
VOICE_CARRIES = 0.50  # tripwire, not a dial


def lint(n: int, baseline: set[str] | None = None) -> list[str]:
    """Deterministic post-checks; every rule here earned its place from an
    observed failure."""
    problems = []
    paths = episode_paths(n)
    for kind, p in paths.items():
        if not p.exists() or p.stat().st_size == 0:
            problems.append(f"{kind} missing or empty: {p.relative_to(BASE)}")
    if problems:
        return problems

    try:
        tags = json.loads(paths["tags"].read_text(encoding="utf-8"))
        missing = REQUIRED_TAGS - set(tags)
        if missing:
            problems.append(f"tags.json missing keys: {sorted(missing)}")
        elif tags.get("mission") != n:
            problems.append(f"tags.json mission {tags.get('mission')} != {n}")
    except json.JSONDecodeError as e:
        problems.append(f"tags.json unparseable: {e}")

    script = paths["script"].read_text(encoding="utf-8")
    if len(script) < 1000:
        problems.append(f"script suspiciously short ({len(script)} chars)")
    # The feed reads ONE line for the public name; assert exactly what it reads.
    if not script.splitlines()[0].strip().startswith("# "):
        problems.append(
            "script's FIRST line is not an H1 title — the feed would fall back "
            f"to the filename (got: {script.splitlines()[0][:60]!r})")
    if not has_target(script):
        problems.append(f"script carries no {LANGUAGE} (the payload must be {LANGUAGE})")
    if not any(SPEAKER_RE.match(ln) for ln in script.splitlines()):
        problems.append("script has no **Speaker:** lines — renderer can't voice it")
    else:
        share = native_share(script)
        if share < MIN_NATIVE_SHARE:
            problems.append(
                f"weave tripwire: only {share:.0%} {NATIVE_LANGUAGE} in spoken lines "
                f"(floor {MIN_NATIVE_SHARE:.0%}) — near-pure {LANGUAGE} can't hold live comprehension")
        voice = carrying_voice(script)
        if voice < VOICE_CARRIES:
            problems.append(
                f"no voice carries the scene: the most-{LANGUAGE} speaker is only "
                f"{voice:.0%} {LANGUAGE} (floor {VOICE_CARRIES:.0%}) — every host is "
                f"narrating, so the {LANGUAGE} is quoted evidence rather than the scene")
    if LEARNER and re.search(rf"\b{re.escape(LEARNER)}\b", script, re.IGNORECASE):
        problems.append(f"fourth wall: script names the learner ({LEARNER})")
    if re.search(r"^\s*(?:\*\s*)?\*\*\s*(?:the\s+)?(?:learner|student)\b", script,
                 re.IGNORECASE | re.MULTILINE):
        problems.append("fourth wall: a speaker is labeled LEARNER/STUDENT — "
                        "self-insert characters break the podcast's own world")

    # Payload fidelity: every lexicon item the sidecar claims must be in the
    # script (frame: keys are slot templates and exempt).
    if not problems:
        lexicon = json.loads((BASE / "progress" / "lexicon.json").read_text(encoding="utf-8"))
        claimed = set(tags.get("new_words_landed", {})) | set(tags.get("callbacks_used", {}))
        mutated = [w for w in claimed
                   if w in lexicon and not w.startswith("frame:")
                   and not payload_present(w, script, lexicon)]
        if mutated:
            problems.append(f"payload infidelity — claimed but not in the script: {mutated}")

    # Nothing beyond the episode's files may have appeared under content/,
    # measured against the PRE-RUN tree; posix paths on both sides.
    allowed = {p.relative_to(BASE).as_posix() for p in paths.values()}
    stray = {p for p in git_dirty() - (baseline or set()) - allowed
             if p.startswith("content/") and p != "content/world.md"}
    if stray:
        problems.append(f"stray writes outside the episode files: {sorted(stray)}")
    return problems


def claim_payload(n: int) -> None:
    """The soak order this dispatch consumed must be CLAIMED by the sidecar, or
    registration never records it and the order never clears. Frames inject
    unconditionally; a word injects only when the script carries it (the same
    `payload_present` the lint asks). An absent one is reported, never invented."""
    paths = episode_paths(n)
    try:
        soak = (json.loads((BASE / "progress" / "learner.json").read_text(encoding="utf-8"))
                .get("soak_order") or {})
        lex = json.loads((BASE / "progress" / "lexicon.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    payload = [w for w in soak.get("payload", []) if w]
    if not payload:
        return
    tags = json.loads(paths["tags"].read_text(encoding="utf-8"))
    script = paths["script"].read_text(encoding="utf-8")
    strip = lambda w: re.sub(r"\s*\([^)]*\)\s*$", "", w).strip()
    claimed = {strip(w) for w in
               set(tags.get("new_words_landed", {})) | set(tags.get("callbacks_used", {}))}
    added = []
    for key in payload:
        if key in claimed:
            continue
        if key.startswith("frame:") or payload_present(key, script, lex):
            tags.setdefault("new_words_landed", {})[key] = 0
            added.append(key)
        else:
            print(f"   ⚠ soak payload '{key}' neither claimed by the sidecar nor in the script")
    if added:
        paths["tags"].write_text(json.dumps(tags, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        print(f"   payload claimed into sidecar: {', '.join(added)}")


def claim_spec(n: int) -> None:
    """Python stamps the scene spec into the sidecar; the writer only obeys it.
    The divergence gate reads these sidecars, so a mislabelled episode would
    corrupt the next three choices. Never invents: an unreadable sidecar is left."""
    sys.path.insert(0, str(BASE / "scripts"))
    from suggest_targets import commissioned_form, load_recent_sidecars, scene_spec
    paths = episode_paths(n)
    try:
        tags = json.loads(paths["tags"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    # Recomputed (a pure function of the sidecars, which the lock holds still).
    spec = scene_spec(load_recent_sidecars(), commissioned_form())
    stamped = {"register": spec["register"], "episode_form": spec["form"],
               "dramatic_ingredient": spec["ingredient"]}
    drifted = {k: (tags.get(k), v) for k, v in stamped.items() if tags.get(k) != v}
    if not drifted:
        return
    tags.update(stamped)
    paths["tags"].write_text(json.dumps(tags, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    for k, (was, now) in drifted.items():
        print(f"   spec stamped: {k} {was!r} → {now!r} (Python decides, the writer obeys)")


def renderer_preflight() -> str | None:
    """None when this host can RENDER, else the reason."""
    sys.path.insert(0, str(BASE / "scripts"))
    try:
        from render_audio import tts_ready
    except ImportError as e:
        return f"the renderer's dependencies are not installed ({e.name})"
    return tts_ready()


def writer_preflight(prefer: str = "auto") -> str | None:
    """None when a writer is available for `prefer`, else the reason."""
    from writer import have_agent
    have_claude = have_agent()
    have_or = bool(os.environ.get("OPENROUTER_API_KEY"))
    if prefer == "claude" and not have_claude:
        return "claude is not on PATH (the local agent writer)"
    if prefer == "openrouter" and not have_or:
        return "OPENROUTER_API_KEY is not set (the cloud writer)"
    if prefer == "auto" and not (have_claude or have_or):
        return "no writer available — need claude on PATH or OPENROUTER_API_KEY"
    return None


def preflight(prefer: str = "auto") -> str | None:
    """None when this host can produce an episode end to end. Checked before any
    expensive pass, locally and cheaply."""
    return writer_preflight(prefer) or renderer_preflight()


_DISPATCH_LOCK = None  # held for the process lifetime; see main()


def acquire_dispatch_lock():
    """One dispatch at a time (render_audio shares the lock). No-op without fcntl."""
    try:
        import fcntl
    except ImportError:
        return None
    fd = open(BASE / ".studio.lock", "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("✗ another studio dispatch holds .studio.lock — not stacking a second run.")
        sys.exit(1)
    return fd


def main():
    ap = argparse.ArgumentParser(description="Studio dispatch — claude (local) or OpenRouter (cloud) writer + Python renderer")
    ap.add_argument("--dry-run", action="store_true",
                    help="passes + lint only; no render, no state, no commit")
    ap.add_argument("--writer", choices=["auto", "claude", "openrouter"], default="auto",
                    help="pass executor: auto (claude if present, else OpenRouter), or force one (A/B)")
    args = ap.parse_args()

    sys.path.insert(0, str(BASE / "scripts"))
    from publish import load_env
    load_env(BASE / ".env")

    # A module global: the flock releases when its file object is collected.
    global _DISPATCH_LOCK
    _DISPATCH_LOCK = acquire_dispatch_lock()

    # A missing credential is not a failure: EXIT_NOT_CONFIGURED means skip.
    reason = preflight(args.writer)
    if reason:
        print(f"⏭️  Not a studio host — {reason}.\n"
              f"    Set the credentials (SETUP.md), or produce on a configured host.")
        sys.exit(EXIT_NOT_CONFIGURED)

    write_pass = resolve_writer(args.writer)
    n = next_mission()
    print(f"Mission {n} — three-pass print-only dispatch ({write_pass.__name__})")
    baseline = git_dirty()
    print("1. passes…")
    if not write_episode(n, write_pass):
        sys.exit(1)

    print("2. lint…")
    problems = lint(n, baseline)
    for p in problems:
        print(f"   ✗ {p}")
    if problems:
        print("   artifacts left in place for inspection — falling back is safe")
        sys.exit(1)
    print("   all checks pass")
    claim_payload(n)
    claim_spec(n)

    if args.dry_run:
        print(f"[dry-run] would render: tier2_mission{n}.mp3 — stopping before state.")
        return

    print("3. render + publish (render_audio.py owns state and the commit)…")
    script = episode_paths(n)["script"]
    mp3 = AUDIO_DIR / f"tier2_mission{n}.mp3"
    # We hold .studio.lock; the child inherits it rather than blocking on its parent.
    r = subprocess.run([sys.executable, str(BASE / "scripts" / "render_audio.py"),
                        str(script), str(mp3)], cwd=BASE,
                       env={**os.environ, "STUDIO_LOCK_HELD": "1"})
    if r.returncode == EXIT_NOT_CONFIGURED:
        print("   ⏭️  render skipped — this host lacks the TTS credentials.")
        sys.exit(EXIT_NOT_CONFIGURED)
    if r.returncode != 0:
        print(f"   ✗ render failed (exit {r.returncode})")
        sys.exit(1)

    # Say it exists; quiet hours are the chokepoint's job.
    try:
        from publish import push_to_phone, jsdelivr_url
        title = episode_paths(n)["script"].stem
        if push_to_phone(f"new episode's up — {title} 🎧", jsdelivr_url(mp3)):
            print("   phone: notified.")
    except Exception as e:
        print(f"   ⚠ publish notification failed (episode is still live): {e}")

    print(f"done — Mission {n} rendered and published.")


if __name__ == "__main__":
    main()
