#!/usr/bin/env python3
"""
The session "ticket" — the menu Python hands the tutor so they never pick words
by eyeballing a 2000-line lexicon. The tutor chooses the story and meaning; this
script computes the candidate set. The bright line: Python computes the menu,
the tutor makes the choice.

Four parts:
  1. FOCUS SET + BACKGROUND — words recognized (comfortable/solid) but not yet
     firing cold, split into TWO BUDGETS. The focus set is ≤FOCUS_SIZE words in
     dense rotation, drilled until they fire cold and then never drilled again.
     The background is everything else: exposure only — soak them into scenes so
     the tail can't rot, never force them to fire. One ranked list cannot do both
     jobs, and trying made it do neither.
  2. DUE CALLBACKS — soft soak targets, reusing generate_callbacks.py (no
     duplicated logic).
  3. NEW CANDIDATES BY CLUSTER — priority-1 word_pool entries not yet in the
     lexicon, grouped by cluster with a coverage stat so the tutor can see which
     clusters are thin. Python shows coverage; the tutor picks the cluster.
  4. VOCABULARY FENCE — all recognized words (comfortable/solid) plus cold
     productions. This is "the sea" the Architect builds from. Every word of
     dialogue that isn't payload should come from this list.

Usage:
    python scripts/suggest_targets.py [--floor-max 8] [--clusters 5] [--per-cluster 5]
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_callbacks import due_callbacks, load_json, days_since, NEVER_SURFACED
from config import (DECK_NAME, DECK_LABEL, DECK_TIERS, TIER_NAMES,
                    FOCUS_SIZE, ASK_COOLDOWN_DAYS)
from sync_state import is_unseen

# Windows consoles default to cp1252 and can't print some scripts (2026-07-15).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent.parent
LEXICON_PATH = BASE / "progress" / "lexicon.json"
WORD_POOL_PATH = BASE / "curriculum" / "word_pool.json"
KNOCK_LOG_PATH = BASE / "progress" / "knock_log.json"
LEARNER_PATH = BASE / "progress" / "learner.json"
SCRIPTS_DIR = BASE / "content" / "scripts"

RECOGNIZED = {"comfortable", "solid"}
# Most-ready-to-fire first: hinted is one hint from cold; among equals, the more
# strongly recognized word is the riper target for forced production.
PROD_ORDER = {"hinted": 0, "none": 1}
RECOG_ORDER = {"solid": 0, "comfortable": 1}

# Drilling that isn't working, FLAGGED not evicted. A word far past the typical
# reps-to-cold is at the point where the approach — not the word — is what needs
# changing. It keeps its focus seat (it IS unfinished); the tutor is told to
# switch angle. Deliberately NOT an eviction rule: a silently parked word is the
# starvation the two-budget split exists to fix.
STUCK_REPS = 10

# Whole-token matching for the ask cooldown (see `probe_hit`). Unicode-aware so
# it works for any script.
TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# ── Scene-spec palettes ──────────────────────────────────────────────
# Variety is structural, not taste: Python forces range on the axes that
# actually make an episode feel fresh, and the tutor/the Director write the
# story inside that frame. The divergence gate forbids repeating any value used
# in the last DIVERGENCE_WINDOW episodes (read from the *.tags.json sidecars).
DIVERGENCE_WINDOW = 3

# Emotional tone — the axis feeds tend to collapse onto "mild irritation".
REGISTERS = ["tenderness", "dread", "mischief", "pride", "suspicion",
             "grief/nostalgia", "delight", "embarrassment", "defiance", "reconciliation"]
# Episode structure (matches the Architect's Episode Form). "lore" is the
# stories-are-curriculum lens (constitution): the payload word as protagonist —
# gate-rotated like every form so it can't take over the feed.
FORMS = ["classic", "vignette", "story", "phone_call", "lore"]
# One dramatic ingredient — all free of vocabulary, all situational.
INGREDIENTS = {
    "subtext": "two people want opposite things under polite words",
    "turn": "the scene flips on a reveal partway through",
    "character": "a vivid, specific person — a tic, an obsession, a lie",
    "stakes": "something real is on the line, not just a chore",
    "genre": "a scam, a confession, a ghost story, a flirtation",
}


def deck_registers(deck: str = DECK_NAME) -> dict:
    """word → curriculum register, joined at menu time from the deck's curriculum
    file — ordering is a menu concern, not state, so the lexicon schema stays
    frozen. Missing file or register degrades to flat ordering. Tier priorities
    themselves live in config (deck.tiers) — a setup-time elaboration, not a
    template opinion."""
    for path in (BASE / "curriculum" / f"{deck}_deck.json",
                 BASE / "curriculum" / "deck.json"):
        if path.exists():
            return {i.get("word", ""): i.get("register", "")
                    for i in json.loads(path.read_text(encoding="utf-8"))}
    return {}


def probe_hit(probe: str, blob: str, tokens: set) -> bool:
    """Did this text mention this lexicon entry?

    A multi-word probe is a phrase and matches as a substring. A SINGLE-word
    probe must match a whole TOKEN, because substring matching makes short keys
    swallow longer ones — a two-character word is inside a dozen longer ones and
    its count inflates to nonsense. Probe matching survives ONLY in
    `recent_ask_counts` (the ask cooldown), where the tutor's free prose
    genuinely is the only source; the counting path is declared events."""
    if not probe:
        return False
    parts = TOKEN_RE.findall(probe)
    if len(parts) > 1:
        return probe in blob
    return bool(parts) and parts[0] in tokens


def stable_jitter(word: str) -> str:
    """The last tiebreak. Alphabetical was the old one, and it is the reason the
    head of a tie group froze: every pass through a cohort happened in the same
    order, so the tail of the alphabet was unreachable. A hash of the word is
    arbitrary but STABLE — deterministic for tests, and it spreads the cohort
    instead of ordering it by a property that correlates with nothing."""
    return hashlib.sha1(word.encode("utf-8")).hexdigest()


def coverage_key(c: dict) -> tuple:
    """THE ordering law, defined once and read by BOTH selectors — the deck and
    the general floor. It exists as a function because the alternative is two
    hand-copied sort keys in two files: the law gets extended in one and not the
    other, and the un-extended half freezes. A term added here reaches every
    channel or none.

        fewest LIFETIME reps → least-recently-worked → ripeness → least-exposed → jitter

    Reps lead because coverage is the property that fails silently; staleness
    cannot break the tie when most of the population has never been worked at
    all. Least-EXPOSED, not most-soaked: sorting the already-heard EARLIER is a
    positive feedback loop (the exposed get more exposed), the anti-coverage
    direction for an exposure queue — and `seen_in` is provenance, not a fairness
    counter. Callers may prefix their own terms (the deck prefixes tier) but may
    not reorder or drop these."""
    return (c.get("reps", 0),
            -c.get("staleness", 0),
            PROD_ORDER.get(c.get("production"), 1),
            RECOG_ORDER.get(c.get("recognition"), 1),
            c.get("exposures", 0),
            stable_jitter(c["word"]))


def rep_counts(lexicon: dict) -> dict:
    """word → LIFETIME declared reps. THE coverage number.

    One counter, two writers: sessions (`sync_state.cmd_update`) and the reply
    judge (`knock_reply.apply_verdict`, one increment per word in a judged
    reply's `fired` list — partial counts included). DECLARED EVENTS ONLY: the
    tempting alternative is to mine the tutor's own prose for mentions, and that
    counts the tutor talking as the learner producing — which allocates focus
    seats by mention frequency and flags never-drilled words as stuck.

    Not to be confused with `recent_ask_counts`, which is a short COOLDOWN — a
    different question with a different answer. Using the cooldown as the
    coverage term is the other classic defect: the count resets after a few days
    and the same words rejoin the front of the queue forever, so a small cycle
    churns while most of the population is never reachable at all."""
    return {w: r["reps"] for w, r in lexicon.items() if r.get("reps")}


def stored_focus_cohort() -> list[str]:
    """The persisted ≤FOCUS_SIZE membership (learner.json, Python-owned).
    [] means no cohort has been seeded yet — day-zero, or a fresh clone."""
    learner = load_json(LEARNER_PATH) or {}
    return [w for w in learner.get("focus_cohort", []) if isinstance(w, str)]


def floor_gap_targets(lexicon: dict, today, max_n: int,
                      asked: dict | None = None, reps: dict | None = None,
                      cohort: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    """The general floor — everything outside the deck. TWO BUDGETS, not one
    ranked list:

      FOCUS      ≤ FOCUS_SIZE words in dense rotation, drilled until they fire
                 cold. Membership is STORED STATE (learner.json), not an
                 emergent sort: a word enters when a seat opens and leaves only
                 on graduation, so membership is a fact readable in a file,
                 immune to counting bugs by construction.
      BACKGROUND everything else. It is an EXPOSURE queue, not a drill queue —
                 soak/episode candidates that keep a word warm without forcing
                 it to fire. Least-exposed/least-recently-exposed first, so
                 coverage is guaranteed rather than hoped for.

    Coverage-first and dense-repetition are in real tension: one ranked list
    either touches the whole population once a month (breadth, nothing
    graduates) or hammers a dozen (depth, the tail rots). Splitting the budget
    is what lets both hold.

    `cohort` is the stored membership; None loads it from learner.json. A held
    word that graduated (or left the floor population — demotion, deck re-tag)
    vacates its seat here; open seats are filled from the front of the
    background order. Persisting the result is the WRITE seams' job
    (`reconcile_focus` via sync_state / knock_reply), never this reader's."""
    if asked is None:
        asked = recent_ask_counts(load_json(KNOCK_LOG_PATH) or [], lexicon)
    if reps is None:
        reps = rep_counts(lexicon)
    if cohort is None:
        cohort = stored_focus_cohort()
    gap = []
    for w, r in lexicon.items():
        if r.get("type") == "pattern":
            continue  # patterns are forced via the Engines block, not the word floor
        if r.get("direction") == "catch":
            continue  # ear-only deck items — never forced to fire
        if r.get("recognition") not in RECOGNIZED or r.get("production") == "cold":
            continue
        ds = days_since(r.get("last_surfaced"), today)
        staleness = NEVER_SURFACED if ds is None else ds
        gap.append({
            "word": w, "gloss": r.get("gloss", ""),
            "recognition": r.get("recognition"), "production": r.get("production", "none"),
            "staleness": staleness, "soaked": len(r.get("seen_in", [])),
            "exposures": r.get("exposures", 0),
            "asks": asked.get(w, 0), "reps": reps.get(w, 0),
        })
    by_word = {c["word"]: c for c in gap}
    if cohort:
        # Stored membership: held seats stand regardless of what any counter
        # says. Graduates (and words that left the floor population) drop out
        # of `by_word` and so vacate their seats here.
        focus = [by_word[w] for w in cohort if w in by_word][:FOCUS_SIZE]
    else:
        # SEED derivation — no cohort stored yet. Words already started hold
        # seats (most-repped first: they are mid-fight, benching them is the
        # churn the stored cohort exists to prevent).
        focus = sorted((c for c in gap if c["reps"]),
                       key=lambda c: (-c["reps"], stable_jitter(c["word"])))[:FOCUS_SIZE]
    held = {c["word"] for c in focus}
    background = sorted((c for c in gap if c["word"] not in held), key=coverage_key)
    seats_open = FOCUS_SIZE - len(focus)
    if seats_open > 0:
        focus += background[:seats_open]
        background = background[seats_open:]
    for c in focus:
        c["band"] = "focus"
    for c in background:
        c["band"] = "background"
    # Within the focus set, least-repped first — spread the reps across the
    # cohort rather than finishing one word at a time. The cooldown still
    # applies INSIDE the set: a word asked in the last ASK_COOLDOWN_DAYS drops
    # behind its cohort-mates for a couple of days. That is the job `asks` was
    # built for and the only job it does now.
    focus.sort(key=lambda c: (c["asks"], coverage_key(c)))
    return (focus[:max_n], background)


def reconcile_focus(lexicon: dict, cohort: list[str], today=None) -> list[str]:
    """The WRITE side of the stored cohort: leave on graduation, enter on
    seat-open. Pure — returns the new membership, sorted for diff stability; the
    callers that persist it are the two seams where graduation can happen
    (`sync_state.cmd_update` and the judge flow in `knock_reply`)."""
    focus, _bg = floor_gap_targets(lexicon, today or date.today(), FOCUS_SIZE,
                                   asked={}, cohort=cohort)
    return sorted(c["word"] for c in focus)


def recent_ask_counts(klog: list, lexicon: dict, days: int = ASK_COOLDOWN_DAYS,
                      now=None) -> dict:
    """word → how many fired knocks in the last `days` asked for it (the original
    `expected_target`) or printed it (body/memo/reply, whole chains).

    Lives HERE, not in `morning_knock`, because the selector is shared and the
    ticket must stay importable without the LLM/TTS stack — outreach may depend
    on selection, never the reverse. It guards a gap staleness cannot see: an
    ask with no reply never sets `last_surfaced`, so a missed item stays
    maximally stale and would be re-asked forever."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    recent = []
    for k in klog:
        if not k.get("acted", True):  # legacy entries (no 'acted') were all fires
            continue
        try:
            ts = datetime.fromisoformat((k.get("timestamp") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            continue
        texts = [k.get("body", ""), k.get("memo_script", ""), k.get("reply_line", "")]
        texts += [x.get("reply_line", "") for x in k.get("exchanges", [])]
        # Every item of a volley was asked, not just the one that opened it —
        # `expected_target` names item 1 and Python walks the rest, so items 2..n
        # were invisible to this count while being the deck's main volume
        # channel. Their asks are native-language situations, so only the
        # targets carry the signal.
        targets = {k.get("expected_target", "")}
        targets |= {v.get("target", "") for v in (k.get("volley") or [])}
        blob = " ".join(t for t in texts if t).lower()
        recent.append((targets, blob, set(TOKEN_RE.findall(blob))))
    counts = {}
    for word, rec in lexicon.items():
        probes = [word.lower()] + [p.lower() for p in rec.get("phonetic", []) if p]
        n = sum(1 for tgts, blob, tokens in recent
                if word in tgts or any(probe_hit(p, blob, tokens) for p in probes))
        if n:
            counts[word] = n
    return counts


def deck_status(lexicon: dict, deck: str = DECK_NAME, today=None,
                asked: dict | None = None, reps: dict | None = None) -> dict | None:
    """A finite, usually deadline-driven deck (the survival set for a real
    event), tagged `deck: "<name>"`. During a sprint this is the HEADLINE
    priority — the tutor forces its not-yet-cold members first. Members split
    by `direction`: "fire" (default — force to cold production) vs "catch"
    (ear-only — the win is solid recognition via eavesdrop/soak; NEVER force
    these to fire). Returns fire progress + pending fire items (chunks said
    whole, frames want a novel slot-fill) + pending catch items, or None if no
    deck exists."""
    members = [(w, r) for w, r in lexicon.items() if r.get("deck") == deck]
    if not members:
        return None
    today = today or date.today()
    regs = deck_registers(deck)
    if asked is None:
        asked = recent_ask_counts(load_json(KNOCK_LOG_PATH) or [], lexicon)
    if reps is None:
        reps = rep_counts(lexicon)
    fire = [(w, r) for w, r in members if r.get("direction", "fire") != "catch"]
    catch = [(w, r) for w, r in members if r.get("direction") == "catch"]
    cold = [w for w, r in fire if r.get("production") == "cold"]

    def stale(r: dict) -> int:
        ds = days_since(r.get("last_surfaced"), today)
        return NEVER_SURFACED if ds is None else ds

    pending = [{
        "word": w, "gloss": r.get("gloss", ""),
        "kind": "frame" if r.get("type") == "pattern" else r.get("type", "chunk"),
        "recognition": r.get("recognition"), "production": r.get("production", "none"),
        "tier": TIER_NAMES.get(DECK_TIERS.get(regs.get(w, ""), len(TIER_NAMES))),
        "unseen": is_unseen(r), "staleness": stale(r),
        "last_surfaced": r.get("last_surfaced"), "asks": asked.get(w, 0),
        "reps": reps.get(w, 0), "soaked": len(r.get("seen_in", [])),
        "exposures": r.get("exposures", 0),
    } for w, r in fire if r.get("production") != "cold"]
    # tier → ask-cooldown → coverage_key. Tier stays primary (it is the deck's
    # pecking order, a setup-time elaboration); the cooldown rides next, exactly
    # as inside the floor's focus set — an unanswered ask is SPEND, and without
    # this term a hidden-target ask would sit at the front and re-fire forever.
    # The rest is `coverage_key`, the SHARED law, so the deck and the general
    # floor cannot drift apart. Unlisted registers sink below every configured
    # tier; no tiers ⇒ the coverage law alone. The deck keeps no focus/background
    # split: it is a finite deadline set, so every member has to clear, and the
    # tiers already say what leads.
    pending.sort(key=lambda c: (DECK_TIERS.get(regs.get(c["word"], ""), len(TIER_NAMES)),
                                c["asks"], coverage_key(c)))
    catch_pending = [{
        "word": w, "gloss": r.get("gloss", ""),
        "kind": "frame" if r.get("type") == "pattern" else r.get("type", "chunk"),
        "recognition": r.get("recognition"), "staleness": stale(r),
        "last_surfaced": r.get("last_surfaced"), "asks": asked.get(w, 0),
        # The pair, resolved for the drill: hear this, say that. A catch item
        # with a partner is drillable as a UNIT — recognizing it is only half
        # the win if the answer doesn't arrive.
        "pairs_with": r.get("pairs_with"),
        "response_gloss": lexicon.get(r.get("pairs_with") or "", {}).get("gloss", ""),
        "reps": reps.get(w, 0), "soaked": len(r.get("seen_in", [])),
        "exposures": r.get("exposures", 0),
        "production": r.get("production", "none"),
    } for w, r in catch if r.get("recognition") != "solid"]
    # Same shared law on the ear — no tier prefix, because catch items clear on
    # recognition and the tier order is a production idea. The ear is the half
    # that starves hardest when nothing rotates it.
    catch_pending.sort(key=coverage_key)
    return {"total": len(fire), "cold": len(cold), "pending": pending,
            "catch_total": len(catch),
            "caught": sum(1 for _, r in catch if r.get("recognition") == "solid"),
            "catch_pending": catch_pending}


def deck_coverage(lexicon: dict, deck: str = DECK_NAME, today=None) -> dict | None:
    """COVERAGE, not progress — the meter a deck headline cannot see.
    `deck_status` answers "how many fire cold?"; this answers "how many have
    ever been WORKED at all?" (a session rep, a judged reply, or a show dose —
    anything that sets `last_surfaced`). An ask with no reply does not count,
    which is exactly why the ask cooldown is a sort term and not this meter.

    The pair matters because a value-ordered queue starves its tail silently: a
    headline can read "won sprint" on pace while most of the deck has never been
    worked at all, and the registers that carry the real-world stakes sit near
    zero. cold/total is honest about what it counts and structurally blind to
    distribution. Reported per tier and per register so the blindness has
    nowhere to hide.

    `soaked_only` = never worked, but heard in an episode: a different state
    from never encountered, and the cheaper one to fix."""
    members = [(w, r) for w, r in lexicon.items() if r.get("deck") == deck]
    if not members:
        return None
    today = today or date.today()
    regs = deck_registers(deck)

    def bucket() -> dict:
        return {"total": 0, "touched": 0, "untouched": 0, "cleared": 0}

    # Tier/register buckets are the FIRE side only — the same split every other
    # caller keeps, so every headline stays honest. The ear gets its own bucket;
    # folding it into the tiers would inflate the top tier with catch frames.
    tiers: dict[str, dict] = {}
    registers: dict[str, dict] = {}
    untouched: list[dict] = []
    fire, catch = bucket(), bucket()
    for w, r in members:
        is_catch = r.get("direction") == "catch"
        reg = regs.get(w, "")
        tier = TIER_NAMES.get(DECK_TIERS.get(reg, len(TIER_NAMES)), "")
        worked = bool(r.get("last_surfaced"))
        done = (r.get("recognition") == "solid") if is_catch else (r.get("production") == "cold")
        buckets = [catch] if is_catch else [fire, tiers.setdefault(tier, bucket()),
                                            registers.setdefault(reg or "?", bucket())]
        for b in buckets:
            b["total"] += 1
            b["touched" if worked else "untouched"] += 1
            b["cleared"] += done
        if not worked and not done:
            untouched.append({
                "word": w, "gloss": r.get("gloss", ""), "tier": tier,
                "register": reg or "?", "direction": "catch" if is_catch else "fire",
                "soaked_only": bool(r.get("seen_in")),
            })
    untouched.sort(key=lambda c: (DECK_TIERS.get(
        regs.get(c["word"], ""), len(TIER_NAMES)), c["word"]))
    return {"tiers": tiers, "registers": registers, "untouched": untouched,
            "fire": fire, "catch": catch}


def engines_to_fire(lexicon: dict) -> list[dict]:
    """Generative patterns (lemmas / frames) not yet firing cold. These are forced
    differently from words: the cold test is producing a NOVEL instance unaided,
    not reciting a memorized line."""
    out = []
    for w, r in lexicon.items():
        if r.get("type") != "pattern" or r.get("production") == "cold":
            continue
        if r.get("direction") == "catch":
            continue  # ear-only patterns — train the ear, don't force

        out.append({"key": w, "gloss": r.get("gloss", ""), "production": r.get("production", "none"),
                    "unseen": is_unseen(r)})
    out.sort(key=lambda c: (c["production"] != "hinted", c["key"]))  # hinted (riper) first
    return out


def vocabulary_fence(lexicon: dict) -> list[dict]:
    """The 'sea' — every word the learner recognizes or produces cold.
    The Architect builds scenes from this pool. Words outside it are the +1."""
    fence = []
    for w, r in lexicon.items():
        recog = r.get("recognition", "")
        prod = r.get("production", "")
        if recog in RECOGNIZED or prod == "cold":
            fence.append({
                "word": w,
                "gloss": r.get("gloss", ""),
                "phonetic": r.get("phonetic", []),
            })
    fence.sort(key=lambda e: e["word"])
    return fence


def new_candidates_by_cluster(lexicon: dict, word_pool: list, n_clusters: int, per_cluster: int):
    """Priority-1 word_pool entries not yet in the lexicon, grouped by cluster.
    Coverage = how many of a cluster's priority-1 entries are already known."""
    clusters: dict[str, dict] = {}
    for entry in word_pool:
        if entry.get("priority") != 1:
            continue
        cluster = entry.get("cluster", "uncategorized")
        c = clusters.setdefault(cluster, {"total": 0, "known": 0, "candidates": [], "seen": set()})
        word = entry["word"]
        if word in c["seen"]:
            continue  # tolerate duplicate rows in the pool
        c["seen"].add(word)
        c["total"] += 1
        if word in lexicon:
            c["known"] += 1
        else:
            c["candidates"].append({"word": word, "gloss": entry.get("gloss", "")})

    # Thinnest coverage first — that's where the floor is least served.
    ranked = sorted(
        (c for c in clusters.items() if c[1]["candidates"]),
        key=lambda kv: (kv[1]["known"] / kv[1]["total"] if kv[1]["total"] else 1.0, -kv[1]["total"]),
    )
    return ranked[:n_clusters], per_cluster


