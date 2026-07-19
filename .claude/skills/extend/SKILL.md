---
name: extend
description: The change discipline for @build — gates that every modification must pass before code is written. Use when adding, editing, or removing any file, prompt, script, constant, or schema field in this system.
---

# Extend — Change Discipline

Every change to the machine passes these seven gates in order. Each gate has an
explicit stop-condition. Do not jump ahead.

---

## Gate 1 — DECISIONS check

Read `docs/DECISIONS.md` (thin index of conclusions; substance lives in git history —
seeded from the reference implementation, continued by this repo's own owner).

**Stop condition:** the change re-litigates a settled decision. Reopening requires new
evidence taken to the repo's owner — never silent drift. Common reopened traps: adding a
schema field, adding a tracking mechanism, adding a persona.

---

## Gate 2 — Structure-freeze test

After bootstrap the shape is frozen. Full law: `docs/PROTOCOL_MAP.md` → "Structure freeze".

Ask: *does this add a row of data, or change a schema / add a file / add a meter?*

- Row of data (a word, a scene, a memory) → proceed.
- Schema change / new file / new meter → write one line in `docs/feature_inbox.md`
  and **stop**, unless the owner explicitly commissioned it this session.

---

## Gate 3 — Explore before implement

When the owner names a problem, explore its shape and tradeoffs with them before
producing code (`docs/DECISIONS.md` → "explore a problem with the learner before
writing code").

**Stop condition:** they have not yet *explicitly* said yes — named the approach,
approved the tradeoff, or said "do it." Silence, a question, or non-objection is NOT
alignment. Until then: state the real situation sharply; write no code.

**Exploring includes the plumbing.** Read the owning file and the relevant log *before*
proposing any mechanism — never hand the owner a choice between mechanisms the evidence
hasn't earned. A mechanism proposed before diagnosis is a symptom cap, and the better
half of the real fix is often a deletion only reading the file can find.

---

## Gate 4 — What does this replace?

Every addition must earn its place. Before writing any code, state out loud:
*"This replaces / simplifies ___."* (`docs/DECISIONS.md` → "Every addition must earn its place.")

**The word budget.** The protocol's prose surfaces — `persona.md.template`,
`constitution.md`, `daily_session.md`, the outreach/judge mandates — carry word budgets
asserted by `scripts/smoke_test.py` → `PROSE_BUDGETS`; growth past budget is a red run.
Raising a budget is allowed only in the same diff as the growth, and the commit must
name the lines it retired. A file that keeps hitting its ceiling is carrying crud or
doing too many jobs — a split-or-retire signal, never a bump-the-number reflex.

If you cannot name what it replaces, that is the signal to stop.

---

## Gate 5 — Surgical-edit routing

Concerns are separated on purpose. Find the one file that owns the concern you are
touching; edit only that file. (`docs/DECISIONS.md` → "Surgical edits to the relevant file.")

Routing table: `references/routing.md` — concern → exact file.

---

## Gate 6 — Config-routing check (the port surface)

Every language-, learner-, or deployment-specific fact that lives in *code* routes
through **`scripts/config.py` → `config/tutor.json`** — the engine never hardcodes a
language fact. If your change wants to embed one, stop: it goes in config (a key) or
the language pack (`protocol/language.md` / dialect files), never in a `.py`.

The invisible-to-a-.md-swap surfaces to watch:

| Item | Location |
|---|---|
| LLM prompts embedded in Python (knock decision, reply judge, catch judge, drill sheet) | `scripts/morning_knock.py`, `scripts/knock_reply.py`, `scripts/render_drill.py` — language rules enter ONLY via the config fragments (`chat_form`, `audio_form`, `weave_rule`, `register_note`) |
| Canonical-script check | `config/tutor.json` → `language.script_regex` (via `config.is_target`) |
| Pinned TTS voices — the tutor's voice, the eavesdrop voice, episode pools | `config/tutor.json` → `tutor.voice_id`, `tts.eavesdrop_voice`, `tts.voices` |
| CDN/repo URL for knock audio links | `config/tutor.json` → `feed.repo` |

**Cloud-never-renders rule:** cloud CI (`tutor-knock.yml`) renders *only* knock memos
(`morning_knock.py`). Episode TTS runs locally only. Do not add TTS calls to other
workflows.

---

## Gate 7 — Post-change duties

Run these after every non-trivial change to the machinery:

1. **New smoke case for every fixed plumbing bug.** (`scripts/smoke_test.py` docstring:
   "A fixed bug becomes a case here the day it's fixed.") Add a scenario function
   (`sN_...`) following the existing pattern; do not write ad-hoc scripts.

   Safe to run (sandboxed — no secrets, no network, no writes outside tempdir):
   ```
   python scripts/smoke_test.py
   ```

2. **Run `/verify`** — the sibling skill that proves the change end-to-end.

3. **Never hand-edit Python-owned JSON.** State advances through `sync_state.py`;
   `progress/*.json` files are the brain. (`docs/DECISIONS.md` → "LLM is the writer,
   Python is the brain.")

4. **Commit hygiene.** `Subsystem: what changed (context if needed)` — short subject,
   sentence case, parenthetical for date/feedback attribution. No ticket numbers.

5. **CI git identity is `github-actions[bot]`** — never a noreply alias that credits
   a real GitHub user. (`docs/DECISIONS.md`.)

---

## Sibling skills

- `/orient` — what the system is; glossary of project jargon
- `/debug` — symptom → evidence triage; per-subsystem failure playbooks
- `/validate` — routine health checks; safe/mutating command inventory
- `/verify` — proving a change works end-to-end
- `/recalibrate` — pedagogy felt-signals; felt signal → evidence → one move
