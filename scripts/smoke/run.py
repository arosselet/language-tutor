"""Inner runner: one pack, one interpreter. `python scripts/smoke/run.py <name>`."""
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import COUNT, FAILS, section  # noqa: E402

MODULES = ("cases_pack", "cases_ledger", "cases_lanes", "cases_flows", "cases_laws")


def main(name: str) -> int:
    print(f"\n=========== smoke: {name} ===========")
    if name == "blank":
        mods = ["cases_blank"]
    else:
        # The live checks read what setup wrote, so they run before any case writes.
        mods = (["cases_live"] if name == "live" else []) + list(MODULES)
    for m in mods:
        mod = importlib.import_module(m)
        for fn in [getattr(mod, f) for f in dir(mod) if f.startswith("case_")]:
            section(f"{m}.{fn.__name__}: {(fn.__doc__ or '').strip().splitlines()[0]}")
            try:
                fn()
            except Exception:
                FAILS.append(f"{m}.{fn.__name__} raised")
                traceback.print_exc()
    print(f"\n{name}: {COUNT[0]} checks, {len(FAILS)} failed"
          + ("".join(f"\n  - {f}" for f in FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
