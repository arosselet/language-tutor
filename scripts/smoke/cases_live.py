"""The live pack only: what setup wrote is complete and the engine can read it. The
fixture packs run on templates and a fixture world, so only here does the suite
see the learner's own prose."""
import json

from harness import ROOT, check


def case_every_prose_slot_is_written():
    """Each slot exists and keeps no template guidance or unfilled placeholder."""
    import pack
    for slot in pack.PROSE_SLOTS:
        p = ROOT / slot
        if not check(f"{slot} exists", p.exists(), "setup Phase 3 writes it"):
            continue
        text = p.read_text(encoding="utf-8")
        left = [m for m in ("this is a synthesis template", "[Write ", "[Name]", "[voice-id]") if m in text]
        check(f"{slot} is filled in", not left, f"still holds {left}")


def case_the_world_canon_parses():
    """world.py reads the cast; the eavesdrop voice belongs to a cast member."""
    import pack
    import world
    check("the canon is usable", not world.problem(), world.problem())
    cast = world.cast()
    check(f"the cast has 5–7 people ({len(cast)})", 5 <= len(cast) <= 7, f"{sorted(cast)}")
    if pack.EAVESDROP_VOICE:
        check("the eavesdrop voice is pinned to a cast member", pack.EAVESDROP_VOICE in cast.values(),
              f"{pack.EAVESDROP_VOICE} not in {sorted(set(cast.values()))}")


def case_the_word_pool_is_canonical():
    """The pool parses, and every key is in the form the ledger keys on."""
    import pack
    path = ROOT / "curriculum" / "word_pool.json"
    if not path.exists():
        return   # reported by the slot case
    pool = json.loads(path.read_text(encoding="utf-8"))
    check(f"the pool holds entries ({len(pool)})", isinstance(pool, list) and len(pool) >= 50)
    bad = [e for e in pool if not (isinstance(e, dict) and e.get("word") and e.get("gloss")
                                   and pack.is_canonical(e["word"]))]
    check("every entry has a canonical word and a gloss", not bad, f"{bad[:3]}")
