---
name: debug
description: Symptom-to-root-cause triage for the knock loop, push queue, reply judge, studio/feed, session state, and CI. Use when a knock didn't arrive, a reply scored wrong, the feed is stale, CI is red, the push queue misfired, or the tutor's behaviour looks like a plumbing bug.
---

# Debug — Triage and Root-Cause

## 1. Doctrine

**Evidence before action. Plumbing before persona.**

When the tutor seems wrong — forgetful, miscalibrated, missing — read the logs first.
The reference implementation's founding incident ("the tutor had no knowledge of my
reply") was a same-tick multi-fire collision in the push queue: 100% plumbing, zero
persona involvement. Full law: `docs/DECISIONS.md` → "Fix the tool, not the personality."

Do not touch prompts, protocol files, or persona until you have a log-confirmed
root cause. If the root cause points to a code change, stop here and use `/extend`
for the fix and `/verify` to prove it.

Unfamiliar with the jargon below (rails gate, deck, `expected_target`, soak order)?
Start with `/orient` → `references/glossary.md`.

---

## 2. Triage Table

| Observed symptom | Suspect subsystem | First evidence command |
|---|---|---|
| No knock arrived today | Rails gate blocked, or CI never ran | `gh run list --workflow=tutor-knock.yml --limit 10` |
| Knock arrived but no audio / "bad file type" | Notifier automation's audio branch | check `knock_log.json` → `audio_url` present? + your notifier's traces (`docs/phone_loop.md`) |
| Knock body asked X, reply scored against Y | Coherence mismatch (`expected_target` vs body) | read last entry in `knock_log.json` → compare `body` and `expected_target` |
| Reply scored wrong ("miss" when the learner fired it) | Judge saw stale / mis-targeted knock | `knock_log.json` last entry → `target_revealed`, `pinned_target`, `expected_target`, `reply`, `reply_verdict` |
| A real cold stuck at hinted | Reveal window (working as designed?) or a hallucinated reveal | `knock_log.json` → was the word in recent bodies/recasts? Capped fires graduate after 2 distinct days (KF-6/KF-8 below) |
| Push arrived twice (or never) | Push queue multi-fire or drain skip | `python scripts/push_queue.py list` + `knock_log.json` → `scheduled` entries |
| Push arrived at wrong time | Queue entry `due` field / quiet-hours deferral | `knock_log.json` → `rationale` field on `scheduled: true` entry |
| Feed shows stale / wrong episode, or wrong dates | RSS rebuild didn't run, or pubDate clobber | `grep '<title>' rss.xml \| head -5` vs newest `.mp3` in `published_audio/` (+ `knocks/`) |
| Status looks wrong (floor/deck numbers) | `lexicon.json` state, compute logic | `python scripts/sync_state.py status` (safe) |
| CI red — smoke workflow | Regression in knock/reply/queue plumbing | `gh run list --workflow=smoke.yml --limit 5` then `gh run view <id> --log` |
| CI red — knock/queue workflow | Missing secret, commit conflict, JSON parse fail | `gh run view <id> --log` |
| Audio knock missing from the podcast feed | Feed refresh failed in that knock run (`refresh_feed()` is failure-tolerant by design) | `gh run view <id> --log` → look for `⚠ rss rebuild failed`; rerun `python scripts/rebuild_rss.py` locally |
| The tutor keeps making the same mistake | May be a protocol bug, not plumbing | read `progress/feedback_log.json`; if pattern appears 2+ times → `/extend` |

---

## 3. Per-Subsystem Playbooks

See `references/subsystems.md` — load it when the triage table points to a specific subsystem.

---

## 4. Known Failure Modes (inherited precedents from the reference implementation)

These bugs were found, root-caused, and fixed in months of real use. The fixes ship in
this template; each has a smoke-test regression. They stay listed because their
*symptoms* recur — recognizing one saves a day of triage.

