# Sollu v6 — Fresh Extraction Spec

> **Status:** W0–W7 and W8(b) done 2026-10-05 (§10). W8(a), a live cold setup by a new learner, is open.
> **Source:** `tamil-tutor` at `43525f5` (2026-10-05), tagged `template-v6-source`: the
> first commit that carries all three landed §0 seams and the 10-05 pedagogy changes
> (§3 item 11). The census figures below were re-taken at the tag (W0).
> **Replaces:** the v5 tree of this repo, tagged `template-v5` (cut from tamil-tutor
> `template-v5-source`, 2026-07-27). Only `README.md` (with its embedded video),
> `LICENSE`, and the welcome media are kept.
> **First real user:** Andrew's teammate, learning French. The spec settles nothing
> about him; his own setup agent settles his specifics. The spec has to hold for
> **any** language.

---

## 0. Groundwork in tamil-tutor (only what helps Tamil on its own)

Work that improves tamil-tutor today *and* cuts a v6 seam lands in the source first, so
the extraction copies a clean seam instead of inventing one.

| Status | Seam | Benefit to Tamil | v6 slot it becomes |
|---|---|---|---|
| **Landed 2026-10-05** | The surface rule (how speakable and readable Tamil are written) was restated in 9 prompt sites and had drifted three ways on register. It is now `language.VOICE_FORM` / `READ_FORM`, spliced everywhere; `dialect.md` keeps the register default; `s129` fails on a retyped rule | One sentence to change, no more drift | `language.audio_form` / `chat_form` |
| **Landed 2026-10-05** | Stored romanizations (`lexicon.phonetic`) are deleted; keys are script and every surface he reads is generated (`writer.to_phonetic`), including the sort-tape push-back. This removes a false "recently shown" match (substring hits like `om` in "from") | Honest cold credit; less code (state_io 127 → 111) | Nothing to template. The read form is generated, never stored, for any language |
| **Landed 2026-10-05** (`43525f5`, D12) | Eight mechanism files imported raw script tests (`is_tamil`, `TAMIL_RE`, `TAMIL_RUN`, `TAMIL_TAIL_RE`, `strip_pulli`) to answer three different questions, including the ledger's own key lookup (`state_io.resolve`). Lanes now import role-named questions with the same answers: `is_canonical`, `has_target`/`target_runs`, `stem`, and `host_stem` (narrower than `stem` on purpose, for substring host-finding). `s91` fails on a range name in a lane | Each lane names its question; a planted range import goes red | The plug point for *declare, don't detect* (§4.5). Without it, W2 has to redesign these six lanes while it ports them (§4.2) |
| Not worth doing | Renaming `Anna`/`Andrew` identifiers, log strings and the `ANNA_PUSH_WEBHOOK_URL` secret | Churn and an outward-facing secret change for no learning benefit | Mechanical rename at W2 |

---

## 1. What we are building

Sollu is a repo that **an agent elaborates into a personal language tutor.** It isn't an
app you configure. You clone it, say *"set up my tutor"*, and do a short interview. The
setup agent then writes the parts that belong to one learner and one language. The
engine, the pedagogy, and the playbooks stay the same for everyone. This is the idea the
README calls *agent-elaborated infrastructure-as-code*, and v6 keeps it unchanged.

What changes is the source. v5 was cut from a July tamil-tutor. Since then tamil-tutor
has changed its pedagogy, its state model and its prompt architecture. v6 is a **fresh
extraction from tamil-tutor's current form**. It is not a patch on v5 and it is not a
file-by-file port.

**Goals**

1. A new learner gets the **same experience Andrew has today** (Anna, the household, the
   tapes, the knocks, honest assessment), adapted to their language, dialect, life and
   stake.
2. **Lean.** Ship the mechanism without the history. tamil-tutor's code and prose carry
   months of dated reasoning ("2026-08-24, Andrew: …"). That history stays in
   tamil-tutor's git. In the template, a comment states the rule. It doesn't tell the
   story of how the rule came about.
3. **No Andrew and no Tamil in the mechanism.** Every learner fact and every language fact
   has exactly one slot, and the setup agent fills it.

**Non-goals (for v6.0)**

- Making tamil-tutor an *instance* of the template. **Keeping tamil-tutor healthy comes
  first.** It adopts nothing from the template until the template has proven itself
  with a real second learner. Work flows Tamil → template. The only exception is
  groundwork that improves tamil-tutor on its own merits (§0).
- New pedagogy. v6 carries over what tamil-tutor does now. It doesn't add anything.
- Supporting every agent host. The repo stays host-neutral markdown, and Claude Code is
  the only host we test.

---

## 2. What we keep from language-tutor v5

