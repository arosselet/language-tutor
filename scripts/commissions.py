#!/usr/bin/env python3
"""THE COMMISSION ROUTER — the runner's half of the commission contract.

A commissioner (the tutor in session, the learner, or an outside agent) files
progress/commissions/pending/<id>.json — a beat sheet plus a schedule. This
tick claims ONE due commission per run, validates it deterministically, runs the
lane script that already knows how to write, render, publish and deliver, and
parks the commission in done/ or failed/.

It is not a writer (no model call, ever) and not a delivery lane (the lane
delivers itself through `deliver_rendered`). It only moves files and runs one
command.

ONE PER TICK, FIFO by date-prefixed id. `schedule.mode: asap` is the next tick;
`at` is no earlier than the timestamp (UTC unless it carries an offset).

FAILURE: a lane that exits non-zero or times out goes back to pending with
`attempts` +1, and past MAX_ATTEMPTS parks in failed/, loudly. A commission that
fails VALIDATION parks on first sight — retrying a malformed file is a
re-dispatch loop — and so does one for a lane not yet wired for a --brief, which
would otherwise block the queue forever.

A BRIEF steers emphasis WITHIN the spine's shape; it cannot commission a shape
the lane does not have. An optional `"title"` names the feed item so a mismatch
is visible, and the lane logs how many of the brief's names reached the sheets.

pending/claimed/done/failed: the claim is committed before the minutes-long lane
runs, so a file left in claimed/ is the evidence of a tick that died mid-lane.

Usage: python scripts/commissions.py run [--dry-run]
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from publish import commit_and_push

COMMISSIONS = BASE / "progress" / "commissions"
PENDING = COMMISSIONS / "pending"
CLAIMED = COMMISSIONS / "claimed"
DONE = COMMISSIONS / "done"
FAILED = COMMISSIONS / "failed"

LANES = ("rotation", "soak", "drill", "episode", "memo")
REQUESTERS = ("tutor", "learner", "agent")
ID_RE = re.compile(r"^[0-9]{8}-[a-z0-9-]+$")
MAX_ATTEMPTS = 3
LANE_TIMEOUT_S = 720  # 12 min; the job's own timeout is the outer bound

# Lanes whose scripts accept --brief. Wired deliberately, one lane at a time —
# a commission for an unwired lane fails validation (see docstring).
WIRED = ("rotation",)


def _now():
    return datetime.now(timezone.utc)


def _at(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_pending():
    PENDING.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(PENDING.glob("*.json")):
        try:
            out.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError) as e:
            out.append((p, {"__unreadable__": str(e)}))
    return out


def validate(c, stem):
    """Deterministic and total: a reason for every malformed commission, never an
    exception; None when runnable."""
    if not isinstance(c, dict) or "__unreadable__" in c:
        why = c.get("__unreadable__") if isinstance(c, dict) else "not a JSON object"
        return f"unreadable commission file ({why})"
    if c.get("id") != stem:
        return f"id {c.get('id')!r} does not match filename {stem!r}"
    if not ID_RE.match(c.get("id") or ""):
        return f"id {c.get('id')!r} is not YYYYMMDD-slug"
    lane = c.get("lane")
    if lane not in LANES:
        return f"unknown lane {lane!r}"
    if lane not in WIRED:
        return f"lane {lane!r} is not wired for commissions yet"
    beats = c.get("beats")
    if not isinstance(beats, dict):
        return "beats must be an object"
    if beats.get("spine", "inventory") not in ("machines", "inventory", "room"):
        return f"unknown rotation spine {beats.get('spine')!r}"
    minutes = beats.get("minutes", 15)
    if (not isinstance(minutes, (int, float)) or isinstance(minutes, bool)
            or not 4 <= minutes <= 60):
        return f"minutes {minutes!r} is outside 4..60"
    if not isinstance(c.get("brief", ""), str):
        return "brief must be a string"
    if not isinstance(c.get("title", ""), str):
        return "title must be a string"
    sched = c.get("schedule") or {}
    if not isinstance(sched, dict) or sched.get("mode", "asap") not in ("asap", "at"):
        return f"bad schedule {sched!r}"
    if sched.get("mode") == "at":
        try:
            _at(sched["at"])
        except (KeyError, TypeError, ValueError):
            return f"unparseable schedule.at {sched.get('at')!r}"
    if c.get("requested_by") not in REQUESTERS:
        return f"unknown requester {c.get('requested_by')!r}"
    return None


def due(c, now):
    sched = c.get("schedule") or {}
    if sched.get("mode", "asap") != "at":
        return True
    return now >= _at(sched["at"])


def lane_command(c):
    """The lane script's argv. A commission is an ORDER: no --if-short."""
    beats = c.get("beats") or {}
    cmd = [sys.executable, "scripts/render_rotation.py",
           "--spine", str(beats.get("spine", "inventory")),
           "--minutes", str(beats.get("minutes", 15))]
    if (c.get("brief") or "").strip():
        cmd += ["--brief", c["brief"].strip()]
    if (c.get("title") or "").strip():
        cmd += ["--title", c["title"].strip()]
    return cmd


