---
name: recalibrate
description: Structured pedagogy recalibration — felt signal → evidence → one move. Use when the learner questions the pedagogy or curriculum ("feels like a chore", "not landing", "I keep hearing words I know"), or reports the same felt complaint a second time. NOT for plumbing symptoms — that's /debug.
---

# Recalibrate — felt signal → evidence → one move

This is the same discipline as `protocol/diagnosis.md`, run deliberately with the learner
at the table. Its job is to keep a "this isn't landing" conversation from turning into
an unscoped redesign.

## 1. Capture the signal, verbatim

Write down one sentence in the learner's own words, then log it:
`python scripts/sync_state.py feedback "<their words>"`.

## 2. Is it already settled?

- `docs/DECISIONS.md`: if this axis has been ruled on, name the entry first. Reopening
  it needs new evidence, not restated taste.
- `progress/feedback_log.json`: look for earlier signals on the same axis. **A third
  strike on one axis is a design flaw, not noise.**

## 3. Evidence before proposals

**First, audit the picture.** Every planner acts on the lexicon's picture of the
learner. Draw ~15 rows the complaint touches and ask their meanings (ask, then reveal;
never "which do you know?"). If the rungs disagree with the answers, the fix is the
feedback loop, not the planner. Two tells of a stale picture: an implausible
distribution (common words still `struggled`), and evidence about the machine (`taught`,
`exposed`) outnumbering evidence about the learner (`tested`, `attended`) by an order of
magnitude.

**Second, trace the behaviour to its rule.** `grep` the protocol and `mandates.py` for
what the learner is describing, then read the symptom that rule was written to prevent.
If that symptom can no longer happen, the rule is the fault.

Then run the read-only sweep: `sync_state.py status`, `sync_state.py feedback`, the last
20 `"move"` labels in `knock_log.json`, and the tail of `session_log.json`.

## 4. One move, subtraction first

The default verdict is **change nothing**: one data point is noise. Otherwise make at
most one move:

1. **Prune.** Retire or loosen the rule step 3 traced. The first candidate is a "never"
   whose guarded failure can no longer happen.
2. **Turn a dial.** Change `progress/profile.md` → Calibration Notes. It's reversible.
3. **Propose.** For a real structural gap, put a proposal and its evidence in
   `docs/feature_inbox.md` for the learner's yes or no. Building it is `/extend`'s job.

## 5. Close

If something got settled, add one line to `docs/DECISIONS.md` with the date and the
evidence. If nothing did, say "noise; nothing to change" and stop. That counts as a
success.