| Keep (the user experience and the idea) | Discard (superseded) |
|---|---|
| `README.md` framing, the Sollu name story, the embedded video, `welcome.mp3` + `welcome_art.jpeg` + `content/scripts/welcome.md` | Every `scripts/*.py`. They are a July architecture with no ledger, state split, writer or voice canon |
| The uninitialized/initialized router: no config means you are the **Setup Guide**, not the tutor | `.gemini/` shells and the `AGENTS.md` symlink, which breaks on a Windows checkout |
| SETUP.md's phased interview → derive → synthesize → init → intake → wire → verify → hand over | The intake sweep's `--recognition comfortable` self-claims. These contradict the current ledger law (§4.4) |
| Prompt fragments as the channel from language to Python. v5 had four (`chat_form`, `audio_form`, `weave_rule`, `register_note`). tamil-tutor converged on two (`READ_FORM`/`VOICE_FORM`, 2026-10-05) and leaves the register default in `dialect.md`. v6 keeps `audio_form`, `chat_form` and `weave_rule` (D13) | `protocol/` prose. It teaches the old *viability floor / forced cold output* thesis that tamil-tutor has since retired |
| The `.template` + **(fixed)/(synthesize)** section convention | v5 smoke suite, `config.py`, and every `docs/` file except as reference material |
| Workflows that **skip cleanly until bootstrapped**, plus cron ticks that ship commented out | |
| `WORKED_EXAMPLE.md` as a quality bar ("match the specificity, never copy") | Its July content. It gets rewritten from October Tamil |
| The two validated derivations: the **Weave Rule** and the **Modality Split**. The Dutch cold run flipped both correctly | |
| `DECISIONS.md` entry: *learner-dependent surfaces are setup-time elaborations* | |

The README also needs edits, which §8 D9 covers: its status banner, its pedagogy section
(still "viability floor"), and its repo map are now false.

---

## 3. What tamil-tutor learned since v5 (why we start fresh)

These are the capabilities v6 must carry. They are also the reason a v5 patch won't do.

1. **Pedagogy pivot.** The old engine was cold-fire production toward a floor. The new
   one is **comprehension-led**: *follow the room, then join it.* Every session opens
   with **coffee-and-lore**, a gift before any question. Production is now a probe. It is
   not a quota.
2. **Honest assessment is enforced in code.** `observations.json` is an append-only
   event ledger. `lexicon.json` evidence fields are a fold of that ledger. Every
   observation records its **medium**, so reading never counts as hearing (`check --heard`
   vs `--read`). Seeds and self-reports are recorded but never vote. `untested` is the
   default rung. The rule is to ask meanings and never let the learner self-mark.
3. **State-layer split:** `state_io` / `observations` / `lexicon_view` / `slips` /
   `session_brief`, with imports pointing one way down the stack.
4. **Writer / executor law** (`writer.py`): `claude -p` runs where a local agent exists,
   and the paid API runs everywhere else. The host decides, not each lane.
5. **Voice canon** (`writer.voice_canon()`): `persona` + `user` + `dialect` are shipped to
   every lane that writes speakable target language. Session-only material
   (`toolbelt`, `heist`, `learner_contract`) is kept out of it so prompts stay small.
6. **The world.** `content/household.md` is a fictional recurring cast with **pinned TTS
   voices**, standing facts, a monthly **arc** and a beat log. `month.py` holds the arc's
   month and `year.py` holds the phase schedule toward a dated anchor (`timeline.py` in v6, D8).
7. **Audio law:** `commissioning.md` (the tutor may make any audio at any time) and
   `audio_channels.md` (capacity routes the format). There are six lanes: soak,
   rotation (with lore movements), drill, episode, `lesson_audio`, plus payoff and sort
   tapes.
8. **Phone loop maturity:** a knock with seven modalities, open-ask and message lanes,
   `rails.py` as the one reach budget, the push queue, the commission router, payoff
   re-cuts, and the receptive check delivered as a tape.
9. **Ratchets:** prose word budgets and code-line budgets, `PROHIBITION_BUDGET` (a coarse
   count of *never / must not / do not / don't* across protocol prose and the LLM
   mandates, so a new prohibition retires an old one), plus `/extend` Gate 4 ("what
   does this replace?").
10. **Learner's half:** `learner_contract.md` holds the daily deal (session anchor +
    separate ear block), the one thing that is asked for, and what the learner owes back.
11. **Measuring is separate from teaching** (2026-10-05). *Stories teach; lists check.*
    A list never teaches, but asking from one is welcome. **The sweep** is infrastructure,
    like the rails: pages of meanings the learner answers and the tutor grades. Gentler
    lessons leave it alone, and only the learner turns it down. Checks draw from every
    `untested` row, taught or not. A right recognition answer proves first contact and
    sets `taught_on`, and a miss lands on `struggled`. A tap reports what the learner
    did and never writes a rung. **`exemplars.md`** gives the tutor and the studio a few
    contrasting days that worked, read as a range to land outside of. It replaces reading
    past scripts as models. Diagnosis prunes a rule before it turns a dial.

---

## 4. The surface map

There are four layers. **L0 pedagogy** and **L1 mechanism** ship as fixed files.
**L2 language pack** and **L3 learner pack** ship as slots, which means templates or
config keys. **Personal/infra** never ships.

### 4.1 `protocol/` (14.7k words today)

