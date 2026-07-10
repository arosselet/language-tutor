# Project Glossary

Every jargon term a newcomer will hit in this repo, in alphabetical order.
Each entry: 1–2 line definition, plus the file where the term is canonically defined.
(Terms tied to synthesized files — persona, hosts — take their concrete shape at setup;
`docs/WORKED_EXAMPLE.md` shows how rich they got in the reference implementation.)

---

## Breakdown

The second half of a `classic` or `story` episode: the two analysts (in character, in the target language) react to the Intercept — replaying one or two interesting beats, never inventorying the whole payload. Goal is **colour and a second soak**, not a glossary; a Breakdown that enumerates every new word has failed its brief. Omitted in `vignette` form.

Defined: `protocol/studio/architect.md`

---

## callbacks

Words scheduled for spaced-repetition resurfacing. `scripts/generate_callbacks.py` computes what's due; `scripts/suggest_targets.py` folds them into the session ticket. The tutor weaves them into the scene where they fit naturally — they are a soft target, not a quota.

Defined: `protocol/daily_session.md` — Targeting section; `docs/PROTOCOL_MAP.md` — Python brain

---

## capped (graduation lane)

A knock-reply grade for a **cold-quality** fire that the reveal window blocks from scoring cold (the knock or recent traffic printed the word). Capped fires on 2 distinct local days **graduate** the word to cold — otherwise a daily-knocked word could never escape hinted through the very channel drilling it. Python verifies every capped/cold claim against computed reveal evidence.

Defined: `scripts/knock_reply.py` — judge mandate + `apply_verdict()`; `docs/DECISIONS.md` — "The capped lane"

---

## cold (fire cold)

A word fires **cold** when the learner produces it from a native-language situation with no prompt, no warm-up, no multiple choice — instant recall, no hesitation. Cold production is the currency that moves the viability floor. Contrast: **hinted** (produced after a nudge) and **stuck** (demotes recognition one level). The tutor logs these via `sync_state.py update --produced-cold / --produced-hinted / --stuck-word`.

Defined: `protocol/daily_session.md` — The Loop and Close & Log sections

---

## deck

A tagged sprint subset of `progress/lexicon.json`. During a deck sprint, a finite set of chunks and frames is tagged `deck:"<name>"`; `suggest_targets.py` surfaces them first and the status line reports **Deck: X/N fire cold** as the headline meter. Each deck item carries a `direction` field: **fire** or **catch** (see those entries).

Defined: `docs/DECISIONS.md` — "Deck sprints for real deadlines"; `scripts/sync_state.py` — `compute_deck()`

---

## dose

A self-contained learning unit — one knock memo, one episode, one push — that requires no prerequisite and carries its own complete rep. The learner should be able to engage with it in whatever gap they have without needing to recall the previous dose. There is no listening-reconciliation ritual.

Defined: `docs/DECISIONS.md` — "Stop chasing listens"

---

## eavesdrop

The catch-axis knock modality: the memo is an overheard **tape** (one side of a phone call, in a second pinned voice — `tts.eavesdrop_voice`), and the notification asks one drift question in the learner's native language. The reply grades **comprehension** on its own small judge mandate and moves recognition only — never production. Disabled unless `tts.eavesdrop_voice` is set.

Defined: `scripts/morning_knock.py` — eavesdrop modality; `scripts/knock_reply.py` — catch judge

---

## engines

Generative structural patterns — verb frames the learner internalizes as a machine, not a memorized line. Examples: the present/future toggle, the obligation frame, the can't-frame. An engine is **online** when the learner can fill a novel slot cold. "One engine online beats five chunks memorized." Logged with `--produced-cold 'frame:…'` only on a novel slot-fill, not a repeat.

Defined: `protocol/daily_session.md` — Targeting section ("Engines to fire"); `protocol/constitution.md` — "Pattern Over List (The Verb Engine)"

---

## field missions

A covert assignment the tutor gives at the end of a session: one line, deployed in real life tonight, unprompted — debriefed at next contact. The native informant stays the unwitting audience, never the examiner. A line that survives live fire is the strongest cold-fire evidence the system has.

Defined: `protocol/persona.md` (synthesized — the stake section); `protocol/constitution.md` — The Native Informant

---

## fire / catch (axes)

Every deck item carries a `direction` field. **Fire** items target cold production — the learner must generate them under pressure. **Catch** items are ear-only — the win is solid recognition via eavesdrop doses and soak; these are never forced to fire. The meter reads both sides: `X/N fire cold · Y/M catch solid`.

Defined: `scripts/sync_state.py` — `compute_deck()`; `docs/PROTOCOL_MAP.md` — `lexicon.json` row

---

## floor-gap

A word the learner recognizes (comfortable or solid) but cannot yet produce cold. Floor-gap targets are **what to force in a session** — they do not need re-teaching, they need cold dispatch in fresh native-language situations. The gap between recognition and production is the work.

Defined: `protocol/daily_session.md` — Targeting section ("Floor-gap targets")

---

## Intercept

The main dialogue scene in a podcast episode — two native speakers in a real situation, carrying the payload words naturally. In `classic` form, the Intercept is followed by the Breakdown; in `vignette` form, the Intercept stands alone. In `lore` form, an optional short Intercept vignette opens as the specimen the analysts then dissect.