def move(path, c, dest_dir, **stamp):
    dest_dir.mkdir(parents=True, exist_ok=True)
    c = dict(c)
    c.update(stamp)
    dest = dest_dir / path.name
    dest.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    path.unlink()
    return dest


def run_one(path, c, cmd, now):
    cid = c["id"]
    c = dict(c)
    c["attempts"] = c.get("attempts", 0) + 1
    if c["attempts"] > MAX_ATTEMPTS:
        dest = move(path, c, FAILED, failed_at=now.isoformat(),
                    fail_reason=f"{c['attempts'] - 1} attempts failed; parking")
        commit_and_push([dest, path],
                        f"commissions: park {cid} in failed/ (attempts exhausted)")
        print(f"   [commission] {cid}: attempts exhausted — parked in failed/")
        return 1
    dest = move(path, c, CLAIMED, claimed_at=now.isoformat())
    commit_and_push([dest, path], f"commissions: claim {cid} (attempt {c['attempts']})")
    print(f"   [commission] {cid}: claimed — running {' '.join(cmd[1:4])} ...")
    try:
        r = subprocess.run(cmd, cwd=BASE, timeout=LANE_TIMEOUT_S,
                           capture_output=True, text=True)
        rc, tail = r.returncode, (r.stdout or "")[-2000:]
    except subprocess.TimeoutExpired as e:
        rc = "timeout"
        tail = (e.stdout or "")[-2000:] if isinstance(e.stdout, str) else ""
    ok = rc == 0
    target = DONE if ok else PENDING
    final = move(dest, c, target,
                 **({"completed_at": _now().isoformat()} if ok else {}))
    commit_and_push([final, dest],
                    f"commissions: {cid} -> {target.name}"
                    + ("" if ok else f" (lane rc={rc})"))
    if ok:
        print(f"   [commission] {cid}: DONE")
    else:
        print(f"   [commission] {cid}: lane failed (rc={rc}) — back to pending")
        print(f"   [commission] lane tail:\n{tail}")
    return 0 if ok else 1


def cmd_run(dry_run):
    now = _now()
    for path, c in load_pending():
        err = validate(c, path.stem)
        if err:
            dest = move(path, c, FAILED, failed_at=now.isoformat(), fail_reason=err)
            commit_and_push([dest, path],
                            f"commissions: park {path.stem} in failed/ ({err[:80]})")
            print(f"   [commission] {path.name}: INVALID — {err}")
            continue
        if not due(c, now):
            continue
        cmd = lane_command(c)
        if dry_run:
            print(f"   [commission] DRY RUN — {path.name} would run:\n"
                  f"      {' '.join(cmd)}")
            return 0
        return run_one(path, c, cmd, now)
    print("   [commission] nothing due")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Claim and run one due audio commission")
    ap.add_argument("run", choices=["run"])
    ap.add_argument("--dry-run", action="store_true",
                    help="validate and print the lane command; move and run nothing")
    args = ap.parse_args()
    sys.exit(cmd_run(args.dry_run))


if __name__ == "__main__":
    main()