| File | Layer | What is Andrew/Tamil in it | v6 fate |
|---|---|---|---|
| `constitution.md` | L0 + L2 + L3 mixed | "By August 2027" goal; "Family Already"; "Dialect: Coimbatore Tamil Only"; **The Wife (Oracle)** role; Noun Shortcut + **Woven Thanglish**; Phonetic Over Script; Tamil examples throughout | **Fixed**, after removing those items: the goal moves to `user.md`, the dialect to `dialect.md`, the Oracle to `stake.md`'s informant policy, and the weave/modality *letter* to `language.md`. Principles stay with neutral wording |
| `daily_session.md` | L1 | Tamil-script example in the `update` command; "cloud Anna"; household | **Fixed**, with names and examples through placeholders |
| `toolbelt.md`, `commissioning.md`, `audio_channels.md`, `diagnosis.md` | L1 | Names; dated Andrew quotes used as justification | **Fixed**. Quotes become plain rules |
| `persona.md` | L2 + L3 | All of it: Anna, Coimbatore, Kongu, elder brother, the masks (mother-in-law, neenga-forms), voice lines | **Template** (synthesize). Keep the v5 fixed/synthesize split, updated to the comprehension charge |
| `user.md` | L3 | All of it: ten years married, "started at year nine" | **Template.** These are standing facts no generator may contradict |
| `heist.md` | L3 | The secret reveal to the wife, field missions, somatic anchors | **Template → `stake.md`.** Op mechanics (anchor = free, mission = assigned and collected, *debrief is contact, never evidence*) stay fixed. Secrecy is optional, kept only if the stake is reveal-shaped |
| `learner_contract.md` | L3 + L0 | The lunch anchor, the separate ear block, "a ratchet might start to hurt" | **Template.** The skeleton is fixed: the floor, no ratchet, what the learner owes back, and *the sweep is infrastructure* (only the learner turns it down). The daily deal is synthesized from the interview |
| `exemplars.md` | L0 rule + L3 content | Every entry: four of Andrew's days (10-04 sweep, 07-28 commission, 07-20 teardown, M77), with his own words. Read by the tutor, the Director and the Architect | **Fixed rule, synthesized content.** The file's frame ships fixed: read as a range, land outside it, keep 4–5 contrasting entries and replace one when it stops being true. A new learner has no days yet, so it ships a short neutral seed that the learner's own days replace (D14) |
| `dialect.md` | L2 | All of it: verb collapse, sandhi, Kongu layer, the neenga default | **Template** (the most-edited pack file after setup) |
| *(new)* `language.md` | L2 | v5 had this as a charter. In tamil-tutor its content is spread across the constitution | **Template.** Target register, Weave letter, Modality letter, register ladder, lore veins |
| `studio/{studio,director,architect,producer}.md` | L1 | Tamil-script examples (producer: 9 lines), "Coimbatore", Thanglish | **Fixed**, with neutral examples and pack references |
| `studio/hosts.md` | L1 + L2 | Analysts Maya/Raj, Coimbatore; "Tamil script only" production rule | **Fixed conventions.** The analyst names move to `world.md`, and "script only" becomes `{audio_form}` |
| `persona.md.example` | — | Old v3-era stub | **Delete** |

### 4.2 `scripts/` (16.8k Python lines + 15.0k smoke lines)

**The language pack today** is `language.py` + `rails.py` constants + `writer.py` models. These are the facts a setup agent writes:

| Fact | Lives today | v6 home |
|---|---|---|
| Script detection `TAMIL_RE` / `TAMIL_RUN` / `TAMIL_TAIL_RE`, `is_tamil`, `strip_pulli` | `language.py` | `config` → `language.script_regex` (nullable) + `language.stem_tail_regex` (nullable). `pack.py` exposes the questions tamil-tutor's lanes already ask: `is_canonical()`, `has_target()`, `target_runs()`, `stem()`, `host_stem()` |
| `REFERENT_NOUNS` (25 Tamil kinship terms) | `language.py` | `config` → `language.referent_nouns` (synthesized) |
| `ANNA_VOICE`, `EAVESDROP_VOICE`; episode voice pools | `language.py`; `render_audio._CHIRP_POOL_*` | `config` → `tts.tutor_voice`, `tts.eavesdrop_voice`, `tts.pools`. Cast pins stay in `world.md` |
| `REPO`, `FEED_TITLE` ("Coimbatore Mappillai"), `FEED_SUMMARY`, `CAPTION_COLUMNS` | `language.py` | `config` → `feed.*` |
| Waking window, `MAX_REACHES_PER_DAY`, `MIN_GAP_HOURS` | `rails.py` | `config` → `rails.*` (learner facts) |
| `MODEL` (cloud), `AGENT_MODEL` (laptop) | `writer.py` | `config` → `writer.*` |
| Timezone | `learner.json` | stays in `learner.json` (it already follows the learner) |

**The prose surface in code.** These are files where a substitution pass won't work and the prose has to be rewritten:

