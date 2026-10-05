#!/usr/bin/env python3
"""The readable chat record — progress/chat.md rendered from knock_log.json.

knock_log.json is the single source of truth for the phone loop; this renders the
transcript the learner can open on their phone. Every writer of the log
regenerates it into its own commit (`publish.publish` enforces that).

Derived output — never hand-edit. Rebuild any time:

  python scripts/render_chat.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from pack import LEARNER, TUTOR
from state_io import KNOCK_LOG_PATH, LOCAL_TZ

CHAT_PATH = BASE / "progress" / "chat.md"

HEADER = f"""\
# {TUTOR} ↔ {LEARNER} — the phone record

Rendered from `knock_log.json` on every knock, reply, and queue drain.
Newest day first. **Derived file — edits here are overwritten.**
"""


def _local(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(LOCAL_TZ)


def _quote(text: str) -> str:
    return "\n".join("> " + ln for ln in (text or "").strip().splitlines())


def render_chat() -> Path:
    log = json.loads(KNOCK_LOG_PATH.read_text(encoding="utf-8")) if KNOCK_LOG_PATH.exists() else []
    spoken = [e for e in log if e.get("acted", True) and e.get("body")]

    # Every TURN is filed under the local day it HAPPENED, not the day its knock
    # fired, so an answer that crosses midnight sorts after what it followed.
    turns: list = []                       # (local datetime, rendered block)
    for e in spoken:
        t = _local(e["timestamp"])
        tag = " / ".join(p for p in (e.get("modality"), e.get("move")) if p)
        audio = " 🎧" if e.get("audio_url") else ""
        turns.append((t, [f"**{t:%H:%M} · {TUTOR}**{audio}  ·  {tag}".rstrip(" ·"),
                          _quote(e["body"]), ""]))
        # Only a turn that left its knock's day carries a back-pointer.
        back = f"  ·  ↩ {t:%m-%d %H:%M} · {e.get('move') or 'knock'}"

        exchanges = e.get("exchanges")
        for x in exchanges or []:
            a = _local(x["at"]) if x.get("at") else t
            when = f"{a:%H:%M} · " if x.get("at") else ""
            verdict = (x.get("verdict") or "").upper()
            block = [f"**{when}{LEARNER}** — **{verdict}**"
                     f"{back if a.date() != t.date() else ''}",
                     _quote(x.get("reply", "")), ""]
            if x.get("reply_line"):
                block += [f"**{TUTOR} ↩**", _quote(x["reply_line"]), ""]
            turns.append((a, block))
        if not exchanges and e.get("response") == "ack":
            a = _local(e["response_at"]) if e.get("response_at") else t
            when = f"{a:%H:%M} · " if e.get("response_at") else ""
            turns.append((a, [f"**{when}{LEARNER}** · 👍 acked"
                              f"{back if a.date() != t.date() else ''}", ""]))

    by_day: dict = {}
    for when_dt, block in turns:
        by_day.setdefault(when_dt.date(), []).append((when_dt, block))

    lines = [HEADER]
    for day in sorted(by_day, reverse=True):
        lines.append(f"\n## {day:%A %Y-%m-%d}\n")
        for _, block in sorted(by_day[day], key=lambda wb: wb[0]):
            lines += block

    # newline="\n": a tracked derived file both CI and a laptop regenerate must
    # be byte-identical across platforms.
    CHAT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return CHAT_PATH


if __name__ == "__main__":
    print(render_chat())
