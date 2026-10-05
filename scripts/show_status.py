#!/usr/bin/env python3
"""
The learner's own dashboard — "show my status".

Word-state comes from progress/lexicon.json; continuity from learner.json;
episodes from episodes.json. Unlike the tutor's brief, this surface may show
countdowns and fractions: the learner opens it themselves.

Usage:
    python scripts/show_status.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audio_titles
import timeline
from pack import FEED_TITLE
from state_io import load_json
from sync_state import compute_floor, compute_engines, compute_ear, trailing_pace

RECOGNIZED = {"comfortable", "solid"}


def bar(pct: float, width: int = 20) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def main():
    base = Path(__file__).parent.parent
    learner = load_json(base / "progress" / "learner.json")
    lexicon = load_json(base / "progress" / "lexicon.json")
    episodes = load_json(base / "progress" / "episodes.json") or {}
    session_log = load_json(base / "progress" / "session_log.json") or []

    if not learner or lexicon is None:
        print("⚠️  Missing learner.json or lexicon.json. See SETUP.md.")
        return

    print("=" * 55)
    print(f"📊 {FEED_TITLE.upper()} — STATUS REPORT")
    print("=" * 55)

    # No streak theatre — recency is the honest signal.
    last = session_log[-1].get("date") if session_log else None
    if last:
        print(f"\n📅 Last logged session: {last}")

    # THE TIMELINE — the learner's surface, not the tutor's: the T-minus prints
    # here and never on `compute_status`. NOT SCHEDULED is a loud absence.
    if timeline.PHASES:
        print("\n🗓  THE TIMELINE")
        print("-" * 55)
        _tl = timeline.load(learner)
        print("    " + timeline.status_line(_tl).replace("\n", "\n    "))
        print("\n".join("    " + ln for ln in timeline.table(_tl)))

    ear = compute_ear(lexicon)
    if ear["total"]:
        pct = ear["caught"] / ear["total"] * 100
        print("\n★ EAR-ONLY — the win is comprehension, never production")
        print("-" * 55)
        print(f"    [{bar(pct)}] {ear['caught']}/{ear['total']} solid on recognition ({pct:.0f}%)")
        if ear["untouched"]:
            print(f"    ⚠ Coverage: {ear['untouched']} never worked — "
                  f"catch advances ONLY through eavesdrop.")

    floor = compute_floor(lexicon)
    print("\n🎯 VIABILITY FLOOR — recognized words that fire cold")
    print("-" * 55)
    print(f"    [{bar(floor['pct'])}] {floor['cleared']}/{floor['total']} ({floor['pct']:.0f}%)")
    print(f"    Floor gap: {floor['total'] - floor['cleared']} recognized words not yet cold.")
    # The pace is a PRODUCTION number, so it sits with the floor, not the ear.
    print(f"    Pace: {trailing_pace()}")

    engines = compute_engines(lexicon)
    if engines["total"]:
        print("\n⚙️  ENGINES — patterns that fire a novel instance cold")
        print("-" * 55)
        print(f"    [{bar(engines['pct'])}] {engines['online']}/{engines['total']} online ({engines['pct']:.0f}%)")

    levels = {"solid": 0, "comfortable": 0, "struggled": 0, "untested": 0}
    n_words = 0
    for r in lexicon.values():
        if r.get("type") == "pattern":
            continue
        n_words += 1
        levels[r.get("recognition", "untested")] = levels.get(r.get("recognition", "untested"), 0) + 1
    print(f"\n📚 RECOGNITION ({n_words} words tracked)")
    print("-" * 55)
    print(f"    solid: {levels['solid']}   comfortable: {levels['comfortable']}   "
          f"struggled: {levels['struggled']}   untested: {levels['untested']}")

    # Ear-only items are marked — they want soak, not drilling.
    struggled = sorted(
        w + (" (ear)" if r.get("direction") == "catch" else "")
        for w, r in lexicon.items()
        if r.get("recognition") == "struggled" and r.get("type") != "pattern")
    if struggled:
        print(f"\n⚠️  STRUGGLED ({len(struggled)}) — candidates for interactive drilling")
        print("-" * 55)
        print("    " + ", ".join(struggled[:12]) + (" ..." if len(struggled) > 12 else ""))

    if episodes:
        recent = sorted(episodes.items(), key=lambda x: int(x[0]), reverse=True)[:5]
        print("\n🎧 RECENT EPISODES (the immersion tank)")
        print("-" * 55)
        for m, ep in recent:
            dur = ep.get("duration_min")
            dur_str = f" ({dur:.1f} min)" if dur else ""
            print(f"    M{m}: {ep.get('title', '')}{dur_str}")

    if session_log:
        print(f"\n📈 RECENT SESSIONS ({len(session_log)} logged)")
        print("-" * 55)
        for s in session_log[-5:]:
            moved = len(s.get("cold", [])) + len(s.get("hinted", []))
            print(f"    {s.get('date','?')} | floor {s.get('floor_pct','?')}% | +{moved} produced | {s.get('note','')[:40]}")

    # CONTACT, as minutes actually played — never renders, which the system
    # could move by writing more files.
    dose = audio_titles.dose_minutes(30)
    print("\n🎧 DOSE — minutes actually played (30d)")
    print("-" * 55)
    print(f"    {dose['minutes']:.0f} min · {dose['per_day']:.1f}/day · "
          f"{dose['taps']} presses over {len(dose['plays'])} artifacts")
    if dose["unmeasured"]:
        print("    ⚠ presses recorded with NO minutes — plumbing, not a quiet month")
    if dose["plays"]:
        top = sorted(dose["plays"].items(), key=lambda kv: -kv[1])[0]
        print(f"    Most replayed: {top[0]} ({top[1]}×)")

    print(f"\n💡 {learner.get('status', 'Ready for more.')}")
    print("=" * 55)


if __name__ == "__main__":
    main()
