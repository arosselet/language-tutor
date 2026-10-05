# Settled Decisions (`@build` reference)

One line per decision: what was settled, and the evidence that settled it. **Don't
re-litigate these.** If new evidence really does reopen one, take it to the learner with
the evidence, and never drift silently. Append your own decisions as they settle, dated,
each naming what it replaces. The narrative behind a line is its commit.

The seed below is inherited. Every entry was earned in the reference system
(tamil-tutor, `docs/LINEAGE.md`), and its evidence is quoted from there.

## How to work on this system

- **The LLM is the writer; Python is the brain.** Push reasoning into deterministic code and keep the model's input small. Never hand-edit Python-owned JSON.
- **Every addition names what it replaces.** An addition that simplifies nothing is suspect. *Evidence: the reference system's worst week was accumulation (NOT-lists, format rotation, micro-debriefs); its best moves were separations.*
- **Surgical edits to the owning file.** Dialect → `dialect.md`, voice → `hosts.md`, selection → `suggest_targets.py`. Never rewrite a role file for a one-off.
- **Fix the tool, not the personality.** When the tutor seems forgetful or pushy, read the plumbing (workflow logs, `knock_log.json` timestamps) before touching persona or prompts. *Evidence: "the tutor had no knowledge of my reply" was a same-tick collision in the push queue.*
- **Diagnosis subtracts first.** Trace a complaint to the rule producing it and prune before adding. *Evidence: when two felt complaints arrived the same weekend, both traced to existing rules and nothing needed adding.*
- **Audit the picture before tuning the behaviour.** "Why do I keep hearing words I know" was a ledger fault, not selection, format or pedagogy. Test the lexicon against the learner's answers first.
- **Felt experience is the primary diagnostic; the feedback ledger is its sensor.** `@build` work is evidence-only.
- **A fade is a signal, not a discipline failure.** Check palatability first, never answer a fade with accountability machinery. *Evidence: the reference system's May fade.*
- **A mechanism proposed before diagnosis is a symptom cap.**
- **"Done" is observed, never declared.**
- **A dropped rule is hunted through code, prompts, skills and tests.** Marking a rule superseded in prose leaves it live everywhere else.
- **One map, one narrative surface.** `docs/PROTOCOL_MAP.md` is the only architecture map, and git holds the history. A second copy of a fact drifts.
- **The budgets are the structure control.** Every surface and script group is budgeted, and a new file is budgeted in the diff that creates it. Rows of data are free.
- **Prohibitions are budgeted: a new never retires an old one.** *Evidence: of 322 reference decisions, 26 retired anything; nothing made a live rule leave when its cause did.*
- **A "never" names what it guards.**
- **Static clean is a ratchet surface, budget zero** (pyflakes). The suite proves only what it executes.
- **Meters measure effect, not execution.** A counter nobody writes reads as measurement. *Evidence: `listens` had only self-report writers and a seed of 0.*
- **CI tests stay hermetic.** The smoke suite carries no secrets and stubs every outward call.
- **Fail forwards.** A renderer fix does not oblige a backfill: fix the machine, add the guard, and re-render only what is still load-bearing.
- **Reference docs anchor to function names, never line numbers.**

## The seam

- **Learner-dependent surfaces are setup-time elaborations.** Persona, user, stake, contract, language, dialect, exemplars and the world are synthesized for each learner, and are never defaults. *Evidence: v5's Dutch cold run derived the weave rule and the modality split correctly from the interview.*
- **The port surface is `config/tutor.json` plus the prose slots.** No mechanism line holds a learner name, a target-script character or a config literal (`cases_laws`). *Evidence: the reference port surface was one regex, then one line, then one file; each step found a fact hiding elsewhere.*
- **Lanes ask the pack a question, never hold a range.** *Evidence: eight files held raw script tests to answer three questions.*
- **Declare, don't detect.** A shared-script target marks its spans (⟦ ⟧); detection only works for a distinct script.
- **The surface rule is stated once.** What the learner reads is the read form, and what a voice speaks is the voice form. Ask which sense receives the line, never which lane sent it. *Evidence: seven mandates restated it and had drifted three ways.*
- **The curriculum schema key is `word`, never a language name.**
- **Imports point one way, down the stack; no lane is a foundation.** A rail more than one channel obeys gets its own file (`rails.py`).
- **The executor is the host's, for every lane.** A local agent CLI when one is on PATH, otherwise the API, chosen in `writer.py` only.
- **Structured output on every JSON lane, and the schema names every key the mandate asks for.** *Evidence: on the agent path a key missing from the schema was silently dropped; soak sheets rendered intro and outro over nothing.*

## The ledger

- **The lexicon is a view over the observation log.** Every evidence field has one writer, `lexicon_view.rebuild`.
- **What the learner told us and what we observed never share a field.** `seed`, `self-report` and `claimed` are recorded and never vote. *Evidence: a day-one self-estimate shared the recognition field with earned evidence; purging the rows instead of separating provenance let it return.*
- **`untested` is not a grade.** *Evidence: 356 of 392 reference rows read `struggled`, known words included, so planners re-aired them.*
- **Hearing is not knowing; a tape is not a teacher.** Delivery never closes the teach gate. Attendance discharges a Teach Beat and never mints one.
- **Reading is not hearing, and the log says which.** Every observation carries its medium.
- **Asking is not teaching: the sweep reaches every untested row.** The sweep is a sensor, outside the ask-less dial.
- **Ambiguous is not cold; never take the flattering reading.** Credit belongs to the word produced, never the target the judge wanted.
- **When the learner's account contradicts a logged verdict, the verdict is the suspect.**
- **Mistakes are a ledger, not prose.** A slip retires and never disappears, and a close is a dated observation.

## Pedagogy

- **Comprehension leads; production is the probe.** The goal is following the room and joining it. Cold-fire counts never define a good lesson. *Evidence: the reference system's April thesis (forced cold output toward a "viability floor") was retired in September for comprehension-first.*
- **Stories teach; lists check.** A bare list never teaches, though a list may check.
- **Taps report what the learner did; questions measure what they know.**
- **A number never leaves the tutor's mouth.** Meters steer Python, and the close names what got clearer.
- **A week of silence is a question the tutor asks once.** "This is annoying" is a complete answer, and the only right response is to change the thing.
- **Exemplars, not templates: the range is the example.** *Evidence: episodes converged under ~1,300 lines of writing law.*
- **The world is fictional, recurring, and runs by the month.** It is never a portrait of the learner's real people. A free-standing scenario is a world that silently doesn't exist.
- **The dialect law reaches every voice, not just the studio.** *Evidence: two native speakers called lane output "book" register; none of it had passed through the dialect file.*
- **The informant is never an examiner.** Their form beats the system's draft, and a debrief is contact, never evidence.
- **Capacity routes the audio channel; the curriculum only fills it.** Commissioning nothing is a first-class outcome.

## Delivery

- **All audio lands on the feed.** A push is ephemeral, and dismissing it must not lose the dose.
- **A published item's title and duration are frozen.** Podcast apps fork on a retitle, and durations are measured, never estimated.
- **Quiet hours belong to `push_to_phone`, not to each lane.**
- **A clock-bound request produces a queue entry, never an acknowledgement.**
- **One serialized CI lane; the drain runs first on every tick.**
- **An unattended production trigger is verifiable, and capped regardless.**
- **Pull before read, push after write: the clone is one of many writers.** Derived files are re-rendered, never merged.
- **Every subprocess decode is pinned to UTF-8.**
