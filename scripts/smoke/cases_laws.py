"""The template's structural laws: the port surface is the pack, the mechanism holds
no learner or language, the schemas name every key their mandates ask for, and the
budgets hold."""
import ast
import io
import json
import re
import subprocess
import sys
import tokenize

from harness import ROOT, check

SCRIPTS = ROOT / "scripts"
# Modules by D10 budget group (§5.2). A new file joins a group in the same diff.
MODULES = {
    "core": ("pack state_io observations lexicon_view dose_evidence slips month generate_callbacks "
             "world suggest_targets receptive_check session_brief show_status sync_state writer "
             "mandates publish render_chat").split(),
    "audio": ("render_audio memo lesson_audio render_soak render_drill render_rotation run_studio "
              "rebuild_rss audio_titles lanes commissions").split(),
    "phone": "morning_knock knock_reply reply_common knock_message push_queue rails render_payoff render_sort".split(),
    "timeline": ["timeline"],
}
BUDGETS = {"core": 8000, "audio": 4000, "phone": 4000, "timeline": 1000, "smoke": 5000}
# The import stack, bottom to top (docs/PROTOCOL_MAP.md → Python brain). Every
# import, lazy ones included, points to a strictly lower layer. A new file joins a
# layer in the same diff, the way it joins a budget group.
LAYERS = [
    "pack",
    "state_io",
    "observations audio_titles generate_callbacks month world timeline rails render_chat mandates",
    "lexicon_view dose_evidence writer rebuild_rss",
    "slips receptive_check publish",
    "suggest_targets render_audio commissions",
    "sync_state memo render_sort",
    "session_brief show_status lanes reply_common push_queue lesson_audio run_studio",
    "knock_message morning_knock render_soak render_drill render_rotation render_payoff",
    "knock_reply",
]
# Upward imports that are allowed, each with its reason. Keep this list short.
BACK_EDGES = {("sync_state", "session_brief"): "`status` prints the brief; imported inside main only"}
# Only pack.py may locate or load the config; everything else asks the pack.
CONFIG_READ_RE = re.compile(r"tutor\.json|SOLLU_CONFIG|\bCONFIG_PATH\b|\bpack\.CONFIG\b"
                            r"|import\b[^\n]*\bCONFIG\b|[\"']config[\"']")
FIXED_PROSE_BUDGET = 9000
# Prohibitions in the fixed law plus every mandate string. Census at birth: 159
# under a distinct-script pack (85 prose + 74 mandates), 160 under a shared-script
# one (the span rule's never). Only ever moves down, or up in a diff that names
# what it could not retire and why. Prose slots are the instance's, not counted.
PROHIBITION_RE = re.compile(r"(?i)\b(?:never|must not|do not|don['’]t)\b")
PROHIBITION_BUDGET = 160


def mechanism_lines(src: str) -> list[tuple[int, str]]:
    """Code lines with docstrings and comments removed — prose may quote anything."""
    docs = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant)
                    and isinstance(b[0].value.value, str)):
                docs |= set(range(b[0].lineno, b[0].end_lineno + 1))
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    code = {t.start[0] for t in toks if t.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                                                       tokenize.INDENT, tokenize.DEDENT)}
    cut = {t.start[0]: t.start[1] for t in toks if t.type == tokenize.COMMENT}
    return [(i, ln[:cut[i]] if i in cut else ln) for i, ln in enumerate(src.splitlines(), 1)
            if i in code and i not in docs]


def _needles() -> set[str]:
    out = set()
    for f in sorted((ROOT / "config" / "examples").glob("*.json")) + [ROOT / "config" / "tutor.json"]:
        c = json.loads(f.read_text(encoding="utf-8"))
        out |= {c["learner"]["name"], c["tutor"]["name"], c["language"]["name"], c["language"]["variety"],
                c.get("feed", {}).get("title", ""), c.get("feed", {}).get("repo", ""),
                c.get("tts", {}).get("tutor_voice", ""), c.get("tts", {}).get("eavesdrop_voice", ""),
                c["writer"]["model"]}
    return {n for n in out if n}