| File | Andrew/Tamil load | v6 approach |
|---|---|---|
| `mandates.py` (644 lines, 17 prompt constants + `SHAPE_CLAUSES`) | "You are Anna… Andrew's phone"; Tamil examples (`poren`, `புரியல`, `saapteengala`); Kongu; "Tamil script"; Thanglish | Neutral mechanism prose with `{tutor}`, `{learner}`, `{chat_form}`, `{audio_form}`, `{weave_rule}`, `{register_note}`, and a small set of **example slots** (`examples.repair_line`, `examples.recast`, `examples.pattern_tease`, …). The setup agent writes those in the target language. Examples carry real weight in prompt quality, so they become pack data. We don't delete them |
| `run_studio.py` (880) | `DIRECTOR`/`ARCHITECT`/`PRODUCER` prompts; **`MIN_ENGLISH_SHARE` Woven-Thanglish tripwire**; "most-Tamil voice" check | Prompts rewritten as above. The tripwire is a **hard seam**, see §4.5 |
| `knock_reply.py`, `reply_common.py`, `morning_knock.py`, `render_rotation.py` (`"who": "anna"` in `SHAPE_CLAUSES`), `suggest_targets.py` | Identifiers and strings: Andrew/Anna (≈200 refs), trip | Mechanical renaming (`tutor`, `learner`) |
| `sync_state.py` (1,521) | The only state writer: `update`, `check` (the Receptive Check), `month`, `year`, `slips`, `knock-response`, `rate-episode`, `feedback`, `add-word`/`add-pattern`. Carries Tamil-script help text and examples, and migrations of Andrew's retired state (`RETIRED_LEARNER_KEYS`, `FOREIGN_BOOKS`) | **Port; it's core.** Rename, swap examples for pack placeholders, and drop only the migrations of retired personal state. `seed-deck` goes with the deck (§4.3) unless W4 intake needs it. It's the largest file in core, so it is the first test of the 8k budget |
| `year.py` | Trip cycle. `ORDER` = excavation, down, across, up, taper, trip, harvest, with fixed lengths; state keys `trip_from`/`trip_to` | **→ `timeline.py`; the phases become data (D8).** The mechanism stays fixed: the phase record (`direction`, `voices`, `situation_given`, `intake`, `marker`), the which-phase-is-today lookup, and the rule that a marker is behavioural and involves a real human. The phase list, names and lengths are written by setup from the learner's stake and date. Andrew's year is the worked example, not a default. The `sync_state year` subcommand follows the rename |
| `household.py` | Path and section names; the cast's target-script spelling is parsed and is load-bearing (an eavesdrop tape is refused unless a cast member's target-form name is in it) | Rename `world.py`. The name match is the referent axis (§4.5): it matches the declared canonical-form name, not a script test |
| `backfill_observations.py`, `render_demo.py` | 09-10 ledger cutover; showcase demos | **Leave behind** |

**Mechanism that ports with renaming and comment-stripping only:**
`observations`, `lexicon_view`, `slips`, `session_brief`, `show_status`,
`generate_callbacks`, `month`, `dose_evidence`, `publish`, `rebuild_rss`, `memo`,
`lanes`, `audio_titles`, `render_soak`, `render_drill`, `render_rotation`,
`lesson_audio`, `receptive_check`, `push_queue`, `knock_message`, `commissions`,
`render_chat`, `rails` (minus constants), `smoke_test` (the runner; the cases are
rebuilt in W5).

**Mechanism that ports with a seam change (D5).** Each of these files tests for the
target script directly, so a Latin-script target changes its behaviour, not just its
names. Each file swaps a script test for a pack accessor:

| File | Today's test | What it's asking |
|---|---|---|
| `state_io` | `is_tamil` in `resolve` | Is this token a lexicon key? (canonical form) |
| `writer` (minus constants) | `TAMIL_RUN` in `to_phonetic` | Does this text need a read-form rewrite? (identity when read = voice) |
| `render_audio` | `is_tamil` on new words | Is this a target word? |
| `render_sort`, `render_payoff` | `TAMIL_RE.search` | Is this key or echo target language? |
| `suggest_targets` | `strip_pulli` | What's the stem? |
| `run_studio` | `MIN_ENGLISH_SHARE`, most-target voice | How much is L1? (the weave tripwire, §4.5) |

These accessors landed in tamil-tutor on 2026-10-05 (D12), so in W2 these lanes port as renames and the seam work is in `pack.py`'s answers.

### 4.3 Everything else

| Area | Personal / Tamil | v6 fate |
|---|---|---|
| `AGENTS.md` | "Andrew", "2027 family visit", the **Astra / `gpt-6-luna`** operating priority | **Rewrite.** Add the uninitialized branch, the two hats, and a *generalized* standing charge ("optimize for continued engagement and enjoyment toward the learner's stake"). Delegation choices specific to Andrew's hosts don't belong in the template |
| `CLAUDE.md` | — | Thin pointer to `AGENTS.md` (the current tamil-tutor pattern) |
| `.claude/skills/anna` | Whole file | → `skills/tutor`. Setup renames it to the persona (Phase 6) |
| `.claude/skills/{orient,debug,validate,extend,verify,recalibrate}` | Dated Andrew incidents, Tamil glossary terms, `s##` case numbers | **Port**, but cut back to the procedures. The glossary is rewritten with neutral terms (heist → stake, Oracle → informant, household → world) |
| `.claude/skills/backport` | — | Stays **in tamil-tutor only**. Update it to point at the v6 seam (§5.1) |
| `.claude/agents/studio.md` | Names | Port |
| *(new)* `.claude/skills/setup` | — | From v5, updated to §6 |
| `.github/workflows/anna.yml` | `ANNA_PUSH_WEBHOOK_URL`, "Judge Tamil reply", personal cron | → `tutor.yml`. Secrets become `PUSH_WEBHOOK_URL`, `OPENROUTER_API_KEY`, `GCP_SA_KEY`. Skips when unbootstrapped or when a module is off. Cron is commented out until setup |
| `docs/DECISIONS.md` (386 lines, 196 "Andrew") | Dated personal history | **Distill** into a template seed of universal decisions, one line each. The instance appends its own |
| `docs/PROTOCOL_MAP.md` | Tamil instantiation narrative | **Port** as the architecture map without the history |
| `docs/JOURNEY`, `ASTRA_CHARGE`, `ASTRA_REVIEW`, `comprehension_plan`, `learning_week`, `feature_inbox`, `home_assistant_knock_buttons`, `shortcuts/*.shortcut` | Personal | **Leave behind.** `WORKED_EXAMPLE.md` gets a fresh rewrite. `phone_loop.md` gets a fresh generic write-up, with HA as one worked receiver |
| `content/` (lessons, scripts, captions, art, articles, cheatsheets), `published_audio/`, `audio/`, `rss.xml`, `logo.jpg` | Personal | **Never ship.** The only exception is `content/world.md.template` |
| `progress/*` | Personal | Ship only `*.json.example` + `profile.md.template` |
| `curriculum/word_pool.json` (534 Tamil-script hits), `trip_deck.json` | Tamil | `word_pool.json.example` (schema); the setup agent synthesizes the pool. The deck is left out of v6.0 (tamil-tutor retired its container) |
| `BOOTSTRAP.md` | Tamil-flavoured bootstrap + the "What Generalizes" layer map | Superseded by `SETUP.md`. The layer map becomes `CUSTOMIZATION.md` |
| `scripts/smoke/` (128 cases) | Fixtures are Andrew + Tamil script throughout | **Rebuild** (§7, W5) |

