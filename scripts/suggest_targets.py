#!/usr/bin/env python3
"""The session "ticket" — the menu Python hands the tutor so it never picks words
by eyeballing the lexicon. The bright line: Python computes the menu, the tutor
makes the choice.

THREE SELECTORS:
  1. THE POOL — everything not yet firing cold, ordered lead > mid > dessert
     (`timeline.register_rank` against the current direction of address) and
     split into TWO BUDGETS: the focus set (≤FOCUS_SIZE, dense rotation, drilled
     until cold, then never again) and the background (exposure only). One ranked
     list cannot do both jobs. The ear (1a), coverage (1c) and the engines (1d)
     are views of this same population, not rival pools.
  2. DUE CALLBACKS — decay, from `generate_callbacks`: not "what is due" but
     "what is fading".
  3. NEW CANDIDATES BY CLUSTER — priority-1 word-pool entries not yet met, with
     coverage per cluster. Python shows coverage; the tutor picks the cluster.

Two readers: the tutor reads the bare command; the studio's Director reads
`--fence`, which adds the full recognized vocabulary (the Architect's "sea").
The slip ledger is printed by `status`, not repeated here.

    python scripts/suggest_targets.py                 # the tutor's menu
    python scripts/suggest_targets.py --fence         # + the Architect's sea
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from generate_callbacks import due_callbacks, days_since
from pack import TUTOR, host_stem
from slips import slip_patterns
from state_io import (KNOCK_LOG_PATH, LEXICON_PATH, is_unseen, load_json, local_date,
                      local_today, soak_pending)
import month
import observations
import timeline

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
WORD_POOL_PATH = BASE / "curriculum" / "word_pool.json"
OBSERVATIONS_PATH = BASE / "progress" / "observations.json"
# A cue, never a ratchet: an overdue check is a line the tutor reads, and nothing
# about it reaches the learner as a number or a debt.
CHECK_EVERY_DAYS = 30
SCRIPTS_DIR = BASE / "content" / "scripts"

RECOGNIZED = {"comfortable", "solid"}
# Most-ready-to-fire first: hinted is one hint from cold.
PROD_ORDER = {"hinted": 0, "none": 1}
RECOG_ORDER = {"solid": 0, "comfortable": 1}
NEVER_SURFACED = 10 ** 6  # sentinel staleness for a null last_surfaced

# ── Scene-spec palettes ──────────────────────────────────────────────
# Variety is structural, not taste: Python forces range on the axes that make an
# episode feel fresh, and the studio writes inside that frame. No value used in
# the last DIVERGENCE_WINDOW episodes (read from *.tags.json sidecars) repeats.
DIVERGENCE_WINDOW = 3
REGISTERS = ["tenderness", "dread", "mischief", "pride", "suspicion",
             "grief/nostalgia", "delight", "embarrassment", "defiance", "reconciliation"]
# "lore" is the stories-are-curriculum lens: the payload word as protagonist.
FORMS = ["classic", "vignette", "story", "phone_call", "lore"]
# Commissioned only through the soak order; the gate never rolls one by itself.
COMMISSIONED_FORMS = ["narrated_drama"]
ALL_FORMS = FORMS + COMMISSIONED_FORMS
INGREDIENTS = {
    "subtext": "two people want opposite things under polite words",
    "turn": "the scene flips on a reveal partway through",
    "character": "a vivid, specific person — a tic, an obsession, a lie",
    "stakes": "something real is on the line, not just a chore",
    "genre": "a scam, a confession, a ghost story, a flirtation",
}

# Words in dense rotation at once. Graduation is production going cold.
FOCUS_SIZE = 12
# Past this many reps the approach, not the word, needs changing: flagged, never
# evicted (a silently parked word is starvation).
STUCK_REPS = 10
# Hinted items silent this long surface for a cold retest — hinted otherwise has
# no follow-up path at all.
RETEST_DAYS = 14
# How long a fired ask suppresses re-asking the same item. It must exceed the
# learner's reply latency: an unanswered ask never sets `last_surfaced`, so
# silence makes an item MORE eligible and this guard is all that stands against it.
ASK_COOLDOWN_DAYS = 7
# Seats held inside the focus set for hinted items going dark.
RETEST_SLOTS = 2
# Seats held at the head of the ear queue for patterns.
EAR_PATTERN_SLOTS = 4

TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def probe_hit(probe: str, blob: str, tokens: set) -> bool:
    """Did this knock mention this lexicon entry? A phrase matches as a
    substring; a single word must match a whole token, or a short key is
    swallowed by every longer word containing it."""
    if not probe:
        return False
    parts = TOKEN_RE.findall(probe)
    if len(parts) > 1:
        return probe in blob
    return bool(parts) and parts[0] in tokens


def stable_jitter(word: str) -> str:
    """The last tiebreak: arbitrary but stable, so a tie group is spread rather
    than walked in an order (alphabetical) that freezes its tail."""
    return hashlib.sha1(word.encode("utf-8")).hexdigest()


def coverage_key(c: dict) -> tuple:
    """THE ordering law, defined once and read by every selector:

        fewest LIFETIME reps → least-recently-worked → ripeness → least-exposed → jitter

    Reps lead because coverage is the property that fails silently. Callers may
    prefix their own terms but may not reorder or drop these."""
    return (c.get("reps", 0),
            -c.get("staleness", 0),
            PROD_ORDER.get(c.get("production"), 1),
            RECOG_ORDER.get(c.get("recognition"), 1),
            c.get("exposures", 0),
            stable_jitter(c["word"]))


def rep_counts(lexicon: dict) -> dict:
    """word → LIFETIME declared reps, the coverage number (sessions and the reply
    judge write it). Not `recent_ask_counts`, which is a cooldown: using that as
    the coverage term makes a few words cycle forever while the rest starve."""
    return {w: r["reps"] for w, r in lexicon.items() if r.get("reps")}


def month_window(lexicon: dict) -> list[str]:
    """The arc's still-open members — what the focus window leads with. A
    graduate leaves a hole rather than summoning a replacement, so the arc
    visibly empties as it closes. The seam between the month and the registry,
    so it reads both; `month` itself never does."""
    learner = load_json(BASE / "progress" / "learner.json") or {}
    rec = month.load(learner)
    if not rec:
        return []
    episodes = load_json(BASE / "progress" / "episodes.json") or {}
    sidecars = {}
    for c in load_recent_sidecars():
        if isinstance(c.get("mission"), int):
            sidecars[c["mission"]] = c
    return month.standing(rec, lexicon, episodes, sidecars)["open_words"]


def floor_gap_targets(lexicon: dict, today, max_n: int,
                      asked: dict | None = None, reps: dict | None = None,
                      window: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    """THE ordered pool — every row not yet firing cold, rank-first, in TWO
    BUDGETS: FOCUS (≤FOCUS_SIZE, led by the month's open members, topped up from
    the background) and BACKGROUND (an exposure queue: least-exposed first, so
    coverage is guaranteed rather than hoped for). Within focus: rank, then
    least-asked (the cooldown), then the shared law."""
    if asked is None:
        asked = recent_ask_counts(load_json(KNOCK_LOG_PATH) or [], lexicon)
    if reps is None:
        reps = rep_counts(lexicon)
    lean = timeline.direction(timeline.load())   # resolved ONCE — never inside a sort key
    gap = []
    for w, r in lexicon.items():
        if r.get("type") == "pattern":
            continue  # patterns are forced via the Engines block
        if r.get("direction") == "catch":
            continue  # ear-only — `ear_targets` owns them
        if r.get("production") == "cold":
            continue  # graduated: never drilled again, just used
        ds = days_since(r.get("last_surfaced"), today)
        staleness = NEVER_SURFACED if ds is None else ds
        gap.append({
            "word": w, "gloss": r.get("gloss", ""),
            "recognition": r.get("recognition"), "production": r.get("production", "none"),
            "register": r.get("register", ""), "rank": timeline.register_rank(r, lean),
            "lead": timeline.RANK_NAMES[timeline.register_rank(r, lean)],
            "staleness": staleness, "soaked": len(r.get("seen_in", [])),
            "exposures": r.get("exposures", 0), "unseen": is_unseen(r),
            "retest": is_going_dark(r, ds),
            "asks": asked.get(w, 0), "reps": reps.get(w, 0),
            "heard_times": r.get("heard_times", 0),
        })
    by_word = {c["word"]: c for c in gap}
    if window is None:
        window = month_window(lexicon)
    focus = [by_word[w] for w in window if w in by_word][:FOCUS_SIZE]
    held = {c["word"] for c in focus}
    background = sorted((c for c in gap if c["word"] not in held), key=pool_key)
    seats_open = FOCUS_SIZE - len(focus)
    if seats_open > 0:
        focus += take_seats(background, seats_open)
        taken = {c["word"] for c in focus}
        background = [c for c in background if c["word"] not in taken]
    for c in focus:
        c["band"] = "focus"
    for c in background:
        c["band"] = "background"
    focus.sort(key=lambda c: (c["rank"], c["asks"], coverage_key(c)))
    return (focus[:max_n], background)


def take_seats(background: list[dict], seats: int) -> list[dict]:
    """Fill open focus seats, holding up to RETEST_SLOTS for items going dark.
    A FLOOR, never a ceiling: it only tops up when dark items won no seat on the
    ordering itself, because fewest-reps-first otherwise starves them forever."""
    natural = background[:seats]
    reserved = min(RETEST_SLOTS, seats // 2)
    if sum(1 for c in natural if c["retest"]) >= reserved:
        return natural
    dark = [c for c in background if c["retest"]][:reserved]
    rest = [c for c in background if not c["retest"]][:seats - len(dark)]
    return sorted(dark + rest, key=pool_key)


def pool_key(c: dict) -> tuple:
    """The pool's own order: rank, then the shared law."""
    return (c["rank"], coverage_key(c))


