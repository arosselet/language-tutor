# Subsystem Playbooks (`/debug` depth reference)

Load this file when the triage table in `.claude/skills/debug/SKILL.md` points to a
specific subsystem. Each playbook: what the subsystem does, which files are the evidence,
and numbered steps.

---

## A. Knock Loop (`morning_knock.py` + `tutor-knock.yml`)

**What it does:** GitHub Actions cron ticks every ~2h. The Rails Gate in
`morning_knock.py` cheaply skips most ticks (no LLM) using the waking window / daily
cap / min gap from `config/tutor.json` → `outreach`. When open, the tutor decides
fire/silence/modality via OpenRouter → optionally renders audio → commits to `main` →
POSTs the `PUSH_WEBHOOK_URL` webhook.

**Evidence files:**
- `progress/knock_log.json` — one entry per WAKE (including silences); last entry is newest.
- GitHub Actions → **Tutor Knock** workflow logs.

**Key knock_log fields to read:**
- `acted` (bool) — `false` = silence; no notification sent.
- `modality` — `"text"` | `"audio"` | `"challenge"` | `"volley"` | `"eavesdrop"` | `"grace"` | `"silence"`
- `rationale` — the tutor's one-line reason; shows why they chose silence or this move.
- `next_check` — when the tutor set their next wake; far in the future explains a quiet day.
- `body` — the notification line.
- `expected_target` — the word/chunk/frame a good reply would fire (empty = no-ask dose). Immutable once logged.
- `pinned_target` / `pinned_revealed` — what a chained follow-up (or volley walk) is asking for *now*.
- `target_revealed` (bool) — `true` = the body showed the target; reply caps at "hinted".
- `volley` / `volley_next` — the binding item queue and the walk position, on a volley knock.
- `audio_url` — present only on audio/eavesdrop knocks; its absence on one is a bug.

**Playbook — no knock arrived:**
```
# SAFE (read-only)
gh run list --workflow=tutor-knock.yml --limit 10
```
1. Check: did the workflow even trigger? If missing today: GitHub schedule slip (common under load) — wait or use `workflow_dispatch` to trigger manually.
2. If it ran: `gh run view <run-id> --log` — look for `[rails] skip — ` lines. Common skip reasons:
   - `quiet hours (HH:MM …)` — the tick landed outside the waking window.
   - `daily cap reached (N/N)` — the day's fires are spent.
   - `min-gap not met (X.Xh < Nh)` — too close to the last reach.
   - `tutor's next_check not due (set for ...)` — the tutor soft-gated themselves.
   - `Not bootstrapped yet` — no `config/tutor.json`; run `/setup`.
3. If `[rails] wake` but then stopped: look for the LLM/TTS step error. Common: missing secret (`OPENROUTER_API_KEY`), or KF-2 (unparseable LLM JSON — the raw text now prints in the log).
4. If `act=false modality=silence`: the tutor chose silence. Check `rationale` in the log entry.

**Playbook — audio knock delivered as text (no player):**
1. Read `progress/knock_log.json` last entry: is `audio_url` present?
   - If absent: the tutor chose a text modality — working as designed.
   - If present but the phone showed text: your notifier took its non-audio branch → KF-4.
2. Check the notifier's trace/debug view for which branch ran (`docs/phone_loop.md` → gotchas).

---

## B. Push Queue (`push_queue.py` + `push-queue.yml`)

**What it does:** Durable "ping me at X" layer. Entries are fully composed at add-time
and drained by a 30-min CI tick. Each fired entry is logged into `knock_log.json`
(field `scheduled: true`) so the reply judge and the rails see it. Quiet hours and the
daily cap apply to non-forced entries; `force: true` bypasses both.

**Evidence files:**
- `progress/push_queue.json` — pending entries, sorted by `due` (ascending).
- `progress/knock_log.json` — entries with `scheduled: true` are past-fired queue items.

**Playbook — push didn't arrive:**
```
# SAFE (read-only)
python scripts/push_queue.py list
gh run list --workflow=push-queue.yml --limit 10
```
1. Is the entry still in the queue? (`list` shows pending). If yes: check its `due` timestamp (UTC) vs now.
2. Is `force: false` and the entry due in quiet hours? It defers silently to the next waking tick.
3. Is the daily cap already reached today? Non-forced entry defers until the next day.
4. Did the drain workflow run? If missing, GitHub schedule slipped.
5. Drain locally (mutating!): only if you have confirmed the entry should fire and secrets are set.

