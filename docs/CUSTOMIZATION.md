# Customization — every dial, and where it lives

A tutor is this engine plus two things the setup agent writes: **`config/tutor.json`**
(the scalars) and the **prose slots** (the files listed below). Together they are the
whole port surface. Nothing in `scripts/` may hold a learner's or tutor's name, the
language's name, a target-script character, or a config literal (voice IDs, the feed's
title and repo, the writer model), and only `scripts/pack.py` may read the config. The
smoke suite (`cases_laws`) fails a mechanism line that does either.

Two worked examples, both kept valid by the smoke suite:

- `config/examples/tamil.json`: a distinct script, a dated stake, every module on.
- `config/examples/spanish.json`: a shared script, no date, the phone loop off.

Validate any config with `python scripts/pack.py check config/tutor.json`. Unknown keys
are errors, so a typo cannot silently do nothing.

## The prose slots

Each is synthesized at setup from the interview, from a `.template` that marks which
sections are **(fixed)** and which are **(synthesize)**.

| File | What it holds |
|---|---|
| `protocol/persona.md` | Who the tutor is: voice, history, the masks they wear |
| `protocol/user.md` | Standing facts about the learner that no generator may contradict |
| `protocol/stake.md` | What mastery climaxes into, and the informant policy (who the native resource is, never an examiner) |
| `protocol/learner_contract.md` | The daily deal: session anchor, ear block, what the learner owes back |
| `protocol/language.md` | Target register, the Weave and Modality letters, the register ladder, lore veins |
| `protocol/dialect.md` | The variety's spoken grammar and its register default |
| `protocol/exemplars.md` | A few contrasting days that worked, read as a range to land outside of |
| `content/world.md` | The recurring cast, each with a pinned voice and a target-form name, approved by the learner |
| `curriculum/word_pool.json` | 150–250 spoken-form glue entries, tagged with registers |

## `config/tutor.json`

### `learner` and `tutor` (required)

| Key | Meaning |
|---|---|
| `learner.name` | How every prompt names the learner. Prompts use the name, never a pronoun |
| `learner.pronouns` | Asked, never inferred from a name. Setup writes them into the prose slots (`user.md`, `persona.md`); no code reads them |
| `learner.native_language` | The language the weave scaffolds in; also the gloss language |
| `tutor.name` | The persona's name: prompts, push titles, the feed's default title |
| `tutor.pronouns`, `tutor.relationship` | The persona's identity in one line each, for setup to write into `persona.md`; no code reads them |

The learner's timezone is not here. It lives in `progress/learner.json`, so it follows them
when they travel.

### `language` (required)

| Key | Meaning | Null / absent |
|---|---|---|
| `name`, `variety` | "Tamil", "Coimbatore (Kongu) colloquial" | required |
| `audio_form` | Prompt fragment: how target language is written for a voice to speak | required |
| `chat_form` | Prompt fragment: how target language appears on a surface the learner reads | required |
| `weave_rule` | Prompt fragment: what the native language carries and what the target carries | required |
| `script_regex` | A regex matching ONE target-script character | **shared script.** Target is declared, not detected (below) |
| `read_rewrite` | The read form differs from the voice form, so read surfaces get the rewrite lane | `false`: the rewrite is the identity. Needs `script_regex` |
| `stem_tail` | What inflection replaces at a word's end: a regex or a suffix list | verbatim matching only |
| `host_tail` | Narrower than `stem_tail`: what a word drops inside a longer phrase | verbatim |
| `tokenization` | `spaces` or `characters` (Chinese, Japanese, Thai) | `spaces` |
| `direction` | `ltr` or `rtl`. **Reserved:** validated, but no renderer reads it yet. Record it so the first RTL port has its slot | `ltr` |
| `referent_nouns` | Kinship/person nouns a tape may name its subject with | no referent check |

### `examples` (optional, at most 8)

One line each in the target language, spliced into prompts that would otherwise need a
worked example. They show the target *form*; they are not past sessions used as models.
If a prompt seems to need a ninth, it is carrying language law, which belongs in
`language.md`.

| Slot | Shape | Tamil | Spanish |
|---|---|---|---|
| `repair_line` | what the learner says instead of an answer | புரியல, மெதுவா சொல்லுங்க | ¿Mande? Más despacio, porfa |
| `addressed_question` | a question fired at them, read form, plus a frame | saapteengala? — answer her | ¿ya comiste? — answer her |
| `typed_spelling` | a typed spelling and what it counts as | "poren" IS போறேன் | "como estas" IS cómo estás |
| `substitution` | a coherent substitute and what it stood in for | "puriyala" for "enna sonneenga?" | "no entendí" for "¿qué dijiste?" |
| `grammar_slip` | a wrong form a native would flag, with the right one | locative -ல where dative -க்கு is needed | ser where estar is needed |
| `pattern_thread` | a soak thread label | the -ணும் tail — the things you have to do | the -ando tail — what's happening right now |
| `contrast_title` | a soak title naming a contrast | வா vs போ · direction only | ser vs estar · what lasts vs what's now |

An empty slot drops the example from its prompt rather than leaving a hole.

### `tts`, `feed`, `rails`, `writer`

