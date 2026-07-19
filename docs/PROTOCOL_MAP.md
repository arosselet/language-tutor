# The Protocol Map (`@build` reference)

The architecture of the learning system — **for working *on* the machine**, not
for running it. The tutor and the studio don't load this file; it's the
engineer's map.

Companions: **`docs/DECISIONS.md`** (settled decisions — read before proposing
structural change) and **`docs/CUSTOMIZATION.md`** (which file owns which dial).

## The two halves

The system splits cleanly into **conversation** (the tutor — always-on, small)
and **production** (the studio — isolated, dispatched). They meet at exactly
one interface: the **soak-order**.

```
protocol/
├── persona.md          The tutor — the one persistent voice        [synthesized at setup]
├── language.md         The language charter (weave, modality split) [synthesized at setup]
├── constitution.md     Universal law: philosophy, tactical & canonical rules
├── daily_session.md    The ~5–15 min forced-output loop (invariants + shapes + campaign)
├── diagnosis.md        How feedback becomes change (dial > prune > propose)
└── studio/             The backstage production crew — runs in an isolated context
    ├── studio.md       Orchestrator + the soak-order contract (the front door)
    ├── director.md     Soak-order + ticket → Master Lesson Plan
    ├── architect.md    Lesson Plan → two-voice script
    ├── producer.md     Dialect pass + integrity + .tags.json sidecar
    ├── hosts.md        Cast bible + production-only rules             [synthesized at setup]
    └── dialect.md      The dialect's spoken-register rules            [synthesized at setup]
```

`*.template` files are the synthesis specs the setup agent elaborates
(`SETUP.md`); they stay in the repo for re-derivation.

## The interface: the soak-order

The tutor writes it at Close & Log; the studio consumes it. It is the *only*
thing that crosses between the two halves (`progress/learner.json` →
`soak_order`):

- `payload` — the words chat just strained — or, when a campaign is live, a
  **seed order**: 2–4 unseen deck items the episode teaches first (captions carry
  the load; the render's `seen_in` stamp is what opens them to the drilling channels)
- `scene_seed` — one line of the running story

The tutor hands **meaning**; the studio derives the rest (register / form /
ingredient, callbacks, density) and owns the **craft**.

A second, softer interface: the **campaign block** (`progress/profile.md` → "The
Campaign — This Week") — a learner-initiated one-week unit plan in the tutor's
prose. Sessions, the studio, and the knock digest all read it; only a live
session writes it.

## Invocation shells (thin, per-agent — all substance lives in `protocol/`)

| Entry | Claude | Gemini |
|---|---|---|
| **Setup** (bootstrap) | `.claude/skills/setup/SKILL.md` | `.gemini/commands/setup.toml` |
| **Tutor** (conversation) | `.claude/skills/tutor/SKILL.md` | `.gemini/commands/tutor.toml` |
| **Studio** (production) | `.claude/agents/studio.md` (subagent) | `.gemini/commands/studio.toml` |

The tutor can commission the studio end-to-end mid-session; `/studio` also runs
standalone.

**Engineering playbooks** (`@build`, plain markdown — readable under any agent):
`.claude/skills/orient` (onboarding + glossary) · `debug` (triage + subsystem
playbooks) · `validate` (health checks + safe/mutating inventory) · `extend`
(change-discipline gates) · `verify` (proving changes + flag semantics).

## State (`progress/` — Python-owned, never hand-edit)

| File | Owner | Holds |
|---|---|---|
| `lexicon.json` | `sync_state.py` | Word brain: recognition + production axes, patterns/engines, deck tags + fire/catch direction, viability floor |
| `learner.json` | `sync_state.py` | Continuity: running story (`last_debrief`), `soak_order`, status (no streak — recency from the session log is the honest signal) |
| `episodes.json` | `sync_state.py` / `render_audio.py` | Episode registry |
| `session_log.json` | `sync_state.py` | Append-only momentum log |
| `feedback_log.json` | `sync_state.py feedback` | The ledger the diagnosis pass reads |
| `knock_log.json` | `morning_knock.py` / `knock_reply.py` | Outreach memory: every wake (fire or silence), replies, verdicts |
| `push_queue.json` | `push_queue.py` | Scheduled pushes, fully composed at add-time; drained by CI |
| `profile.md` | the tutor (LLM) | Teacher's notebook — assessment, gaps, calibration dials, sprint priorities |
| `chat.md` | `render_chat.py` | Derived, human-readable phone-loop transcript |

## Python brain (`scripts/`)

`config.py` (the one config surface — every language/learner/deployment
constant) · `sync_state.py` (owns all state writes; `seed-deck` loads curated
decks; live burn-rate on the status line) · `suggest_targets.py` (the ticket +
scene-spec divergence gate) · `generate_callbacks.py` (spaced repetition) ·
`render_audio.py` (TTS + episode registration + RSS) · `render_drill.py`
(spoken production volley from the deck's due list — cue → silence → answer;
read-only on the brain) · `show_status.py` (human dashboard) ·
`morning_knock.py` (agentic outreach: rails gate + the tutor's fire/silence
policy; digest carries the deck-due menu) · `knock_reply.py` (judges phone
replies, moves the production axis) · `push_queue.py` (durable "ping me at X")
· `rebuild_rss.py` · `render_chat.py` · `smoke_test.py` (sandboxed regression
net — run it after any engine change).

The LLM is the writer; Python is the brain. Never hand-edit Python-owned JSON.

## Structure freeze

Once bootstrapped, the shape is **frozen**. The discipline: **add content
freely, change structure rarely.**

- ✅ Content (a word, a scene, an episode, a memory) → always open; *that is the learning.*
- 🛑 Structure (a new file, a schema, a meter, a refactor) → frozen. Route the
  itch to `docs/feature_inbox.md`; don't act on it mid-session.

Test for any change: *does it add a row of data, or change a schema?* Rows are
free; schema changes wait.
