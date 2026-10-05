---
name: extend
description: The change discipline for @build — gates every modification passes before code is written. Use when adding, editing or removing any file, prompt, script, constant or schema field.
---

# Extend — change discipline

Seven gates, in order. Each one has a stop condition.

## Gate 1 — decisions

Read `docs/DECISIONS.md`. **Stop** if the change re-litigates a settled decision.
Reopening one takes new evidence, brought to the learner.

## Gate 2 — budget

Does this add a row of data, or a file, field, meter or rule? A row → proceed. Anything
else is budgeted in this same diff (`scripts/smoke/cases_laws.py`) and has to clear
Gate 4. Was it uncommissioned? Then write one line in `docs/feature_inbox.md` and
**stop**.

## Gate 3 — explore before implementing

**Stop** until the learner has explicitly said yes to the approach. Silence or
non-objection is not a yes. Exploring includes the plumbing: read the owning file and
the log before proposing a mechanism. A mechanism proposed before diagnosis is a
symptom cap.

## Gate 4 — what does this replace?

State it: *"this replaces / simplifies ___."* A prohibition also names what it guards
("never X, because Y"), so a later audit can retire it. The ratchets:

| Surface | Budget |
|---|---|
| Code lines per module group (comments and docstrings free) | core 8k · audio 4k · phone 4k · timeline 1k · smoke 5k |
| Fixed protocol prose | 9k words |
| Prohibitions in the fixed law + mandates | `PROHIBITION_BUDGET`, only ever down |
| pyflakes findings | 0, never moves |

Growth past a budget is a red run. A raise goes in the same diff as the growth, and the
commit names what it could not retire. A new `scripts/*.py` joins a group in
`cases_laws.MODULES` and a layer in `cases_laws.LAYERS` in the diff that creates it. **If you can't name what it replaces,
stop.**

## Gate 5 — surgical routing

Find the one file that owns the concern (`docs/PROTOCOL_MAP.md`) and edit only that
file. If the map is wrong, fix the map in the same diff.

## Gate 6 — port surface

A learner or language fact lives in `config/tutor.json` (read via `pack.py`) or in a
prose slot, nowhere else. Lanes ask the pack a question and never hold a regex, a name or
a config literal. `cases_laws` fails the build on a learner name, a config value or a
target-script character on any mechanism line. A worked example in a prompt is an
**example slot** (`$NAME`, at most 8), never inline target text. A new key in the config
goes into `pack.check`, `docs/CUSTOMIZATION.md` and both `config/examples/*.json` in the
same diff.

## Gate 7 — after the change

1. **A smoke case for every fixed bug**, as a `case_*` function in the
   `scripts/smoke/cases_*.py` file that owns the lane.
2. **The silent no-op test.** Answer it out loud: *what does this look like when it
   silently does nothing, and can the system tell that apart from success?* Assert the
   effect, not the execution. Round-trip through the real entry point and re-read the
   state file. Make an absence loud. If the honest answer is "it would look like
   success", the change isn't finished.
3. Run `/verify`.
4. Never hand-edit Python-owned JSON.
5. Commit subject: `Subsystem: what changed`. CI commits as `github-actions[bot]`.