| Key | Meaning | Default |
|---|---|---|
| `tts.provider` | `google` or `edge` | `google` |
| `tts.tutor_voice` | The tutor's pinned voice ID. Setup lists real voices before pinning; never guess an ID | none ⇒ audio module off |
| `tts.eavesdrop_voice` | The overheard voice, pinned so the ear tracks one speaker | none ⇒ no eavesdrop modality |
| `tts.pools` | `{chirp|wavenet|edge: {male: [...], female: [...]}}`, the episode casting catalogue | empty |
| `feed.repo` | `owner/name`; the CDN, RSS and site URLs derive from it | none |
| `feed.title`, `feed.summary`, `feed.caption_columns` | The podcast's public identity and caption header | derived from names |
| `rails.waking_start_hour`, `waking_end_hour` | Local hours a reach may land, end exclusive | 8, 21 |
| `rails.max_reaches_per_day`, `min_gap_hours` | How often the phone loop may reach the learner | 3, 3 |
| `writer.model` | The cloud model slug (OpenRouter), chosen to fit the cost ceiling | required |
| `writer.agent_model` | The model `claude -p` runs where a local agent exists | the CLI default |

### `modules`

| Module | Default | What turning it off does |
|---|---|---|
| core | always on | — |
| `audio` | on when `tts.tutor_voice` is set | no tapes, no studio, no feed; workflows skip green |
| `phone` | off until setup wires a receiver | no knocks, replies or push queue |
| `timeline` | on when `timeline.phases` is set | selection uses `default_direction`; no phase markers |

The workflows ask `python scripts/pack.py module <name>` (exit 0 = on); a blank clone
answers off for every module, so its Actions skip green.

### `timeline` (only with a dated stake)

The mechanism is fixed. The phases are data, written from the learner's stake and date,
so a wedding next month and a trip next year each get their own plan.

| Key | Meaning |
|---|---|
| `event` | What the dated stake is called on status surfaces ("trip") |
| `directions` | `{name: {room, leads}}`: who a lean points at, and which word-pool registers lead in it |
| `default_direction` | The lean outside a scheduled year |
| `trails` | Registers that sort last in every direction |
| `phases` | Ordered list (below) |

Each phase is `{name, days, direction, voices, situation_given, intake, marker}`. Exactly
one phase carries `"event": true` and spans the stake's dates (`days: null`). A phase
before the event may set `days: null` to share the run-up evenly with the others; any
remainder goes to the last one, nearest the event. `intake` overrides the new-words dial
when not null. Every `marker` is behavioural and involves a real human: a milestone the
machine can award itself measures the machine. The dates live in
`progress/learner.json.timeline` (`opened`, `event_from`, `event_to`).

## Language-shaped axes (SPEC §4.5) and their slots

| Axis | Slot | Null means |
|---|---|---|
| Telling target from native in a string | `script_regex`, or declared spans | Shared script: audio writers wrap target in `⟦ ⟧` (the pack adds that rule to `AUDIO_FORM`); `unmark()` strips them before TTS or display; undeclared text never counts as target |
| Read form vs voice form | `chat_form`, `audio_form`, `read_rewrite` | The forms are equal and the rewrite lane passes text through |
| The Weave | `weave_rule` + `language.md` | Required; the English-share tripwire reads its spans |
| Word boundaries | `tokenization` | Space-delimited; meters count runs |
| Inflection tolerance | `stem_tail`, `host_tail` | Verbatim matching |
| Register ladder | `language.md` + `timeline.directions` | One rung is valid |
| Referents and kinship | `referent_nouns` + `world.md` names | No referent check |
| Diglossia | `dialect.md` | Always synthesized; its weight depends on the gap |
| Script direction | `direction` (reserved; nothing reads it yet) | `ltr`. An RTL port wires captions and notifications to it and adds the case |
| TTS coverage | `tts.*` | No voices ⇒ the audio module is off |

A port that hits an axis not listed here adds a row and a slot, never a special case.

## Dials outside the config

| Dial | Where | Who turns it |
|---|---|---|
| Pedagogy: input minutes, coverage target, new words per dose, pacing | `progress/profile.md` → Calibration Notes | the tutor, reversibly (`protocol/diagnosis.md`); the learner sets the numbers |
| The month's arc | `progress/profile.md` → The Arc; `content/world.md` §4 | the tutor at the month cut |
| The stake's dates | `learner.json` → `timeline` via `sync_state.py timeline` | setup, then the learner |
| Time zone, quiet-until | `learner.json` | the learner |
| Secrets: `OPENROUTER_API_KEY`, `GCP_SA_KEY`, `PUSH_WEBHOOK_URL` | `.env` locally; GitHub Actions secrets in the cloud | setup Phase 6 |
| The tick schedule | `.github/workflows/tutor.yml` → `schedule:` (ships commented out) | setup Phase 6 |
| The phone receiver | outside the repo; contract in `docs/phone_loop.md` | setup Phase 6 |
| Structural budgets | `scripts/smoke/cases_laws.py` | `@build`, only down, or up with what it could not retire |

How the slots read when filled for a real learner: `docs/WORKED_EXAMPLE.md`. Which part
of the machine owns each concern: `docs/PROTOCOL_MAP.md`.