def recent_ask_counts(klog: list, lexicon: dict, days: int = ASK_COOLDOWN_DAYS, now=None) -> dict:
    """word → how many fired knocks in the last `days` asked for it (the
    expected target or a volley item) or printed it (body, memo, recast, chains).
    Importable without the model/TTS stack, because the ticket must be."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    recent = []
    for k in klog:
        if not k.get("acted", True):
            continue
        try:
            ts = datetime.fromisoformat((k.get("timestamp") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            continue
        # The *_script drafts are exact; the read surfaces are scanned too, since
        # the read-form rewrite falls back to the voice form when it fails.
        texts = [k.get(f, "") for f in ("body", "body_script", "memo_script", "reply_line", "reply_line_script")]
        texts += [x.get(f, "") for x in k.get("exchanges", []) for f in ("reply_line", "reply_line_script")]
        # Every volley item was asked, not just the one that opened it.
        targets = {k.get("expected_target", "")}
        targets |= {v.get("target", "") for v in (k.get("volley") or [])}
        blob = " ".join(t for t in texts if t).lower()
        recent.append((targets, blob, set(TOKEN_RE.findall(blob))))
    counts = {}
    for word in lexicon:
        n = sum(1 for tgts, blob, tokens in recent
                if word in tgts or probe_hit(word.lower(), blob, tokens))
        if n:
            counts[word] = n
    return counts


def is_going_dark(rec: dict, staleness: int | None) -> bool:
    """A hinted item gone silent — the follow-up path hinted never had. Never-
    surfaced rows are excluded (no prior test to repeat), and so are ear-only
    rows (a retest is a production move)."""
    return (rec.get("production") == "hinted"
            and rec.get("direction") != "catch"
            and staleness is not None and staleness < NEVER_SURFACED
            and staleness >= RETEST_DAYS)


def ear_targets(lexicon: dict, today=None, reps: dict | None = None) -> dict:
    """Comprehension targets: rows the learner cannot yet hear. Two populations
    needing OPPOSITE instructions, carried as `ear_only`:

      - `direction: "catch"` — ear-ONLY; never forced to fire.
      - patterns — often produced and still not heard; ear work here does not ban a fire.

    Eligibility is not the catch tag: a pattern the learner says but cannot hear
    belongs here. Never-surfaced rows STAY (a coverage queue, not a return
    clock): for a catch row the eavesdrop dose IS first contact. Patterns hold
    EAR_PATTERN_SLOTS seats at the head (a floor, never a ceiling)."""
    today = today or local_today()
    if reps is None:
        reps = rep_counts(lexicon)

    def stale(r: dict) -> int:
        ds = days_since(r.get("last_surfaced"), today)
        return NEVER_SURFACED if ds is None else ds

    pool = [(w, r) for w, r in lexicon.items()
            if r.get("direction") == "catch" or r.get("type") == "pattern"]

    pending = [{
        "word": w, "gloss": r.get("gloss", ""),
        "kind": "frame" if r.get("type") == "pattern" else r.get("type", "chunk"),
        "recognition": r.get("recognition"), "staleness": stale(r),
        "last_surfaced": r.get("last_surfaced"),
        "ear_only": r.get("direction") == "catch",
        # Hear this, say that: a catch item with a partner is drilled as a unit.
        "pairs_with": r.get("pairs_with"),
        "response_gloss": lexicon.get(r.get("pairs_with") or "", {}).get("gloss", ""),
        "reps": reps.get(w, 0), "soaked": len(r.get("seen_in", [])),
        "exposures": r.get("exposures", 0),
        "production": r.get("production", "none"),
    } for w, r in pool if r.get("recognition") != "solid"]
    pending.sort(key=coverage_key)

    held = [c for c in pending[:EAR_PATTERN_SLOTS] if c["kind"] == "frame"]
    if len(held) < EAR_PATTERN_SLOTS:
        seated = {c["word"] for c in
                  [c for c in pending if c["kind"] == "frame"][:EAR_PATTERN_SLOTS]}
        pending = ([c for c in pending if c["word"] in seated]
                   + [c for c in pending if c["word"] not in seated])

    return {"total": len(pool), "pending": pending,
            "caught": sum(1 for _, r in pool if r.get("recognition") == "solid"),
            "untouched": sum(1 for _, r in pool if not r.get("last_surfaced"))}


def check_due(today=None) -> int | None:
    """Days since the last BY-EAR Receptive Check, or None if never run. A cue on
    the surface the tutor reads every session, because the learner does not run
    commands. A page-only check records evidence but does not stop the clock: a
    check that cannot re-base the goal must not quiet the thing asking for one.
    Dated on the learner's clock."""
    events = load_json(OBSERVATIONS_PATH) or []
    days = [((today or local_today()) - local_date(e["at"])).days
            for e in events if e.get("channel") == "check"
            and observations.medium_of(e) == "audio"]
    return min(days) if days else None