def load_recent_sidecars(limit: int | None = None) -> list[dict]:
    """All *.tags.json sidecars, newest mission first. Skips unreadable ones."""
    cars = []
    for p in SCRIPTS_DIR.glob("*.tags.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(d.get("mission"), int):
            # Only integer missions count: a reference tape carrying a string
            # mission belongs to the feed, never the scene rotation (and a
            # str/int sort crash took the whole ticket down in the reference impl).
            cars.append(d)
    cars.sort(key=lambda d: d.get("mission", 0), reverse=True)
    return cars[:limit] if limit else cars


def pick_divergent(palette, axis_key: str, sidecars: list[dict], rotate: int):
    """Choose a palette value that diverges from the last DIVERGENCE_WINDOW
    episodes on `axis_key`. Prefers values never used, then least-recently used.
    `rotate` (the episode count) spreads cold-start picks so we don't always
    land on the first palette entry before history accrues."""
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


def scene_spec(sidecars: list[dict]) -> dict:
    """The structural variety gate: register + form + dramatic ingredient,
    each forced to diverge from the last 3 episodes."""
    n = len(sidecars)
    ingredient = pick_divergent(list(INGREDIENTS), "dramatic_ingredient", sidecars, n)
    return {
        "register": pick_divergent(REGISTERS, "register", sidecars, n),
        "form": pick_divergent(FORMS, "episode_form", sidecars, n),
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
    args = parser.parse_args()

    lexicon = load_json(LEXICON_PATH)
    word_pool = load_json(WORD_POOL_PATH)
    learner = load_json(BASE / "progress" / "learner.json") or {}
    # An EMPTY lexicon ({}) is a valid day-zero state — the ticket still serves
    # the new-candidates section. Only a MISSING file is an error.
    if lexicon is None or not word_pool:
        print("Error: lexicon.json or word_pool.json not found. See SETUP.md.")
        return
    today = date.today()

    print("=" * 60)
    print("SESSION TICKET — Python computes the menu; the tutor picks the story.")
    print("=" * 60)

    # Next engine focus — the deliberate unlock priority (set via sync_state update
    # --next-engine). Surfaced first so the tutor never re-derives the order session by session.
    next_engine_key = learner.get("next_engine", "")
    if next_engine_key and lexicon:
        r = lexicon.get(next_engine_key, {})
        prod = r.get("production", "none")
        if prod != "cold":
            gloss = r.get("gloss", "")
            unseen_flag = " · ⚠ UNSEEN — teach first (show it), NEVER cold-quiz" if is_unseen(r) else ""
            print(f"\n🎯 NEXT ENGINE: {next_engine_key} — {gloss}  [production: {prod}{unseen_flag}]")
            print(f"   One cold novel instance of this pattern = engine online.")

    # The deck — the finite, deadline-driven sprint set. When it exists it is the
    # HEADLINE: force its not-yet-cold members first (the tutor narrates the countdown).
    # One knock-log read, one ask count, both selectors — they share the ordering
    # law, so they must share the term that implements it.
    asked = recent_ask_counts(load_json(KNOCK_LOG_PATH) or [], lexicon)
    reps = rep_counts(lexicon)
    deck = deck_status(lexicon, today=today, asked=asked, reps=reps)
    if deck:
        print(f"\n★ {DECK_LABEL.upper()}  (the sprint headline — force these before the general floor)")
        print("-" * 60)
        print(f"  {deck['cold']}/{deck['total']} deck phrases fire cold. "
              f"Not-yet-cold ({len(deck['pending'])}) — pick from these first:")
        for t in deck["pending"][:12]:
            tag = "hinted→cold" if t["production"] == "hinted" else f"{t['recognition']}, cold-pending"
            if t.get("unseen"):
                tag += " · ⚠ UNSEEN — teach first (show it, gloss it), NEVER cold-quiz"
            if t["staleness"] >= NEVER_SURFACED:
                tag += " · never worked"
            tier = f" · {t['tier']}" if t.get("tier") else ""
            print(f"  - [{t['kind']}{tier}] {t['word']} — {t['gloss'] or '[no gloss]'}  [{tag}]")
        hidden = len(deck["pending"]) - 12
        if hidden > 0:
            print(f"  … {hidden} more below the cut (least-recently-worked first — the tail rotates up)")
        if deck["catch_total"]:
            print(f"\n  EAR-ONLY ({deck['caught']}/{deck['catch_total']} solid) — eavesdrop/soak targets; "
                  f"win = recognition, never force these to fire:")
            for t in deck["catch_pending"][:8]:
                never = " · never worked" if t["staleness"] >= NEVER_SURFACED else ""
                print(f"  - [{t['kind']}] {t['word']} — {t['gloss'] or '[no gloss]'}  [{t['recognition']}{never}]")
                if t.get("pairs_with"):
                    print(f"      ↳ the answer: {t['pairs_with']} — {t['response_gloss'] or '[no gloss]'}"
                          f"  (drill the PAIR: hear it, answer it — recognition alone isn't the win here)")

    cov = deck_coverage(lexicon, today=today)
    if cov:
        print("\n★ DECK COVERAGE  (how many have been WORKED — the meter cold/total can't see)")
        print("  ENGINEERING NUMBERS — they steer selection; they are never narrated to the learner.")
        print("-" * 60)
        # Tier order is config order (deck.tiers); the unnamed bucket collects
        # registers no tier claims. No tiers configured ⇒ one flat bucket.
        for i in sorted(cov["tiers"], key=lambda t: next(
                (n for n, nm in TIER_NAMES.items() if nm == t), len(TIER_NAMES))):
            b = cov["tiers"][i]
            label = i or "untiered"
            regs_in = sorted((r, x) for r, x in cov["registers"].items()
                             if TIER_NAMES.get(DECK_TIERS.get(r, len(TIER_NAMES)), "") == i)
            detail = ", ".join(f"{r} {x['touched']}/{x['total']}" for r, x in regs_in)
            flag = "  ⚠" if b["untouched"] else ""
            print(f"  {label:9} worked {b['touched']:2}/{b['total']:2} · cold {b['cleared']:2}{flag}"
                  + (f"   ({detail})" if detail else ""))
        c = cov["catch"]
        if c["total"]:
            print(f"  {'ear-only':9} worked {c['touched']:2}/{c['total']:2} · solid {c['cleared']:2}"
                  + ("  ⚠" if c["untouched"] else ""))
        if cov["untouched"]:
            u_fire = [u for u in cov["untouched"] if u["direction"] == "fire"]
            u_catch = [u for u in cov["untouched"] if u["direction"] == "catch"]
            soaked = sum(1 for u in cov["untouched"] if u["soaked_only"])
            ear = f" + {len(u_catch)} ear-only" if u_catch else ""
            print(f"\n  ⚠ NEVER WORKED: {len(u_fire)} fire item(s){ear} "
                  f"({soaked} heard in an episode but never asked).")
            starving = [f"{r} ({x['untouched']})" for r, x in sorted(
                cov["registers"].items(), key=lambda kv: -kv[1]["untouched"])
                if x["untouched"]]
            if starving:
                print("     Starving registers: " + ", ".join(starving))
            print("     They now sort to the head of their tier — fire from the top and this drains.")

    # 0. Scene spec — structural variety gate (audio episodes especially)
    spec = scene_spec(load_recent_sidecars())
    print("\n0. SCENE SPEC  (force range; vary everything EXCEPT the vocabulary)")
    print("-" * 60)
    print(f"  Register:   {spec['register']}")
    print(f"  Form:       {spec['form']}")
    print(f"  Ingredient: {spec['ingredient']} — {spec['ingredient_desc']}")
    if spec["recent"]:
        recent_str = ", ".join(f"M{m} {reg}/{form}" for m, reg, form in spec["recent"])
        print(f"  (diverging from last {DIVERGENCE_WINDOW}: {recent_str})")

    # 1. Floor-gap — two budgets. FOCUS is drilled; BACKGROUND is only exposed.
    print(f"\n1. FOCUS SET  (≤{FOCUS_SIZE} in dense rotation — DRILL these until they fire cold)")
    print("-" * 60)
    gap, background = floor_gap_targets(lexicon, today, args.floor_max,
                                        asked=asked, reps=reps,
                                        cohort=learner.get("focus_cohort"))
    if not gap:
        print("  (floor is clear — nothing recognized is stuck below cold)")
    for t in gap:
        tag = "hinted→cold" if t["production"] == "hinted" else f"{t['recognition']}, cold-pending"
        rep = f"{t['reps']} rep{'s' if t['reps'] != 1 else ''}" if t["reps"] else "never drilled"
        cool = (f"  · asked in last {ASK_COOLDOWN_DAYS}d — vary the scene or take the next one"
                if t["asks"] else "")
        if t["reps"] >= STUCK_REPS:
            cool = (f"  · ⚠ STUCK — {t['reps']} reps and still not cold. "
                    f"Drilling it again won't work; change the angle.")
        print(f"  - {t['word']} — {t['gloss'] or '[no gloss]'}  [{tag} · {rep}]{cool}")
    print(f"  Graduation is production going COLD. After that a word is never "
          f"drilled again — it is just used.")

    if background:
        print(f"\n1a. BACKGROUND  ({len(background)} not yet started — EXPOSE, don't drill)")
        print("-" * 60)
        print("  Soak/episode candidates: work them into scenes so they stay warm and")
        print("  the tail can't rot. Never force these to fire — they are not the focus.")
        for t in background[:8]:
            print(f"  - {t['word']} — {t['gloss'] or '[no gloss]'}")
        if len(background) > 8:
            print(f"  … {len(background) - 8} more waiting behind them")

    # 1b. Engines — generative patterns to force a novel instance of
    engines = engines_to_fire(lexicon)
    if engines:
        print("\n1b. ENGINES TO FIRE  (patterns — force a NOVEL instance, not a memorized line)")
        print("-" * 60)
        for e in engines:
            tag = "hinted→cold" if e["production"] == "hinted" else "cold-pending"
            if e.get("unseen"):
                tag += " · ⚠ UNSEEN — teach first (show it), NEVER cold-quiz"
            print(f"  - {e['key']} — {e['gloss'] or '[no gloss]'}  [{tag}]")

    # 2. Callbacks — soft soak (reused logic)
    print("\n2. DUE CALLBACKS  (soft soak — weave in where they fit)")
    print("-" * 60)
    callbacks = due_callbacks(lexicon, today, args.callbacks_max)
    if not callbacks:
        print("  (nothing due — the recognized set is fresh)")
    for cb in callbacks:
        if cb.get("direction") == "catch":
            gap_tag = "ear"  # soak-by-design, not production debt
        else:
            gap_tag = "floor-gap" if cb["production"] != "cold" else "retention"
        print(f"  - {cb['word']} — {cb['gloss'] or '[no gloss]'}  [{gap_tag}]")

    # 3. New candidates by cluster — the tutor picks the cluster
    print("\n3. NEW CANDIDATES BY CLUSTER  (priority-1, not yet met — pick a thin cluster)")
    print("-" * 60)
    ranked, per_cluster = new_candidates_by_cluster(lexicon, word_pool, args.clusters, args.per_cluster)
    if not ranked:
        print("  (no priority-1 clusters with unmet words)")
    for name, c in ranked:
        print(f"  [{name}]  known {c['known']}/{c['total']}")
        for cand in c["candidates"][:per_cluster]:
            print(f"      - {cand['word']} — {cand['gloss']}")

    # 4. Vocabulary fence — the sea the Architect swims in
    print("\n4. VOCABULARY FENCE  (the sea — Architect builds from these; everything else is +1)")
    print("-" * 60)
    fence = vocabulary_fence(lexicon)
    if not fence:
        print(f"  (empty — no recognized words yet; Architect must scaffold heavily with the learner's native language)")
    else:
        print(f"  {len(fence)} known words. The Architect should build dialogue from this pool.")
        print(f"  Words outside this list must be answerable from context within seconds.")
        print()
        for entry in fence:
            phon = entry["phonetic"][0] if entry["phonetic"] else ""
            phon_str = f" ({phon})" if phon else ""
            print(f"  - {entry['word']}{phon_str} — {entry['gloss'] or '[no gloss]'}")

    floor_gap_total = sum(1 for r in lexicon.values()
                          if r.get("type") != "pattern" and r.get("direction") != "catch"
                          and r.get("recognition") in RECOGNIZED and r.get("production") != "cold")
    print(f"\nFloor gap: {floor_gap_total} recognized words not yet firing cold.")
    print(f"Vocabulary fence: {len(fence)} words (the sea).")


if __name__ == "__main__":
    main()
