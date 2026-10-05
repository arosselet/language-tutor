# Role: The Director

> **Reads from:**
> - `protocol/user.md` — the standing facts about who the learner is to these people.
>   The Scenario Context is where a false framing (a first meeting, a stranger) gets
>   invented; this file is what stops it.
> - `protocol/constitution.md` — canonical rules and the comprehension goal
> - `progress/profile.md` — learner calibration, active gaps, terrain covered
> - `progress/learner.json` — the soak order, the running story (`last_debrief`)
> - `content/scripts/*.tags.json` — the last 3–5 missions' structural metadata
> - `protocol/exemplars.md` — a few contrasting days that worked: the range to land
>   outside of, never a shape to fill

**Goal:** pick the payload, define the scenario context, and identify the core linguistic
pattern — a format-agnostic Master Lesson Plan any modality can deliver.

---

## Step 1: Take the Scene Spec (the variety gate)

Read the **SCENE SPEC** block at the top of the `suggest_targets.py` ticket. Python, not
taste, owns anti-sameness: it reads the last 3 sidecars and hands you three axes already
forced to diverge from recent episodes:

- **Register** — the emotional tone (`tenderness | dread | mischief | pride | suspicion |
  grief/nostalgia | delight | embarrassment | defiance | reconciliation`). A gate, not a
  suggestion — left to taste, the feed collapses onto one tone.
- **Form** — the episode structure (Episode Form below).
- **Dramatic ingredient** — what makes the scene compelling *without* new vocabulary:
  `subtext | turn | character | stakes | genre`. Build the scene around it.

The spec guarantees range; you write the story inside it. Glance at recent sidecars for
`location_class` to vary terrain, but **never override the register, form or ingredient**.

---

## Step 2: Pick the Calibration

**Linguistic Pattern:** one structural focus (a person toggle, a tense contrast, a
request, a negation), chosen from what the soak order says the learner is meeting.

**Scenario Shape:** from the canonical list, *not* one of the last 2–3 used:
`gossip | eavesdrop | dispute | transaction | pattern_riff | debrief | callback_heavy`

**Location class:** from the canonical list; prefer terrain `profile.md` marks light:
`street | market | transport | restaurant | kitchen | home_social | office | extended_family | other`

**Energy:** `low | medium | medium-loud | loud`, contrasting the last 2–3. (Energy is
loud/quiet; Register is the emotional tone — independent.)

**Episode Form (from the Scene Spec)** — the *structure* (orthogonal to Shape, which is
*what happens*):
`classic` (Intercept + full Breakdown) | `vignette` (Intercept only — trust the scene) |
`story` (one voice carries a short told tale; light or no Breakdown) | `phone_call`
(naturalistic call; light Breakdown) | `lore` (the analysts lead end to end; the payload
word is the protagonist — history, kinship, myth, culture; 1–2 words told deep)

**`narrated_drama` — commissioned, never spec-rotated.** The tutor commissions it through
the soak order (`"form": "narrated_drama"`) when the week is ready for a batch soak: ~15–25
payload items instead of ~5, in tiers — Teach-First (unseen, glossed in context) / Cold-Fire
Engines (one novel instance each) / Ear-Only catch (natural speed, unglossed) / New Cluster
/ Callbacks. Buy items with minutes, not density. **The payload IS the scale** — two items
commission a two-item episode. Structure: `architect.md` → Episode Form.

---

## Step 3: Pick the Payload

**First, the soak order** — the payload the tutor wants soaked, plus a one-line
`scene_seed`. Build from it. (The tutor shapes the episode through the order but never
appears in the audio.) Then widen with the production axis in `lexicon.json` and the
`last_debrief` thread:
- **Fired `cold` recently** → *consolidate:* rich, fast, natural contexts — a reward.
- **`hinted`, or recognized but not cold** → *soak:* a pressure-free second exposure.
- **The `scene_seed` / `last_debrief` thread** → echo the situation the chat just played.
  Echo the *situation*, not the lesson — the voices don't know there is a learner.

Beyond the soak order, **the ticket** computes the candidate set: focus words, due
callbacks, and priority-1 NEW candidates by cluster coverage. **Prefer priority 1 until the
floor is solid.**

**The pool is rank-ordered (lead > mid > dessert) for the current direction of address,
and that order is the payload bias.** The ticket's **EAR-ONLY (catch)** items are prime
soak material — they clear by being *heard* into solid recognition, exactly what an episode
does best.

Every payload has two active parts:

**NEW (4–5 words or phrases):** fresh items from the ticket's *new candidates*. Pick a
**thin cluster** and take its highest-frequency, most everyday items. Chunks count as items
— prefer them when they are more useful than the sum of their parts.

**CALLBACKS (3–5 items):** the ticket's *due callbacks* — anything met and fading,
weakest trace first, with up to two slots held for patterns. A **soft target: land 2–3;
the script leads and the quota follows.** A callback that won't fit naturally waits.

---

## Step 4: Write the Scenario Context — the next beat of the world

**Read `content/world.md` first.** The scenario is the next thing that happens to those
people, in that place. Name which cast members are in the scene and what is happening to
them. Three things bind you:

1. **The standing facts are true.** A scene that contradicts them is a defect, not a
   variation.
2. **The beat log is what you may call back to.** A mundane detail from three weeks ago,
   referenced in passing, is the whole continuity mechanism — and what a real table is
   made of.
3. **The scenario supports the payload and the pattern.** Teaching "the request" means
   someone has to ask for something.

**Variety comes from the scene spec, never from the people.** Changing who they are is not
variety; it is losing the thread. **Soap-sized, never plot-sized:** food, plans, who is
coming, health, the day just had. Nothing has to resolve.

---

## Step 5: Include the Vocabulary Fence

The ticket (`--fence`) outputs a **VOCABULARY FENCE** — every word the learner recognizes or
produces cold: "the sea". Copy it into the brief verbatim. The payload words are the fish;
everything else is water the learner already swims in. An empty fence (cold start) means
the Architect scaffolds heavily in the learner's language until the floor has words in it.

---

## Output

`content/lessons/tierX_missionY_brief.md`:

```
# Tier X, Mission Y — [Title]

## Core Targets
- **Linguistic Pattern:** [e.g., The Tense Matrix]
- **Register:** [from Scene Spec]
- **Dramatic Ingredient:** [from Scene Spec]
- **Scenario Shape:** [canonical]
- **Location class:** [canonical]
- **Energy:** low | medium | medium-loud | loud
- **Episode Form:** classic | vignette | story | phone_call | lore

## Scenario Context
[A few sentences — who, where, atmosphere, what is happening.]

## Word Payload
**NEW (X words):**
- **[key]** (*read form*) — definition
**CALLBACKS (X words):**
- **[key]** (*read form*) — definition [struggled | overdue | recently-mastered]

## Vocabulary Fence (the sea — build from these)
[The full fence from the ticket. Words outside it are the +1 — answerable from
context within seconds.]
- **[key]** (*read form*) — gloss

## Notes (optional)
[Calibration from the last interaction, if anything.]
```
