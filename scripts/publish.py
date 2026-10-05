#!/usr/bin/env python3
"""THE DELIVERY TAIL: everything between "a lane made a dose" and "it is on the
learner's phone and on main" — the commit path with its rebase net, the feed
rebuild, the CDN URL and the one push chokepoint. It ENFORCES the waking window
at that chokepoint; `rails.py` owns it.

Imports point one way, down the stack, and a channel never owns an invariant
more than one channel obeys. A lane hands over what it produced; it does not own
the ordering, the quiet-hours check or the commit list.

The notification receiver is any webhook (D6): `PUSH_WEBHOOK_URL` receives a POST
of {title, text_content, knock_id, tag[, audio_url]}. See `docs/phone_loop.md`.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from pack import REPO, TUTOR
from render_chat import render_chat
from state_io import KNOCK_LOG_PATH, LOCAL_TZ, RECENT_AUDIO_PATH
import lexicon_view
from observations import OBSERVATIONS_PATH
from rails import in_waking_window


KNOCKS_DIR = BASE / "published_audio" / "knocks"   # tracked, CDN-served dir

# Lock-screen render budget. Past ~160 characters a phone cuts the body and the
# dose dies unseen. Warn-only: the fix belongs in the composer.
BODY_BUDGET = 160


def over_budget(text: str, budget: int = BODY_BUDGET) -> bool:
    return len(text or "") > budget


def load_env(path: Path):
    """Minimal .env -> os.environ, never overwriting what is set (CI secrets)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# Append-only arrays whose rows carry a unique key: two writers appending between
# a checkout and its push collide TEXTUALLY on rows that do not disagree. rel ->
# (identity key, sort key). Anything else conflicting is a real disagreement and
# stays loud. The observation log keys on `id` because a retell scores several
# words inside one second.
UNIONABLE = {"progress/push_queue.json": ("id", "due"),
             "progress/knock_log.json": ("timestamp", "timestamp"),
             "progress/observations.json": ("id", "at")}

# Files with no state of their own, each a render of a source of truth: rebuild
# from the merged source instead of merging the output.
DERIVED = {"progress/chat.md": render_chat, "progress/lexicon.json": lexicon_view.remerge}


def _union_conflict(rel: str) -> bool:
    """Resolve ONE conflicted append-only array by keeping every row from both
    sides; False if anything is off-pattern, which keeps the abort loud.
    REBASE INVERSION: stage :2 is UPSTREAM and :3 is OURS — backwards silently
    drops the other writer's row."""
    key, order = UNIONABLE[rel]

    def side(stage: int):
        r = subprocess.run(["git", "show", f":{stage}:{rel}"], cwd=BASE,
                           capture_output=True, text=True, encoding="utf-8")
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None

    theirs, ours = side(2), side(3)
    if not isinstance(theirs, list) or not isinstance(ours, list):
        return False
    merged, seen = [], set()
    for row in theirs + ours:
        if not isinstance(row, dict) or row.get(key) is None:
            return False       # a keyless row cannot be deduped; refuse rather than guess
        if row[key] in seen:
            continue
        seen.add(row[key])
        merged.append(row)
    merged.sort(key=lambda r: str(r.get(order, "")))
    (BASE / rel).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run(["git", "add", rel], cwd=BASE, check=True)
    print(f"   ↳ merged {rel}: {len(theirs)} theirs + {len(ours)} ours -> {len(merged)}")
    return True


def _rerender_derived(rel: str) -> bool:
    """Resolve a DERIVED conflict by rebuilding from source. Runs AFTER the union
    pass, which leaves the merged source on disk. Asserts the renderer wrote the
    conflicted path, or the markers would be committed as the resolution."""
    written = Path(DERIVED[rel]()).resolve()
    if written != (BASE / rel).resolve():
        print(f"   ⚠ {rel} renderer wrote {written}, not {BASE / rel} — refusing")
        return False
    subprocess.run(["git", "add", rel], cwd=BASE, check=True)
    print(f"   ↳ re-rendered {rel} from its source (not merged)")
    return True


def _rebase_onto_main() -> bool:
    """Land our one commit on origin/main, union-resolving append conflicts and
    re-rendering derived ones. False if a conflict is real, rebase aborted."""
    if subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"],
                      cwd=BASE).returncode == 0:
        return True
    stopped = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"],
                             cwd=BASE, capture_output=True, text=True, encoding="utf-8").stdout.split()
    unresolvable = [f for f in stopped if f not in UNIONABLE and f not in DERIVED]
    if (stopped and not unresolvable
            and all(_union_conflict(f) for f in stopped if f in UNIONABLE)
            and all(_rerender_derived(f) for f in stopped if f in DERIVED)):
        subprocess.run(["git", "rebase", "--continue"], cwd=BASE,
                       env={**os.environ, "GIT_EDITOR": "true"}, check=True)
        return True
    print(f"   ⚠ unresolvable rebase conflict: {unresolvable or stopped or 'none reported'}")
    subprocess.run(["git", "rebase", "--abort"], cwd=BASE)
    return False


