"""The pack contract: the questions answer for THIS pack's script model, and the
validator has teeth. Cases branch on the pack's declared shape, never its name."""
import copy
import json

from harness import ROOT, check, marked, target_sample


def case_the_questions_answer_for_this_script_model():
    """Detect for a distinct script, declare for a shared one (D5)."""
    import pack
    word = target_sample()
    check("the pack yields a target sample to test with", word, "no examples or referent nouns")
    if not word:
        return
    line = f"we went {marked(word)} today"
    check("has_target sees a target word in a mixed line", pack.has_target(line))
    check("has_target sees none in a plain native-language line",
          not pack.has_target("we went to the market today"))
    check("target_runs returns the target unit(s), in order",
          pack.target_runs(line) and pack.target_runs(line)[0] in word, f"{pack.target_runs(line)}")
    check("l1_runs keeps the native-language words and drops the target",
          "went" in pack.l1_runs(line) and word not in " ".join(pack.l1_runs(line)))
    check("unmark leaves what is spoken", pack.SPAN_OPEN not in pack.unmark(line))
    check("is_canonical accepts the canonical form", pack.is_canonical(word))
    if pack.DISTINCT_SCRIPT:
        check("a romanized token never mints a key", not pack.is_canonical("romanized"))
        check("the audio form carries no span rule", pack.SPAN_OPEN not in pack.AUDIO_FORM)
    else:
        check("undeclared target text is never detected (declare, don't detect)",
              not pack.has_target(f"we went {word} today"))
        check("the audio form tells writers to declare spans", pack.SPAN_OPEN in pack.AUDIO_FORM)


def case_read_form_rewrite_is_the_identity_unless_declared():
    """`needs_read_form` fires only for a pack that declares read_rewrite."""
    import pack
    word = target_sample() or "x"
    if pack.READ_REWRITE:
        check("a voice-form line needs the read form", pack.needs_read_form(f"say {word}"))
    else:
        check("no line ever needs the rewrite", not pack.needs_read_form(f"say {marked(word)}"))


def case_stems_follow_the_declared_rule():
    """A stem rule trims; no rule is verbatim; host_stem is never wider than stem."""
    import pack
    cfg = pack.CONFIG["language"]
    word = target_sample() or "palabra"
    if not cfg.get("stem_tail"):
        check("no stem rule → verbatim", pack.stem(word) == word)
    check("host_stem keeps at least what stem keeps", len(pack.host_stem(word)) >= len(pack.stem(word)))


def case_spellings_fold_per_script_model():
    """`fold` drops case (and accents in a shared script); `heads` matches whole words
    in a shared script and a prefix in a distinct one."""
    import pack
    word = target_sample() or "palabra"
    if pack.DISTINCT_SCRIPT:
        check("a distinct script keeps its marks (vowel signs are letters)", pack.fold(word) == word)
        check("a prefix heads a longer key", pack.heads(word[:-1], word))
    else:
        check("case and accents fold away", pack.fold("Cómo  ESTÁS") == pack.fold("como estas"))
        check("a whole leading word heads a phrase", pack.heads(word, f"{word} extra"))
        check("a fragment never heads a phrase", not pack.heads(word[:2], f"{word} extra"))


def case_the_validator_has_teeth():
    """Planted bad configs are refused, each with a sentence."""
    import pack
    base = json.loads((ROOT / "config" / "tutor.json").read_text(encoding="utf-8"))
    check("the live config validates", pack.check(base) == [], f"{pack.check(base)}")

    def broken(mutate):
        c = copy.deepcopy(base)
        mutate(c)
        return pack.check(c)

    def two_events(c):
        c.setdefault("modules", {})["timeline"] = True
        c["timeline"] = {"directions": {"x": {}}, "phases": [
            {"name": "a", "days": None, "direction": "x", "marker": "m"},
            {"name": "b", "event": True, "days": None, "direction": "x", "marker": "m"},
            {"name": "c", "event": True, "days": None, "direction": "x", "marker": "m"}]}
    plants = {
        "a typo'd key": lambda c: c["language"].__setitem__("scrpt_regex", None),
        "a regex that does not compile": lambda c: c["language"].__setitem__("script_regex", "[a-"),
        "a rewrite with nothing to detect": lambda c: c["language"].update(script_regex=None, read_rewrite=True),
        "a ninth example slot": lambda c: c.setdefault("examples", {}).__setitem__("ninth", "x"),
        "audio on with no pinned voice": lambda c: (c.setdefault("tts", {}).__setitem__("tutor_voice", ""),
                                                     c.setdefault("modules", {}).__setitem__("audio", True)),
        "an inverted waking window": lambda c: c.setdefault("rails", {}).__setitem__("waking_start_hour", 23),
        "a missing required section": lambda c: c.pop("writer"),
        "a bool where an int belongs": lambda c: c.setdefault("rails", {}).__setitem__("min_gap_hours", True),
        "two event phases": two_events,
    }
    for name, mutate in plants.items():
        check(f"refused: {name}", broken(mutate))


def case_modules_follow_the_config():
    """Core always on; the others are the config's flags (§5.2)."""
    import pack
    import timeline
    check("core is always on", pack.module_on("core"))
    import subprocess
    import sys
    for m in ("core", "audio", "phone", "timeline"):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pack.py"), "module", m],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        check(f"the workflow gate agrees on {m}", (r.returncode == 0) == pack.module_on(m), r.stdout)
    check("timeline phases exist only when the module is on",
          bool(timeline.PHASES) == pack.module_on("timeline"))
    if not pack.module_on("timeline"):
        check("with no timeline, problem() says so instead of scheduling nothing silently",
              "no timeline module" in timeline.problem({}))
        check("with no timeline every row sorts mid", timeline.register_rank({"register": "x"}, "") == 1)
