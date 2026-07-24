# Feature Inbox — build-itches parked, not acted on

The structure freeze (`docs/PROTOCOL_MAP.md`) routes every mid-session build
itch here instead of into the codebase. Each entry: the itch, the evidence,
and what it would replace. The diagnosis pass (`protocol/diagnosis.md`)
promotes an entry only when a *reproduced* pattern demands it — and the
learner says yes.

*(empty — good)*

- **Clock-bound requests must schedule, not just acknowledge** (from Tamil, 2026-07-24 —
  queue for the v5 milestone re-extraction, do not per-fix). `knock_reply.py`'s judge
  mandate here still reads `SCHEDULING (optional)… null to skip, which is usual`, and
  routes learner steering into `meta_note`. In Tamil this cost a real request: the learner
  asked for a timed dose, got a warm acknowledgement, and nothing was queued — the mandate
  had told the model scheduling was usual to skip. The fix (mechanism, no language content):
  a `wants_scheduled_push()` detector that forces ONE re-ask when a time-bound request
  comes back with `schedule:null`, plus a mandate change making a clock-bound ask MANDATORY.
  Note the seam: the request-language patterns (time/ask words) are a base-language slot,
  not hard English. Carries its own smoke case. Also fold in ffprobe-first feed durations
  (`rebuild_rss.py` uses mutagen's `audio.info.length`, inaccurate for raw
  frame-concatenated TTS MP3s — same "honest meters" reason).

- **Port a language-agnostic studio DRIVER — the colloquial-drift cooker** (from Tamil,
  2026-07-24; the higher-value one — surfaced by Andrew asking "if someone sets up
  Malayalam, will it elaborate a new studio?"). Today the template ships the three-pass
  studio as DESIGN — `protocol/studio/{director,architect,producer,studio}.md` (mechanism)
  + `dialect/hosts/persona/language` slots — but no `run_studio.py`, because the Tamil
  driver was welded to `agy` (a local CLI), correctly bucketed personal/local. So a new
  language (Malayalam, Arabic, Bengali, literary-vs-spoken Hindi — the diglossic languages
  that most NEED colloquial-drift handling) gets the recipe and no cooker. The unblock:
  Tamil's 2026-07-24 executor-agnostic writer + `inline_canon()` — a single-shot OpenRouter
  pass that carries `protocol/studio/*.md` INTO the prompt instead of needing an agent to
  read them off disk. That is precisely a portable driver: no `agy`, reads the template's
  own protocol files + the filled language slots. Port it as the studio driver (the `agy`
  path stays a source-repo optimization). Makes episode production real for every
  colloquial-drift instance, not just Tamil. A v5+ milestone, its own focused pass; needs
  the bootstrap to wire the writer key + GCP render secret and confirm the Spanish fixture
  can produce end-to-end.

- **A `/distill` skill for template users** (2026-07-19, v4 sync observation): the
  DECISIONS header says "append your own as they settle," but the wrap-up ritual
  behind it lives only as a global skill on the reference impl's machine. A
  generalized `/distill` (harvest a session's settled conclusions into
  docs/DECISIONS.md; empty wrap-up is valid) would make the repo-is-the-memory
  discipline portable. Cheap; decide at next sync.