def register_coverage(lexicon: dict, today=None) -> dict | None:
    """COVERAGE, not progress: how many rows have ever been WORKED, per register.
    A value-ordered queue starves its tail silently, and a cold/total headline
    can read like a won sprint while most rows were never touched. Rows with no
    register are one `unregistered` bucket so they cannot swamp a tier;
    `soaked_only` (heard, never asked) is the cheaper state to fix."""
    today = today or local_today()

    def bucket() -> dict:
        return {"total": 0, "touched": 0, "untouched": 0, "cleared": 0}

    # Register buckets are the FIRE side only; the ear has its own bucket.
    lean = timeline.direction(timeline.load())
    registers: dict[str, dict] = {}
    untouched: list[dict] = []
    fire, catch, unregistered = bucket(), bucket(), bucket()
    for w, r in lexicon.items():
        is_catch = r.get("direction") == "catch"
        reg = r.get("register", "")
        worked = bool(r.get("last_surfaced"))
        done = (r.get("recognition") == "solid") if is_catch else (r.get("production") == "cold")
        if is_catch:
            buckets = [catch]
        elif reg:
            buckets = [fire, registers.setdefault(reg, bucket())]
        else:
            buckets = [unregistered]
        for b in buckets:
            b["total"] += 1
            b["touched" if worked else "untouched"] += 1
            b["cleared"] += done
        if reg and not worked and not done:
            untouched.append({
                "word": w, "gloss": r.get("gloss", ""),
                "register": reg, "direction": "catch" if is_catch else "fire",
                "soaked_only": bool(r.get("seen_in")),
            })
    if not (fire["total"] or catch["total"]):
        return None
    untouched.sort(key=lambda c: (timeline.register_rank(c, lean), c["word"]))
    return {"registers": registers, "untouched": untouched, "lean": lean,
            "fire": fire, "catch": catch, "unregistered": unregistered}