def current_branch() -> str:
    """The checked-out branch, or "" in a detached HEAD (treated as main: CI)."""
    return subprocess.run(["git", "branch", "--show-current"], cwd=BASE,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()


def commit_and_push(paths: list[Path], msg: str):
    """Commit and push to main. REFUSES from any other branch: the rebase replays
    every commit on the branch onto main, so a dose rendered mid-feature-work
    would ship the whole branch. Refusing, not retargeting — the feed URL is
    pinned to @main, so a dose pushed elsewhere would 404 on the phone."""
    branch = current_branch()
    if branch and branch != "main":
        raise RuntimeError(
            f"refusing to publish from '{branch}': this pushes HEAD:main and would "
            f"rebase every commit on this branch onto main and ship them. Commit "
            f"is NOT made; switch to main (or cherry-pick the dose) and re-run.")
    # Windows may import BASE through an 8.3 alias; compare canonical paths.
    rels = [str(p.resolve().relative_to(BASE.resolve())) for p in paths]
    subprocess.run(["git", "add", *rels], cwd=BASE, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=BASE, check=True)
    # main has several writers and this checkout goes stale during LLM/TTS steps.
    if not _rebase_onto_main():
        raise RuntimeError("rebase onto origin/main needs a human — tree left clean")
    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=BASE, check=True)


def refresh_feed() -> Path | None:
    """Rebuild rss.xml so every dose stays findable. Feed polish must never kill a dose."""
    try:
        subprocess.run([sys.executable, str(BASE / "scripts" / "rebuild_rss.py")],
                       cwd=BASE, check=True)
        return BASE / "rss.xml"
    except Exception as e:
        print(f"   ⚠ rss rebuild failed ({e}) — continuing without feed update")
        return None


def jsdelivr_url(mp3: Path) -> str:
    rel = mp3.resolve().relative_to(BASE.resolve()).as_posix()
    return f"https://cdn.jsdelivr.net/gh/{REPO}@main/{rel}"  # unique filename => always fresh


def push_to_phone(body: str, audio_url: str | None, knock_id: str = "",
                  requested: bool = False) -> bool:
    """POST one notification to the receiver; True if pushed, False if held.

    QUIET HOURS ARE ENFORCED HERE, at the one chokepoint every lane shares, so no
    lane can forget them. `requested=True` exempts a reply the learner's own tap
    asked for: the rails stop UNrequested reaches.

    `knock_id` rides the payload for correlation (which knock a reply answers);
    `tag` is the notification's IDENTITY, minted per push — a receiver replaces a
    notification bearing a tag already on screen, so a per-knock tag would let a
    second reply silently eat the first."""
    if not requested and not in_waking_window():
        local = datetime.now(LOCAL_TZ)
        print(f"   phone: quiet hours ({local:%H:%M} {local.tzname()}) — not pushed. "
              f"The artifact is on the feed for the morning.")
        return False
    if audio_url:
        # Pre-warm the CDN: the phone fetches the attachment the instant the
        # notification lands, and a cold path can take long enough to drop it.
        try:
            with urllib.request.urlopen(audio_url, timeout=60) as r:
                r.read()
        except OSError as e:
            print(f"   ⚠ CDN pre-warm failed ({e}) — pushing anyway")
    webhook = os.environ["PUSH_WEBHOOK_URL"]
    payload = {"title": TUTOR, "text_content": body, "knock_id": knock_id,
               "tag": f"tutor-{knock_id or 'knock'}-{time.time_ns()}"}
    if audio_url:
        payload["audio_url"] = audio_url
    req = urllib.request.Request(webhook, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    # Retry absorbs transient network blips; the final failure raises so an
    # unreachable receiver is a red run, not a silent drop.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req) as r:
                print(f"   push -> HTTP {r.status}")
            return True
        except OSError as e:  # URLError, gaierror, timeouts
            if attempt == 2:
                raise
            wait = 5 * (attempt + 1)
            print(f"   ⚠ push attempt {attempt + 1} failed ({e}) — retrying in {wait}s")
            time.sleep(wait)


# ── THE TAIL: one owner for the ordering ────────────────────────────────────

def publish(state_paths: list, message: str, *, mp3=None,
            feed: bool | None = None) -> tuple[list, str]:
    """Assemble the commit for a finished dose and return `(paths, message)` in
    the ONE correct order. The lane logs and records exposure first, then passes
    this straight to `commit_and_push`, then pushes.

      FEED AFTER THE LOG: `rebuild_rss` titles pushed doses from the knock log,
      and a podcast app treats a published title as part of an item's identity.
      THE MP3 GOES ON MAIN BEFORE THE NOTIFICATION: the CDN serves only paths
      already on main, so the audio leads the commit.
      THE OBSERVATION LOG RIDES EVERY DOSE: knock lanes run on stateless runners,
      and an uncommitted event is gone when the job ends.
      A DERIVED FILE FOLLOWS ITS SOURCE: a commit carrying the knock log carries
      a fresh `chat.md`.

    The commit and push stay at the lane (`from publish import commit_and_push`)
    so the smoke suite's stubs intercept them on the lane's module. `feed`
    defaults to "this run made audio"; push_queue passes feed=True with no mp3
    because its mp3s went out in an earlier commit."""
    if feed is None:
        feed = mp3 is not None
    paths = [q for q in state_paths if q]
    if OBSERVATIONS_PATH.exists() and OBSERVATIONS_PATH not in paths:
        paths.append(OBSERVATIONS_PATH)
    if mp3 is not None:
        paths.insert(0, mp3)
    if feed:
        rss = refresh_feed()
        if rss:
            # Both, always: the rating picker's list derives from the feed, and a
            # rewrite that never leaves the runner reads exactly like success.
            paths.extend([rss, RECENT_AUDIO_PATH])
    if any(Path(q).name == KNOCK_LOG_PATH.name for q in paths) \
            and not any(Path(q).name == "chat.md" for q in paths):
        paths.append(render_chat())
    return paths, message