### 4.4 Learner-pack concepts: Andrew's version → general slot

| Andrew's instance | General slot (interview → file) |
|---|---|
| The heist: a secret reveal to his wife | **Stake.** What mastery climaxes into (reveal / trip / exam / move / heritage). Secrecy is optional → `stake.md` |
| The wife as Oracle | **Informant policy.** Who the native resource is (none is a valid answer), and the rule that they are never an examiner → `stake.md` |
| "Family already, language not yet" | **Standing facts** → `user.md` |
| August 2027 trip, `year.py` phases | **Timeline:** the stake's date and the phases leading to it, elaborated in the interview (a wedding in a month and a trip in a year get very different plans) → `config.timeline` (phases) + `learner.json.timeline` (dates and progress). No date means no timeline module |
| The Coimbatore household (Paati … Ravi) | **World:** a fictional recurring cast in the target region, with pinned voices and a register ladder across ages → `world.md`. **The learner approves the cast** before anything uses it |
| Lunch session + separate ear block | **Daily deal** → `learner_contract.md` |
| 3 reaches/day, 08–21 local | **Rails** → `config.rails` |
| Home Assistant + iOS Shortcuts | **Notification receiver.** Any webhook-capable app; documented in `phone_loop.md` |
| $5–10/month, CAD | **Cost budget.** The interview asks for it, and setup picks the writer model and TTS tier to fit |
| Intake: recognizer, ten years of table exposure | **Starting point** (beginner / recognizer / rusty). The intake seeds `untested` rows and then runs a **Receptive Check** (the learner answers meanings, the agent marks them). No self-claimed rungs |

### 4.5 Language-shaped assumptions (what any port exposes)

tamil-tutor's mechanism quietly assumes things that are true of Tamil. Each language
breaks a different subset of them. Tamil's distinct script made some assumptions easy to
grep for. A Latin-script target makes them invisible, and Korean or Japanese would expose
others. **The template doesn't solve these per language.** It names each axis, puts a
slot behind it, and has the setup agent elaborate the slot in the interview. The
examples below show that an axis is real. They don't decide anything for those
languages.

| Axis | Tamil's assumption | Breaks for (e.g.) | Template answer |
|---|---|---|---|
| **Telling target from L1 inside a string** | Target = "has Tamil script" (`is_tamil`, `TAMIL_RUN`; English-share tripwire, studio lint, phonetic check) | Any shared-script pair: French, Dutch, Spanish | **Declare, don't detect.** Generated lines carry their language as a field; `script_regex` is a fast path only when the scripts differ. Lanes ask a role-named question (`has_target`, `target_runs`), never a regex |
| **Read form vs voice form** (the Modality Split) | Reads phonetic romanization, voice gets script, an LLM rewrite bridges them | Collapses for Latin-script targets. Multiplies for Japanese (kana/kanji/romaji) and Chinese (hanzi/pinyin + tones) | **Keep the rewrite lane** and make it the identity when the forms are equal. Read form and voice form are interview-derived pack fragments |
| **The Weave** | Code-switching with English is native, so English nouns are authentic | Dutch, French (sentence-boundary weave); some regional varieties partly flip back | **Interview derivation** → `language.md` + `weave_rule` fragment. The English-share tripwire reads the derived rule |
| **Word boundaries / counting** | Space-delimited words; meters count words | Chinese, Japanese, Thai (no spaces) | Meters count **declared spans**, not whitespace tokens. A pack slot names the tokenization rule |
| **Inflection tolerance** | Agglutinative stem + vowel-sign tail (`TAMIL_TAIL_RE`, `strip_pulli`) | Fusional (French elision, Spanish conjugation), isolating (Chinese: none), other agglutinative (Korean, Turkish: different tails) | **Interview elaboration** → `stem` rule in the pack (regex, suffix list, or null = verbatim) |
| **Register ladder** | `-nga` politeness; year phases down → across → up | Korean speech levels, Japanese keigo, French *tu/vous*, near-flat English-like registers | `language.md` names the ladder's rungs; timeline phases and the world cast map onto them. One rung is valid |
| **Referents & kinship** | 26 Tamil kinship nouns name a tape's subject | Korean age/gender-relative terms; languages that prefer names over kin terms | `referent_nouns` is pack data; `world.md` gives each cast member a canonical-form name |
| **Diglossia** | Spoken Coimbatore vs literary Tamil; the dialect pass rewrites | Arabic, Malayalam, Swiss German strongly; French mildly (*ne* dropping) | `dialect.md` is always synthesized; its weight depends on the gap |
| **Script direction & rendering** | LTR; known font fallbacks (the Grantha tofu note) | Arabic, Hebrew (RTL captions and notifications) | Caption and notification renderers take direction from the pack. **Untested until a port needs it** |
| **TTS coverage** | Chirp3-HD `ta-IN` pool, two pinned voices | Smaller languages have few or no voices | Setup lists the real voices before pinning. With no voices, the audio module stays off |

