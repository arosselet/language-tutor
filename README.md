# Language Tutor — a personal coach your agent builds around you

A template for bootstrapping a **persistent, stateful language coach** for any
language — powered by whatever coding agent you already use (Claude Code,
Gemini CLI, …). Clone it, say *"set up my tutor"*, answer a ten-minute
interview, and the agent synthesizes the rest: a tutor persona native to your
target culture, a language charter for *your* dialect, a seed curriculum of
high-frequency glue words, a podcast pipeline in native voices, and — if you
want it — a phone loop where the tutor reaches you first and grades the reply
you type into the notification.

Think of it as **agent-elaborated infrastructure-as-code**: the repo ships a
language-agnostic engine plus synthesis templates; the setup agent elaborates
them into one specific tutor for one specific learner. The same template
elaborates into many shapes — a Coimbatore-Tamil elder brother for an engineer
married into a Tamil family, a Mexican-Spanish neighborhood friend for a
heritage speaker, a Kansai-Japanese sempai for an exam sprint.

**Hear it first (6 min):** [`welcome.mp3`](published_audio/welcome.mp3) — two
hosts and four languages explain what this is, what to expect, and why it isn't
another app you'll quietly abandon. Transcript:
[`content/scripts/welcome.md`](content/scripts/welcome.md).
<!-- Inline player: attach the welcome video (this audio + album art, see the
     script header) through the GitHub web editor and put the resulting
     user-attachments URL here on its own line — GitHub renders it as a player. -->

**The worked example:** this template was extracted from
[tamil-tutor](https://github.com/arosselet/tamil-tutor), a real system in daily
use for months. `docs/WORKED_EXAMPLE.md` distills how each template elaborated
there; `docs/DECISIONS.md` seeds the lessons it learned the hard way. This
snapshot elaborates tamil-tutor at tag `template-v2-source`; the reference
implementation moves ahead of it, and the template re-syncs by wholesale
re-extraction at stable milestones — not per-fix backports.

## Quick start

```
git clone https://github.com/arosselet/language-tutor my-tutor
cd my-tutor
# open your agent here (claude, gemini, …) and say:
#   "set up my tutor"        (or run /setup on Claude Code)
```

Prerequisites: Python 3.10+, an LLM coding agent. Audio needs a TTS provider
(edge-tts is free and keyless; Google Cloud TTS is nicer). The optional phone
loop needs a GitHub repo with Actions and any webhook-capable notifier
(`docs/phone_loop.md`).

## The pedagogy (why this isn't a flashcard app)

The system tracks one honest number — the **viability floor**: of everything
you *recognize*, how much can you actually **fire cold** (produce unaided, from
a situation, no warm-up)? Everything serves moving that number:

- **Recognition plateaus; production breaks through.** Pure comprehensible
  input builds a big passive vocabulary, then stalls. The engine is *forced
  cold output*: a situation in your native language in, the target language
  out. Narrow and deepen before widening.
- **Engines, not word lists.** High-utility verbs are taught as generative
  patterns (tense matrix, person toggle) and tested by demanding a *novel*
  instance. Metered separately as **engines online**.
- **Glue over vocabulary.** Verbs, connectors, pronouns, particles — the ~80%
  of spoken connectivity. Know the glue and the environment turns from noise
  into input.
- **Register-first, ruthlessly.** The dialect people actually speak; textbook
  and literary registers are ignored entirely.
- **Assessment is invisible; correction is a recast.** No quizzes, no grammar
  terminology. The tutor says it the natural way, moves on, and quietly
  updates state.
- **Momentum over accountability.** Contact time beats completion; one rep
  beats zero; no streaks, no guilt. The coach reaches first — and backs off
  when you say you're busy, because that's a real answer.
- **The only narrative is yours.** Scenes are disposable one-use pegs; the
  story with real stakes is your arc toward the thing mastery climaxes into —
  a reveal, a trip, an exam. Climax = mastery.

## One brain, many surfaces

Every mode reads and writes the same `progress/` state, so a word strained in
chat is what the next podcast soaks, and a word soaked in audio is what the
next chat forces cold:

- **The daily session** (~10–15 min chat) — one living scene, cold fires as
  moves inside it; opens on the running story, never "what do you want to do
  today?"
- **The studio** — a three-role production crew (Director → Architect →
  Producer) the tutor commissions end-to-end: dual-voice podcast episodes in
  native TTS voices, published to an RSS feed your podcast app subscribes to.
- **The drill track** — hands-free spoken volleys (cue → silence → answer,
  twice) for the car and the kitchen.
- **The knock loop** — the tutor decides, inside hard anti-pester rails,
  whether/when/how to reach your phone: a text micro-dose, a 60–90s audio memo
  in its one pinned voice, a challenge, a multi-item volley blitz, an
  overheard eavesdrop tape (ear-training), or grace. Type a reply straight
  into the notification and a judge grades it — text the knock *showed* you
  caps at "hinted"; only unaided production fires cold (with a graduation
  lane so daily-knocked words can still escape the cap across days).
- **Field missions** — one line assigned for live deployment tonight,
  debriefed tomorrow. The strongest cold-fire evidence there is.
- **Deck sprints** — a real deadline (trip, wedding, exam) gets a finite,
  informant-vetted deck burned down against the date.

## The system design

- **LLM is the writer, Python is the brain.** State writes, target selection,
  spaced repetition, variety enforcement, outreach rails, and verdict caps are
  deterministic code (`scripts/`); the LLM supplies voice, meaning, and craft.
- **Two halves, one interface.** Conversation (the tutor) and production (the
  studio) meet at exactly one contract — the *soak-order* — so neither can
  colonize the other.
- **Everything language-specific is data.** One config file
  (`config/tutor.json`) + four synthesized protocol files are the whole
  language pack; the engine never hardcodes a language fact.
  `docs/CUSTOMIZATION.md` maps every dial.

## Repository map

```
SETUP.md              → The agent-led bootstrap protocol (start here)
config/               → tutor.json — the one config surface (synthesized at setup)
protocol/             → The pedagogy: constitution, daily session, session tools, diagnosis
                        + synthesized: persona, language charter, studio cast & dialect
protocol/studio/      → The production crew: director, architect, producer
curriculum/           → word_pool.json (seed glue words) + optional sprint decks
progress/             → The learner's brain: lexicon, continuity, logs (Python-owned)
scripts/              → The engine: state, ticket, render, drills, knock, judge, queue, smoke test
docs/                 → WORKED_EXAMPLE, CUSTOMIZATION, DECISIONS, PROTOCOL_MAP, phone_loop
.github/workflows/    → The ticks: knock decisions, push-queue drain, reply judging, smoke test
.claude/ + .gemini/   → Thin per-agent shells (/setup, /tutor, /studio)
```

## After setup

- **`/tutor`** (or just chat) — the daily session. The tutor drives.
- *"Show my status"* — the dashboard (`show_status.py`).
- *"Make me an episode"* — the tutor commissions the studio end-to-end.
- *"This isn't working"* — logged to the feedback ledger; a periodic diagnosis
  pass turns *reproduced* patterns into one small change (usually a dial,
  sometimes a deletion, rarely a proposal).
- Phone sessions: the repo syncs via GitHub, so the tutor runs from
  [claude.ai/code](https://claude.ai/code) on your phone with full state.

Publishing note: the podcast feed and lock-screen audio serve files off your
repo's `main` — that requires a **public** repo (and your progress files are
part of it). Keep the repo private and you keep everything except remotely
served audio.

---

*Contact time > completion. One rep is better than zero.*
