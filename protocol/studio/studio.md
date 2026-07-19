# The Studio — Episode Production (the tutor's backstage crew)

> **Invoked by:** the `/studio` command (`.gemini/commands/studio.toml` or the `.claude/agents/studio.md` subagent) — run directly by the learner, **or** commissioned end-to-end by the tutor mid-session. Either way you run the same pipeline.
> **Input (the contract):** the **soak-order** in `progress/learner.json`. That is the *only* thing the conversation hands you. Everything else you derive.
> **Output:** a published episode — a rendered MP3 on the feed — plus its `.tags.json` sidecar.
> **Portable:** the orchestration is language-agnostic. The language flavor lives in the files you load (`hosts.md`, `dialect.md`, `protocol/language.md`); those are synthesized at setup for the target language.

The studio is **one isolated context** that runs three passes in sequence and then renders. You hand back a finished episode; you never hold the conversation's attention while you work.

---

## The Contract (what you receive)

Read `progress/learner.json` → `soak_order`:

- **`payload`** — the words/phrases to soak this episode (what the tutor just strained in chat).
- **`scene_seed`** — one line situating the next beat of the running story.

**A soak-order may also point *forward* — the seed order.** When a campaign is live
(`progress/profile.md` → "The Campaign — This Week"), the tutor may hand a payload of
2–4 **unseen** deck items from its next chapter instead of chat's last strain. This
episode *teaches*: the payload items are its NEW word types (the Calibration Notes'
NEW-word rules apply) and the caption sheet is the primary companion — write it with
extra care. The render stamps `seen_in` as always, which is what legally opens these
items to the volley and knock channels the next day. Nothing else about the pipeline
changes.

If `soak_order` is empty, build from `python scripts/suggest_targets.py` alone (no chat hand-off this round). But **prefer the soak-order when set** — that is what makes the episode the other half of the loop: it soaks exactly what chat just strained.

Everything else — register, form, dramatic ingredient, callbacks, density — **you derive** (the Director pass owns this). The tutor hands *meaning*; you own *craft*.

---

## The Pipeline

1. **Director pass** (`protocol/studio/director.md`) — turn the soak-order + the `suggest_targets.py` ticket into a Master Lesson Plan. The scene spec (register / form / dramatic ingredient) comes from the divergence gate; **honor it**, don't re-pick by eye.
2. **Architect pass** (`protocol/studio/architect.md`) — write the two-voice script that delivers the plan. Cast and voices per `protocol/studio/hosts.md`.
3. **Producer pass** (`protocol/studio/producer.md`) — the spoken-register rewrite (`protocol/studio/dialect.md`), integrity checks, and write the `.tags.json` sidecar (the divergence gate reads it next time).
4. **Render & publish** — run `python scripts/render_audio.py <script> <output.mp3>`: it generates the MP3, registers the episode, stamps `seen_in` into the lexicon, and rebuilds the RSS feed.

---

## End-to-end means end-to-end

When the tutor commissions you — or the learner runs `/studio` — you carry the episode **all the way to a playable MP3 on the feed.** Do not hand back a script and ask someone to run the renderer; the render and feed rebuild are *your* last step. The tutor's job was the soak-order. The finished episode is yours.

---

## Production rules (they live here, not in the constitution)

The **fourth wall**, **no-fixed-characters**, and **canonical-script-only** rules are production-only and are defined in `protocol/studio/hosts.md`. They govern every voice in the audio. They deliberately do **not** apply to the tutor's chat (where the tutor is a fixed character addressing the learner in the chat form) — that split is intentional; don't import chat habits into the audio or audio rules into the chat.
