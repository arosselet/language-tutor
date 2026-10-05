---
name: orient
description: First-session onboarding for @build work on this repo — what the system is, the two hats, the reading order, and the glossary. Use when starting fresh engineering work here, onboarding a new model or engineer, or asking "where does X live?"
---

# Orient — what this system is

A persistent, stateful language tutor for one learner. The **tutor** (a persona the setup
agent synthesized, `protocol/persona.md`) runs a daily comprehension-led session. The
**studio** produces audio episodes from the session's soak-order. Between sessions,
optional phone lanes reach the learner and judge replies (`docs/phone_loop.md`). Python
owns every state write, and every evidence field is the fold of
`progress/observations.json`.

Is there no `config/tutor.json`? Then the repo is not set up, and the only job is
`SETUP.md`.

## The two hats

- **The tutor (default)** runs the lesson through `.claude/skills/tutor/SKILL.md`, which
  setup renames after the persona. The tutor never loads `docs/`.
- **`@build`** works on the machine. It is invoked by `@build` in the message, edits the
  machine and never runs the lesson.

## @build reading order

Stop at the first doc that closes your question.

| # | File | Why |
|---|---|---|
| 1 | `docs/DECISIONS.md` | Settled decisions. Read before any structural change |
| 2 | `docs/PROTOCOL_MAP.md` | The only map: halves, state, the stack, modules |
| 3 | `docs/CUSTOMIZATION.md` | Every dial and its owner; the port surface |
| 4 | `protocol/constitution.md` | The law. Read before editing any `protocol/` file |
| 5 | `docs/feature_inbox.md` | Parked itches. Check before acting on an idea |

For Python, read the script you will change and the `scripts/smoke/cases_*.py` file that
covers it.

## Sibling skills

| Task | Skill |
|---|---|
| Diagnose a failure | `/debug` |
| Routine health check | `/validate` |
| Make a change | `/extend` |
| Prove a change works | `/verify` |
| Pedagogy feels wrong | `/recalibrate` |

Jargon is in `references/glossary.md`.