def _hits(src: str, needles: set[str], script: re.Pattern | None) -> list[str]:
    found = []
    for i, ln in mechanism_lines(src):
        hit = [n for n in needles if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", ln)]
        if script and script.search(ln):
            hit.append("<target script>")
        if hit:
            found.append(f"{i}: {hit}")
    return found


def case_no_mechanism_file_holds_a_learner_or_a_language():
    """Every fixture's names and config literals, and a distinct target script, stay out
    of mechanism lines (prose is free). The sweep proves it can see a planted copy."""
    import pack
    needles = _needles()
    script = re.compile(pack.CONFIG["language"]["script_regex"]) if pack.DISTINCT_SCRIPT else None
    files = [p for p in SCRIPTS.glob("*.py") if p.name != "pack.py"]
    check(f"the sweep reads the mechanism ({len(files)} files)", len(files) >= 30)
    bad = {p.name: h for p in files if (h := _hits(p.read_text(encoding="utf-8"), needles, script))}
    check("no mechanism line holds a learner name, config literal or target script", not bad, f"{bad}")
    name = sorted(needles)[0]
    planted = f'"""{name} in a docstring is free."""\nX = "{name}"  # trailing\n'
    check("a planted copy is caught, and the docstring is free",
          [h.split(":")[0] for h in _hits(planted, {name}, None)] == ["2"])


def _config_reads(src: str) -> list[int]:
    return [i for i, ln in mechanism_lines(src) if CONFIG_READ_RE.search(ln)]


def case_only_the_pack_reads_the_config():
    """pack.py is the one reader of config/tutor.json; every other file asks it."""
    files = [p for p in SCRIPTS.glob("*.py") if p.name not in ("pack.py", "smoke_test.py")]
    bad = {p.name: r for p in files if (r := _config_reads(p.read_text(encoding="utf-8")))}
    check("no mechanism line locates or loads the config", not bad, f"{bad}")
    planted = '"""reads config/tutor.json in prose — free."""\nC = json.load(open("config/tutor.json"))\n'
    check("a planted direct read is caught, and the docstring is free", _config_reads(planted) == [2])


def case_the_fixed_prose_names_no_learner_or_language():
    """The fixed protocol is learner- and language-neutral and inside its word budget."""
    import pack
    fixed = sorted((ROOT / "protocol").glob("*.md")) + sorted((ROOT / "protocol" / "studio").glob("*.md"))
    slots = {s for s in pack.PROSE_SLOTS}
    fixed = [p for p in fixed if p.relative_to(ROOT).as_posix() not in slots]
    words = sum(len(p.read_text(encoding="utf-8").split()) for p in fixed)
    check(f"fixed prose within budget ({words}/{FIXED_PROSE_BUDGET} words)", words <= FIXED_PROSE_BUDGET)
    names = [pack.LEARNER, pack.TUTOR, pack.LANGUAGE, pack.VARIETY]
    bad = [f"{p.name}: {n}" for p in fixed for n in names
           if re.search(rf"\b{re.escape(n)}\b", p.read_text(encoding="utf-8"))]
    check("no fixed protocol file names this learner, tutor or language", not bad, f"{bad}")


def case_the_prohibitions_do_not_grow():
    """A new never retires an old one in the same diff."""
    import mandates
    import pack
    fixed = [p for p in sorted((ROOT / "protocol").rglob("*.md"))
             if p.relative_to(ROOT).as_posix() not in set(pack.PROSE_SLOTS)]
    texts = [p.read_text(encoding="utf-8") for p in fixed]
    # The pack's fragments are spliced into many mandates; each counts ONCE, so the
    # census is the same law under every pack (the span rule adds its one never).
    fragments = [f for f in (pack.AUDIO_FORM, pack.CHAT_FORM, pack.WEAVE_RULE) if f]
    for k, v in vars(mandates).items():
        if k.isupper() and isinstance(v, str):
            for f in fragments:
                v = v.replace(f, "")
            texts.append(v)
    texts += fragments
    nevers = sum(len(PROHIBITION_RE.findall(t)) for t in texts)
    check("the prohibition scan still sees the law it counts", len(fixed) > 8 and nevers > 50,
          f"{len(fixed)} files, {nevers} prohibitions — an empty scan would pass any budget")
    check(f"prohibitions in the law: {nevers}/{PROHIBITION_BUDGET}", nevers <= PROHIBITION_BUDGET,
          f"over by {nevers - PROHIBITION_BUDGET}")


def case_every_prose_slot_has_a_template():
    """The port surface is config/tutor.json + PROSE_SLOTS, each with a template."""
    import pack
    missing = [s for s in pack.PROSE_SLOTS
               if not ((ROOT / f"{s}.template").exists() or (ROOT / f"{s}.example").exists())]
    check("every prose slot ships a .template or .example", not missing, f"{missing}")


def case_schemas_name_every_key_their_mandates_ask_for():
    """A key a mandate names but the schema omits is DROPPED on the agent path."""
    import mandates
    import render_drill
    import render_soak
    import knock_reply
    import morning_knock

    def keys(schema):
        out = set()
        def walk(s):
            if isinstance(s, dict):
                out.update(s.get("properties", {}))
                for v in s.get("properties", {}).values():
                    walk(v)
                walk(s.get("items"))
        walk(schema)
        return out

    def asked(mandate):
        tail = mandate[mandate.rfind("Return ONLY"):] if "Return ONLY" in mandate else mandate
        return set(re.findall(r'"([a-z_]+)":', tail))

    pairs = {"SOAK": (mandates.SOAK_MANDATE, render_soak.SOAK_SCHEMA),
             "DRILL": (mandates.DRILL_MANDATE, render_drill.DRILL_SCHEMA),
             "JUDGE": (mandates.JUDGE_MANDATE + mandates.VOICE_MANDATE, knock_reply.JUDGE_SCHEMA),
             "CATCH": (mandates.CATCH_JUDGE_MANDATE + mandates.VOICE_MANDATE, knock_reply.CATCH_SCHEMA),
             "OUTREACH": (mandates.OUTREACH_MANDATE, morning_knock.DECIDE_SCHEMA)}
    for name, (mandate, schema) in pairs.items():
        missing = asked(mandate) - keys(schema)
        check(f"{name}: the schema names every key the mandate asks for", not missing, f"{sorted(missing)}")


def case_the_budgets_hold():
    """D10: core ≤ 8k, audio ≤ 4k, phone ≤ 4k, smoke ≤ 5k lines; every file is in a group."""
    on_disk = {p.stem for p in SCRIPTS.glob("*.py")} - {"smoke_test"}
    grouped = {m for ms in MODULES.values() for m in ms}
    check("every script belongs to a module group", on_disk == grouped,
          f"ungrouped {sorted(on_disk - grouped)}, missing {sorted(grouped - on_disk)}")
    for group, mods in MODULES.items():
        n = sum(len((SCRIPTS / f"{m}.py").read_text(encoding="utf-8").splitlines())
                for m in mods if (SCRIPTS / f"{m}.py").exists())
        check(f"{group}: {n}/{BUDGETS[group]} lines", n <= BUDGETS[group])
    smoke = [SCRIPTS / "smoke_test.py", *sorted((SCRIPTS / "smoke").glob("*.py"))]
    n = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in smoke)
    check(f"smoke: {n}/{BUDGETS['smoke']} lines", n <= BUDGETS["smoke"])