**Acceptance for this table:** W5 fixtures cover both outcomes of the first two
axes (distinct script vs shared script). The rest are slots with a documented null
meaning. A port that hits an axis not listed here adds a row; it doesn't add a
special case.

---

## 5. Target shape of v6

### 5.1 The seam

```
config/tutor.json        ← L2 + L3 scalars (language, tutor, tts, feed, rails, writer, modules, examples)
scripts/pack.py          ← the ONLY reader of config; replaces language.py; imports nothing else
protocol/*.template      ← synthesized prose: persona, user, stake, learner_contract, language, dialect
content/world.md.template
curriculum/word_pool.json.example
progress/*.example, progress/profile.md.template
```

The invariant tamil-tutor earned, *one file answers "what does a port change?"*, carries
over: **`config/tutor.json` + the `.template` list *is* the port surface.** A ratchet
asserts that no mechanism file contains the target script, a learner name, or a
config-owned literal. These are the descendants of three guards: `s70`'s needle check
(every pack value has one home), `s91` (no language fact outside the pack) and `s93`
(the prose port-surface list names real files).

**The script sweep only bites on a distinct-script fixture.** For a Latin-script target,
"no mechanism file contains the target script" can't be checked, and a fact about the
language written in Roman letters is invisible to it anyway (`s93`'s finding: the
`-nga` ending, "Woven Thanglish"). So the ratchet runs against the distinct-script W1
fixture. Names and config literals are checked as needles for any language. Facts
about the language written in prose are held by the port-surface file list, never by
a regex.

### 5.2 Modules

| Module | Contents | Default |
|---|---|---|
| **core** | session (skill + protocol), state + ledger + lexicon view, ticket + callbacks + slips, world + month, receptive check, **the sweep's planner** (`render_sort --plan-only` today), status/brief | always on |
| **audio** | `render_audio`, `memo`, soak, rotation, drill, `lesson_audio`, studio (`run_studio` + subagent), RSS feed | on if TTS is configured |
| **phone** | knock, reply/open-ask/message lanes, rails, push queue, commissions, payoff, sort tape (the rendered tape; its planner is core), workflow ticks | off until setup wires a receiver |
| **timeline** | `timeline.py` phases toward the stake's date | on only if the stake has a date |

`config.modules` holds these flags. A module that is off makes its workflow step skip
green.

### 5.3 Lean rules

- **Comments state the rule, not the history.** A docstring has one paragraph: what it
  owns, what it doesn't, and the invariant. No dates, no names, no incident narratives.
  Lineage is one line, `docs/LINEAGE.md` → tamil-tutor tag.
- **Budgets (ratchet-enforced from day one).** Settled as proposed (D10) and re-counted
  after W2. Core Python ≤ 8k lines, audio ≤ 4k, phone ≤ 4k, smoke ≤ 5k, fixed protocol
  prose ≤ 9k words. For reference, tamil-tutor today is 16.8k + 15.0k lines and 14.7k
  words, and v5 was 6.9k lines.
- **`PROHIBITION_BUDGET` carries over** (§3 item 11). Its census is re-taken on the
  template's own prose, not inherited (tamil-tutor: 195).
- **Every carried-over feature names its tamil-tutor evidence in one line in
  `DECISIONS.md`.** Anything without evidence stays behind.

---

## 6. The setup experience (SETUP.md v6)

The v5 phases stay. The changes below bring them in line with the current architecture.

