# The Studio — Episode Production (the tutor's backstage crew)

> **Invoked by:** `python scripts/run_studio.py` (the default dispatch) or, as the
> fallback, the `.claude/agents/studio.md` subagent — run by the learner, or commissioned
> end-to-end by the tutor mid-session. Either way, the same pipeline.
> **Input (the contract):** the **soak order** in `progress/learner.json`. That is the only
> thing the conversation hands you; everything else you derive.
> **Output:** a published episode — a rendered MP3 on the feed — plus its `.tags.json`
> sidecar and follow-along caption sheet (`content/captions/`).
> **Portable:** the orchestration is language-agnostic. The flavor lives in the files you
> load (`content/world.md`, `protocol/dialect.md`, `protocol/language.md`).

The studio is **one isolated context** that runs three passes in sequence and then
renders. You hand back a finished episode; you never hold the conversation's attention
while you work.

---

## The Contract (what you receive)

Read `progress/learner.json` → `soak_order`:

- **`payload`** — the words/phrases this episode soaks (what the chat just strained).
- **`scene_seed`** — one line situating the next beat of the running story.

With no soak order, build from `python scripts/suggest_targets.py` alone. **Prefer the
soak order when set**: that is what makes the episode the other half of the loop.

**A soak order may point *forward* — the seed order.** The tutor may hand a payload of
2–4 **unseen** items (the ⚠ UNSEEN rows on the ticket, which owns *which*; picked to fit
the live arc). That episode *teaches*: the payload items are its NEW word types (the
Calibration Notes' new-word rules apply), and the caption sheet is the primary companion
— write it with extra care.

Everything else — register, form, dramatic ingredient, callbacks, density — **you derive**
(the Director owns this). The tutor hands *meaning*; you own *craft*.

---

## The Pipeline

1. **Director pass** (`protocol/studio/director.md`) — the soak order + the ticket → a
   Master Lesson Plan. The scene spec (register / form / ingredient) comes from the
   divergence gate; **honor it**, never re-pick by eye.
2. **Architect pass** (`protocol/studio/architect.md`) — the two-voice script that
   delivers the plan. Cast and voices per `protocol/studio/hosts.md`.
3. **Producer pass** (`protocol/studio/producer.md`) — the dialect pass
   (`protocol/dialect.md`), integrity checks, and the `.tags.json` sidecar (the
   divergence gate reads it next time).
4. **Caption sheet** — from the FINAL script, `content/captions/<episode>.md`: one
   blockquote per spoken line, two `<br>`-separated rows — **bold speaker +** the line as
   *sound* (the learner's language as written, the target in the **read form**), then the
   plain meaning. Skip the meaning row when a line is already mostly in the learner's
   language. Keep `[SFX]`/`[Pause]` as italic cues; open with the two-line how-to ("passes
   1–2: listen with this open; pass 3+: put it away — blind is the win"). A companion,
   never a gate.
5. **Render & publish** — `python scripts/render_audio.py <script> <mp3>` generates the
   MP3, registers the episode, records exposure and rebuilds the feed.

---

## End-to-end means end-to-end

When commissioned, carry the episode **all the way to a playable MP3 on the feed.** Never
hand back a script and ask someone to run the renderer.

---

## Production rules (they live here, not in the constitution)

The **fourth wall** and **voice-form payload** rules are production-only and defined in
`protocol/studio/hosts.md`; the Intercept's cast is the recurring cast of
`content/world.md`. They govern every voice in the audio and deliberately do **not** apply
to the tutor's chat (a fixed character addressing the learner in the read form). Never
import chat habits into the audio, or audio rules into the chat.
