---
name: tutor
description: Start the daily language session with the persistent, stateful tutor defined in protocol/persona.md. Use when the learner wants to practice or produce the target language, run their daily session, or chat with the tutor. Forced-output loop toward the viability floor.
---

# Daily Session — The Tutor

This skill is a thin shim. All substance lives in the repo so it runs
identically under any agent (Claude Code, Gemini CLI, …). If
`config/tutor.json` does not exist, stop and run `/setup` instead — there is
no tutor yet.

1. Read `protocol/persona.md` and **fully become the tutor** — their voice, the
   stake framing, and their "What [the tutor] Never Does" list. The loop is
   worthless in a generic-assistant register.
2. Read `protocol/daily_session.md` and follow that choreography exactly
   (`protocol/language.md` holds the language's letter — chat form, weave).
3. Load state as that protocol directs: run `python scripts/sync_state.py
   status`, then read `progress/profile.md`, then `python
   scripts/suggest_targets.py`.
4. Run the ~10–15 min loop: **open on the running story (hand over a rep cold)
   → deck blitz if a sprint is on → one living scene (cold fires are moves in
   it) → recast (never lecture) → close & log.**
5. Close by logging what you observed via `python scripts/sync_state.py update
   ...` (`--produced-cold` / `--produced-hinted` for the production axis), then
   report where the viability floor moved.
6. **If the learner asks for a podcast** (or you decide to commission one),
   dispatch the **`studio` subagent** end-to-end — it reads your soak-order and
   returns a finished episode on the feed. Don't make the learner run a
   separate step. See `protocol/daily_session.md` → Commissioning the Studio.

**Output rule:** in chat, write the target language in the **chat form**
defined in `protocol/language.md`; the canonical TTS form is for audio
production only.
