#!/usr/bin/env python3
"""The smoke suite runner.

    python scripts/smoke_test.py            # both fixture packs + the blank clone
    python scripts/smoke_test.py --pack tamil

Each pack runs in its OWN sandbox and interpreter, because the pack is read at
import: the sandbox is a copy of this repo with `config/tutor.json` set to the
fixture and `progress/` initialized from the examples — the shape a real setup
produces. Every outward call (model, git, push, TTS) is stubbed inside the cases;
nothing here touches the network, the real `progress/`, or the remote.

A live repo (one with its own `config/tutor.json`) also runs the suite against
itself, so a learner's pack is held to the same laws as the fixtures.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PACKS = {"tamil": BASE / "config/examples/tamil.json",
         "spanish": BASE / "config/examples/spanish.json"}
COPY = ("scripts", "protocol", "content", "curriculum", "progress", "config", "docs",
        "AGENTS.md", "SETUP.md", "requirements.txt")


def sandbox(config: Path | None, live: bool = False) -> Path:
    """A throwaway copy of the repo; `config` None makes it a blank clone. A fixture
    pack gets the fixture world and the templates as its prose; the live pack keeps
    the learner's own, so the suite tests what setup actually wrote."""
    root = Path(tempfile.mkdtemp(prefix="sollu_smoke_"))
    for name in COPY:
        src = BASE / name
        if src.is_dir():
            shutil.copytree(src, root / name, ignore=shutil.ignore_patterns(
                "__pycache__", "*.mp3", "tutor.json"))
        elif src.exists():
            shutil.copy2(src, root / name)
    if config is not None:
        shutil.copy2(config, root / "config" / "tutor.json")
        for ex in (root / "progress").glob("*.json.example"):
            ex.with_suffix("").write_text(ex.read_text(encoding="utf-8"), encoding="utf-8")
        for name in ("knock_log", "push_queue", "feedback_log"):
            (root / "progress" / f"{name}.json").write_text("[]", encoding="utf-8")
        if not live:
            (root / "content" / "world.md").write_text(
                (BASE / "scripts/smoke/world_fixture.md").read_text(encoding="utf-8"), encoding="utf-8")
            (root / "curriculum" / "word_pool.json").write_text("[]", encoding="utf-8")
            for t in (root / "protocol").glob("*.md.template"):
                t.with_suffix("").write_text(t.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def run_pack(name: str, config: Path | None) -> bool:
    root = sandbox(config, live=name == "live")
    try:
        r = subprocess.run([sys.executable, str(root / "scripts" / "smoke" / "run.py"), name],
                           cwd=root, env={**__import__("os").environ, "PYTHONUTF8": "1",
                                          "PYTHONDONTWRITEBYTECODE": "1"})
        return r.returncode == 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", choices=[*PACKS, "blank", "live"])
    args = ap.parse_args()
    runs = {"blank": None, **PACKS}
    if (BASE / "config" / "tutor.json").exists():
        runs["live"] = BASE / "config" / "tutor.json"
    if args.pack:
        runs = {args.pack: runs[args.pack]}
    results = {name: run_pack(name, cfg) for name, cfg in runs.items()}
    print("\n" + " · ".join(f"{n}: {'GREEN' if ok else 'RED'}" for n, ok in results.items()))
    print("ALL GREEN" if all(results.values()) else "FAILURES")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
