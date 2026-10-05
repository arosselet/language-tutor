---
name: debug
description: Symptom-to-root-cause triage for the knock loop, push queue, reply judge, studio/feed, session state, and CI. Use when a push didn't arrive, a reply scored wrong, the feed is stale, CI is red, or the tutor's behaviour looks like a plumbing bug — including doses that have drifted samey.
---

# Debug — triage and root cause

## Doctrine

**Evidence before action. Plumbing before persona.** When the tutor seems forgetful,
miscalibrated or pushy, read the logs first. Touch no prompt, protocol file or persona
until a log confirms the root cause. Behavioural drift counts too. "It sends too much of
one thing" is triageable from the log's move labels and the prompt's incentive lines.
Never answer it with a quota invented from taste.

## Triage table

| Symptom | Suspect | First evidence |
|---|---|---|
| No push today | Rails gate, module off, or CI never ran | Actions → `tutor.yml` runs; `python scripts/pack.py module phone` |
| Push arrived, no audio | Receiver template | `knock_log.json` → `audio_url` present? Then the receiver's own trace |
| Body asked X, reply graded against Y | Coherence (`expected_target` vs body) | the last `knock_log.json` entry |
| Reply graded wrong | Stale or mis-targeted knock; missing `knock_id` | `knock_log.json` → `reply`, `reply_verdict`, `target_revealed` |
| Push twice, or never | Queue multi-fire or drain skip | `python scripts/push_queue.py list`; `scheduled` entries in the log |
| I replied and **nothing** ran | The inbound leg: an expired token, or the receiver's dispatch | Actions filtered to `repository_dispatch`. If pushes still arrive, outbound works, so suspect the token |
| Feed stale or wrong | RSS rebuild didn't run | `rss.xml` first titles vs the newest files in `published_audio/` |
| Status numbers look wrong | A rung set by hand | `python scripts/lexicon_view.py` (zero divergent rows is the contract) |
| CI red | Smoke regression, a missing secret, or a commit conflict | the failing run's log |
| The tutor repeats a mistake | Possibly protocol, not plumbing | `progress/feedback_log.json`; at 2+ entries → `/extend` |
| Doses feel same-shaped | Incentive drift in a mandate | `grep -o '"move": "[^"]*"' progress/knock_log.json \| tail -15`, then the mandate's preference lines |

## The quiet class

Loud failures (crashes, parse errors) show up in logs. The quiet class is different:
nothing fails, every instrument reads green, and the dose is simply about the wrong
thing. **Don't start from the error log, because there won't be one.** Name what the
subsystem promises, find the one place that would prove it happened, and check whether
anything reads it.

## Exit

1. A code fix → `/extend`, then `/verify`.
2. Every fixed plumbing bug gets a smoke case in the `scripts/smoke/cases_*.py` file that
   owns the lane. Assert the effect, round-trip through the writer, and make the absence
   loud.
3. A pattern of 2+ feedback entries → `python scripts/sync_state.py feedback "…"` before
   proposing anything.

This skill owns triage only: `/validate` for health checks, `/extend` for the fix,
`/verify` for proof.
