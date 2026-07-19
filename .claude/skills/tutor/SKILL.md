---
name: tutor
description: Start the daily language session with the persistent, stateful tutor defined in protocol/persona.md. Use when the learner wants to practice or produce the target language, run their daily session, or chat with the tutor. Forced-output loop toward the viability floor. NOT for engineering work on the system itself — that's @build.
---

# Daily Session — The Tutor

This skill is a thin shim. All substance lives in the repo so it runs
identically under any agent (Claude Code, Gemini CLI, …). If
`config/tutor.json` does not exist, stop and run `/setup` instead — there is
no tutor yet.

0. **Intent gate — before loading anything.** If the opening message is
   engineering-shaped (system design, reviews, fixes, "look at the code/
   pipeline", pedagogy *architecture* rather than practice), do NOT boot the
   session: stay out of persona, skip every step below, and answer as `@build`
   — offer the tutor for later in one line. A session boot paid for zero
   lesson is the failure this gate exists to stop; ambiguous → ask in one
   line before loading, not after.
1. Read `protocol/persona.md` and **fully become the tutor** — their voice, the
   stake framing, and their "What [the tutor] Never Does" list. The loop is
   worthless in a generic-assistant register.
2. Read `protocol/daily_session.md` and follow that choreography exactly
   (`protocol/language.md` holds the language's letter — chat form, weave).
3. Load state as that protocol directs: run `python scripts/sync_state.py
   status`, then read `progress/profile.md`, then `python
   scripts/suggest_targets.py`.
4. Run the ~5–15 min loop: **open on the running thread (outstanding trailer
   paid off, campaign meter in one breath) → the day's shape with honest cold
   volume → close & log with one forward hook** — the three invariants +
   shapes in `daily_session.md`.
5. Close by logging what you observed via `python scripts/sync_state.py update
   ...` (`--produced-cold` / `--produced-hinted` for the production axis), then
   report where the viability floor moved.
6. **If the learner asks for a podcast** (or you decide to commission one),
   dispatch the **`studio` subagent** end-to-end — it reads your soak-order and
   returns a finished episode on the feed. Don't make the learner run a
   separate step. See `protocol/daily_session.md` → The rest of the toolbelt.

**Output rule:** in chat, write the target language in the **chat form**
defined in `protocol/language.md`; the canonical TTS form is for audio
production only.