def engines_to_fire(lexicon: dict) -> list[dict]:
    """Patterns not yet firing cold. The cold test is a NOVEL instance produced
    unaided, not a memorized line."""
    out = []
    for w, r in lexicon.items():
        if r.get("type") != "pattern" or r.get("production") == "cold":
            continue
        if r.get("direction") == "catch":
            continue  # ear-only patterns — train the ear, don't force
        out.append({"key": w, "gloss": r.get("gloss", ""),
                    "production": r.get("production", "none"), "unseen": is_unseen(r)})
    out.sort(key=lambda c: (c["production"] != "hinted", c["key"]))  # hinted (riper) first
    return out


def drill_menu(lexicon: dict, today=None, asked: dict | None = None,
               reps: dict | None = None, max_n: int = FOCUS_SIZE) -> list[dict]:
    """The pool's head as one flat production menu — the knock lane, the volley
    and the drill tape all pick from it. A view: the focus set plus the engines,
    composed once here. UNSEEN items ride WITH their flag; the teach-first law is
    the caller's (a menu shows them marked, a volley excludes them)."""
    lean = timeline.direction(timeline.load())
    focus, _bg = floor_gap_targets(lexicon, today or local_today(), max_n,
                                   asked=asked, reps=reps)
    menu = [{"word": t["word"], "gloss": t["gloss"], "kind": "chunk",
             "production": t["production"], "recognition": t["recognition"],
             "lead": t["lead"], "rank": t["rank"], "unseen": t["unseen"],
             "retest": t["retest"], "asks": t["asks"], "reps": t["reps"],
             "staleness": t["staleness"], "exposures": t["exposures"]}
            for t in focus]
    if reps is None:
        reps = rep_counts(lexicon)
    for e in engines_to_fire(lexicon):
        r = lexicon.get(e["key"], {})
        ds = days_since(r.get("last_surfaced"), today or local_today())
        menu.append({"word": e["key"], "gloss": e["gloss"], "kind": "frame",
                     "production": e["production"], "recognition": r.get("recognition"),
                     "lead": timeline.RANK_NAMES[timeline.register_rank(r, lean)],
                     "rank": timeline.register_rank(r, lean),
                     "unseen": e["unseen"], "retest": is_going_dark(r, ds),
                     "asks": (asked or {}).get(e["key"], 0), "reps": reps.get(e["key"], 0),
                     "staleness": NEVER_SURFACED if ds is None else ds,
                     "exposures": r.get("exposures", 0)})
    menu.sort(key=lambda c: (c["rank"], c["asks"], coverage_key(c)))
    return menu[:max_n]


def vocabulary_fence(lexicon: dict) -> list[dict]:
    """The 'sea' — every word the learner recognizes or produces cold. The
    Architect builds scenes from this pool; words outside it are the +1."""
    fence = []
    for w, r in lexicon.items():
        recog = r.get("recognition", "")
        prod = r.get("production", "")
        if recog in RECOGNIZED or prod == "cold":
            fence.append({"word": w, "gloss": r.get("gloss", "")})
    fence.sort(key=lambda e: e["word"])
    return fence


