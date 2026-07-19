# Settled Decisions (`@build` reference)

Questions that were explored, decided, and closed — **seeded from the Tamil
reference implementation** (months of daily use; see `docs/WORKED_EXAMPLE.md`),
then continued by this repo's own learner. **Don't re-litigate these** — if new
evidence genuinely reopens one, take it to the learner with the evidence; never
silently drift. Append your own as they settle; every addition should state
what it replaces.

## How to work on this system

- **LLM is the writer, Python is the brain.** Push reasoning into deterministic
  code; keep the LLM's input surface small. Never hand-edit Python-owned JSON.
- **Every addition must earn its place.** Before adding a file, field, rule, or
  script, state what it replaces or simplifies — an addition that doesn't
  simplify something else is suspect. The reference system's worst moments were
  accumulation; its best moves were separations.
- **Surgical edits to the relevant file.** Concerns are separated on purpose:
  dialect problem → `dialect.md`, voice problem → `hosts.md`, word selection →
  `suggest_targets.py`, variety → the scene spec. Never rewrite role files for
  a one-off.
- **Fix the tool, not the personality.** When the tutor seems dumb, forgetful,
  or pushy, read the plumbing first — workflow logs, `knock_log.json`
  timestamps — before touching persona or prompts. (Reference case: "the tutor
  had no knowledge of my reply" was a same-tick multi-fire collision in the
  push queue — 100% plumbing.)
- **Structure freeze after bootstrap.** Rows of data are free; schema changes
  wait. Route build-itches to `docs/feature_inbox.md`. (Canonical in
  `docs/PROTOCOL_MAP.md`.)
- **Lightweight triggers for lightweight actions.** When a request is "fire the
  existing automation with one value," wire a shortcut/webhook one-liner —
  don't route it through a full chat session.
- **Calibration dials live in `progress/profile.md` → Calibration Notes** —
  coverage %, new-word counts, pacing. Change the parameter; never encode a
  dial's value in protocol prose or assistant memory.
- **A fade is palatability data, not a discipline failure.** Contact is king
  *only when the input is palatable and reliably varying*. When contact drops:
  diagnose the grating first (too dense? too contrived? same scenario
  re-run?); never answer a fade with accountability machinery.

## Settled design decisions

- **Absorption-first, then production-as-accelerant.** Pure comprehensible
  input plateaued; forced cold output toward the **viability floor** is the
  engine. Narrow and deepen; widen only after the floor.
- **One persistent tutor is the single interactive front door.** Default mode,
  no keyword. Text modalities are tools the tutor deploys; a tutor-menu
  orchestrator was tried and retired.
- **Continuity is prose memory, not a schema.** One running story carried in
  `learner.json`'s `last_debrief`/`soak_order`, rewritten cumulatively by the
  tutor. A thread-tracking schema (threads table, due-ness scoring) was built
  and **rejected**. Python computes the *menu*; the tutor makes the *choice and
  the meaning*.
- **Narrative-saga continuity rejected.** Serialized fictional plot rings
  hollow and fights "fresh situations, not repetition." Scenes are disposable
  one-use pegs. The one true narrative is the learner's own arc; **climax =
  mastery**.
- **Variety is structural, not taste.** The scene-spec gate (register / form /
  dramatic ingredient, divergence window 3) is a **gate, not a suggestion** —
  taste-based variety is how sameness drifts back. The Breakdown is **colour,
  not coverage** (never a glossary).
- **The Producer owns the dialect transformation.** The Architect writes
  plausible spoken register only; dialect rules never go in `architect.md`
  (rule-budget crowding there makes episodes drill-shaped).
- **Stop chasing listens.** The knock and each episode is a **self-contained
  dose**; no listen-reconciliation ritual, no "press play" nudges, no streak
  counters (a stored streak lies the moment a day is skipped). The
  low-friction chat/phone rep is the loop; audio is the immersion tank.
- **Knocks are read-only on session state.** They write only
  `knock_log.json`; learning state advances only through interactive reps
  (sessions, judged replies). Cold credit demands an *unrevealed* target —
  text the notification showed caps at hinted, enforced in code.
- **Outreach policy is the tutor's; Python holds only the rails.** Waking
  hours, daily cap, min gap = deterministic gate; whether/how/when = the
  tutor's decision, optimized for the learner *showing up*, never taps.
  Silence is first-class; the busy/back-off social contract is real signal.
- **Competent over local** (default register dial). Clear, correct standard
  colloquial first; "pass as a local" is the long game, not the entry bar.
- **Deck sprints for real deadlines.** A finite, informant-vetted deck is the
  headline meter while a date looms; the abstract floor climb resumes after.
- **Stories are curriculum (the lore pivot).** Anti-teacher bans
  over-corrected into a scenario monoculture; language-lore (etymology /
  kinship / myth / culture) is first-class *input* — an episode form, a chat
  tangent, a knock dose. Guardrails: gate-rotated like any form; no production
  debt; "No Academic Terms" bans terminology, never stories.
- **CI git identity is `github-actions[bot]`** — never a noreply alias that
  credits a real user.
- **The knock loop's honesty is computed, never remembered** (carried in at
  `template-v2-source`). The judge's reveal claims resolve against evidence
  Python derives from the log: `revealed_recently` (what was actually shown in
  48h of traffic), the chain **pin** (a follow-up moves the pin;
  `expected_target` is immutable so the log stays auditable), and the
  **coherence law** (pick the target first, write the body as its ask; a
  mis-targeted knock is void). Trusting the model's memory denied real colds
  and graded replies against questions never asked.