```
# MUTATING — fires the push, commits, and notifies
python scripts/push_queue.py drain
```

**Playbook — push arrived twice (KF-1 pattern):**
1. Check `knock_log.json` for two entries with `scheduled: true` and close timestamps.
2. Confirm the drain caps at one non-forced fire per tick (`non_forced_fired` in `cmd_drain`). If the bug recurs, add a smoke case.
3. If two *forced* entries fired: expected — `force: true` bypasses the cap by design.

**Playbook — check queue state:**
```
# SAFE (read-only)
python scripts/push_queue.py list

# SAFE (dry-run — prints what would fire, no writes)
python scripts/push_queue.py drain --dry-run
```

---

## C. Reply Judge (`knock_reply.py` + `log-knock-response.yml`)

**What it does:** the phone fires a `repository_dispatch: knock-response` event on a
tap or typed reply. The workflow calls either `sync_state.py knock-response ack` (tap)
or `knock_reply.py "<text>"` (typed reply). The judge scores per word, moves the
production axis (upgrades only — never demotes), and pushes a recast + scoreboard
back. An **eavesdrop** knock takes a separate lane: the reply grades comprehension
and moves recognition only.

**Evidence files:**
- `progress/knock_log.json` — last entry's `reply*` fields + `exchanges` (the full chain).
- `progress/lexicon.json` — production axis values for the scored word(s).
- GitHub Actions → **Log Knock Response** workflow logs.

**Key knock_log reply fields:**
- `reply` — the raw typed text (latest exchange; history in `exchanges`).
- `reply_verdict` — `"cold"` | `"hinted"` | `"miss"` | `"chat"` (or a catch verdict on eavesdrop).
- `reply_fired` / `reply_fired_cold` / `reply_fired_capped` — per-word credit, accumulated across the chain.
- `reply_line` — the tutor's push-back (recast + optional chained/volley ask).
- `chained` — number of chained follow-up asks on this knock.

**Playbook — reply scored wrong:**
1. Read the last `knock_log.json` entry. Confirm `reply` matches what was typed.
2. Check the **pin**: a chained knock grades against `pinned_target`, not `expected_target`. Compare the pin to what the last recast actually asked.
3. Check `target_revealed` and the recent traffic: a shown word caps at "hinted"/CAPPED — this is the hard rule, enforced in `apply_verdict()`. A capped word graduates to cold after capped fires on 2 distinct local days.
4. Check the coherence safety net: if `body` and the target diverge, the judge voids the target and says so in `rationale` (KF-3).
5. If the judge workflow ran: `gh run view <id> --log` — look for `! '<word>' resolves to no lexicon record`. A fired word without a lexicon record is skipped, loudly.
6. Dry-run a re-judge (LLM fires; no writes):
```
# SAFE — prints verdict only; no state writes, no push-back
python scripts/knock_reply.py --dry-run "<the reply text>"
```
7. If the production axis is wrong in the lexicon: correct it from a chat session via `sync_state.py update --produced-cold '<word>'` (mutating).

**Playbook — continuity decay (reply to an old knock):**
- If the last exchange is >3h old, the judge receives `hours_since_last_exchange` and
  treats the scenario as expired — the reply is graded as an open rep. Intended, not a bug.

---

## D. Studio / Audio / RSS / Feed (`render_audio.py` + `rebuild_rss.py`)

**What it does:** Local-only pipeline (cloud never renders episodes).
`render_audio.py` reads a markdown script, calls TTS, stitches MP3, writes to
`published_audio/`, registers the episode in `progress/episodes.json`, stamps
`seen_in` in `progress/lexicon.json`, and calls `rebuild_rss.py` as a lifecycle hook.
`rebuild_rss.py` scans `published_audio/` for `tier*.mp3`, `drill_*.mp3`, and
`knocks/*.mp3`, and writes `rss.xml`, preserving existing pubDates.

