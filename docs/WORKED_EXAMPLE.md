# Worked Example: The Tamil Instantiation

This template was extracted from a real, running system: **tamil-tutor**
(<https://github.com/arosselet/tamil-tutor>), built by and for one learner over
months of daily use. Everything in this repo — the engine, the pedagogy, the
templates — is that system with the Tamil-and-one-learner layer lifted out.
This file is the distilled record of *how each template elaborated* for that
learner, so a setup agent can see how concrete the synthesis must get.

**Never copy content from here** — it's a different language, dialect, and
life. Match the *specificity*.

## The learner and the stake

Andrew: an English-speaking engineer married into a Tamil-speaking family from
Coimbatore. Years of ambient exposure made him a **recognizer** — hundreds of
words understood at the family table, almost none firing in his mouth. That gap
*is* this system's engine; his archetype is why the viability floor (recognized
→ fires cold) is the headline meter.

**The stake ("the heist"):** his wife is a native speaker and doesn't know how
far he's gotten. The dream is the jaw-drop reveal — answering in clean
colloquial Tamil at a family gathering, unannounced. The elaboration that
followed: the tutor is the **safe room** (a hundred zero-stakes failures buy
the one live moment the learner picks); secrecy is the point, not
embarrassment-avoidance; and the wife is the **Oracle** — a vocab-confirming
resource and the *unwitting audience* of **field missions** ("say '*suvaiya
irukku*' at dinner tonight, unprompted — debrief tomorrow"), never an examiner
or a progress check. A trip to India later added a **deadline deck**: ~50
Oracle-vetted survival chunks and frames burned down against the landing date.

## The tutor persona

**Anna** — Tamil for "elder brother," which *is* the relationship archetype:
warm, a little bossy, proud of you, and a menace when you're rolling — needling
and daring, because that's how affection talks at a Tamil table. He/him, from
Coimbatore, Kongu Tamil as mother tongue (not studied — *his*). "Warmth for
the lapses, teeth for the streaks." His persona file carries 5–7 illustrative
lines mixing English logistics with phonetic Tamil payload (*"illa da — close,
but we'd say 'poren'. sollu again."*), which calibrate every future session's
register. His **masks**: he becomes the mother-in-law (forcing deferential
neenga-forms), the fast-bantering cousin, the gossiping auntie — one beat, then
steps out and recasts as himself.

## The language charter (the two derived rules)

- **Weave Rule, Tamil letter:** spoken Coimbatore Tamil is heavily
  code-switched with English ("Thanglish") — so *English nouns are authentic*:
  fridge, office, bus stay English, and using pure-Tamil nouns marks you as a
  scholar, not a local. English carries scene-setting; the load-bearing verb or
  chunk is always Tamil. (For a language where code-switching isn't native,
  this derivation flips — the template explains.)
- **Modality Split, Tamil letter:** Tamil has its own script, so chat runs in
  **phonetic Latin** ("poren" *is* போறேன் — never make the learner fight a
  Tamil keyboard) while **audio/TTS is Tamil script only** (a Tamil voice
  speaks it). Lexicon keys are canonical Tamil script; each record carries the
  phonetic spellings the learner actually types, and Python resolves them.
  Config: `script_regex` = the Tamil Unicode block.
- **Register:** colloquial Coimbatore, literary Tamil ignored completely —
  வேணும் never வேண்டும், போறேன் never போகிறேன். After real-world contact the
  dial settled on **"competent over local"**: clear standard colloquial first,
  hyper-local Kongu markers as the long game.

## The dialect file (Producer's toolbox)

Concrete written→spoken transformations with script examples: verb-form
collapse tables (போகிறேன் → போறேன்), fusion in fast speech (அது என்ன →
அதென்ன), subject-pronoun drop when verb endings carry it, discourse markers
(ஆமா, சரி, பாரு — with doubling as natural rhythm), a ban on Tamil-root +
English-suffix hybrids (தூக்கு-ing doesn't exist in real speech), and a
regional "Kongu layer" with one analyst named as the reference ear. Shorthand
test at the top: *"Would a Coimbatore auto driver say this to his friend?"*

## The cast

Intercept hosts: two unnamed Coimbatore-native peers — Host A (F) urban,
English-fluent, sharper; Host B (M) more local, stays in Tamil longer, warmer.
Breakdown analysts: **Maya** (F, chases the *why*, loves patterns) and **Raj**
(M, obsessed with Coimbatore flavor, ties language to place and people) — they
also lead the `lore` episode form end-to-end.

## The word pool

~285 entries of spoken-form glue across clusters (`connectors, pronouns,
questions, verb_present/past/future/command, emotions, descriptions,
social_reaction, daily_routine, home_kitchen, family, obligation_ability,
proposals, phone_scheduling`), priority-tagged. All canonical Tamil script,
all colloquial forms, English glosses. Example entry:
`{"word": "அதனால தான்", "gloss": "That's why / That's the reason",
"cluster": "connectors", "priority": 1}`.

## What months of running it settled

The transferable conclusions are seeded in this repo's `docs/DECISIONS.md`.
The short version of what the Tamil system learned the hard way: pure
comprehensible input plateaus (forced cold output toward the floor is the
engine); continuity works as one rewritten prose debrief, not a thread schema;
variety must be structurally enforced or everything drifts to the same
mildly-irritated kitchen scene; never chase listens or streaks; the coach
reaches first but silence is a first-class move and "I'm busy" is a real
answer; and when the tutor seems dumb or pushy, the bug is in the plumbing,
not the personality.
