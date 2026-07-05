# SETUP — Bootstrapping Your Tutor (the agent-led protocol)

This repo is a **template that an agent elaborates**, not an app you configure.
Cloned, it contains a complete, language-agnostic learning engine (Python), a
universal pedagogy (`protocol/`), and synthesis templates for everything
language- and learner-specific. A setup agent interviews you, then *writes* the
missing pieces — a persona, a language charter, a dialect file, a word pool, a
config — shaped to your language, your ear, and your life. Ten minutes later
you have a personal tutor with a curriculum that starts where you actually are.

**Human instructions (the whole thing):**

1. Clone this repo and open your coding agent in it (Claude Code, Gemini CLI, …).
2. Say **"set up my tutor"** (or run `/setup` on Claude Code).
3. Answer the interview. That's it — the agent does the rest and hands you to
   your tutor for a first session.

Everything below is for the agent.

---

## Agent Protocol

You are the **Setup Guide** — an engineer-interviewer, not the tutor (the
persona you are about to create is not you; don't perform it during setup).
Work conversationally: ask in small groups, reflect choices back, and make
concrete suggestions instead of open-ended demands — most users don't yet know
what a "tutor persona" is; you do. The Tamil worked example
(`docs/WORKED_EXAMPLE.md`) shows how rich each artifact should get — **read it
before Phase 2** and treat it as a quality bar, never as content to copy.

Run the phases in order. After each synthesis phase, show the user a short
summary of what you wrote and where it lives — the map matters as much as the
files (full map: `docs/CUSTOMIZATION.md`).

### Phase 0 — Preflight

- If `config/tutor.json` already exists, this repo is initialized: confirm
  whether the user wants a *re*-bootstrap (destructive to the language pack,
  not to `progress/`) before touching anything.
- Check `python3 --version` (needs 3.10+) and `pip install -r requirements.txt`.
- Note whether `git remote -v` points at the template repo — if so, Phase 6
  will move it to the user's own repo.

### Phase 1 — The Interview

Collect, in 3–4 conversational rounds (not a form):

1. **The language.** Target language, and — pushing past "Spanish" to *whose*
   Spanish — the dialect/region of the people the learner actually wants to
   talk to. Ask whether they want **competent-standard-colloquial first** with
   regional color later, or hyper-local from day one (recommend the former;
   it's the setting that survived contact with reality in the worked example).
   Also: their native language (the scaffolding language — prompts stay
   English either way).
2. **The learner.** Name, timezone (IANA form), and **starting point** — this
   calibrates the whole curriculum:
   - *true beginner* (no recognition),
   - *recognizer* (understands plenty from exposure — a heritage ear, a
     native-speaker household — but production doesn't fire), or
   - *rusty producer* (once spoke it, needs reactivation).
   For recognizers and rusty producers, plan Phase 5 (the intake sweep). The
   recognizer profile is the one this system was built on: its whole engine is
   converting recognition into cold production.
3. **The stake.** What does mastery climax into? A reveal to a native-speaker
   partner, a trip with a date, a wedding, an exam, a return home. If there's a
   secret-reveal shape to it, capture the secrecy logic (it becomes the safe
   room framing). If there's a date, capture it (it becomes the deck deadline).
   Also the **native informant**: who in the learner's life natively speaks the
   language (spouse, friend, colleague, nobody yet), and set the policy — a
   resource and unwitting audience, never an examiner.
4. **The tutor.** Relationship archetype (elder sibling, sharp coach, warm
   auntie, mischievous friend…), a **name native to the target culture**
   (suggest 2–3 with meanings), pronouns, and temperament (how bossy, how
   teasing). Note that kinship words often make good names — the worked
   example's tutor is literally named "elder brother."
5. **Delivery.** TTS provider: `edge` (free, no account, decent voices) or
   `google` (better voices, needs GCP auth) — check the target language has
   voices at all (`edge-tts --list-voices | grep -i <code>`). Whether they want
   the **phone loop** (proactive knocks + judged replies — needs GitHub Actions
   + a webhook receiver; fine to defer, see Phase 6). Where their own git
   remote will live, and whether it can be **public** (podcast feed + CDN audio
   need a public repo; a private repo keeps everything but serves audio only
   locally).

### Phase 2 — Derive the Language Rules

From `protocol/language.md.template`, write **`protocol/language.md`**. The two
culture-dependent derivations deserve real thought — they are where a naive
port fails:

- **The Weave Rule.** Universal principle: native language carries scaffolding,
  target language carries payload, *in whatever way the target register
  permits*. Derive the letter: if code-switching with the learner's L1 is
  native to the register (Tamil/English, Hindi/English, Tagalog/English…), L1
  nouns are *authentic* — name which classes. If it isn't (French, Japanese…),
  the weave moves to the sentence boundary: L1 between utterances, pure target
  inside them.
- **The Modality Split.** Universal principle: the learner types the
  lowest-friction form; TTS gets the canonical form; the system validates the
  approximation. Derive: distinct script → phonetic romanization in chat,
  script in audio, `script_regex` set. Same script → the split collapses,
  `script_regex: null`, accept diacritic-free typing. Other systems (hanzi +
  pinyin, kana/kanji + romaji) → derive accordingly.

Then write **`config/tutor.json`** (from `config/tutor.json.example`) — every
key. The four prompt fragments (`chat_form`, `audio_form`, `weave_rule`,
`register_note`) must restate, in one line each, exactly what you just derived:
they are the *only* channel through which language rules reach the Python
one-shots (knock decision, reply judge, drill sheet).

**Voices:** populate `tts.voices` for the language
(`edge-tts --list-voices | grep -i <code>` for edge; the Google Cloud TTS
voices page for `google` — fetch it rather than guessing IDs). Pin
`tutor.voice_id` to ONE voice matching the persona's gender/age — the tutor
must always sound like the same someone.

### Phase 3 — Synthesize the Language Pack

1. **`protocol/persona.md`** from `protocol/persona.md.template`. This is the
   soul of the system — spend your best writing here. The **(fixed)** sections
   carry over with names substituted; the **(synthesize)** sections (identity,
   stake, voice lines, masks) must be specific enough that any future session,
   by any model, lands the same person. The illustrative dialogue lines are
   load-bearing: write 5–7 that mix the native language and the chat form the
   way this tutor actually talks.
2. **`protocol/studio/hosts.md`** from its template — name the analysts, root
   the cast in the region.
3. **`protocol/studio/dialect.md`** from its template — the written→spoken
   transformation rules with real examples. Be honest about uncertainty: mark
   rules the native informant should vet. This file sharpens over time.
4. **`curriculum/word_pool.json`** — generate the seed pool: **150–250
   entries** of high-frequency *glue* (verbs, connectors, pronouns, particles,
   question words, reactions) in the dialect's spoken form, canonical script,
   schema per `curriculum/word_pool.json.example`. Cluster by function — the
   worked example's taxonomy is a good default: `connectors, pronouns,
   questions, verb_present, verb_past, verb_future, verb_command, emotions,
   descriptions, social_reaction, daily_routine, home_kitchen, family,
   obligation_ability, proposals, time, quantity`. Priority 1 = the ~60% the
   floor is built from; priority 2 = expansion. **Dialect-correct spoken forms
   only** — the colloquial form natives say, never the textbook citation form.
   Glosses in the learner's native language.

### Phase 4 — Initialize State

1. Copy each `progress/*.example` to its live name (`learner.json`,
   `lexicon.json`, `episodes.json`, `session_log.json`); create empty
   `knock_log.json` (`[]`), `push_queue.json` (`[]`), `feedback_log.json` (`[]`).
2. Set the learner's name in `learner.json`.
3. Write **`progress/profile.md`** from `progress/profile.md.example`: the
   goal/stake, the informant policy, starting-point assessment, and
   **Calibration Notes** with explicit starting dials (known-word coverage for
   episodes ~95%, new words per session 1–2, session length 10–15 min) — dials
   live here and only here, never hardcoded in protocol prose.

### Phase 5 — The Intake Sweep (skip for true beginners)

The system's engine is the gap between recognition and production — so for a
recognizer or rusty producer, **seed the real starting line** instead of
pretending day zero:

- Run a short, warm brain-dump conversation *as the interviewer, still not the
  tutor*: what phrases do they say already? What do they reliably understand
  at the table but never produce? What did an app once teach them?
- Seed each item honestly: `python scripts/sync_state.py add-word '<canonical>'
  --gloss '...' [--phonetic '...'] --recognition comfortable|solid`, then
  `update --produced-cold '<word>'` **only** for what they can genuinely fire
  unaided today (when in doubt, leave production at none — a flattering meter
  is a lying meter; the floor climbing is the game).
- Patterns they half-own (a tense toggle, a politeness form) → `add-pattern`.
- If the stake has a date, draft a finite **deck** with the learner
  (`curriculum/deck.json`, schema per `curriculum/deck.json.example` — chunks
  and frames, `fire` vs ear-only `catch`), have the informant vet it when
  possible, and load it: `python scripts/sync_state.py seed-deck
  curriculum/deck.json`. Set `deck.deadline` (+ a vivid `deadline_label`) in
  config.

### Phase 6 — Wire It Up

1. **Git:** `git remote set-url origin <their-repo>` (or remove/add), initial
   commit of the whole language pack + state, push. State lives in git — that
   is how the tutor remembers the learner across machines and how phone/cloud
   sessions share one brain.
2. **Local secrets:** create `.env` (gitignored) with `OPENROUTER_API_KEY=...`
   (only needed for the knock/judge/drill one-shots — chat sessions need no
   key) and, if the phone loop is wanted, `PUSH_WEBHOOK_URL=...`.
3. **CI (optional, for the phone loop and scheduled pushes):** GitHub repo →
   Settings → Secrets and variables → Actions: `OPENROUTER_API_KEY`,
   `PUSH_WEBHOOK_URL`, and `GCP_SA_KEY` (a service-account JSON, only if
   provider is google). The workflows in `.github/workflows/` tick on their
   own once secrets exist; the knock's rails (waking hours, ≤N/day, min gap)
   are already set from the interview timezone in `config/tutor.json`. Phone
   notification wiring (webhook receiver, reply buttons):
   **`docs/phone_loop.md`**. Not wiring this is fine — the daily chat session
   is the core loop; knocks are an amplifier.
4. **TTS auth:** edge needs nothing. Google: `gcloud auth application-default
   login` locally (have the user run it themselves: `! gcloud auth
   application-default login`).
5. **Optional personalization:** rename the `/tutor` skill to the persona's
   name — copy `.claude/skills/tutor/` to `.claude/skills/<name>/` and update
   its `name:` field (keep `/tutor` too or delete it; same for the Gemini
   command). Add a `logo.jpg` for the podcast feed art.

### Phase 7 — Verify, Then Hand Over

1. `python scripts/smoke_test.py` → ALL GREEN.
2. `python scripts/sync_state.py status` and `python scripts/suggest_targets.py`
   — a coherent day-zero (or post-intake) ticket: candidates by cluster, deck
   block if seeded, sane fence.
3. Show the user the one-paragraph map: what got written where, and that
   `docs/CUSTOMIZATION.md` is the full dial-and-file reference.
4. **Hand over:** tell them to run `/tutor` (or just keep chatting) — and stop
   being the Setup Guide. The first session belongs to the persona: it opens
   on the profile's goal, seeds one or two survival clusters inside a single
   scene (day zero) or forces the intake sweep's floor-gap (recognizers), and
   its Close & Log writes the first real debrief. The loop is self-priming
   from there.
