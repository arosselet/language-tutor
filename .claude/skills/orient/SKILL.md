---
name: orient
description: First-session onboarding for this repo — what the system is, the two hats (the tutor vs @build), reading order for @build context, subsystem map, and pointer to the project glossary. Use when starting fresh work on this repo, onboarding a new model or engineer, or asking "where does X live?"
---

# Orient — Language-Tutor System Onboarding

## What This System Is

An n-of-1 language-learning system for one learner. One persistent LLM persona — **the tutor** (name and identity in `protocol/persona.md`) — runs a daily forced-output chat loop: the tutor hands the learner a native-language situation, the learner must produce the target language back. A **studio** pipeline produces podcast episodes that soak exactly what the chat session just strained, closing the recognition-to-production loop. Between sessions, a **knock** system (GitHub Actions cron + `scripts/morning_knock.py`) does agentic phone outreach; the learner types replies that `scripts/knock_reply.py` judges. Scheduled nudges live in `progress/push_queue.json`, drained every 30 minutes by CI. All learner state lives in `progress/` as Python-owned JSON — never hand-edit it.

The design principle is **"LLM is the writer, Python is the brain"** — Python owns every state write. After bootstrap, structure is frozen: content rows are always free; schema changes park in `docs/feature_inbox.md`. Full law lives in `docs/DECISIONS.md` (settled decisions — do not re-litigate) and `docs/PROTOCOL_MAP.md` (the architecture map); read both before any structural work.

If `config/tutor.json` does not exist, this clone is **uninitialized** — the right move is `/setup` (SETUP.md), not engineering.

---

## The Two Hats

### The tutor (default) — run the lesson

No keyword needed. Invoked via `/tutor` (Claude Code) or `.gemini/commands/tutor.toml` (Gemini).

Their identity, loading order, and the session loop are owned by `.claude/skills/tutor/SKILL.md` (which routes to `protocol/persona.md` + `protocol/daily_session.md`) — don't restate them here; read that shim if you need the sequence.

The tutor does **not** load `docs/PROTOCOL_MAP.md`, `docs/DECISIONS.md`, or `SETUP.md`. Those are the engineer's map.

### `@build` — work on the machine

Invoked by typing `@build` in the message. Role: Python developer and system architect. Edits the machine; never runs the lesson.

Files @build loads — see the reading order below.

---

## @build Reading Order

Read these before any structural work. Stop at the first doc that closes your question.

| # | File | Why it matters |
|---|---|---|
| 1 | `docs/DECISIONS.md` | Settled decisions — read before ANY structural change; prevents re-litigating closed questions |
| 2 | `docs/PROTOCOL_MAP.md` | Full architecture: subsystem map, state schema, Python brain inventory, the soak-order contract |
| 3 | `docs/CUSTOMIZATION.md` | Which file owns which dial — the surgical-edit map |
| 4 | `protocol/constitution.md` | The canonical rules the learning system enforces — mandatory before editing any `protocol/` file |
| 5 | `docs/feature_inbox.md` | Where build-itches park during the structure freeze — check before acting on an idea |

For the Python brain: read the script you intend to change, plus `scripts/smoke_test.py` before touching anything that writes state.

---

## Subsystem Map

| Subsystem | Entry File | One-line purpose |
|---|---|---|
| Chat loop (the tutor) | `.claude/skills/tutor/SKILL.md` | Daily forced-output session; commissions studio, queues pushes |
| Studio (audio) | `protocol/studio/studio.md` | Three-pass episode pipeline: Director → Architect → Producer → render |
| Knock (outreach) | `scripts/morning_knock.py` | Agentic phone reach: rails gate + the tutor's fire/silence policy; CI workflow: `.github/workflows/tutor-knock.yml` |
| Push queue | `scripts/push_queue.py` | Durable scheduled pushes, fully composed at add-time; drained every 30 min by CI: `.github/workflows/push-queue.yml` |
| Reply judge | `scripts/knock_reply.py` | Judges typed replies; moves the production axis; triggered by `.github/workflows/log-knock-response.yml` |
| State | `scripts/sync_state.py` | Owns all writes to `progress/`; run `python scripts/sync_state.py status` to inspect safely |
| Setup (bootstrap) | `SETUP.md` + `.claude/skills/setup/SKILL.md` | The agent-led elaboration of this template into one specific tutor |
| CI | `.github/workflows/` | Four workflows: `tutor-knock.yml`, `push-queue.yml`, `log-knock-response.yml`, `smoke.yml` |

---

## Where to Go From Here

**Glossary** — every project-jargon term a newcomer will hit (viability floor, soak-order, engines, the stake, Intercept, Breakdown, scene spec, capped, volley, etc.) with a 1–2 line definition and the file where each is defined: `references/glossary.md`.

**Sibling skills** (procedures, not orientation):

| Task | Skill |
|---|---|
| Diagnose a failure | `/debug` |
| Routine health checks | `/validate` |
| Make a change to the system | `/extend` |
| Prove a change works end-to-end | `/verify` |
