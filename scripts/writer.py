#!/usr/bin/env python3
"""WHO MAKES THE CALL — the one place that chooses an executor for a model lane.

THE RULE: a laptop has an agent with a subscription already paid for; a GitHub
runner has neither. So the HOST decides, here, once, by asking whether the
`claude` binary exists — never a lane, never a flag someone must remember. On the
laptop a lane spends tokens already bought; in Actions it spends cash.

The cloud path (`_api_json`, `_api_text`) is a first-class branch, not an error
path: it is what runs whenever a lane is routed to Actions. Test it by forcing it.

STRUCTURED OUTPUT SURVIVES THE CROSSING: the API path sends `JSON_MODE`; the agent
path sends a per-lane `--json-schema`, which constrains the shape (stronger).

THE PROMPT GOES DOWN STDIN, not argv: Windows caps a command line near 32,767
characters and these prompts inline the voice canon. Stdin has no ceiling.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Module-level on purpose: the smoke suite swaps this name for a stub client.
from openai import OpenAI

from mandates import READ_REWRITE
from pack import AGENT_MODEL, WRITER_MODEL, needs_read_form, target_runs, unmark

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
OPENROUTER_BASE = "https://openrouter.ai/api/v1"   # OpenAI-compatible; one key, many models
# ONE MODEL PER EXECUTOR, stated once each and never derived at a call site:
# `MODEL` is the cloud writer (decide, judges, the read-form rewrite); every
# other lane runs on the agent where one exists. A bad agent slug makes the CLI
# print an error and EXIT 0, so `_agent_json` treats empty stdout as failure.
MODEL = WRITER_MODEL
OPENROUTER_MODEL = MODEL
# A grading model writes the production axis: a vendor change recalibrates the
# learning record silently. The graded replies in knock_log.json are the A/B corpus.

# THINKING IS PART OF THE BUDGET, and only the MODEL knows what it costs. A call
# site declares what its ANSWER needs; the thinking room is added HERE, once.
# Some reasoners expand into whatever room exists, so there are two dials: the cap
# (sent as `reasoning.max_tokens`) pulls the distribution down without bounding
# the tail, and the headroom absorbs what escapes it. A ceiling is not a spend —
# unused headroom bills at nothing, and a truncation is a dead lane. Neither
# number is portable across models: SWAP THE MODEL, RE-MEASURE BOTH.
REASONING_HEADROOM = 8000
REASONING_CAP = 4000
# Both API paths send it, because elasticity is a property of the model. It rides
# `extra_body` (an OpenRouter extension); a provider that ignores it falls back to
# the ceiling alone.
REASONING_BUDGET = {"reasoning": {"max_tokens": REASONING_CAP}}


def budget(answer_tokens: int) -> int:
    """The ceiling for one call: what the artifact needs, plus this model's room
    to think. Call sites pass the former; never a raw `max_tokens`."""
    return answer_tokens + REASONING_HEADROOM

# STRUCTURED OUTPUT, one definition. Every JSON lane sends it; text lanes must NOT.
# It makes prose-wrapped JSON impossible at the API instead of survivable at the
# parser. It requires the word "JSON" in the prompt, which every mandate carries.
JSON_MODE = {"type": "json_object"}

def parse_llm_json(text: str) -> dict:
    """Parse a model's JSON, surviving the wrappers models still produce. A
    BACKSTOP behind JSON_MODE, kept because a judge has no retry loop and a dead
    judge is a reply the learner sent and got nothing back for.

    Strategy: strip a leading fence → json.loads → a fenced block ANYWHERE (last
    wins) → {..} slice → ast.literal_eval (single quotes, True/False/None). Prints
    the raw text before any re-raise so the log shows what came back."""
    import ast as _ast
    import re as _re
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        for block in reversed(_re.findall(r"```(?:json)?\s*\n(.*?)```", text, _re.DOTALL)):
            try:
                return json.loads(block.strip(), strict=False)
            except json.JSONDecodeError:
                continue
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            print(f"--- unparseable LLM response (no braces) ---\n{text}\n---")
            raise
        slice_ = text[start : end + 1]
        try:
            return json.loads(slice_, strict=False)
        except json.JSONDecodeError:
            try:
                result = _ast.literal_eval(slice_)
                if isinstance(result, dict):
                    return result
            except (ValueError, SyntaxError):
                pass
            print(f"--- unparseable LLM response (all fallbacks failed) ---\n{text}\n---")
            raise


def parse_llm_response(resp) -> dict:
    """`parse_llm_json` for a raw API response, plus the one check text alone
    cannot make: TRUNCATION. A parser gap and a truncation look identical in the
    text and want opposite fixes, and only `finish_reason` tells them apart.

    Raised as ValueError (not re-rolled by `ask_json`). It names the dial it
    MEASURED: thinking over the headroom points here; an answer over its declared
    size points at the call site."""
    c = resp.choices[0]
    if getattr(c, "finish_reason", None) == "length":
        text = c.message.content or ""
        det = getattr(getattr(resp, "usage", None), "completion_tokens_details", None)
        think = getattr(det, "reasoning_tokens", None) if det else None
        where = ("no usage split on this response — check the ANSWER first" if think is None
                 else f"THINKING ran out: {think} reasoning tokens over "
                      f"REASONING_HEADROOM={REASONING_HEADROOM}; re-measure it for this "
                      f"model, the call site is not the dial" if think > REASONING_HEADROOM
                 else f"the ANSWER ran out: {think} reasoning tokens fit the headroom, "
                      f"so raise `answer_tokens` at the CALL SITE")
        raise ValueError(f"LLM response TRUNCATED at the ceiling on {OPENROUTER_MODEL} "
                         f"({len(text)} chars of artifact emitted) — {where}. Not a "
                         f"parser gap.\n--- truncated response ---\n{text}\n---")
    return parse_llm_json(c.message.content)

# ── The read-form rewrite — the one TEXT lane here ───────────────────────────
# It shares the CLIENT with the JSON lanes, never JSON_MODE. Reached from the
# knock lane and every reply push-back. It is the identity when the read form
# equals the voice form (`pack.needs_read_form`).


def rephrase_read_form(body: str) -> str:
    """Ask the composer to rewrite its own body into the read form. The model
    knows how it spelt the thing, so a colloquial contraction survives; a lexicon
    lookup flattens exactly the register the dialect canon protects."""
    return ask_text(READ_REWRITE, body, answer_tokens=300)


def to_read_form(text: str, label: str = "body") -> str:
    """A surface the learner READS, in the read form. Leftovers WARN and ship: a
    leaked word costs the learner far less than a dose they never get. One re-ask
    first, because the agent sometimes keeps the voice form with the read form
    appended — the one thing this function exists to keep off the lock screen."""
    if not needs_read_form(text):
        return unmark(text)
    print(f"   ✎ {label} carries the voice form — asking for the read form…")
    out = rephrase_read_form(text) or text
    if needs_read_form(out):
        out = rephrase_read_form(text) or out
    if needs_read_form(out):
        print(f"   ⚠ voice form survived the rewrite: {' '.join(target_runs(out))}")
    return out


# A SCHEMA MUST DESCRIBE A SHAPE. Handed `{"type": "object"}` with no properties,
# the CLI answers in an envelope — {"output": "<the real sheet as a JSON STRING>"}
# — which parses, has the key, and renders an empty tape. So every lane declares
# its top-level shape; the mandates carry the craft.
STR = {"type": "string"}
INT = {"type": "integer"}
BOOL = {"type": "boolean"}
STRS = {"type": "array", "items": STR}


def obj(**props) -> dict:
    """A top-level object schema; everything declared is required. UNDECLARED
    KEYS ARE NOT SAFE: the API path passes them through, the agent path silently
    drops them. If a mandate names a key, name it here too."""
    return {"type": "object", "properties": props, "required": list(props)}


def nullable(schema: dict) -> dict:
    """The same shape, or null — for a key a mandate declares conditional.
    Undeclaring a key to mean "optional" deletes it on the agent path."""
    return {**schema, "type": [schema["type"], "null"]}


def arr(**props) -> dict:
    """An array of objects with `props`. Left unconstrained, an array of
    objects can come back as an array of strings."""
    return {"type": "array", "items": obj(**props)}


# The envelope's fingerprint: no lane asks for an `output` string.
ENVELOPE_KEY = "output"
# A `claude -p` call starts a whole session; matches run_studio.PASS_TIMEOUT_S.
AGENT_TIMEOUT_S = 900


def have_agent() -> bool:
    """Is there a local agent to spend the subscription on? The whole host test."""
    return shutil.which("claude") is not None


def _agent_json(system: str, user: str, schema: dict) -> dict:
    """One print-only pass on the local agent. Raises on any failure; never
    silently returns the API's work."""
    cmd = ["claude", "-p", *(["--model", AGENT_MODEL] if AGENT_MODEL else []),
           "--json-schema", json.dumps(schema, ensure_ascii=False)]
    r = subprocess.run(
        cmd, input=f"{system}\n\n---\n\n{user}", cwd=BASE, timeout=AGENT_TIMEOUT_S,
        capture_output=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    # The CLI exits 0 on a bad model string, so empty stdout is failure too.
    if r.returncode != 0 or not out:
        raise RuntimeError(f"claude -p exit {r.returncode}: {(r.stderr or out)[-300:]}")
    got = parse_llm_json(out)
    if isinstance(got.get(ENVELOPE_KEY), str):
        raise RuntimeError(
            "claude -p returned an {'output': '<json string>'} ENVELOPE, not the "
            "artifact — the schema handed to it did not describe a shape. The "
            "lane would have rendered an empty dose. Schema was: "
            f"{json.dumps(schema, ensure_ascii=False)[:200]}")
    return got


def _api_json(system: str, user: str, answer_tokens: int, model: str | None = None) -> dict:
    """One pass through OpenRouter — same prompt, same contract."""
    client = OpenAI(base_url=OPENROUTER_BASE, api_key=os.environ["OPENROUTER_API_KEY"])
    resp = client.chat.completions.create(
        model=model or OPENROUTER_MODEL, max_tokens=budget(answer_tokens),
        response_format=JSON_MODE, extra_body=REASONING_BUDGET,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return parse_llm_response(resp)


def ask_json(system: str, user: str, schema: dict, answer_tokens: int = 2400,
             tries: int = 3, prefer: str = "auto", model: str | None = None) -> dict:
    """One model call -> parsed JSON, on whichever executor this host has.

    `schema` is REQUIRED: a default would hand the agent a permissive schema and
    render a shell. `answer_tokens` is what the ARTIFACT needs. A no-JSON reply is
    re-rolled (a lane that asks fifteen times cannot survive a coin-flip parse); a
    truncation is not. `prefer` forces 'agent'/'api' for a test; `model`
    overrides the API slug for one call."""
    use_agent = have_agent() if prefer == "auto" else (prefer == "agent")
    for attempt in range(1, tries + 1):
        try:
            if use_agent:
                return _agent_json(system, user, schema)
            return _api_json(system, user, answer_tokens, model)
        except (subprocess.SubprocessError, RuntimeError, OSError) as e:
            # LOUD: a present-but-broken agent quietly billing the API reads green
            # because the artifact arrived. A degrade that costs money announces itself.
            if not use_agent:
                raise
            print(f"   ⚠ LOCAL AGENT FAILED — falling back to the PAID API. "
                  f"This run costs money and the subscription path is broken; "
                  f"fix it, do not ignore it.\n     {type(e).__name__}: {e}")
            use_agent = False
        except ValueError as e:
            if attempt == tries or "TRUNCATED" in str(e):
                raise
            print(f"   ⚠ no JSON in the reply ({str(e)[:120]}) — "
                  f"retry {attempt + 1}/{tries}")
    raise RuntimeError("ask_json: retries exhausted without a result or an error")


def _agent_text(system: str, user: str) -> str:
    """One print-only pass on the local agent, no schema (a schema makes the CLI
    emit an object, the one thing a line must not be)."""
    cmd = ["claude", "-p", *(["--model", AGENT_MODEL] if AGENT_MODEL else [])]
    r = subprocess.run(
        cmd, input=f"{system}\n\n---\n\n{user}", cwd=BASE, timeout=AGENT_TIMEOUT_S,
        capture_output=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        raise RuntimeError(f"claude -p exit {r.returncode}: {(r.stderr or out)[-300:]}")
    return out


def _api_text(system: str, user: str, answer_tokens: int) -> str:
    """One pass through OpenRouter for a PROSE answer. JSON_MODE stays absent."""
    client = OpenAI(base_url=OPENROUTER_BASE, api_key=os.environ["OPENROUTER_API_KEY"])
    resp = client.chat.completions.create(
        model=OPENROUTER_MODEL, max_tokens=budget(answer_tokens),
        extra_body=REASONING_BUDGET,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return (resp.choices[0].message.content or "").strip()


def ask_text(system: str, user: str, answer_tokens: int = 300,
             prefer: str = "auto") -> str:
    """One model call -> a LINE, on whichever executor this host has. No retry:
    there is no parse to re-roll."""
    use_agent = have_agent() if prefer == "auto" else (prefer == "agent")
    if use_agent:
        try:
            return _agent_text(system, user)
        except (subprocess.SubprocessError, RuntimeError, OSError) as e:
            print(f"   ⚠ LOCAL AGENT FAILED — falling back to the PAID API. "
                  f"This run costs money and the subscription path is broken; "
                  f"fix it, do not ignore it.\n     {type(e).__name__}: {e}")
    return _api_text(system, user, answer_tokens)


def executor_name() -> str:
    """What this host will use — printed first, so a run that costs money is
    legible before it starts."""
    return f"claude -p ({AGENT_MODEL or 'default model'}, subscription)" if have_agent() \
        else f"openrouter ({OPENROUTER_MODEL}, PAID)"


# ── THE VOICE CANON — one owner for every pass that writes target language aloud ──
VOICE_CANON_FILES = ("protocol/persona.md", "protocol/user.md", "protocol/dialect.md")


def voice_canon() -> str:
    """Who the tutor is, the learner's standing facts, and the spoken-register
    law — for EVERY pass that can emit target language a voice will speak, not
    just the studio: the knock memos, tapes and sheets carry most of the daily ear
    contact, and a lane without the dialect law writes the book register.

    LOUD ON ABSENCE: a half-canon would put every lane back on the book register
    with every instrument green."""
    parts = []
    for rel in VOICE_CANON_FILES:
        p = BASE / rel
        if not p.exists():
            raise FileNotFoundError(
                f"voice canon missing: {rel} — every spoken-language lane reads it; "
                f"refusing to generate speech without the register law")
        parts.append(p.read_text(encoding="utf-8").strip())
    return "\n\n---\n\n".join(parts)
