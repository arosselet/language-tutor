---
name: recalibrate
description: Structured pedagogy recalibration — felt signal → evidence → one move. Use when the learner questions the pedagogy or curriculum ("feels like a chore/drill", "not landing", "strengthen the curriculum", "review the system against my goals"), or reports the same felt-complaint a second time. NOT for plumbing symptoms — that's /debug.
---

# Recalibrate — Felt Signal → Evidence → One Move

The failure this skill replaces (learned in the reference implementation): the
same "the system isn't landing" conversation re-derived from scratch, over and
over — each an unscoped architecture session, several ending in mechanisms
later reverted. This is a bounded pass instead. The law underneath is
`protocol/diagnosis.md` (the tutor's periodic self-check); this is the same
discipline run deliberately, with the learner at the table.

## 1. Capture the felt signal, verbatim

One sentence in the learner's words — not your paraphrase. Log it immediately:
`python scripts/sync_state.py feedback "<what they said>"` (mutating, one line).
The ledger across sessions is what turns feelings into evidence. A named
feeling, however vague, is the highest-value signal the system gets.

## 2. Check it isn't already settled

- `docs/DECISIONS.md` — has this axis been ruled on? If yes, name the entry
  before anything else. Reopening a settled decision needs *new evidence*,
  never restated taste.
- `progress/feedback_log.json` — prior felt-signals on the same axis. A
  signal's **third strike on one axis is a design flaw, not noise.**

## 3. Evidence before proposals — read, don't theorize

Read-only sweep, all safe:
- `python scripts/sync_state.py status` — floor, deck, soak, production axis
- `python scripts/sync_state.py feedback` — the accumulated ledger
- `grep -o '"move": "[^"]*"' progress/knock_log.json | tail -20` — dose shapes actually sent
- `progress/session_log.json` tail — what recent sessions actually did

The evidence decides; taste doesn't. A mechanism proposed before the sweep is
a symptom cap (`/extend` Gate 3 carries the same law).

## 4. One move, cheapest first

`protocol/diagnosis.md` law, verbatim: the default verdict is **change nothing**
(one data point is noise; a reproduced pattern is signal). Then at most one move:

1. **Turn a dial** — `progress/profile.md` Calibration Notes. Reversible. ~90% of healing.
2. **Prune** — delete the scene-type/meter/rule that isn't earning its place.
3. **Propose (gated)** — real structural gap → proposal + evidence to
   `docs/feature_inbox.md` for the owner's yes/no. Building it is `/extend`'s job, later.

## 5. Close

Settled something → record it in `docs/DECISIONS.md` so the next wave of this
feeling meets a recorded conclusion instead of a blank page. Nothing settled →
say "noise; nothing to change" and stop. That verdict is a success, not a
failure of the pass.
