# The Protocol Map (`@build` reference)

The architecture of the system: what each part owns and where it sits. It is for working
**on** the machine. The tutor and the studio never load it.

Companions: `docs/DECISIONS.md` (settled decisions, one line each; read it before
proposing a structural change) and `docs/CUSTOMIZATION.md` (every dial, and the file that
owns it). **This is the only map.** A concern's owner is found here, and if this file is
wrong it gets fixed in the same diff as the code.

## The seam

```
config/tutor.json            the language and learner scalars, read only by scripts/pack.py
protocol/*.md.template        synthesized prose: persona, user, stake, learner_contract,
                              language, dialect, exemplars
content/world.md.template     the world canon
curriculum/word_pool.json.example, progress/*.example, progress/profile.md.template
```

**`config/tutor.json` plus `pack.PROSE_SLOTS` is the whole port surface.** Everything
else is fixed mechanism and fixed law, and neither one names a learner, a tutor, a
language or a target-script character. `cases_laws` enforces this.

## The two halves

**Conversation** (the tutor, always on and small) and **production** (the studio,
isolated and dispatched) meet at exactly one interface: the **soak-order**.

```
protocol/
├── persona.md          the tutor: one persistent voice              (slot)
├── user.md             who the learner is to the world; in the voice canon   (slot)
├── stake.md            the payoff and its ops; session only          (slot)
├── learner_contract.md the learner's half: anchors, the one ask; session only (slot)
├── language.md         weave, modality, inflection, register, lore   (slot)
├── dialect.md          the spoken-register law for every voice line  (slot)
├── exemplars.md        a few contrasting days that worked            (slot)
├── constitution.md     universal law: the goal, tactical and canonical rules
├── toolbelt.md         the tutor's reach; session only, never in the voice canon
├── daily_session.md    the comprehension-led session, and the sweep
├── diagnosis.md        the healing loop: feedback ledger → dial / prune / propose
├── commissioning.md    the tutor's audio authority, and what a dose carries
├── audio_channels.md   which channel carries a dose
└── studio/             the backstage crew, run in an isolated context
    ├── studio.md       orchestrator + the soak-order contract
    ├── director.md     soak-order + ticket → lesson plan
    ├── architect.md    lesson plan → two-voice script
    ├── producer.md     dialect pass + integrity + .tags.json sidecar
    └── hosts.md        voice conventions; the cast itself is content/world.md
```

**The voice canon** is persona + user + dialect (`writer.voice_canon()`). It ships to
every pass that writes or judges a single line. A file no voice lane can act on
(toolbelt, stake, contract) stays out of it, because each extra word is paid for on
every call.

### The interface: the soak-order

The tutor writes it at Close & Log, and the studio or a lane consumes it
(`progress/learner.json` → `soak_order`):

- `payload`: the words the chat just strained, or, when an arc is live, a seed order of
  2–4 unseen items the episode teaches first.
- `scene_seed`: the arc's next beat, read from the canon.
- `channel` / `focus`: which lane it addresses, and what a carousel permutes.

The tutor hands over **meaning**. The studio derives register, form, callbacks and
density, and owns the craft.

A second, softer interface is the **arc block** (`progress/profile.md` → "## The Arc"):
the month's situation in the world, in tutor-owned prose. It names no items, because the
ticket owns those. Only a live session writes it, and exactly one such heading may exist.

## Invocation shells (thin; the substance lives in `protocol/`)

| Entry | File | Note |
|---|---|---|
| Router | `AGENTS.md` (`CLAUDE.md` points to it) | no config → setup guide; config → the two hats |
| Setup | `.claude/skills/setup/SKILL.md` → `SETUP.md` | the phased interview |
| Tutor | `.claude/skills/tutor/SKILL.md` | setup renames it after the persona |
| Studio | `.claude/agents/studio.md` | the subagent fallback; `run_studio.py` is the default dispatch |

**Episode dispatch:** `python scripts/run_studio.py` makes three print-only writer calls
(Director → Architect → Producer). Python persists the artifacts and lints them: the
sidecar schema, the weave-density tripwire, the fourth wall, payload fidelity (verbatim
for chunks, stem-tolerant for words), the voice map and stray writes. `render_audio.py`
owns render, registration and commit. A non-zero exit falls back to the subagent.

## State (`progress/`: Python-owned, never hand-edited)

