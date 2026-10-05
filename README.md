# Sollu — a personal coach your agent builds around you

[![Smoke Test](https://github.com/arosselet/language-tutor/actions/workflows/smoke.yml/badge.svg)](https://github.com/arosselet/language-tutor/actions/workflows/smoke.yml)

> ### Status: v6 — a fresh extraction, 2026-10-05
>
> Sollu is extracted from a working system — [tamil-tutor](https://github.com/arosselet/tamil-tutor),
> which one person uses every day. That is the template's whole value and also
> its catch: **the extraction is only as mature as the day it was taken.**
>
> This is v6, re-derived from tamil-tutor at `template-v6-source` rather than
> patched forward (`docs/LINEAGE.md`; the July snapshot is tagged `template-v5`).
> The smoke suite holds the template to its laws on two worked packs — Tamil, a
> distinct script, and Spanish, which shares English's — and on a blank clone.
> What it has not had yet is a cold setup by someone other than its author; treat
> the setup interview as the least-travelled road in the repo.
>
> **Nothing here is promised to anyone and nobody is waiting on it — MIT, you get
> what you pay for.** Read it as a design study you can run, not a maintained
> dependency.

A template for bootstrapping a **persistent, stateful language coach** for any
language — powered by the coding agent you already use (tested on Claude Code; the
protocol is plain markdown any agent can read). Clone it, say *"set up my tutor"*, answer a ten-minute
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

<video src="https://github.com/user-attachments/assets/462ad0bd-8ec5-4d3e-934f-3329c38e7554" controls width="360" height="360"></video>

Audio: [`welcome.mp3`](published_audio/welcome.mp3) · transcript:
[`content/scripts/welcome.md`](content/scripts/welcome.md).

**The name:** *Sollu* (சொல்லு) is spoken Tamil for **"say it!"** — the
one-word imperative the whole system is built around. It's what the reference
tutor — an elder brother — says when he hands you a situation and wants the
line back, and the name keeps the template's origin language as its star. The form is itself a first lesson in register:
சொல்லு is how an elder speaks *down* the table, and said *up* the table it
takes the respect ending — சொல்லுங்க (*sollunga*). That ending is doing live
work: it signals where you stand with the person you're facing. (Other endings
have worn smooth — சாப்பிடுங்க சாப்பிடுங்க, "eat, eat!", urges everyone at the
table alike.) Which endings carry meaning and which are just how the word sounds
now is exactly the kind of thing the tutor derives for your language and teaches.

<!-- Tamil here must never START a run with ப, வ, or a Tamil digit: Ubuntu's
default Noto Grantha font claims exactly those codepoints, and Chrome picks
fallback per run by its FIRST character — such runs render as tofu for any
Ubuntu+Chrome visitor. Evidence: tamil-tutor docs/DECISIONS.md (2026-07-19). -->

**The worked example:** this template was extracted from
[tamil-tutor](https://github.com/arosselet/tamil-tutor), a real system in daily
use for months. `docs/WORKED_EXAMPLE.md` shows how each template elaborated
there; `docs/DECISIONS.md` seeds the lessons it learned the hard way, each with
its evidence. The template re-syncs by wholesale re-extraction at stable
milestones — never per-fix backports. The synthesis has also run cold beyond
its origin: a second tutor (Dutch, Netherlands colloquial) was elaborated from a
fresh interview in one sitting, both culture-dependent rules deriving correctly
— *flipped* for the new language, not copied.

## Quick start

```
git clone https://github.com/arosselet/language-tutor my-tutor
cd my-tutor
# open your agent here (claude, …) and say:
#   "set up my tutor"        (or run /setup on Claude Code)
```

Prerequisites: Python 3.10+, an LLM coding agent. Audio needs a TTS provider
(edge-tts is free and keyless; Google Cloud TTS is nicer). The optional phone
loop needs a GitHub repo with Actions and any webhook-capable notifier
(`docs/phone_loop.md`).

## The pedagogy (why this isn't a flashcard app)

The goal is **following the room, and then joining it**: whole exchanges at
ordinary native speed, about the things the learner's people actually talk
about. Everything else serves that.

- **Comprehension leads; production is the probe.** A lesson makes an exchange
  understandable — the blockage unpacked, the example changed — and invites a few
  useful responses once meaning is clear. A listening lesson can stand on its
  own. No daily output quota; no score gates the ear.
- **Stories teach; lists check.** New words arrive inside a scene, a piece of
  lore, a reason to care — one open-handed **teach beat** before anything may
  quiz them. A list is for finding out what is known, never for teaching it.
- **The ledger is honest.** Every fact about the learner is an observation with
  a channel and a sense: heard is not read, delivered is not attended, attended
  is not known, and what the learner *says* they know never votes. The picture
  is checked by asking — the sweep — because every lesson is planned off it.
- **Register-first, ruthlessly.** The dialect people actually speak, in the
  register the learner's table uses; textbook forms are rewritten before any
  voice says them.
- **A world, not homework.** A fictional household (or office, or club) recurs
  month to month with soap-sized stakes, so the ear tracks the same people
  across hundreds of lines. It is never a portrait of the learner's real people.
- **Momentum over accountability.** Contact time beats completion; a partial
  session counts; a missed day is nothing. No streaks, no numbers recited, no
  guilt. A fade is a signal about the material, and the tutor asks what is
  grating — once.
- **The only narrative is yours.** The story with real stakes is the learner's
  arc toward the thing mastery pays off in — a table, a trip, a wedding, an exam
  — and, if it has a date, a timeline of phases set at setup for that date.

## One brain, many surfaces

Every mode reads and writes the same `progress/` state, so a word strained in
chat is what the next tape soaks, and a word heard on a tape is what the next
chat unpacks:

- **The daily session** (~15 min chat) — opens by *giving* (the running story,
  coffee-and-lore, a payoff), then makes one exchange understandable and closes
  by handing the studio a soak-order.
- **The studio** — a three-role production crew (Director → Architect →
  Producer) that turns the soak-order and the month's arc into a two-voice
  episode in native TTS voices, published to an RSS feed your podcast app
  subscribes to. *(audio module)*
- **Rotation, soak and drill tapes** — one press of play: a cadence of
  movements, passive repetition for an ear on autopilot, or hands-free spoken
  volleys for the car. *(audio module)*
- **The knock loop** — the tutor decides, inside hard anti-pester rails,
  whether, when and how to reach your phone: a text, a voice memo, an overheard
  tape and its payoff, a mission, or silence. Reply into the notification and a
  judge grades it; text the knock *showed* you caps at "hinted". *(phone module)*
- **The timeline** — phases between today and the stake's date, each deciding
  which register leads, how many voices a tape carries and whether new words
  still enter. *(timeline module)*

## The system design

- **LLM is the writer, Python is the brain.** State writes, target selection,
  spaced repetition, variety enforcement, outreach rails, and verdict caps are
  deterministic code (`scripts/`); the LLM supplies voice, meaning, and craft.
- **Two halves, one interface.** Conversation (the tutor) and production (the
  studio) meet at exactly one contract — the *soak-order* — so neither can
  colonize the other.
- **Everything learner- or language-specific is data.** One config file
  (`config/tutor.json`) plus the synthesized prose slots (persona, learner,
  stake, contract, language, dialect, exemplars, the world) are the whole port
  surface; a smoke-suite law fails the build if a learner name, a config value
  or a target-script character appears in the mechanism.
  `docs/CUSTOMIZATION.md` maps every dial, `docs/PROTOCOL_MAP.md` every part.

## Repository map

```
SETUP.md              → The agent-led bootstrap protocol (start here)
AGENTS.md             → The router: no config → setup guide; config → tutor or @build
config/               → tutor.json (written at setup) + examples/ (Tamil, Spanish)
protocol/             → The law: constitution, daily session, diagnosis, toolbelt,
                        commissioning, audio channels — plus *.md.template slots
                        the setup agent synthesizes (persona, user, stake, …)
protocol/studio/      → The production crew: studio, director, architect, producer, hosts
content/              → world.md (the fictional world canon) + episode scripts
curriculum/           → word_pool.json (the seed pool, synthesized at setup)
progress/             → The learner's ledger and continuity (Python-owned)
scripts/              → The engine; pack.py is the only reader of config
scripts/smoke/        → The smoke suite: both example packs + a blank clone
docs/                 → CUSTOMIZATION, WORKED_EXAMPLE, PROTOCOL_MAP, DECISIONS,
                        phone_loop, LINEAGE, SPEC_v6
.github/workflows/    → tutor.yml (the ticks; cron ships commented out) + smoke.yml
.claude/              → Thin shells: /setup, /tutor, the studio subagent, and the
                        @build playbooks /orient, /debug, /validate, /extend,
                        /verify, /recalibrate
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
