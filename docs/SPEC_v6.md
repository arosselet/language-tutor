# Sollu v6 — Fresh Extraction Spec

> **Status:** specification only, 2026-10-05. Nothing is implemented yet.
> **Source:** `tamil-tutor` at `8a4ccf9` (2026-10-04). It gets tagged `template-v6-source` when work starts.
> **Replaces:** the v5 tree of this repo (`template-v5-source`, 2026-07-27). Only
> `README.md` (with its embedded video), `LICENSE`, and the welcome media are kept.
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
| Candidate, not approved | About 20 call sites import raw script regexes (`TAMIL_RE`, `TAMIL_RUN`, `TAMIL_TAIL_RE`, `strip_pulli`) to answer three different questions. Role-named accessors (`is_canonical`, `has_target`/`target_runs`, `stem`) would make each lane name its question | Clearer lanes, a simpler `s91` | The plug point for *declare, don't detect* (§4.5) |
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
| The four prompt fragments (`chat_form`, `audio_form`, `weave_rule`, `register_note`) as the channel from language to Python | `protocol/` prose. It teaches the old *viability floor / forced cold output* thesis that tamil-tutor has since retired |
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
   month and `year.py` holds the phase schedule toward a dated anchor.
7. **Audio law:** `commissioning.md` (the tutor may make any audio at any time) and
   `audio_channels.md` (capacity routes the format). There are six lanes: soak,
   rotation (with lore movements), drill, episode, `lesson_audio`, plus payoff and sort
   tapes.
8. **Phone loop maturity:** a knock with seven modalities, open-ask and message lanes,
   `rails.py` as the one reach budget, the push queue, the commission router, payoff
   re-cuts, and the receptive check delivered as a tape.
9. **Ratchets:** prose word budgets and code-line budgets, plus `/extend` Gate 4 ("what
   does this replace?").
10. **Learner's half:** `learner_contract.md` holds the daily deal (session anchor +
    separate ear block), the one thing that is asked for, and what the learner owes back.

---

## 4. The surface map

There are four layers. **L0 pedagogy** and **L1 mechanism** ship as fixed files.
**L2 language pack** and **L3 learner pack** ship as slots, which means templates or
config keys. **Personal/infra** never ships.

### 4.1 `protocol/` (14.3k words today)

| File | Layer | What is Andrew/Tamil in it | v6 fate |
|---|---|---|---|
| `constitution.md` | L0 + L2 + L3 mixed | "By August 2027" goal; "Family Already"; "Dialect: Coimbatore Tamil Only"; **The Wife (Oracle)** role; Noun Shortcut + **Woven Thanglish**; Phonetic Over Script; Tamil examples throughout | **Fixed**, after removing those items: the goal moves to `user.md`, the dialect to `dialect.md`, the Oracle to `stake.md`'s informant policy, and the weave/modality *letter* to `language.md`. Principles stay with neutral wording |
| `daily_session.md` | L1 | Tamil-script example in the `update` command; "cloud Anna"; household | **Fixed**, with names and examples through placeholders |
| `toolbelt.md`, `commissioning.md`, `audio_channels.md`, `diagnosis.md` | L1 | Names; dated Andrew quotes used as justification | **Fixed**. Quotes become plain rules |
| `persona.md` | L2 + L3 | All of it: Anna, Coimbatore, Kongu, elder brother, the masks (mother-in-law, neenga-forms), voice lines | **Template** (synthesize). Keep the v5 fixed/synthesize split, updated to the comprehension charge |
| `user.md` | L3 | All of it: ten years married, "started at year nine" | **Template.** These are standing facts no generator may contradict |
| `heist.md` | L3 | The secret reveal to the wife, field missions, somatic anchors | **Template → `stake.md`.** Op mechanics (anchor = free, mission = assigned and collected, *debrief is contact, never evidence*) stay fixed. Secrecy is optional, kept only if the stake is reveal-shaped |
| `learner_contract.md` | L3 + L0 | The lunch anchor, the separate ear block, "a ratchet might start to hurt" | **Template.** The skeleton is fixed (the floor, no ratchet, what the learner owes back). The daily deal is synthesized from the interview |
| `dialect.md` | L2 | All of it: verb collapse, sandhi, Kongu layer, the neenga default | **Template** (the most-edited pack file after setup) |
| *(new)* `language.md` | L2 | v5 had this as a charter. In tamil-tutor its content is spread across the constitution | **Template.** Target register, Weave letter, Modality letter, register ladder, lore veins |
| `studio/{studio,director,architect,producer}.md` | L1 | Tamil-script examples (producer: 9 lines), "Coimbatore", Thanglish | **Fixed**, with neutral examples and pack references |
| `studio/hosts.md` | L1 + L2 | Analysts Maya/Raj, Coimbatore; "Tamil script only" production rule | **Fixed conventions.** The analyst names move to `world.md`, and "script only" becomes `{audio_form}` |
| `persona.md.example` | — | Old v3-era stub | **Delete** |