| File | Owner | Holds |
|---|---|---|
| `observations.json` | `lexicon_view.observe` / `expose` | **The ledger.** Every observation as an event: word, channel, kind (taught / attended / exposed / tested / claimed), axis, result, source. Append-only. `seed` and `self-report` are recorded and never vote. A `taught` on a delivery channel stays pending until an `attended` event or a watched test discharges it |
| `lexicon.json` | static half: `sync_state.py`; evidence half: `lexicon_view.rebuild` | The word brain. Gloss, type, register, direction and pairs_with are curriculum. Recognition, production, reps, exposures, heard_on, last_surfaced, seen_in and taught_on are **the fold of the log**, with one writer |
| `learner.json` | `sync_state.py` | Continuity: `last_debrief`, `soak_order`, `month` (name, dates, the finale's mission; membership and completion are folds), `timeline` (three dates; the phases are derived, never stored), status (no streak) |
| `episodes.json` | `sync_state.py` / `render_audio.py` | The episode registry |
| `session_log.json` | `sync_state.py` | The append-only momentum log |
| `feedback_log.json` | `sync_state.py feedback` | What the diagnosis pass reads |
| `slip_log.json` | `slips.py` | What keeps going wrong, and its closes |
| `knock_log.json` | `morning_knock.py` / `knock_reply.py` | Outreach memory: every wake (fire or silence), reply and verdict |
| `push_queue.json` | `push_queue.py` | Scheduled pushes, composed at add time and drained at the start of every tick |
| `commissions/{pending,claimed,done,failed}/` | `commissions.py` | Commissioned doses, claimed one per tick |
| `profile.md` | the tutor | The teacher's notebook: assessment, the arc block, calibration dials |

## Python brain (`scripts/`)

**Imports point one way, down the stack.** A lower layer never imports a higher one, and
a channel never owns an invariant that more than one channel obeys. `cases_laws` asserts
the direction. Bottom to top:

- **`pack.py`**: the only reader of config. Lanes ask it **questions** (`is_canonical`,
  `has_target`, `target_runs`, `l1_runs`, `stem`, `host_stem`, `needs_read_form`,
  `unmark`, `voice_locale`, `module_on`), never a regex. The answers differ for a
  distinct-script target (`script_regex`) and a shared-script one (declared ⟦ ⟧ spans).
  It imports nothing from the repo.
- **`state_io.py`**: paths, load/save, the local clock, token→key `resolve`, the soak
  payload resolvers, and read-only predicates. It imports only the pack.
- **`observations.py`**: the log's vocabulary and its appender. **`lexicon_view.py`**:
  `derive` (pure fold), `rebuild` (the one writer of evidence), `observe`, `expose` (the
  delivery seam every lane calls), and `divergence` (the honesty check).
- **`world.py`**: reader and one appender for `content/world.md`. It imports only the
  state layer, because a canon that could see progress would start being chosen by
  deficit. `run_studio` refuses a model pass without it and copies the voice pins into
  every script itself.
- **`timeline.py`** (timeline module): the phase schedule between the month and the
  stake's date. A phase decides the lean (which registers lead selection), the ear ramp
  (voices; whether the situation is given) and the intake cap. Only the three dates are
  stored.
- **Selection:** `suggest_targets.py` (the ticket), `generate_callbacks.py` (spaced
  repetition), `slips.py` (the slip ledger), `month.py` (the arc's month),
  `receptive_check.py` (recognition recording). `sync_state.py` sits beside them and
  owns every state write (`seed` loads a curated set; rows arrive untested).
- **Policy** lives with the lane that reads it. The exception is a rail more than one
  channel obeys: `rails.py` (the waking window, daily cap, min gap, `reaches_today`) is
  shared by the knock and the queue.
- **`writer.py`**: model config, the JSON parsers, the read-form rewrite, and **the one
  place that chooses an executor** (a local agent CLI when one is on PATH, otherwise the
  API). `mandates.py` holds the prompt canon and splices the example slots.
- **`publish.py`**: the delivery tail. It covers the rebase net with its union and
  re-render resolvers, `commit_and_push`, the feed refresh, and `push_to_phone`, the one
  chokepoint where quiet hours are enforced. `rebuild_rss.py` and `render_audio.py` (TTS,
  provider-aware) feed it.
- **`memo.py`**: a script in, an mp3 out. It sits below every lane that speaks.
- **The lanes:** `lanes.py` holds what a family shares (`deliver_rendered`: exposure →
  soak stamp → commit → notify). The audio module covers `render_soak`, `render_drill`,
  `render_rotation`, `lesson_audio` and `run_studio`. The phone module covers
  `morning_knock` (agentic outreach), `knock_reply` (judges replies, moves the
  production axis), `knock_message` (the learner talking to the tutor, ungraded),
  `reply_common`, `push_queue`, `render_payoff`, `render_sort` (the Receptive Check as a
  tape) and `commissions`.
- **Read surfaces:** `session_brief.py` (what the tutor loads), `show_status.py` (the
  learner's dashboard), `render_chat.py` (`progress/chat.md`), `audio_titles.py`.

**No lane is a foundation.** If two lanes need the same thing, it moves down a layer.

## Modules

`config.modules` switches four groups (`core` is always on): **audio**, **phone** and
**timeline**. The flags are read at the workflow layer: a module that is off makes its
workflow step skip green (`.github/workflows/tutor.yml` asks `pack.py module <name>`).
The tutor also reads them, so it never commissions a lane that is off. Group membership
and the line budgets live in `scripts/smoke/cases_laws.py`.

## Structure

The ratchet controls structure. The budgets are core ≤ 8k code lines, audio ≤ 4k,
phone ≤ 4k, timeline ≤ 1k, smoke ≤ 5k and fixed protocol prose ≤ 9k words. The
prohibition count can only fall. A new file joins a budget group in the diff that
creates it, and every addition names what it replaces. Rows of data are always free.
