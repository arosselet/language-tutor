# Customization Map — where everything lives, and which dial to turn

Everything the setup agent synthesized keeps living in plain files you (or your
`@build` hat) can edit. This is the map: what each file owns, and the *right*
place for each kind of change. The companion discipline is `docs/DECISIONS.md`
— read it before structural changes.

## The one rule about dials

**Calibration dials live in `progress/profile.md` → Calibration Notes** —
coverage %, new-words-per-session, pacing, session length. Change the
parameter there; never encode a dial's value into protocol prose, persona
text, or code. Protocol files say *"read the dial in profile.md"*; only
profile.md says the number.

## File-by-file

### `config/tutor.json` — the machine's language pack
| Key | Owns | Typical tweaks |
|---|---|---|
| `learner.timezone` | knock rails, "Now:" clock | moved? change it here only |
| `language.script_regex` | canonical-key check (null = same script) | rarely touched after setup |
| `language.chat_form / audio_form / weave_rule / register_note` | the ONLY channel language rules reach the Python one-shot prompts (knock, judge, drill) | sharpen wording if phone judging misreads your typing |
| `tutor.voice_id` | the tutor's one pinned voice | re-pin if the voice grates — then keep it pinned |
| `tts.*` | provider, language code, voice pools | add voices as providers ship them |
| `tts.eavesdrop_voice` | the second pinned voice for eavesdrop tapes (the overheard caller) | set it to enable the catch-axis knock; empty = modality off |
| `feed.*` | podcast identity + repo for CDN/RSS URLs | rename your feed |
| `outreach.*` | waking window, daily cap, min gap, LLM model | make knocks quieter/louder; swap models |
| `outreach.volley_size` | deck items per volley knock (the daily blitz) | raise it when the deck's burn rate trails the deadline |
| `deck.*` | sprint name/label/deadline | set when a real date appears; clear after |

### `protocol/` — the pedagogy and the people
| File | Owns | Tweak when |
|---|---|---|
| `constitution.md` | universal law (weave principle, no-academic-terms, lore rule, invisible assessment) | almost never — it's the settled pedagogy |
| `language.md` | *your language's* letter of the weave + modality split, register, lore veins | the informant corrects a derivation; your register goal shifts |
| `persona.md` | who the tutor is, the stake, voice lines, masks, never-does | the persona drifts or the stake changes (new trip, post-reveal) — edit surgically, keep the fixed sections |
| `daily_session.md` | the session choreography + close/log contract | rarely; it encodes the loop that works |
| `session_tools.md` | the five in-session formats | add/prune a format the tutor actually uses/never uses |
| `diagnosis.md` | how feedback becomes change (dial > prune > propose) | almost never |
| `studio/hosts.md` | the cast | recast names/personalities |
| `studio/dialect.md` | written→spoken transformation rules | **most-edited file in the pack** — sharpen every time the informant flags textbook-ese |
| `studio/director.md / architect.md / producer.md` | the production passes | engineering changes only (`@build`) |

**Surgical edits to the relevant file.** Dialect problem → `dialect.md`. Voice
problem → `hosts.md`. Word selection → `suggest_targets.py`. Scene variety →
the scene-spec palettes. Never rewrite a role file for a one-off.

### `curriculum/` — content the tutor draws from
- `word_pool.json` — the someday-list of glue words (schema in its
  `.example`). Add rows freely; the ticket surfaces thin clusters. Rows of
  data are always free.
- `deck.json` (any name) — a finite sprint set loaded via
  `sync_state.py seed-deck`. The file is the source of truth: edit it and
  re-seed; removals un-tag cleanly.

### `progress/` — the learner's brain (Python-owned)
Never hand-edit the JSON — `sync_state.py` owns all writes (`update`,
`add-word`, `add-pattern`, `seed-deck`, `feedback`, `knock-response`). The one
hand-edited file is **`profile.md`** — the tutor's own teacher's notebook:
goal, gaps, coverage map, **Calibration Notes**.

### `scripts/` — the engine (`@build` territory)
Entry points: `sync_state.py` (state), `suggest_targets.py` (the ticket +
scene-spec gate — the REGISTERS/FORMS/INGREDIENTS palettes at its top are the
variety vocabulary and safe to re-flavor), `generate_callbacks.py` (spaced
repetition; the INTERVAL_DAYS table is a legitimate dial),
`render_audio.py`, `render_drill.py`, `rebuild_rss.py`, `show_status.py`,
`morning_knock.py` / `knock_reply.py` / `push_queue.py` (the phone loop),
`smoke_test.py` (run after any engine change). All language/learner constants
route through `scripts/config.py` → `config/tutor.json`; if you find yourself
hardcoding a language fact in a `.py`, stop — it goes in config or the pack.

### `.github/workflows/` — the ticks
`tutor-knock.yml` (outreach tick — every 2h; the rails do the precise
filtering, so trimming the cron is optional frugality), `push-queue.yml`
(30-min drain), `log-knock-response.yml` (phone taps/replies in),
`smoke.yml` (regression net on push). Secrets: `OPENROUTER_API_KEY`,
`PUSH_WEBHOOK_URL`, `GCP_SA_KEY` (google TTS only).

### Shells
`.claude/skills/tutor` + `.claude/skills/setup` + `.claude/agents/studio.md`
(Claude Code) and `.gemini/commands/*.toml` + `.gemini/GEMINI.md` (Gemini) are
**thin shims** — substance stays in `protocol/` so any agent behaves
identically. Renaming the `/tutor` skill to your persona's name is encouraged.
The `@build` playbooks (`.claude/skills/orient|debug|validate|extend|verify`)
are plain markdown any agent can read; they are the guard rails that keep the
machine lean — reach for them before engineering work.

## Suggested first customizations (after a week of use)

1. **Sharpen `dialect.md`** with everything your informant winced at.
2. **Tune the knock rails** to your real day (`outreach.*`).
3. **Re-flavor the scene-spec palettes** (`suggest_targets.py`) to your world —
   locations and shapes you'll actually inhabit.
4. **Prune session tools** the tutor never reaches for; the system's best
   moves are subtractions.
5. **Start `docs/DECISIONS.md` entries of your own** — every settled argument
   with yourself goes there so no future session re-litigates it.