# ── The rotation's intake quota ──────────────────────────────────────────────
# A few pool words ride the head of the standing tape, and only ones its lead
# shape can teach: a root with hosts the lexicon already holds.
INTAKE_CAP = 5    # profile.md → Calibration Notes: new word types per audio dose
# Endings, not roots: they pass the host test by the dozen and are pattern material.
INTAKE_SKIP = {"case_markers", "aspect_auxiliaries"}


def inventory_hosts(lexicon: dict, roots=None) -> dict:
    """root -> phrases that appear to contain it. The gap is often INVENTORY, not
    vocabulary: the learner holds parts without knowing they are parts.

    The match is on `host_stem`, not the bare key, because a citation form can
    change shape inside a longer word. Substring matching is PROPOSAL ONLY and
    over-fires; the sheet-writer is told to drop coincidences — mechanism
    proposes, meaning disposes."""
    singles = [k for k in (lexicon if roots is None else roots)
               if " " not in k and not k.startswith("frame:") and len(k) >= 3]
    out = {}
    for root in singles:
        stem = host_stem(root)
        hosts = [k for k in lexicon
                 if k != root and stem in k and not k.startswith("frame:")]
        if len(hosts) >= 2:
            out[root] = hosts[:5]
    return out


def intake_rows(lexicon: dict, word_pool: list, cap: int | None = None) -> list[dict]:
    """Pool words for the head of an inventory tape: priority-1, not yet a row,
    not an ending, WITH hosts — in pool order, capped. Self-advancing: a word the
    tape taught is minted at delivery and leaves this list. The default cap is
    the timeline phase's (zero in a taper); an explicit `cap` is never second-guessed."""
    if cap is None:
        cap = timeline.intake_cap(timeline.load(), INTAKE_CAP)
    fresh = {e["word"]: e for e in word_pool if e.get("priority") == 1
             and e["word"] not in lexicon and e.get("cluster") not in INTAKE_SKIP}
    hosts = inventory_hosts(lexicon, fresh)
    return [{"word": w, "gloss": e.get("gloss", ""), "production": "none", "direction": "",
             "type": "", "register": "", "last_surfaced": "", "hosts": hosts[w],
             "intake": True}
            for w, e in fresh.items() if w in hosts][:cap]


def new_candidates_by_cluster(lexicon: dict, word_pool: list, n_clusters: int, per_cluster: int):
    """Priority-1 word-pool entries not yet in the lexicon, grouped by cluster,
    thinnest coverage first."""
    clusters: dict[str, dict] = {}
    for entry in word_pool:
        if entry.get("priority") != 1:
            continue
        cluster = entry.get("cluster", "uncategorized")
        c = clusters.setdefault(cluster, {"total": 0, "known": 0, "candidates": [], "seen": set()})
        word = entry["word"]
        if word in c["seen"]:
            continue
        c["seen"].add(word)
        c["total"] += 1
        if word in lexicon:
            c["known"] += 1
        else:
            c["candidates"].append({"word": word, "gloss": entry.get("gloss", "")})

    ranked = sorted(
        (c for c in clusters.items() if c[1]["candidates"]),
        key=lambda kv: (kv[1]["known"] / kv[1]["total"] if kv[1]["total"] else 1.0, -kv[1]["total"]),
    )
    return ranked[:n_clusters], per_cluster


