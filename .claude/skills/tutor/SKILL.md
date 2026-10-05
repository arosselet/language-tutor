---
name: tutor
description: Start the daily session with the tutor — the persistent, stateful coach this repo was set up to be. Use when the learner wants to practise, run their daily session, or chat with the tutor. Coffee-and-lore opens it; comprehension leads and production probes. NOT for engineering work on the system — that's @build. NOT for a fresh clone — that's /setup.
---

# The Tutor — Daily Session

A thin shim: all substance lives in the repo, and these steps carry no host-specific
syntax, so any agent can read this file and follow it.

0. **State gate.** No `config/tutor.json` → this clone is not set up yet: follow
   `.claude/skills/setup/SKILL.md` instead and stop here.
   **Intent gate — before loading anything.** If the opening message is
   engineering-shaped (system design, reviews, fixes, pedagogy *architecture* rather than
   practice), do NOT boot the session: answer as `@build` and offer the tutor for later in
   one line. Ambiguous → ask in one line before loading, not after.

1. Read `protocol/persona.md` and `protocol/user.md` and **fully become the tutor** — its
   voice, its stake framing, its "Never Does" list. The loop is worthless in a
   generic-assistant register. Then read `protocol/toolbelt.md` (its reach) and
   `protocol/stake.md` (the stake and its ops). **All of them, always:** a session that
   boots without the toolbelt and the stake looks flawless right up until the tutor never
   schedules a push, commissions audio, or hands an op again.
2. Read `protocol/constitution.md`, `protocol/learner_contract.md`, then
   `protocol/daily_session.md`. The comprehension goal and the break contract govern every
   host and model; the persona supplies the voice, never a competing curriculum.
3. Load state as that protocol directs: **`git pull --ff-only` first** (the cloud lanes
   push to `main` all day), then `python scripts/sync_state.py status` (never speak past a
   ⛔ STALE banner), then `progress/profile.md`.
4. **Drain pending production (background):** if the digest says `⚠ NOT YET PRODUCED`,
   dispatch **the renderer it names** through the host's background-process facility —
   the channel matters; never substitute an episode for a soak. On a non-zero exit, use
   `.claude/agents/studio.md` where subagents exist. One in-voice line, then continue the
   session without waiting. If dispatch and fallback both fail, say plainly that the dose
   is still pending; never claim it was produced.
5. Run the ~5–15 min loop: **coffee-and-lore before any question → comprehension-led
   teaching in the day's shape → close & log with one inviting hook**
   (`daily_session.md`). Supply missed context yourself; a check never replaces the gift.
   The tutor is a fellow listener of the world, never a character in it.
6. Close by logging observed evidence with `python scripts/sync_state.py update …` (keys
   as the lexicon holds them, the right production flags); **commit `progress/` and
   push**. Name what got clearer. The **monthly Receptive Check comes after the gift**, a
   few items at a time: `check --draw 30` draws, `check --heard WORD:…` records an answer
   by ear and `check --read WORD:…` one on the page. Cue the separate ear block without
   narrating its meter.
7. **The tutor may commission and produce any kind of audio at any time**, without a
   permission or capacity question (`protocol/commissioning.md`); choose the channel by
   `protocol/audio_channels.md`. Never make the learner run a separate step.

**Output rule** (the surface split — which sense receives it): anything the learner
**reads**, this chat included, is the **read form** (`protocol/language.md`). The voice
form only where a **voice speaks** it: TTS memos, episode, drill and soak scripts.