- **The capped lane breaks the hinted-forever trap** (carried in at
  `template-v2-source`). A cold-quality fire blocked only by the reveal window
  records as CAPPED; capped fires on 2 distinct local days graduate the word
  to cold. Without it, the very channel drilling a word daily could never let
  it escape hinted.
- **The project is named Sollu — சொல்லு, "say it!"** (2026-07-10). The repo slug stays
  `language-tutor`; the public name is the pedagogy in one imperative (forced output is
  the engine) and keeps the origin language the star of the language-agnostic template.
  Replaces the descriptive-only "language-tutor" as the project's face.
- **Volley targets are Python's; the tutor writes only the situations**
  (carried in at `template-v2-source`). The tutor's taste concentrates reps on
  the same headliners; a binding, recency-demoted menu keeps deck coverage
  honest. Same division as everywhere else: Python computes the menu, the LLM
  makes the meaning.
- **Per-segment loudness normalization to −16 LUFS (measured static gain)** (2026-07-11).
  Chirp3-HD voices across locales arrive up to 6 dB apart; the fr-CA guest in the welcome
  episode was audibly hot. Static gain per segment (ffmpeg loudnorm probe → volume filter)
  replaces per-voice hand-tuning. `render_audio.py → normalize_segment()`.
- **Google TTS language_code must match the voice's locale, derived per-voice** (2026-07-11).
  The API rejects a mismatch; a single config-wide `TTS_LANGUAGE_CODE` cannot serve a
  polyglot Voice Map (e.g. the welcome episode spans en-US, es-US, fr-CA, ta-IN). Fix:
  split the voice name on `-` to extract its locale. Root cause: multi-locale casts were
  silently falling back to the pool when the explicit Voice Map failed to render.
- **`clean_for_tts` must preserve periods** (2026-07-11). Stripping them renders long
  lines as breathless run-ons — Chirp3 uses sentence stops for pacing. Root cause was
  exposed by a ~120-word segment with no internal stops. `clean_memo_for_tts` already
  documented this rule ("memo prose needs them"); the dialogue path now matches.
- **Voice Map comment annotation breaks the regex** (2026-07-11). The header comment
  must read exactly `Voice Map:` followed immediately by the JSON object. Adding a
  parenthetical annotation — e.g. `Voice Map (Google Chirp3-HD):` — silently defeats
  the match and falls back to the tutor.json pool, wrong cast with no warning.
- **mp4 for GitHub uploads: 1 fps, `-g 9999`, no `-tune stillimage`** (2026-07-11).
  For a still-image video, `stillimage` tune forces every frame to be an independent
  I-frame (20 MB+). Correct approach: `-framerate 1 -g 9999` so only one I-frame
  exists and ~413 empty P-frames follow. CRF 18 at 1 fps lands ~5.6 MB with full art
  quality — under GitHub's 10 MB attachment cap.
- **Welcome episode framing settled** (2026-07-11). Engineer-author + keen-learner
  (not two skeptics; not "what does it optimize?"). Tamil is a worked example the
  repo was extracted from, not its origin. Core demo: four axes English doesn't encode
  (Tamil respect endings, Tamil inclusive/exclusive we, Turkish evidentiality, Japanese
  pronoun-avoidance). Montréal and Arabic beats cut for runtime (target 6:30 → 6:54).
- **Second milestone re-sync — carried in at `template-v3-source`** (2026-07-16;
  recorded 2026-07-19, backfilled — the sync pre-dated the reference impl's
  `/backport` distill contract). The engine advance since v2, re-applied
  semantically: knock_id reply correlation, fenced-JSON parse fallback,
  lore/eavesdrop cooldown guards, teach-first `introduces` + `is_unseen()`,
  pull-before-read status banner, delivery retry, deck-tier ordering (since
  re-seamed as `deck.tiers` config — next entry).
- **Third milestone re-sync — carried in at `template-v4-source`** (2026-07-19,
  run before the reference impl's public post; its sync policy triggers on
  sharing). The advance since v3, re-applied semantically: the fielding dose
  (heard question in, produced answer out — gated on the second voice), the
  KF-10 volley surface fix (volley_open_ask — whatever Python tracks, Python
  says), the campaign (profile block + digest + seed orders), the mandate
  subtraction (including the lore-preference-line deletion the v3 sync missed),
  Teach Beat + Play canon, the minimum-law daily_session (session_tools.md
  deleted — absorbed), narrated_drama as a commissioned batch-soak form, the
  tier-0 deck headline, SFX-as-air, _vN feed resolution, the ticket crash
  guard, /recalibrate + the tutor intent gate + one-owner command safety +
  KF-9/10, prose budgets (measured, ~5–8% headroom), and smoke parity s14–s23 —
  closing the v3 gap where mechanisms shipped without their regression cases.
  **Known gap, deliberate:** the sidecar-claims-payload law has no
  deterministic home here (the template's studio is agent-dispatched; the
  reference impl enforces it in run_studio.py's lint) — it lives as producer.md
  prose, first suspect if payload stamps misbehave. Also left behind: the
  studio watchdog and the lunch anchor (learner/local pack), /backport
  (reference-impl side).
- **Learner-dependent surfaces are setup-time elaborations, not template
  opinions** (2026-07-16). When a backported feature's value depends on the end
  user (deck tiers were the instance: whether registers have a pecking order is
  the learner's reality), the template ships the *mechanism* behind a config key
  plus a worked example in SETUP.md as grist for the setup agent — never the
  reference impl's concrete values hardcoded in a script. Replaces the
  half-Tamil DECK_TIERS map that rode in with the 07-16 backport.
