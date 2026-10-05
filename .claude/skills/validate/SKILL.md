---
name: validate
description: Routine health check — run the smoke suite, check state invariants, confirm feed/registry coherence and CI green. Use after any machinery change, after a clone, before trusting state, or before a session. (For a specific symptom, start with /debug.)
---

# Validate — routine health check

Run the layers in order. Stop at the first failure and go to `/debug`.

## Layer 1 — smoke (sandboxed, safe)

```
python scripts/smoke_test.py               # both example packs, the blank clone, and this repo's own pack
python scripts/smoke_test.py --pack live   # just this repo's pack
```

Each pack runs in a throwaway copy with every model, TTS, push and git call stubbed.
**Pass:** the last line is `ALL GREEN`. It covers the pack, the ledger, the lanes and the
laws (budgets, import direction, no learner or language in mechanism, pyflakes). It
doesn't cover the sound of audio, phone delivery, or what a model actually writes.

## Layer 2 — status (read-only)

```
python scripts/sync_state.py status
```

**Pass:** it completes without `Error:` or `not found`. A stale soak-order warning is a
content signal (run a session), not a fault.

## Layer 3 — state invariants on the real tree

| Invariant | Check |
|---|---|
| Every evidence field equals the fold of the log | `python scripts/lexicon_view.py` → `0 divergent` |
| The config validates | `python scripts/pack.py check` |
| Every lexicon key is canonical for the pack | `python -c "import json,sys; sys.path.insert(0,'scripts'); import pack; d=json.load(open('progress/lexicon.json',encoding='utf-8')); print([k for k in d if not pack.is_canonical(k) and not k.startswith('frame:')] or 'ok')"` |

**After any merge that touched `progress/`**, run `python scripts/lexicon_view.py --rebuild`,
then `git diff -- progress/lexicon.json`. Expect nothing. The lexicon is derived, and
git can auto-merge two folds of two different logs without a conflict. Rebuilding and
diffing is the only honest check.

## Layer 4 — feed and registry coherence

`rss.xml` should list at least as many items as `progress/episodes.json` registers, and
its newest item should match the newest file in `published_audio/`. If it doesn't, a
render stopped midway → `/debug`.

## Layer 5 — CI green

The latest `smoke.yml` run on `main` should be `success`.

## What validation cannot catch

Voice drift, wrong register, teaching quality and content errors. Behaviour complaints
go to `/debug`, and felt pedagogy signals go to `/recalibrate`.
