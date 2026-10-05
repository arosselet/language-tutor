# Sollu — Claude Code context

**Read `AGENTS.md` in this directory now** — it is the canonical router (setup vs live,
the two hats, the skill library) and it is host-neutral. This file adds only what is
specific to Claude Code.

- **Uninitialized** (no `config/tutor.json`) — `/setup`, or say "set up my tutor".
- **The tutor** — `/tutor` (setup may rename it to the tutor's name), or read
  `.claude/skills/tutor/SKILL.md`.
- **Studio** — `python scripts/run_studio.py` is the default dispatch;
  `.claude/agents/studio.md` is the subagent fallback when it exits non-zero.
- **Engineering playbooks** are slash commands as well as files: `/orient`, `/debug`,
  `/validate`, `/extend`, `/verify`, `/recalibrate`.