| Phase | v6 change |
|---|---|
| 0 Preflight | Detect the executor (`claude` on PATH?), Python version, `gcloud`/`edge-tts` |
| 1 Interview | Add these to v5's set: **standing facts** (→ `user.md`), **daily deal** (session anchor + ear block → `learner_contract.md`), **cost ceiling**, **notification receiver** (or none), **the stake's timeline** (optional: the date, and what the run-up, the event and any after should be — the agent proposes phases and the learner confirms), **whose speech, concretely** (a region and the people the learner actually hears, never just a language name), and the **§4.5 axes** as derivations the agent proposes and the learner confirms. Stay conversational: 3–4 rounds |
| 2 Derive | Weave + Modality letters → `language.md` + `config.language` + **example slots** for the mandates. Verify voices exist by listing them; never guess IDs |
| 3 Synthesize | persona, user, stake, learner_contract, dialect, **world** (place, 5–7 cast across the register ladder, a pinned voice each, standing facts; **the learner approves the cast**), word pool (150–250 spoken-form glue entries), `exemplars.md` seed (D14), the **timeline** phases if the stake has a date (D8) |
| 4 Init state | Copy the `.example` files; `profile.md` with the Calibration Notes dials; no arc yet. The first session writes it |
| 5 Intake | Seed recognized items as `untested`, then run a short **Receptive Check** in which the learner answers meanings. Never a self-claimed rung. Skip for beginners |
| 6 Wire | Git remote (public vs private trade-off for the feed), `.env`, Actions secrets, uncomment cron for enabled modules, rename the `/tutor` skill, shed the welcome media |
| 7 Verify & hand over | Smoke green; `status` + ticket coherent; render one short `lesson_audio` clip if audio is on; hand over to the persona for session one (coffee-and-lore first) |

---

## 7. Workstreams