Defined: `protocol/studio/architect.md`

---

## knock

The agentic phone-outreach system. `scripts/morning_knock.py` runs on a CI cron, checks the rails gate (waking hours, daily cap, min gap), then the tutor decides fire or silence and which modality — the valid set is `text`, `audio`, `challenge`, `volley`, `eavesdrop`, `grace`, `silence` (`morning_knock.py` `MODALITIES`; anything else falls back to `text`). A knock memo is a self-contained dose. The learner's typed reply is judged by `scripts/knock_reply.py`, which moves the production axis.

Defined: `docs/PROTOCOL_MAP.md` — Python brain and knock_log.json rows; `docs/DECISIONS.md` — "Outreach policy is the tutor's"

---

## lore

Language stories deployed as first-class input: etymology, cross-language kinship, myth, and cultural logic behind a word or register. Lore is not decoration — a word with a story has more retrieval hooks than a word with a scene. Lore never creates production debt (no deck item, no floor gap) and never takes over the feed rotation.

Defined: `protocol/constitution.md` — "Stories Are Curriculum (the lore rule)"

---

## masks

The tutor impersonating a native speaker from the learner's world (an elder demanding deference, a fast-bantering peer, a gossip) for one beat in-register, then stepping out to recast as themselves. Masks force the register the deck needs. One beat, then dropped; the one continuous relationship stays the tutor.

Defined: `protocol/persona.md` (synthesized — the masks section)

---

## native informant

The native speaker in the learner's life (spouse, friend, colleague — set at setup in `progress/profile.md`) used as a 60-second vibe-check resource, not a teacher or examiner. Their form always beats the system's draft; they are never turned into a progress check. When a deck sprint runs, the informant vets the deck.

Defined: `protocol/constitution.md` — "The Native Informant"

---

## recast

The tutor's correction method: when the learner is off, say it the natural way and move on — no grammar tables, no case names, no lecture. When the miss has a *pattern* behind it, the recast may carry **one clause of why**, by example, never terminology — the **Contrast Beat**; one clause is a beat, two is a lecture. Recast is the only permitted form of correction.

Defined: `protocol/constitution.md` — "The Contrast Beat"; `protocol/daily_session.md` — The Loop step 4

---

## scene spec

The three-axis structural selector Python hands the Director for each episode: **register** (emotional tone), **form** (classic / vignette / story / phone_call / lore), and **dramatic ingredient** (subtext / turn / character / stakes / genre). Computed by `scripts/suggest_targets.py` from the last 3 `*.tags.json` sidecars (`DIVERGENCE_WINDOW`) to guarantee anti-sameness. It is a gate, not a suggestion — overriding it is how variety drift comes back.

Defined: `protocol/studio/director.md`; `docs/DECISIONS.md` — "Variety is structural, not taste"

---

## soak-order

The handoff from the chat session to the studio. The tutor writes it at Close & Log into `progress/learner.json` → `soak_order`: two fields — **`payload`** (the words chat just strained) and **`scene_seed`** (one line situating the next beat of the running story). The studio consumes it as its only input from the conversation half. This is the only interface between the two halves of the system.

Defined: `docs/PROTOCOL_MAP.md` — "The interface: the soak-order"; `protocol/daily_session.md` — Close & Log step 3

---

## the stake

What mastery climaxes into for this learner — a reveal, a trip with a date, an exam, a return home (captured at setup; it shapes the persona's framing and any deck deadline). The tutor is the **safe room**: a hundred zero-stakes failures there buy the one live moment the learner picks.

Defined: `protocol/persona.md` (synthesized); `progress/profile.md` — the goal

---

## ticket

The output of `python scripts/suggest_targets.py` — the structured session brief the tutor picks from: floor-gap targets to force cold, engines to fire (with a novel slot), due callbacks to weave in, new candidates grouped by cluster coverage, and the vocabulary fence. The tutor picks from the ticket; they do not re-derive targets by eye.

Defined: `protocol/daily_session.md` — "Targeting — Narrow and Deepen"

---

## viability floor

Of the words the learner *recognizes* (comfortable/solid), the share firing **cold** — enough operational capacity to navigate real situations without going blank. `scripts/sync_state.py status` reports it as `Viability floor: X/Y recognized words fire cold (Z%)`. Production moves the floor; recognition without production does not.

Defined: `docs/DECISIONS.md` — "Absorption-first, then production-as-accelerant"; `scripts/sync_state.py` — `compute_floor()`

---

## volley

The deck's daily volume dose as a knock: Python picks `outreach.volley_size` due deck items (**binding** — coverage stays honest), the tutor writes one native-language situation per item, and the reply judge walks the queue deterministically — one item per exchange, miss = recast-and-move, the judge's own chain ignored. Counts as one demand dose for the variety law.

Defined: `scripts/morning_knock.py` — volley modality + `volley_targets()`; `protocol/daily_session.md` — "The volley"

---

## the Weave

The core register rule: the learner's native language carries the logistics (scene-setting, "why we are here"); the target language carries the payload (the load-bearing action word). The per-language letter — which words stay native, where the code-switch is idiomatic — is derived at setup and lives in `protocol/language.md`.

Defined: `protocol/constitution.md` — "The Weave"; `protocol/language.md` (synthesized)
