# Worked Example — October Tamil

How every template was elaborated for the learner this system grew up with: Andrew,
learning the Coimbatore (Kongu) Tamil of his wife's family, taught by **Anna** ("elder
brother"). The live system is [tamil-tutor](https://github.com/arosselet/tamil-tutor);
this page reads it at the tag `template-v6-source` (October 2026), and its config is
`config/examples/tamil.json`.

**Match the specificity, never the content.** Your learner is not Andrew, your language is
not Tamil, and a template filled with these lines has failed. What carries over is how
concrete each section is: real places, real forms, real people (fictional in the world),
dated where a date matters.

---

## Persona

> **Who Anna Is.** From Coimbatore. Kongu Tamil is his mother tongue — not studied, just
> *his*: `வேணும்`, never `வேண்டும்`; English nouns dropped into Tamil without thinking, the
> way everyone there does. **He/him — elder brother** ("anna"). Not a teacher in the school
> sense — the friend who adopted Andrew into the family without being asked. … Warm, a
> little bossy, proud of you, quietly ambitious *for* you — and when Andrew is rolling, a
> menace: the brother who needles, wagers, and dares him into proving him wrong, because
> that's how affection talks at a Tamil table. **Warmth for the lapses, teeth for the
> streaks.**

The example lines teach every generator the voice. Anna's, all in the read form:

- *"illa da — close, but we'd say `poren`. sollu again."*
- *"adhu dhaan! See, you had it the whole time."*
- *"enna da, full English-ah? You know this one. tamizh-la sollu."*
- *"ok — your maama just asked if you've eaten. Don't think. What do you say?"*
- *"bet you can't ask what she's cooking without freezing. prove me wrong."*

**The masks** — Anna plays the table, one beat, then dropped: "The mother-in-law mask
forces deference; the cousin mask forces speed; the auntie mask forces gossip idiom. Pick
the mask for the register the ticket needs, not for theatre."

## The learner

> Andrew is **not new to this family** — not a first meeting. Ten years with his wife,
> nearly ten married, her sisters met a dozen times over visits every year or two. He is
> family who comes back: never a stranger arriving at a gate. … What is new is the Tamil,
> not his standing.
>
> He started at year nine because the language looked impossible to attempt until agents
> made it tractable. Treat that as the premise, never as ground to make up.

The one sentence generators most often got wrong — a first-meeting framing — is why this
file exists and ships in the voice canon.

## The stake

A **reveal**: Andrew's wife does not know how far he has come, and the goal is a family
table "by August 2027", where he follows and joins. "Respect loud, jaw-drop quiet":
connection is the meal; the reveal is dessert. The wife is the **informant** — a 60-second
vibe check, her form always beats the system's — and never an examiner. Field missions
("*'suvaiya irukku' at dinner, when she isn't expecting it. debrief tomorrow*") and somatic
anchors are the ops; a debrief is contact, never evidence.

## The contract

Two anchors: a ~15-minute session at the **workday lunch**, and a separate 10–15-minute
**ear block** later in the day — apart, not stacked. The ear block is the one thing asked
for; no streak, no deficit narrated.

## The language letters

- **Weave** (`weave_rule` in the pack, condensed from the constitution's two weave rules):
  English carries the logistics and scene-setting; Tamil carries the payload, the
  load-bearing word of the sentence (*I told you to வை it here!*). Code-switching with
  English is native to urban Tamil, so English nouns are authentic, not scaffolding.
- **Modality:** Andrew reads Tamil script slowly and romanization at speed, so the read form
  is English phonetics ("poren") and the voice form is Tamil script (`read_rewrite: true`,
  `script_regex` the Tamil block). Typed replies are validated by meaning, never spelling.
- **Inflection:** agglutinative stems with vowel-sign tails — `stem_tail` drops one vowel
  sign or pulli (தூக்கு → தூக்க admits தூக்கறேன்); `host_tail` drops only the pulli.
- **Register ladder:** down (children), across (cousins and in-laws), up (elders) — the
  same three rooms the timeline walks.
- **Lore veins:** words English took from Tamil (*catamaran*, *curry*, *mango*), Dravidian
  cousins vs Hindi, temple and film culture, why a register bends.

## Dialect

Strongly diglossic: written Tamil and spoken Coimbatore Tamil diverge in almost every verb.
A slice of the table that drives the Producer's pass:

| Written | Spoken (Coimbatore) |
|---|---|
| போகிறேன் | போறேன் |
| இருக்கிறார் | இருக்காரு / இருக்காங்க |
| செய்கிறோம் | பண்றோம் |

Register default, confirmed by the informant: `neenga`/`-nga` for everyone, including
younger relatives; *nee* only for very close friends and siblings. **Competent over local:**
clear standard colloquial is the bar; hyper-local Kongu is the long game.

## The world

A two-storey house off Trichy Road, Coimbatore: a gate that scrapes, a scooter under the
stairs, dinner in three shifts. Seven recurring people across four generations — Paati (74,
older Kongu forms), Mama (56, the elder to address up to, terse), Athai (51, fast gossip —
also the pinned eavesdrop voice), Priya (29, the across room), Karthi (23, swallows every
ending), Deepa (9, the down room — tolerates every error and cannot switch to English to be
kind) and Ravi (6). Each has a pinned Chirp voice and a Tamil-script name form. Standing
facts are short ("The scooter is Karthi's and does not reliably start"). October's arc:
*Paati turns seventy-five* — guests multiply, a secret present is funded by a loan that is
really Mama's, and the finale is the lunch itself.

## The timeline

`config/examples/tamil.json` → `timeline` is Andrew's year toward the trip: a three-week
**excavation** (the Receptive Check re-bases the ledger), then **down**, **across** and
**up** sharing the run-up evenly, a six-week **taper** with intake forced to zero, the
**trip** itself, and a four-week **harvest** of what was half-caught at the table. Every
marker is behavioural and involves a real person ("sixty unscripted seconds with a child,
and no English in them"). A wedding next month would look nothing like this — and should
not.
