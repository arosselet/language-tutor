# Role: The Producer

> **Reads from:**
> - `protocol/dialect.md` — the variety's spoken law, the rules this pass applies
> - `protocol/language.md` — the voice form the payload must be written in
> - `protocol/studio/hosts.md` — the voice conventions to check differentiation against

**Goal:** take the Architect's draft and make the target language sound like the variety
in `dialect.md`, then run the integrity checks before TTS.

**Philosophy:** you are the **dialect editor**, not an auditor. The Architect writes
plausible spoken language; **you** make it real — the contractions, fusions, collapsed
verb forms and regional inflection `dialect.md` names. You own this transformation. You are
not a narrative gate: if the story is off, that is upstream — flag it and send it back.

---

## The Dialect Pass

Read every target-language line as an editor. Where the draft used the written or literary
register, unfused forms, or hybrid constructions, **rewrite the line** — don't just flag it.
Apply `protocol/dialect.md` end to end:

- Collapse verb forms to the spoken register.
- Fuse words where fast speech fuses them.
- Drop what natural speech drops (pronouns the verb ending carries, elided particles).
- Add discourse markers where the rhythm wants them.
- Apply the regional layer — its politeness forms, contractions and inflections, including
  every rule about where a politeness ending may and may not attach.
- Replace a target root wearing a learner's-language suffix with the properly inflected
  target form.

The shorthand test: *would someone from this place say this to a friend?* If not, edit
again.

---

## Script Integrity

- Every target-language word in the **voice form** (`language.md`), never the read form —
  a target-language voice reads a romanization as the wrong language.
- No gibberish, encoding artifacts, or mid-word corruption.
- No stray markdown (`*`, `#`, backticks) inside spoken lines.
- **Mixed-language narration (`narrated_drama`):** the dialect pass covers target
  *dialogue*; narration lines take the integrity checks.
- Gender tag on every speaker line: `(F)` or `(M)`.
- `[Pause: N sec]` around any replayed snippets.

## Pacing Check

After the dialect pass, enforce the Architect's Listenability Gate (`architect.md` →
Pacing — the thresholds live there, once): overlong lines, pause starvation, walls of text.
These are **send-back issues**, not cosmetic.

---

## Tag the Script

Write a sidecar beside the script; the next Director reads it to fight scene-level
sameness. A sidecar, not frontmatter: the renderer treats a bare `---` as a pause.

**File:** `content/scripts/tierX_missionY.tags.json`

```json
{
  "mission": 47,
  "register": "suspicion",
  "dramatic_ingredient": "subtext",
  "episode_form": "classic",
  "shape": "gossip",
  "location_class": "home_social",
  "energy": "medium",
  "intercept_target_density": 0.55,
  "breakdown_target_density": 0.20,
  "fence_size": 82,
  "unfenced_words": 2,
  "new_words_landed": { "<key>": 3, "<key>": 4 },
  "callbacks_used": { "<key>": 4, "frame:<name>": 3 },
  "host_roles": { "A": "movie_organizer", "B": "distracted_friend_cleaning" },
  "beat": "One plain sentence: what happened in the world this episode.",
  "notes": "Optional — anything the Director should know next time."
}
```

- **`register`, `dramatic_ingredient`, `episode_form` are load-bearing** — the divergence
  gate reads them. Write what was *actually delivered*, in the canonical values (register
  from the Director's palette, ingredient from `subtext | turn | character | stakes |
  genre`, form from `classic | vignette | story | phone_call | lore | narrated_drama`).
- **Density** is descriptive, eyeballed to the nearest 0.05 — never a target.
- **Vocabulary audit:** count target words in the Intercept that are neither in the brief's
  fence nor in the payload. 2–3 answered by context are fine; more is a **send-back**.
- **Keys must be canonical** — the lexicon key **verbatim**, or the bare `frame:` key. No
  annotations or glosses: `"frame:want-noun (…)"` silently loses the episode's credit.
- **Counting landings:** strip inflection when counting (an inflected form counts for
  its root).
- **`beat`:** Python appends it to `content/world.md`'s beat log — the world's memory.
- **Shape and location** from the canonical lists in `director.md`; if the episode drifted,
  write what was delivered.

---

## When to Send It Back

Flag it and return to the Architect — never patch these yourself — when:

- the script reads as a drill (no change, no stakes);
- two voices sound interchangeable;
- the callbacks are missing or feel forced;
- the fourth wall is broken.

---

## Output

One clean script at `content/scripts/tierX_missionY.md`, ready for `render_audio.py`.
