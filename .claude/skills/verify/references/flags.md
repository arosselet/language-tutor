# Flag Semantics — Full Reference

All claims verified in source (symbol names cited; line numbers deliberately omitted —
they rot). When precision matters, grep the cited symbol.

---

## `morning_knock.py`

Source: `scripts/morning_knock.py` — `main()`.

| Flag | LLM fires? | TTS fires? | Files written? | Commit/push? | Phone push? |
|---|---|---|---|---|---|
| *(bare)* | YES | YES if the tutor picks audio/eavesdrop | `knock_log.json`, MP3 (audio), `rss.xml` (audio — via `refresh_feed()`, failure-tolerant), `chat.md` | YES | YES |
| `--dry-run` | **YES** | **YES if audio/eavesdrop** | MP3 only (written before the dry-run gate) | NO | NO |
| `--force` | YES | YES if audio | same as bare | YES | YES |

`--dry-run` detail: `rails_gate()` runs (no LLM), `build_digest()` runs (calls
`sync_state.py status` as a subprocess — read-only), `decide()` runs (LLM, with up to
3 parse retries). For silence: the gate fires early, no writes. For fire: TTS renders
if audio (`render_memo()`), then the dry-run gate returns before `log_decision()`,
`refresh_feed()`, `push_to_phone()`, or `commit_and_push()`.

`--force` detail: skips the rails gate's waking-hours/daily-cap/min-gap/next_check
checks (`if force: return True, "forced"`). No other change.

---

## `knock_reply.py`

Source: `scripts/knock_reply.py` — `main()` (production lane) and
`handle_catch_reply()` (eavesdrop lane).

| Flag | LLM fires? | Files written? | Commit/push? | Phone push? |
|---|---|---|---|---|
| *(bare)* | YES | `lexicon.json`, `knock_log.json`, `feedback_log.json` (if `meta_note` present) | YES | YES |
| `--dry-run` | **YES** | NO | NO | NO |

`--dry-run` detail: `judge()` (or `judge_catch()` on an eavesdrop knock) is called —
the LLM fires. The dry-run gate returns before `apply_verdict()` /
`apply_catch_verdict()`, any `save_json()` calls, `commit_and_push()`, and
`push_to_phone()`.

---

## `push_queue.py`

Source: `scripts/push_queue.py` — `cmd_drain()`, `cmd_add()`, `cmd_cancel()`.

### drain subcommand

| Flag | Files written? | Commit/push? | Phone push? |
|---|---|---|---|
| *(bare)* | `knock_log.json`, `push_queue.json` | YES | YES |
| `--dry-run` | NO | NO | NO |
| `--no-commit` | YES (both files) | NO | YES |

`--dry-run` detail: inside the fired loop, `if args.dry_run: continue` skips
`push_to_phone()`; after the loop the dry-run gate returns before writing
`knock_log.json`, `push_queue.json`, or calling `commit_and_push()`.

`--no-commit` detail: `push_to_phone()` fires normally; both files are written;
`commit_and_push()` is behind `if not args.no_commit:`.

### add subcommand

`--no-commit`: `enqueue()` is called unconditionally (writes `push_queue.json`);
`commit_and_push()` is behind `if not args.no_commit:`.

### cancel subcommand

`--no-commit`: `save_queue(kept)` is called unconditionally (writes
`push_queue.json`); `commit_and_push()` is behind `if not args.no_commit:`.

---

## `render_drill.py`

Source: `scripts/render_drill.py` — `main()`.

| Flag | LLM fires? | TTS fires? | Files written? | Commit/push? | Phone push? |
|---|---|---|---|---|---|
| *(bare)* | YES | YES | `published_audio/drill_*.mp3` | YES (+ `rss.xml`) | YES |
| `--dry-run` | **YES** | NO | NO | NO | NO |
| `--no-publish` | YES | **YES** | `published_audio/drill_*.mp3` | NO | NO |

`--dry-run` detail: the LLM sheet writer runs; the gate prints the JSON sheet and
returns before render, file writes, `rebuild_rss.py`, `commit_and_push()`, or
`push_to_phone()`.

`--no-publish` detail: LLM + TTS run, the MP3 is written; the gate returns before
`rebuild_rss.py`, `commit_and_push()`, and `push_to_phone()`.

---

## `render_audio.py`

Source: `scripts/render_audio.py` — `main()`.

**No dry-run or no-publish flag.** Argparse only defines `input_file`, `output_file`,
`--provider`, and `--voice-type`. Every run:
1. Renders TTS → writes `audio/<basename>` and `published_audio/<basename>`.
2. Calls `register_mission_in_state()` → writes `episodes.json` and `lexicon.json`.
3. Runs `rebuild_rss.py` → writes `rss.xml`.
4. Runs `git add` + `git commit` + `git push`.

Verify `render_audio.py` changes by source-read only. Never run it in a verify pass.