**Evidence files:**
- `published_audio/` — the actual audio files served to the feed.
- `progress/episodes.json` — episode registry (title, words, duration_min, listens).
- `rss.xml` — the feed. The only feed (KF-5).

**Playbook — feed shows stale / wrong episode:**
```
# SAFE (read-only)
ls -lt published_audio/*.mp3 | head -5
python -c "import json; e=json.load(open('progress/episodes.json')); mx=max(e,key=int); print(mx, e[mx]['title'])"
grep -c '<item>' rss.xml
```
1. Does the newest file in `published_audio/` appear in `rss.xml`? If not, `rebuild_rss.py` didn't run or ran from a different working directory.
2. Are the pubDates all identical and recent? That's KF-7 territory — confirm `existing_pub_dates()` found the old `rss.xml`.
3. Is `episodes.json` stale vs `rss.xml`? They are separate: RSS reads `published_audio/` directly; `episodes.json` is the Python brain's registry. Both should agree on title/count.
4. To regenerate RSS locally (mutating — rewrites `rss.xml`, run from the repo root):
```
# MUTATING — rewrites rss.xml
python scripts/rebuild_rss.py
```
5. CDN lag: `rss.xml` is served from GitHub raw content. A fresh push takes ~30s to serve; podcast apps may cache longer.

---

## E. Session State (`sync_state.py`)

**What it does:** `sync_state.py` owns all writes to `progress/`. The `status`
sub-command is the safe read-only dashboard. `update` moves the recognition and
production axes.

**Evidence command (safe, read-only):**
```
python scripts/sync_state.py status
```

**Playbook — floor/deck numbers look wrong:**
1. Run `status` — it recomputes live from `lexicon.json`; the stored `learner.json` status line can lag (it's updated by `update`, not by every read).
2. If a specific word's axis is wrong, read its record directly:
```
# SAFE (read-only)
python -c "import json; lex=json.load(open('progress/lexicon.json')); print(lex.get('<word>', 'not found'))"
```
3. Verify the canonical key: when the language has a distinct script, lexicon keys are canonical script (`config.is_target`); phonetic variants live in the `phonetic` list and `resolve()` maps them.
4. If a phone-rep cold fire didn't update the axis: the word may have resolved to `None` (no lexicon record). The judge prints `! '<word>' resolves to no lexicon record — not scored`. Fix: seed the record first (`sync_state.py add-word`).
5. To correct state from a known-good chat session — `update` (mutating):
```
# MUTATING — moves production axis (upgrades only from the judge; update can set any level)
python scripts/sync_state.py update --produced-cold '<word>'
```

---

## F. CI / Workflows

**Four workflows (`.github/workflows/`):**

| Workflow file | Name in Actions UI | Trigger | What it does |
|---|---|---|---|
| `tutor-knock.yml` | Tutor Knock | cron + dispatch | Runs `morning_knock.py`; commits audio + log. Skips clean pre-bootstrap |
| `push-queue.yml` | Push Queue Drain | cron (*/30 min) | Runs `push_queue.py drain`; commits queue + log. Skips clean pre-bootstrap |
| `log-knock-response.yml` | Log Knock Response | `repository_dispatch: knock-response` | Runs `knock_reply.py` (reply) or `sync_state.py knock-response` (tap) |
| `smoke.yml` | Smoke Test | push to main (scripts/**, config/**, workflows/**, requirements.txt) | Runs `smoke_test.py` sandboxed |

**Playbook — CI red:**
```
# SAFE (read-only)
gh run list --workflow=<filename> --limit 10
gh run view <run-id> --log
```

Common causes:
- **Missing secret:** `OPENROUTER_API_KEY`, `PUSH_WEBHOOK_URL`, or `GCP_SA_KEY` not set → step fails with auth error or 401.
- **Git rebase conflict:** knock, queue, and the laptop all push to `main`. Workflows use `git pull --rebase --autostash origin main` before push; look for `CONFLICT` in the log.
- **Smoke test FAIL:** a regression in knock/reply/queue plumbing. The log names the failing case. Run `python scripts/smoke_test.py` locally to reproduce.
- **Not bootstrapped:** the knock and queue workflows gate on `config/tutor.json` and skip clean until `/setup` has run — a skipped tick on a fresh clone is correct, not red.