| # | Workstream | Done when |
|---|---|---|
| W0 | **Freeze and clear.** Tag tamil-tutor HEAD `template-v6-source` (no earlier than `43525f5`) and re-take this spec's census there. Tag this repo's current main `template-v5`. In one commit, clear the tree down to the kept files | Both tags pushed; census figures match the tag; tree contains only README, LICENSE, welcome media, this spec |
| W1 | **Pack contract.** `config/tutor.json` schema + `pack.py` + the template list + the §4.5 seam decisions, including the role-named accessors of §4.2's seam-change table (landed in tamil-tutor first, D12) | Schema doc'd in `CUSTOMIZATION.md`; two fixture configs validate: a **distinct-script** pack (Tamil-shaped) and a **shared-script** pack (the v5 Spanish example). Every §4.5 slot has a documented null |
| W2 | **Mechanism port**, bottom-up by layer (`pack` → `state_io` → ledger → selection → writer → publish → lanes). Rename, de-Tamil, strip history | Ratchet: zero learner names / target script / config literals in mechanism files; import-direction guard green |
| W3 | **Prose port.** Fixed protocol files neutralized; templates written with (fixed)/(synthesize) sections; mandates and studio prompts slotted | Each template has a guidance block and a worked pointer; prose budgets set |
| W4 | **Setup protocol.** `SETUP.md` + `skills/setup` per §6 | A dry run on a blank clone reaches Phase 7 |
| W5 | **Tests.** A new, small smoke suite run against both fixtures, plus a blank-clone case | Green on both; blank clone green; cases cover the ledger law, rails, the referent rule, modality on/off, weave branches |
| W6 | **Docs.** `WORKED_EXAMPLE.md` (October Tamil: comprehension pivot, world, ledger, the year as one worked timeline), `CUSTOMIZATION.md`, `PROTOCOL_MAP.md`, `DECISIONS.md` seed, `phone_loop.md`, README edits | A reviewer can find every dial from `CUSTOMIZATION.md` |
| W7 | **Workflows.** `tutor.yml` + `smoke.yml`; module-aware skips | Blank fork: Actions green with no secrets |
| W8 | **Acceptance.** (a) A live cold setup by a new learner (the teammate's French is the first), through a first session and one rendered dose. (b) A paper round-trip: fill the template's slots from Andrew's facts and diff against tamil-tutor's protocol. Every Tamil-instance file must be reachable from a slot | (a) the teammate runs session 2 unassisted; (b) no unmapped Tamil surface remains, or each gap is logged as a known v6.1 item |

Order: W0 → W1 (the seam has to be designed first) → W2 ∥ W3 → W4 → W5 → W6/W7 → W8.
`backport/SKILL.md` in tamil-tutor gets updated in the same pass as W1, so future
milestones map onto the v6 seam.

---

## 8. Decisions

**Settled (Andrew, 2026-10-05).** All decisions are settled; none are open.

| # | Decision |
|---|---|
| D1 | **Replace language-tutor in place.** Tag the current main `template-v5`, then clear the tree in one commit. The URL, the README and its video survive, and v5 stays reachable |
| D2 | **The month-of-stillness rule is a recommendation, not a gate.** Tag tamil-tutor HEAD at W0. A v6.1 re-extraction is expected |
| D5 | **Declare, don't detect** for target vs L1 (§4.5). The romanization rewrite lane stays and becomes the identity when read form = voice form |
| D7 | **tamil-tutor's health comes first.** It adopts nothing from the template until the template is proven. W8(b) is a paper test only |
| D10 | **Size budgets** as proposed in §5.3. Re-census after W2 and set them in the same diff |
| — | **Weave, inflection tolerance, register ladder and the other §4.5 axes are interview elaborations**, never template defaults |
| D8 | **The timeline is an interview elaboration.** `year.py` becomes `timeline.py`: fixed mechanism, phases as data. Setup writes the phases from the learner's stake and date, so a wedding next month and a trip next year each get their own plan. Andrew's year (audit → down → across → up → taper → trip → harvest) appears in `WORKED_EXAMPLE.md`, never as a default |
| D12 | **Role-named accessors land in tamil-tutor before W1.** Done 2026-10-05 (`43525f5`): `is_canonical`, `has_target`/`target_runs`, `stem` and `host_stem` replace the raw script tests, so W2 renames these lanes instead of redesigning them |
| D13 | **Prompt fragments: `audio_form`, `chat_form`, `weave_rule`.** `register_note` is dropped and `dialect.md` owns the register default, matching tamil-tutor's 2026-10-05 change. `weave_rule` stays because the English-share tripwire needs a value to read |
| D14 | **`exemplars.md` ships a fixed frame plus a short neutral seed** of 2–3 contrasting *kinds* of day (an ask, a teardown, a commission), with no learner in them. Setup marks it provisional, and the tutor replaces seed entries with the learner's own days as they happen, keeping 4–5 that contrast |
| D3 | **Pack form: JSON config + a fixed `pack.py` reader.** Setup writes data, never Python. Rules that need logic are expressed as data (a regex, a suffix list, or null = verbatim); a language that outgrows that adds a row to §4.5, not a hook file |
| D4 | **Modules as drafted (§5.2).** Core always on; audio on when a TTS voice is configured; timeline on when the stake has a date; **phone off by default**, offered at Phase 6 |
| D6 | **Notification receiver: a generic webhook contract** (POST a small JSON body). **ntfy** is the documented zero-infrastructure default and **Home Assistant** the worked example. Setup asks what the learner already runs |
| D9 | **README: keep the frame, the name story and the video.** Rewrite the status banner, the pedagogy section (comprehension-led, not floor) and the repo map in W6 |
| D11 | **Example slots in mandates: at most 8**, named by function (repair line, recast, pattern tease, …), written by setup in the target language. Needing more means the prompt is carrying language law, which belongs in `language.md`. These are single lines showing the target form, not past sessions used as models, so *exemplars, not templates* (§3 item 11) doesn't apply |


## 9. Risks

- **Over-extraction.** The pedagogy prose is long because it was earned. Cutting the
  history can also cut the *reason* a rule binds. Mitigation: each fixed rule keeps one
  "because" clause, and `DECISIONS.md` keeps the evidence line.
- **A port exposes an axis §4.5 doesn't list** (caption sheets, sort-tape pacing, the
  knock's script-in-body rule are the likely places). Mitigation: the shared-script
  fixture runs from W1, not W8. A new axis becomes a table row and a slot, never a
  special case.
- **Source keeps moving.** tamil-tutor ships daily. Mitigation: D2 freeze plus the
  `backport` skill, and no per-fix syncing.
- **Cost surprises for a new learner.** Mitigation: the cost ceiling is an interview item,
  setup maps it to writer and TTS choices, and `show_status` prints the month's spend
  when that's available.

---

## 10. Acceptance record

**W7 (2026-10-05).** `smoke.yml` passed on GitHub on the blank template with no secrets
(run 37357650737: actionlint, then the blank, Tamil and Spanish suites). `tutor.yml`
passed actionlint and drew no validation failure. Its dispatch path was checked locally
(blank → `ready=false`; the Spanish pack → audio on, phone and timeline off), but it has
not run in Actions yet. Its first run is setup's Phase 7.

**W8(b), the paper round-trip (2026-10-05).** Every Tamil-instance surface at
`template-v6-source` is reachable from a slot:

| tamil-tutor surface | v6 home |
|---|---|
| `persona.md`, `user.md`, `learner_contract.md`, `dialect.md`, `exemplars.md` | the slot of the same name. Sections map one to one; dialect's seven merge into six |
| `heist.md` + the constitution's goal line and informant section | `stake.md` (The Stake, The Secret, Native Resources, The Ops) |
| The constitution's dialect strictness, Woven Thanglish, phonetic acceptance, surface split, lore veins | `language.md` (register, weave, modality, lore) + `config.language` |
| `content/household.md`, the analysts in `hosts.md` | `content/world.md` |
| The studio's dialect test, the Kongu layer, the reference ear | `dialect.md` (the test line, The Regional Layer) |
| Tamil worked examples in the mandates | `config.examples` (the D11 slots) |
| `language.py`, `household.py`, `year.py` | `pack.py` + config, `world.py`, `timeline.py` |
| `curriculum/word_pool.json`, `progress/profile.md` | `.example` / `.template` |
| `backfill_observations.py`, `render_demo.py`, `trip_deck.json`, the personal docs | left behind (§4.2, §4.3) |

**One gap was found and closed in the same diff:** the exemplars seed carried three kinds
of day against the file's own "four or five", and tamil-tutor's fourth kind (a familiar
shape after a gap) is universal. It is now seed 4. **Known v6.1 items:** none from the
mapping. Acceptance residue:

- W8(a) is open: a live cold setup by a new learner.
- A right-to-left script is untested (`CUSTOMIZATION.md` §4.5 row).
- `tutor.yml` has not yet run in Actions.

**Found in tamil-tutor and reported, not fixed (D7):**

- M94's first line is the Voice Map comment, so the feed titles it by filename.
- `content/household.md`'s beat log is never committed, because `render_audio`'s commit
  list omits it.
- `render_payoff --dry-run` counts a try and commits a refusal.
- `anna.yml` inlines two dispatch payload values into `run:`.
