---
name: verify
description: Prove a change works end-to-end — change type → verification path, which commands are safe vs mutating, how to add a smoke case, and the honest-residual rule. Use to confirm a fix holds or to learn what a flag actually skips before running it.
---

# Verify — end-to-end proof

## Rails

**Never exercise a change against live `progress/`.** It is the learner's real state.

| Mutating: never in a verify pass | Writes |
|---|---|
| `morning_knock.py` (bare) | a model call, `knock_log.json`, a real push, a commit |
| `knock_reply.py TEXT` (bare) | lexicon + log, a commit, a push back |
| `push_queue.py drain` (bare) | a real push, the queue + log, a commit |
| `render_audio.py`, `run_studio.py` (bare) | audio, `rss.xml`, a commit and push |
| `sync_state.py update / seed / check / feedback …` | state files |

| Safe | Notes |
|---|---|
| `python scripts/smoke_test.py` | sandboxed copies, every outward call stubbed |
| `sync_state.py status`, `show_status.py`, `lexicon_view.py` (no `--rebuild`) | read-only |
| `pack.py check`, `pack.py module <name>` | read-only |
| `push_queue.py list` | read-only |

**Dry-run flags are not all equal.** `--dry-run` on the soak, drill, rotation, payoff,
knock and studio lanes still makes the **model call**. Three of them write before they
stop:

- `morning_knock.py --dry-run` renders and writes the memo MP3 on an audio path.
- `run_studio.py --dry-run` leaves the script and sidecar in `content/`.
- `render_payoff.py --dry-run` **commits** when it refuses a tape.

`--no-publish` renders real audio locally and skips the feed, the commit and the push.
`--plan-only` (rotation, sort) makes no model call. Read the branch in the script
before trusting a flag you haven't used.

## Change type → path

| Changed | Verify by |
|---|---|
| Any lane's logic | `smoke_test.py` + a new `case_*` for the behaviour |
| State schema, `sync_state`, `lexicon_view` | smoke + `status` + `lexicon_view.py` (0 divergent) + the `progress/*.example` files carry the field |
| `pack.py` or a config key | `pack.py check config/examples/*.json` + smoke on every pack |
| A mandate or prompt | smoke (schema-vs-mandate law) + a `--dry-run` of one lane, read by eye |
| `render_audio.py` | read the source; a `--no-publish` render on a sibling lane if TTS is configured; say what you didn't hear |
| `protocol/*.md` prose | read it against `protocol/constitution.md`. There is no runtime surface |
| Workflows | smoke locally, then watch the run after the push |

## Adding a smoke case

Add a `case_<what_it_guards>()` function to the `scripts/smoke/cases_*.py` file that owns
the lane. The runner finds it by name, and its docstring's first line is its title.
Use `harness.check(name, ok, detail)`. For stubs, use `Recorder()` and replace the
module's `push_to_phone`, `commit_and_push` and model call, then restore them in a
`finally`. Use `write` and `read` for sandbox state. The case must hold on **every
pack**. Use `harness.target_sample()` and `harness.marked()` rather than writing target
text inline.

## Honest residual

End every pass by naming what was not exercised: real TTS audio, phone delivery, the
network side of git, `render_audio` beyond what you read, and prose (reading is the
only check).