def case_imports_point_down_the_stack():
    """Every import, lazy ones included, points to a strictly lower layer (LAYERS)."""
    local = {p.stem for p in SCRIPTS.glob("*.py")} - {"smoke_test"}
    rank = {m: i for i, layer in enumerate(LAYERS) for m in layer.split()}
    check("every script sits in a layer", set(rank) == local,
          f"unlayered {sorted(local - set(rank))}, missing {sorted(set(rank) - local)}")

    def deps(name):
        tree = ast.parse((SCRIPTS / f"{name}.py").read_text(encoding="utf-8"))
        out = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                out |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                out.add(n.module)
        return out & local - {name}
    up = [f"{m} -> {d}" for m in sorted(local & set(rank)) for d in sorted(deps(m))
          if d in rank and rank[d] >= rank[m] and (m, d) not in BACK_EDGES]
    check("no import points up or sideways", not up, f"{up}")
    check("pack imports nothing local", not deps("pack"), f"{deps('pack')}")


def case_the_static_gate_is_clean():
    """pyflakes over scripts/ — the suite only proves what it executes."""
    r = subprocess.run([sys.executable, "-m", "pyflakes", *map(str, sorted(SCRIPTS.glob("*.py")))],
                       capture_output=True, text=True, encoding="utf-8")
    if "No module named pyflakes" in r.stderr:
        check("pyflakes is installed (requirements.txt)", False, "pip install -r requirements.txt")
        return
    check("zero pyflakes findings", r.returncode == 0, r.stdout[-400:])