def load_recent_sidecars(limit: int | None = None) -> list[dict]:
    """All *.tags.json sidecars with an integer mission, newest first."""
    cars = []
    for p in SCRIPTS_DIR.glob("*.tags.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(d.get("mission"), int):
            cars.append(d)
    cars.sort(key=lambda d: d.get("mission", 0), reverse=True)
    return cars[:limit] if limit else cars


def pick_divergent(palette, axis_key: str, sidecars: list[dict], rotate: int):
    """A palette value not used in the last DIVERGENCE_WINDOW episodes: never-used
    first, then least recently used. `rotate` spreads cold-start picks."""
    recent = {c.get(axis_key) for c in sidecars[:DIVERGENCE_WINDOW]}
    last_used: dict = {}
    for c in sidecars:  # newest-first → first occurrence is the most recent use
        v = c.get(axis_key)
        if v in palette and v not in last_used:
            last_used[v] = c.get("mission", 0)
    eligible = [v for v in palette if v not in recent] or list(palette)
    unused = [v for v in eligible if v not in last_used]
    if unused:
        return unused[rotate % len(unused)]
    return min(eligible, key=lambda v: last_used.get(v, -1))


def episode_commission(learner: dict | None = None) -> dict | None:
    """The standing soak order when it is a LIVE commission for the episode lane
    (has a payload, routed to episodes, still owed), else None. A consumed order
    must not keep commanding the ticket or pinning the next episode's form."""
    if learner is None:
        learner = load_json(BASE / "progress" / "learner.json") or {}
    order = learner.get("soak_order") or {}
    if not [w for w in order.get("payload", []) if w]:
        return None
    if (order.get("channel") or "episode") != "episode":
        return None
    if order.get("delivered") or not soak_pending():
        return None
    return order


def commissioned_form(learner: dict | None = None) -> str | None:
    """The form the standing order ASKS FOR, or None to let the gate roll. An
    unrecognised form is ignored loudly — a typo must not send the Director
    off-palette or silently mean "no episode"."""
    order = episode_commission(learner)
    if order is None:
        return None
    form = (order.get("form") or "").strip()
    if form and form not in ALL_FORMS:
        print(f"  ⚠ soak order asks for form '{form}', which the studio cannot "
              f"build — ignoring; the spec rolls as usual")
        return None
    return form or None


def slips_by_word(patterns: list[dict]) -> dict[str, list[dict]]:
    """Lexicon key → live slip patterns attached to it, worst first. Annotates a
    row already selected, so even a single slip is worth showing."""
    out: dict[str, list[dict]] = {}
    for p in patterns:
        if not p["live"]:
            continue
        for w in p["words"]:
            out.setdefault(w, []).append(p)
    for rows in out.values():
        rows.sort(key=lambda p: p["count"], reverse=True)
    return out


def slip_note(patterns: list[dict]) -> str:
    """The one-line annotation hung off a selected item."""
    p = patterns[0]
    said = p["examples"][-1][1] if p["examples"] else ""
    times = f"{p['count']}×" if p["count"] > 1 else "once"
    tail = ("Not a repetition problem — teach the pattern."
            if p["count"] > 1 else "Worth one clause of contrast.")
    return (f"      ↳ SLIPPED {times} ({p['tag']})"
            + (f" — last time: “{said}”. " if said else ". ") + tail)


def scene_spec(sidecars: list[dict], commissioned: str | None = None) -> dict:
    """The structural variety gate: register + form + ingredient, each diverging
    from the last 3 episodes. A commissioned form overrides the form axis only."""
    n = len(sidecars)
    ingredient = pick_divergent(list(INGREDIENTS), "dramatic_ingredient", sidecars, n)
    return {
        "register": pick_divergent(REGISTERS, "register", sidecars, n),
        "form": commissioned or pick_divergent(FORMS, "episode_form", sidecars, n),
        "commissioned": bool(commissioned),
        "ingredient": ingredient,
        "ingredient_desc": INGREDIENTS[ingredient],
        "recent": [(c.get("mission"), c.get("register", "—"), c.get("episode_form", "—"))
                   for c in sidecars[:DIVERGENCE_WINDOW]],
    }


def main():
    parser = argparse.ArgumentParser(description="The session ticket: floor-gap + callbacks + new candidates")
    parser.add_argument("--floor-max", type=int, default=FOCUS_SIZE,
                        help=f"Max focus-set words to show (default {FOCUS_SIZE} — the whole cohort)")
    parser.add_argument("--callbacks-max", type=int, default=5, help="Max due callbacks (default 5)")
    parser.add_argument("--clusters", type=int, default=5, help="Max thin clusters to surface (default 5)")
    parser.add_argument("--per-cluster", type=int, default=5, help="Max new candidates per cluster (default 5)")
    parser.add_argument("--fence", action="store_true",
                        help="include the Vocabulary Fence (the Director needs it; the tutor does not)")
    args = parser.parse_args()

    lexicon = load_json(LEXICON_PATH)
    word_pool = load_json(WORD_POOL_PATH)
    learner = load_json(BASE / "progress" / "learner.json") or {}
    # An EMPTY lexicon is valid day-zero state; only a MISSING file is an error.
    if lexicon is None or not word_pool:
        print("Error: lexicon.json or word_pool.json not found. See SETUP.md.")
        return
    today = local_today()

    print("=" * 60)
    print(f"SESSION TICKET — Python computes the menu; {TUTOR} picks the story.")
    print("=" * 60)

    # The lean and the marker — no dates, no countdown, no denominator: a
    # countdown in the coach's mouth is a pressure device. The schedule lives on
    # the learner's own surfaces.
    _ph = timeline.phase(timeline.load(learner))
    if _ph:
        print(f"\n🧭 WORKING {_ph['direction'].upper()} — to the "
              f"{timeline.ROOMS.get(_ph['direction'], _ph['direction'])}.\n"
              f"   What this phase is for: {_ph['marker']}")

    # The deliberate unlock priority (`sync_state update --next-engine`).
    next_engine_key = learner.get("next_engine", "")
    if next_engine_key and lexicon:
        r = lexicon.get(next_engine_key, {})
        prod = r.get("production", "none")
        if prod != "cold":
            gloss = r.get("gloss", "")
            unseen_flag = " · ⚠ UNSEEN — teach first (show it), NEVER cold-quiz" if is_unseen(r) else ""
            print(f"\n🎯 NEXT ENGINE: {next_engine_key} — {gloss}  [production: {prod}{unseen_flag}]")
            print("   One cold novel instance of this pattern = engine online.")

    asked = recent_ask_counts(load_json(KNOCK_LOG_PATH) or [], lexicon)
    reps = rep_counts(lexicon)
    slips = slip_patterns()
    slipped = slips_by_word(slips)

    # THE COMMISSION — the repair that earned this dose, ahead of everything the
    # ticket computes. It arrives as computed context because a prose pointer to
    # "read the soak order" loses to a code-assembled list.
    commission = episode_commission(learner)
    if commission:
        print("\n★ THE COMMISSION  (⚠ THIS OUTRANKS EVERY LIST BELOW — build the "
              "episode around it)")
        print("-" * 60)
        print("  PAYLOAD (must be audible in the script, repeatedly):")
        for item in [w for w in commission.get("payload", []) if w]:
            print(f"    → {item}")
        if commission.get("focus"):
            print(f"\n  FOCUS: {commission['focus']}")
        if commission.get("scene_seed"):
            print(f"\n  SCENE SEED: {commission['scene_seed']}")
        print(f"\n  Commissioned {commission.get('from', '—')} off a mistake the learner is "
              f"still making. The lists below are the SEA this scene swims in; the")
        print("  payload above is what it is FOR. An episode that does not carry it "
              "has not filled the order, however good it is.")

    spec = scene_spec(load_recent_sidecars(), commissioned_form(learner))
    print("\n0. SCENE SPEC  (force range; vary everything EXCEPT the vocabulary)")
    print("-" * 60)
    print(f"  Register:   {spec['register']}")
    print(f"  Form:       {spec['form']}"
          f"{'  ← COMMISSIONED by the soak order; do NOT re-pick' if spec['commissioned'] else ''}")
    print(f"  Ingredient: {spec['ingredient']} — {spec['ingredient_desc']}")
    if spec["recent"]:
        recent_str = ", ".join(f"M{m} {reg}/{form}" for m, reg, form in spec["recent"])
        print(f"  (diverging from last {DIVERGENCE_WINDOW}: {recent_str})")

    # 1. The pool. FOCUS is drilled; BACKGROUND is exposed by the render lanes
    # and not printed. The ear steers WHAT; the slip ledger (in `status`) steers HOW.
    print(f"\n1. FOCUS SET  (≤{FOCUS_SIZE} candidates for teaching and production probes; THE EAR leads)")
    print("-" * 60)
    if commission:
        print("  ⚠ A COMMISSION IS LIVE (top of the ticket). It outranks this list — these are "
              "what the scene may draw on, not what it is about.")
    gap, background = floor_gap_targets(lexicon, today, args.floor_max,
                                        asked=asked, reps=reps)
    if not gap:
        print("  (the pool is clear — nothing is stuck below cold)")
    for t in gap:
        tag = "hinted→cold" if t["production"] == "hinted" else f"{t['recognition']}, cold-pending"
        rep = f"{t['reps']} rep{'s' if t['reps'] != 1 else ''}" if t["reps"] else "never drilled"
        cool = f"  · asked in last {ASK_COOLDOWN_DAYS}d — vary the scene or take the next one" if t["asks"] else ""
        if t["reps"] >= STUCK_REPS:
            cool = (f"  · ⚠ STUCK — {t['reps']} reps and still not cold (most words take 2). "
                    f"Drilling it again won't work; change the angle.")
        if t["unseen"]:
            cool += "  · ⚠ UNSEEN — teach first (show it, gloss it), NEVER cold-quiz"
        # A priming cue, not a score: prime a word heard often; never quiz one
        # never played (a cold ask on an unplayed dose is collecting homework).
        heard = f" · heard {t['heard_times']}x" if t.get("heard_times") else ""
        print(f"  - [{t['lead']}] {t['word']} — {t['gloss'] or '[no gloss]'}  [{tag} · {rep}{heard}]{cool}")
        if t["retest"]:
            print(f"      ↳ GOING DARK — {t['staleness']}d silent since it was hinted. "
                  f"Retest it cold in a scene that does not hand it over.")
        if t["word"] in slipped:
            print(slip_note(slipped[t["word"]]))
    print("  Cold production leaves this probe pool; it does not prove comprehension. "
          "Use these words in exchanges, with THE EAR below steering the lesson.")

    ear = ear_targets(lexicon, today=today, reps=reps)
    if ear["total"]:
        # No ratio here: a menu that carries its own score invites reading it as
        # progress. This block says WHICH, never HOW MANY.
        print("\n1a. THE EAR  (comprehension — the primary steer; win = recognition, "
              "never a fire)")
        print("-" * 60)
        since = check_due(today)
        if since is None or since >= CHECK_EVERY_DAYS:
            ago = "never run" if since is None else f"{since}d ago"
            print(f"  ⏱ RECEPTIVE CHECK IS DUE ({ago}) — `python scripts/sync_state.py "
                  f"check --draw 30`, worked into the hour one item at a time, never "
                  f"shown as a list. It is the only thing that can re-base the goal.")
        for t in ear["pending"][:8]:
            never = " · never worked" if t["staleness"] >= NEVER_SURFACED else ""
            axis = "" if t["ear_only"] else "  · the learner FIRES this — the ear is what is behind"
            print(f"  - [{t['kind']}] {t['word']} — {t['gloss'] or '[no gloss]'}  [{t['recognition']}{never}]{axis}")
            if t.get("pairs_with"):
                print(f"      ↳ the answer: {t['pairs_with']} — {t['response_gloss'] or '[no gloss]'}"
                      f"  (drill the PAIR: hear it, answer it — recognition alone isn't the win here)")

    cov = register_coverage(lexicon, today=today)
    if cov and cov["fire"]["total"]:
        print("\n1c. COVERAGE  (how many have been WORKED — the meter cold/total can't see)")
        print("  ENGINEERING NUMBERS — they steer selection; they are never narrated to the learner.")
        print("-" * 60)
        for reg, b in sorted(cov["registers"].items(),
                             key=lambda kv: (timeline.register_rank({"register": kv[0]}, cov["lean"]), kv[0])):
            mark = timeline.RANK_NAMES[timeline.register_rank({"register": reg}, cov["lean"])]
            flag = "  ⚠" if b["untouched"] else ""
            print(f"  {reg:12} worked {b['touched']:3}/{b['total']:3} · "
                  f"cold {b['cleared']:3}  [{mark}]{flag}")
        c = cov["catch"]
        if c["total"]:
            print(f"  {'ear-only':12} worked {c['touched']:3}/{c['total']:3} · solid {c['cleared']:3}"
                  + ("  ⚠" if c["untouched"] else ""))
        u = cov["unregistered"]
        if u["total"]:
            print(f"  {'unranked':12} worked {u['touched']:3}/{u['total']:3} · cold {u['cleared']:3}"
                  f"   (no register — they sort mid; ranking them is a curriculum job)")
        if cov["untouched"]:
            u_fire = [x for x in cov["untouched"] if x["direction"] == "fire"]
            u_catch = [x for x in cov["untouched"] if x["direction"] == "catch"]
            soaked = sum(1 for x in cov["untouched"] if x["soaked_only"])
            ear_str = f" + {len(u_catch)} ear-only" if u_catch else ""
            print(f"\n  ⚠ NEVER WORKED, among the ranked: {len(u_fire)} fire item(s){ear_str} "
                  f"({soaked} heard in an episode but never asked).")
            starving = [f"{r} ({x['untouched']})" for r, x in sorted(
                cov["registers"].items(), key=lambda kv: -kv[1]["untouched"])
                if x["untouched"]]
            if starving:
                print("     Starving registers: " + ", ".join(starving))
            print("     They sort to the head of their tier — fire from the top and this drains.")

    engines = engines_to_fire(lexicon)
    if engines:
        print("\n1d. ENGINES TO FIRE  (patterns — force a NOVEL instance, not a memorized line)")
        print("-" * 60)
        for e in engines:
            tag = "hinted→cold" if e["production"] == "hinted" else "cold-pending"
            if e.get("unseen"):
                tag += " · ⚠ UNSEEN — teach first (show it, gloss it), NEVER cold-quiz"
            print(f"  - {e['key']} — {e['gloss'] or '[no gloss]'}  [{tag}]")

    print("\n2. DUE CALLBACKS  (soft soak — weave in where they fit)")
    print("-" * 60)
    callbacks = due_callbacks(lexicon, today, args.callbacks_max)
    if not callbacks:
        print("  (nothing due — the recognized set is fresh)")
    for cb in callbacks:
        tag = cb["recognition"] + (" · ear" if cb.get("direction") == "catch" else "")
        print(f"  - {cb['word']} — {cb['gloss'] or '[no gloss]'}  [{tag}]")

    print("\n3. NEW CANDIDATES BY CLUSTER  (priority-1, not yet met — pick a thin cluster)")
    print("-" * 60)
    ranked, per_cluster = new_candidates_by_cluster(lexicon, word_pool, args.clusters, args.per_cluster)
    if not ranked:
        print("  (no priority-1 clusters with unmet words)")
    for name, c in ranked:
        print(f"  [{name}]  known {c['known']}/{c['total']}")
        for cand in c["candidates"][:per_cluster]:
            print(f"      - {cand['word']} — {cand['gloss']}")

    if not args.fence:
        return
    print("\n4. VOCABULARY FENCE  (the sea — Architect builds from these; everything else is +1)")
    print("-" * 60)
    fence = vocabulary_fence(lexicon)
    if not fence:
        print("  (empty — no recognized words yet; Architect must scaffold heavily with the learner's language)")
    else:
        print(f"  {len(fence)} known words. The Architect should build dialogue from this pool.")
        print("  Words outside this list must be answerable from context within seconds.")
        print()
        for entry in fence:
            print(f"  - {entry['word']} — {entry['gloss'] or '[no gloss]'}")

    floor_gap_total = sum(1 for r in lexicon.values()
                          if r.get("type") != "pattern" and r.get("direction") != "catch"
                          and r.get("recognition") in RECOGNIZED and r.get("production") != "cold")
    print(f"\nFloor gap: {floor_gap_total} recognized words not yet firing cold.")
    print(f"Vocabulary fence: {len(fence)} words (the sea).")


if __name__ == "__main__":
    main()
