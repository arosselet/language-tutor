# Protocol: Cast & Voices

> **Read by:** `protocol/studio/architect.md`, `protocol/studio/producer.md`,
> `protocol/studio/director.md`
> **Defines:** the speaking roles across every episode. Who the people are — names,
> voices, the two analysts — lives in `content/world.md`; this file holds the conventions.

Two episode segments, each with its own voices.

---

## The Intercept — the world's cast

**The Intercept is performed by the recurring cast** of `content/world.md`: who they are,
how each one talks, and the TTS voice pinned to each. The learner is an observer of their
world, never an addressee.

**Tagging convention:** the character's name plus a gender marker — `**<Name> (F):**`,
`**<Name> (M):**`. The gender tag is always present; the renderer requires it.

**Do not write a Voice Map.** Python reads the pins out of the canon and injects the block
itself (`scripts/world.py`). A voice table retyped each episode drifts, and the ear tracks
a *speaker* before it tracks a word.

**The register differences are the teaching instrument**, and they live in the canon: an
elder's older forms, a terse speaker, a fast one, a young one swallowing every ending. Two
characters who sound interchangeable is a defect.

**A world, not an arc:** a fixed cast and geography where things happen and nothing has to
resolve. The divergence gate still governs every episode's variety.

---

## The Breakdown Analysts

Two named analysts (named in `content/world.md`) appear in every Breakdown segment — and
**lead the `lore` form end to end** (their deep-dive *is* the episode: a payload word's
history, kinship, myth, culture). In a Breakdown they talk **to each other** about the
Intercept they just heard — playing back snippets, joking about the characters' choices,
unpacking the NEW words in context.

- **One analyst:** sharp, pattern-focused; loves the "why" and the rule underneath.
- **The other:** warmer, story-focused; connects language to place and people.

**Tagging convention:** `**Analyst <Name> (F):**` and `**Analyst <Name> (M):**`

---

## The Drama Cast (`narrated_drama` only)

One **Narrator** plus up to 2–3 in-scene voices, every line gender-tagged. The Narrator
speaks the learner's language as scaffolding, second person, present tense — and that
"you" addresses the **protagonist inside the story**, never the listener: "you squint at
the screen" is in-world narration; "you learned this last week" is a fourth-wall break
and a send-back. The voice-form rule binds the Narrator's embedded target language with no
exception.

---

## Rules That Apply to All Voices

- **Fourth wall stays up.** No addressing the listener, no meta-narration about the
  learner's state or activity. Canonical here — production-only.
- **Target language in its voice form only** — `config/tutor.json` → `language.audio_form`
  (`pack.AUDIO_FORM`), never the read form. Canonical here — production-only (the chat
  uses the read form by design).
- **Gender tag on every speaker line.** `(F)` or `(M)` always present — the renderer
  requires it.
