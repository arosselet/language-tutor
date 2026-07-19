# Surgical-Edit Routing Table

Companion to `/extend` Gate 5. Find the concern you are touching; edit **only that file**.
If a file is missing, stop and report — do not create a substitute.

| Concern | File | Notes |
|---|---|---|
| The tutor's persona voice, stake framing, "What the tutor Never Does" | `protocol/persona.md` | Synthesized at setup; edit surgically, keep the fixed sections |
| The language's letter of the weave + modality split, register, lore veins | `protocol/language.md` | Synthesized at setup |
| Spoken-register / dialect transformation rules | `protocol/studio/dialect.md` | Producer applies; never put dialect rules in `architect.md` |
| Podcast cast names and regional voice identity | `protocol/studio/hosts.md` | Script-only rules live here (fourth wall, no ad-libs) |
| Word selection ticket (floor-gap targets, engines, new candidates) | `scripts/suggest_targets.py` | |
| Scene-spec divergence gate (register / form / dramatic ingredient) | `scripts/suggest_targets.py` | `scene_spec()`; the REGISTERS/FORMS/INGREDIENTS palettes are safe to re-flavor |
| Session law (invariants, shapes, campaign contract, close mechanics) | `protocol/daily_session.md` | Minimum-law: the shapes and one-line moves live here; there is no separate formats file |
| Pedagogical law and canonical rules (Fresh Execution, Contrast Beat) | `protocol/constitution.md` | Universal law — language-specific examples belong in `language.md` |
| All state writes to `progress/*.json` | `scripts/sync_state.py` | Never hand-edit Python-owned JSON directly |
| Pedagogy feels wrong (chore/drill/samey) | `/recalibrate` | Felt signal → ledger → evidence → at most one move |
| Language/learner/deployment constants (script regex, voices, repo URL, rails, volley size) | `config/tutor.json` via `scripts/config.py` | Port surface — see `/extend` Gate 6 |
| Outreach rails (waking hours, daily cap, min gap) | `config/tutor.json` → `outreach.*` | Read by `morning_knock.py` |
| Outreach decision prompt (the tutor's fire/silence policy prose) | `scripts/morning_knock.py` → `OUTREACH_MANDATE` | Policy is the tutor's; Python holds only the rails |
| Knock reply judge prompt (grades, reveal caps, chains) | `scripts/knock_reply.py` → `JUDGE_MANDATE` / `CATCH_JUDGE_MANDATE` | Language rules enter only via config fragments |
| Drill script prompt (cue/answer format) | `scripts/render_drill.py` | Same config-fragment rule |
| Episode TTS voice pools | `config/tutor.json` → `tts.voices` | Local-render only; cloud never calls this |
| RSS feed structure | `scripts/rebuild_rss.py` | `rss.xml` is the only feed; pubDates are preserved across rebuilds |
| Calibration dials (coverage %, new-word counts, pacing) | `progress/profile.md` → Calibration Notes | Change the number, not a prompt or protocol prose |
| Spaced-repetition callback generation | `scripts/generate_callbacks.py` | The INTERVAL_DAYS table is a legitimate dial |
| Scheduled push composition and queue drain | `scripts/push_queue.py` | `drain --dry-run` previews without firing |
| Smoke-test regression cases | `scripts/smoke_test.py` | Add a case the day a bug is fixed — never ad-hoc scripts |