### 4.2 `scripts/` (16.8k Python lines + 14.7k smoke lines)

**The language pack today** is `language.py` + `rails.py` constants + `writer.py` models. These are the facts a setup agent writes:

| Fact | Lives today | v6 home |
|---|---|---|
| Script detection `TAMIL_RE` / `TAMIL_RUN` / `TAMIL_TAIL_RE`, `is_tamil`, `strip_pulli` | `language.py` | `config` → `language.script_regex` (nullable) + `language.stem_tail_regex` (nullable). `pack.py` exposes `is_canonical()`, `target_spans()`, `stem()` |
| `REFERENT_NOUNS` (26 Tamil kinship terms) | `language.py` | `config` → `language.referent_nouns` (synthesized) |
| `ANNA_VOICE`, `EAVESDROP_VOICE`; episode voice pools | `language.py`; `render_audio._CHIRP_POOL_*` | `config` → `tts.tutor_voice`, `tts.eavesdrop_voice`, `tts.pools`. Cast pins stay in `world.md` |
| `REPO`, `FEED_TITLE` ("Coimbatore Mappillai"), `FEED_SUMMARY`, `CAPTION_COLUMNS` | `language.py` | `config` → `feed.*` |
| Waking window, `MAX_REACHES_PER_DAY`, `MIN_GAP_HOURS` | `rails.py` | `config` → `rails.*` (learner facts) |
| `MODEL` (cloud), `AGENT_MODEL` (laptop) | `writer.py` | `config` → `writer.*` |
| Timezone | `learner.json` | stays in `learner.json` (it already follows the learner) |

**The prose surface in code.** These are files where a substitution pass won't work and the prose has to be rewritten:

| File | Andrew/Tamil load | v6 approach |
|---|---|---|
| `mandates.py` (640 lines, 15 prompt constants) | "You are Anna… Andrew's phone"; Tamil examples (`poren`, `புரியல`, `saapteengala`); Kongu; "Tamil script"; Thanglish | Neutral mechanism prose with `{tutor}`, `{learner}`, `{chat_form}`, `{audio_form}`, `{weave_rule}`, `{register_note}`, and a small set of **example slots** (`examples.repair_line`, `examples.recast`, `examples.pattern_tease`, …). The setup agent writes those in the target language. Examples carry real weight in prompt quality, so they become pack data. We don't delete them |
| `run_studio.py` (879) | `DIRECTOR`/`ARCHITECT`/`PRODUCER` prompts; **`MIN_ENGLISH_SHARE` Woven-Thanglish tripwire**; "most-Tamil voice" check | Prompts rewritten as above. The tripwire is a **hard seam**, see §4.5 |
| `knock_reply.py`, `reply_common.py`, `morning_knock.py`, `render_rotation.py` (`"who": "anna"`), `suggest_targets.py`, `sync_state.py` | Identifiers and strings: Andrew/Anna (≈200 refs), trip | Mechanical renaming (`tutor`, `learner`) |
| `sync_state.py` | One-shot repair lists of Tamil rows | **Drop.** These are personal migrations |
| `year.py` | Trip cycle; phases down/across/up/taper/trip/harvest | **Optional module.** It depends on the stake having a date. The register ladder (down → across → up) generalizes, for example French *tu*/*vous*, and the ladder names come from `language.md` |
| `household.py` | Path and section names | Rename `world.py`. Otherwise generic |
| `backfill_observations.py`, `render_demo.py` | 09-10 ledger cutover; showcase demos | **Leave behind** |

**Mechanism that ports with renaming and comment-stripping only:** `state_io`,
`observations`, `lexicon_view`, `slips`, `session_brief`, `show_status`,
`suggest_targets`, `generate_callbacks`, `month`, `dose_evidence`, `writer` (minus
constants), `publish`, `rebuild_rss`, `render_audio`, `memo`, `lanes`, `audio_titles`,
`render_soak`, `render_drill`, `render_rotation`, `lesson_audio`, `receptive_check`,
`render_sort`, `render_payoff`, `push_queue`, `knock_message`, `commissions`,
`render_chat`, `rails` (minus constants).

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
| `docs/DECISIONS.md` (365 lines, 185 "Andrew") | Dated personal history | **Distill** into a template seed of universal decisions, one line each. The instance appends its own |
| `docs/PROTOCOL_MAP.md` | Tamil instantiation narrative | **Port** as the architecture map without the history |
| `docs/JOURNEY`, `ASTRA_CHARGE`, `ASTRA_REVIEW`, `comprehension_plan`, `learning_week`, `feature_inbox`, `home_assistant_knock_buttons`, `shortcuts/*.shortcut` | Personal | **Leave behind.** `WORKED_EXAMPLE.md` gets a fresh rewrite. `phone_loop.md` gets a fresh generic write-up, with HA as one worked receiver |
| `content/` (lessons, scripts, captions, art, articles, cheatsheets), `published_audio/`, `audio/`, `rss.xml`, `logo.jpg` | Personal | **Never ship.** The only exception is `content/world.md.template` |
| `progress/*` | Personal | Ship only `*.json.example` + `profile.md.template` |
| `curriculum/word_pool.json` (534 Tamil-script hits), `trip_deck.json` | Tamil | `word_pool.json.example` (schema); the setup agent synthesizes the pool. The deck is left out of v6.0 (tamil-tutor retired its container) |
| `BOOTSTRAP.md` | Tamil-flavoured bootstrap + the "What Generalizes" layer map | Superseded by `SETUP.md`. The layer map becomes `CUSTOMIZATION.md` |
| `scripts/smoke/` (126 cases) | Fixtures are Andrew + Tamil script throughout | **Rebuild** (§7, W5) |

### 4.4 Learner-pack concepts: Andrew's version → general slot

| Andrew's instance | General slot (interview → file) |
|---|---|
| The heist: a secret reveal to his wife | **Stake.** What mastery climaxes into (reveal / trip / exam / move / heritage). Secrecy is optional → `stake.md` |
| The wife as Oracle | **Informant policy.** Who the native resource is (none is a valid answer), and the rule that they are never an examiner → `stake.md` |
| "Family already, language not yet" | **Standing facts** → `user.md` |
| August 2027 trip, `year.py` phases | **Anchor date** (optional) → `learner.json.year`. No date means no year module |
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
| **Register ladder** | `-nga` politeness; year phases down → across → up | Korean speech levels, Japanese keigo, French *tu/vous*, near-flat English-like registers | `language.md` names the ladder's rungs; `year` phases and world cast map onto them. One rung is valid |
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
config-owned literal. These are the descendants of `s70` and `s91`.

### 5.2 Modules

| Module | Contents | Default |
|---|---|---|
| **core** | session (skill + protocol), state + ledger + lexicon view, ticket + callbacks + slips, world + month, receptive check, status/brief | always on |
| **audio** | `render_audio`, `memo`, soak, rotation, drill, `lesson_audio`, studio (`run_studio` + subagent), RSS feed | on if TTS is configured |
| **phone** | knock, reply/open-ask/message lanes, rails, push queue, commissions, payoff, sort tape, workflow ticks | off until setup wires a receiver |
| **year** | `year.py` phases | on only if the stake has a date |

`config.modules` holds these flags. A module that is off makes its workflow step skip
green.

### 5.3 Lean rules

- **Comments state the rule, not the history.** A docstring has one paragraph: what it
  owns, what it doesn't, and the invariant. No dates, no names, no incident narratives.
  Lineage is one line, `docs/LINEAGE.md` → tamil-tutor tag.
- **Proposed budgets (ratchet-enforced from day one).** These are open, see D10. Core
  Python ≤ 8k lines, audio ≤ 4k, phone ≤ 4k, smoke ≤ 5k, fixed protocol prose ≤ 9k words.
  For reference, tamil-tutor today is 16.8k + 14.7k lines and 14.3k words, and v5 was
  6.9k lines.
- **Every carried-over feature names its tamil-tutor evidence in one line in
  `DECISIONS.md`.** Anything without evidence stays behind.

---

## 6. The setup experience (SETUP.md v6)

The v5 phases stay. The changes below bring them in line with the current architecture.

| Phase | v6 change |
|---|---|
| 0 Preflight | Detect the executor (`claude` on PATH?), Python version, `gcloud`/`edge-tts` |
| 1 Interview | Add these to v5's set: **standing facts** (→ `user.md`), **daily deal** (session anchor + ear block → `learner_contract.md`), **cost ceiling**, **notification receiver** (or none), **anchor date** (optional), **whose speech, concretely** (a region and the people the learner actually hears, never just a language name), and the **§4.5 axes** as derivations the agent proposes and the learner confirms. Stay conversational: 3–4 rounds |
| 2 Derive | Weave + Modality letters → `language.md` + `config.language` + **example slots** for the mandates. Verify voices exist by listing them; never guess IDs |
| 3 Synthesize | persona, user, stake, learner_contract, dialect, **world** (place, 5–7 cast across the register ladder, a pinned voice each, standing facts; **the learner approves the cast**), word pool (150–250 spoken-form glue entries) |
| 4 Init state | Copy the `.example` files; `profile.md` with the Calibration Notes dials; no arc yet. The first session writes it |
| 5 Intake | Seed recognized items as `untested`, then run a short **Receptive Check** in which the learner answers meanings. Never a self-claimed rung. Skip for beginners |
| 6 Wire | Git remote (public vs private trade-off for the feed), `.env`, Actions secrets, uncomment cron for enabled modules, rename the `/tutor` skill, shed the welcome media |
| 7 Verify & hand over | Smoke green; `status` + ticket coherent; render one short `lesson_audio` clip if audio is on; hand over to the persona for session one (coffee-and-lore first) |

---

## 7. Workstreams

| # | Workstream | Done when |
|---|---|---|
| W0 | **Freeze and clear.** Tag tamil-tutor `template-v6-source`. Tag this repo's current main `template-v5`. In one commit, clear the tree down to the kept files | Both tags pushed; tree contains only README, LICENSE, welcome media, this spec |
| W1 | **Pack contract.** `config/tutor.json` schema + `pack.py` + the template list + the §4.5 seam decisions | Schema doc'd in `CUSTOMIZATION.md`; two fixture configs validate: a **distinct-script** pack (Tamil-shaped) and a **shared-script** pack (the v5 Spanish example). Every §4.5 slot has a documented null |
| W2 | **Mechanism port**, bottom-up by layer (`pack` → `state_io` → ledger → selection → writer → publish → lanes). Rename, de-Tamil, strip history | Ratchet: zero learner names / target script / config literals in mechanism files; import-direction guard green |
| W3 | **Prose port.** Fixed protocol files neutralized; templates written with (fixed)/(synthesize) sections; mandates and studio prompts slotted | Each template has a guidance block and a worked pointer; prose budgets set |
| W4 | **Setup protocol.** `SETUP.md` + `skills/setup` per §6 | A dry run on a blank clone reaches Phase 7 |
| W5 | **Tests.** A new, small smoke suite run against both fixtures, plus a blank-clone case | Green on both; blank clone green; cases cover the ledger law, rails, the referent rule, modality on/off, weave branches |
| W6 | **Docs.** `WORKED_EXAMPLE.md` (October Tamil: comprehension pivot, world, ledger), `CUSTOMIZATION.md`, `PROTOCOL_MAP.md`, `DECISIONS.md` seed, `phone_loop.md`, README edits | A reviewer can find every dial from `CUSTOMIZATION.md` |
| W7 | **Workflows.** `tutor.yml` + `smoke.yml`; module-aware skips | Blank fork: Actions green with no secrets |
| W8 | **Acceptance.** (a) A live cold setup by a new learner (the teammate's French is the first), through a first session and one rendered dose. (b) A paper round-trip: fill the template's slots from Andrew's facts and diff against tamil-tutor's protocol. Every Tamil-instance file must be reachable from a slot | (a) the teammate runs session 2 unassisted; (b) no unmapped Tamil surface remains, or each gap is logged as a known v6.1 item |

Order: W0 → W1 (the seam has to be designed first) → W2 ∥ W3 → W4 → W5 → W6/W7 → W8.
`backport/SKILL.md` in tamil-tutor gets updated in the same pass as W1, so future
milestones map onto the v6 seam.

---

## 8. Decisions

**Settled (Andrew, 2026-10-05)**

| # | Decision |
|---|---|
| D1 | **Replace language-tutor in place.** Tag the current main `template-v5`, then clear the tree in one commit. The URL, the README and its video survive, and v5 stays reachable |
| D2 | **The month-of-stillness rule is a recommendation, not a gate.** Tag tamil-tutor HEAD at W0. A v6.1 re-extraction is expected |
| D5 | **Declare, don't detect** for target vs L1 (§4.5). The romanization rewrite lane stays and becomes the identity when read form = voice form |
| D7 | **tamil-tutor's health comes first.** It adopts nothing from the template until the template is proven. W8(b) is a paper test only |
| D10 | **Size budgets** as proposed in §5.3. Re-census after W2 and set them in the same diff |
| — | **Weave, inflection tolerance, register ladder and the other §4.5 axes are interview elaborations**, never template defaults |

**Open (each has a recommendation)**

| # | Decision | Recommendation |
|---|---|---|
| D3 | Pack form | **JSON config + a `pack.py` reader.** The setup agent writes data, not Python, and the "one file" property survives |
| D4 | Module boundaries (§5.2) | As drafted. Phone loop **off** by default |
| D6 | Notification receiver | A generic webhook contract. Document **ntfy** as the zero-infrastructure default and **Home Assistant** as the worked example. The learner's agent asks what they run |
| D8 | Year module in v6.0? | **Ship it as optional**, on only when the stake has a date |
| D9 | README | Keep the frame, the name story and the video. Rewrite the status banner, the pedagogy section (comprehension-led, not floor) and the repo map |
| D11 | Example slots in mandates: how many? | **≤ 8**, named by function. More than that means the prompt is carrying language law, and that belongs in `language.md` |

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