### KF-1: Same-tick multi-fire push collision
**Symptom:** Two queued pushes both due → both fire in one drain tick → the reply is
judged against the second (last-logged) knock, not the one being answered.
**Fix shipped:** drain caps at one non-forced fire per tick; the rest defers.
**Regression:** `smoke_test.py` → section 6 (#1).

### KF-2: Prose-wrapped / single-quoted LLM JSON killed a knock tick
**Symptom:** Knock workflow shows `Expecting value: line 1 column 1` (or `Expecting
property name enclosed in double quotes: char 1` — the tell of a single-quoted Python
dict); no knock fired.
**Fix shipped:** `parse_llm_json()` strips fences → `json.loads` → `{...}` slice →
`ast.literal_eval`, printing raw text before any re-raise; `decide()` retries up to 3×.
**Regression:** `smoke_test.py` → section 1 (#2).

### KF-3: Misaligned expected_target — coherence mismatch
**Symptom:** Valid replies repeatedly scored as "miss"; the judge feels rigid for days.
**Fix shipped:** the coherence law (pick the target FIRST, write the body as its ask)
+ the judge's safety net (a mis-targeted knock is void; grade against the body's own
natural answers) + UNSEEN teach-before-quiz flags on the menu.
**Verify:** read last `knock_log.json` entries — the body's natural answer should be
`expected_target`.

### KF-4: Notifier audio branch silently disabled
**Symptom:** Audio knocks deliver text only — no inline player, no attachment error.
**Precedent:** a Home Assistant template condition (`{{ x is defined and x }}`)
returned the URL *string*, which a core update counted as falsy → the automation
always took the text branch. Conditions must render literal booleans.
**Where:** your notifier's config — see `docs/phone_loop.md` → gotchas.

### KF-5: A second feed artifact masked the newest episode
**Symptom:** Feed player shows an old episode as the newest.
**Precedent:** a stale concatenated "playlist" artifact appeared first in the feed.
**Law shipped:** `rss.xml` is the only feed. If a second feed artifact ever appears,
that's the bug.

### KF-6: Chain pin destroyed the ask · menu blind to recency · hallucinated reveals
**Symptom:** log's `expected_target` absurd vs the body; the same surface ask fires
daily under different move names; correct unaided productions stuck at hinted (a real
cold denied for a reveal that never happened); chat.md shows only the last reply of a
chain.
**Fix shipped:** chains move `pinned_target`/`pinned_revealed` (never
`expected_target`); every exchange appends to `exchanges` (chat renders the full
chain); the menu demotes recently-asked items and outcome memory carries the actual
ask; `revealed_recently()` computes reveals from the log — the judge may cap against
that list only.
**Regression:** `smoke_test.py` → section 10 (#3).

### KF-7: RSS rebuild clobbered pubDates
**Symptom:** every feed item shows the same recent date after any rebuild.
**Precedent:** `os.path.getmtime()` on a CI runner is the checkout time.
**Fix shipped:** `rebuild_rss.py` parses the current `rss.xml` for guid→pubDate and
reuses saved dates; mtime only for genuinely new items.

### KF-8: The hinted-forever trap
**Symptom:** a word knocked on daily can never score cold — every ask re-reveals it.
**Fix shipped:** the capped lane — cold-quality fires blocked only by the reveal
window record as CAPPED and graduate to cold after 2 distinct local days, verified
against computed evidence in both directions.
**Regression:** `smoke_test.py` → section 11 (#4).

---

## 5. Exit: Once Root-Caused

1. If the fix is a code change → use `/extend` (change discipline gate → surgical edit → smoke case).
2. Use `/verify` to prove the fix end-to-end.
3. Every fixed plumbing bug gets a new smoke case in `scripts/smoke_test.py` — this is the contract that keeps the KF list from recurring.
4. If the fix is notifier config → update your notifier and the notes you keep per `docs/phone_loop.md`.
5. If the root cause is a pattern of 2+ feedback entries → log with `python scripts/sync_state.py feedback "note"` (mutating — appends to `progress/feedback_log.json`) before proposing the fix.

---

### KF-9: One-knock-at-a-time notifications ate stacked doses
**Symptom:** a knock logs "no-tap" though the learner swears they saw nothing — a later
push replaced it on the lock screen.
**Root cause:** a fixed notification tag made every push self-replacing; replies could
only correlate to the last-fired knock.
**Fix:** every push carries its log timestamp as `knock_id` (round-tripped by the
notification's action data); `find_knock()` targets that entry, last-fired only as
fallback. Notifications stack. **Verify:** smoke → section 14.

### KF-10: Volley surface desynced from the pin — the judge improvised the chain
**Symptom:** mid-volley, a chat reply made the open ask vanish; the judge re-asked an
earlier item, declared the volley finished, or claimed a score its verdict never produced.
**Root cause (code, not judge discipline):** `judge()` received the notification body
frozen at ask 1 while Python's pin walked the queue — from item 2 on, every volley read
as a KF-3 mis-target and the coherence safety net *lawfully voided the pin*.
**Fix:** `volley_open_ask()` is the single owner of the current ask — the judge grades
against it, chat verdicts re-present it, the last judged item sets `volley_done`. The
meta-lesson: the LLM must never own chain *surface* any more than chain *state* —
whatever Python tracks, Python must also say. **Verify:** smoke → section 21.

---

**Scope:** This skill owns triage only. Routine health checks → `/validate`. Making the fix → `/extend`. Proving it → `/verify`.
