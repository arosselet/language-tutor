# Glossary

Each term gets one line and the file that defines it. If a term here and its file
disagree, the file wins and this line gets fixed.

| Term | Meaning | Owner |
|---|---|---|
| **pack** | `config/tutor.json` as read by `scripts/pack.py`. The language and learner scalars | `scripts/pack.py` |
| **prose slot** | A synthesized file (persona, user, stake, contract, language, dialect, exemplars, world, word pool) shipped as a `.template` | `pack.PROSE_SLOTS` |
| **example slot** | One target-language line spliced into a prompt (`$NAME`); at most 8 | `pack.EXAMPLE_SLOTS`, `scripts/mandates.py` |
| **read form / voice form** | How the learner *reads* the target (e.g. romanized) vs how a *voice* is given it (e.g. native script) | `language.chat_form` / `audio_form` |
| **declared span** | ⟦ ⟧ around target text in a shared-script language; stripped before display and TTS | `pack.unmark` |
| **voice canon** | persona + user + dialect, shipped to every pass that writes or judges a line | `writer.voice_canon` |
| **stake** | The payoff the learning is for (a reveal, a trip, a wedding) and its ops | `protocol/stake.md` |
| **informant** | The learner's trusted native speaker: vibe checks, never an examiner | `protocol/constitution.md` |
| **world** | The fictional, recurring canon: place, cast with pinned voices, standing facts, the month's arc | `content/world.md`, `scripts/world.py` |
| **arc / month** | One month of the world's life, its finale an ear test | `scripts/month.py`, `profile.md` → The Arc |
| **timeline / phase** | The schedule between today and the stake's date; a phase sets the lean, the ear ramp and the intake cap | `scripts/timeline.py`, `config.timeline` |
| **ledger** | `observations.json`: every observation as an event (taught / attended / exposed / tested / claimed) | `scripts/observations.py` |
| **the fold** | The lexicon's evidence fields, derived from the ledger by one writer | `scripts/lexicon_view.py` |
| **Teach Beat** | The one open-handed first contact before anything may quiz a word | `protocol/daily_session.md` |
| **the sweep / Receptive Check** | Asking what the learner knows, row by row, so the picture stays true | `protocol/daily_session.md`, `receptive_check.py`, `render_sort.py` |
| **ticket** | The menu Python hands the tutor at session start | `scripts/suggest_targets.py` |
| **soak-order** | The one interface from chat to production: payload + scene seed + channel | `learner.json`, `protocol/studio/studio.md` |
| **slip** | A recurring error on the slip ledger, with escalation and close | `scripts/slips.py` |
| **knock** | A between-session reach to the phone, decided by the tutor inside the rails | `scripts/morning_knock.py` |
| **rails** | The reach budget: waking window, daily cap, minimum gap | `scripts/rails.py` |
| **commission** | An ordered dose, claimed one per tick | `scripts/commissions.py`, `protocol/commissioning.md` |
| **rotation / soak / drill** | The audio lanes: a cadence of movements / passive repetition / spoken volleys | `scripts/render_*.py`, `protocol/audio_channels.md` |
| **payoff** | An overheard tape, handed back with its meaning after every line | `scripts/render_payoff.py` |
| **module** | core / audio / phone / timeline; switched in `config.modules` | `pack.module_on` |
| **ratchet** | A smoke law that only tightens: budgets, prohibitions, no learner or language in mechanism | `scripts/smoke/cases_laws.py` |
