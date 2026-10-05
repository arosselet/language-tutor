"""The smoke harness: checks, stubs and the sandbox paths. Runs inside a sandbox
(see smoke_test.py), so writing progress/ here never touches a real learner."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FAILS: list[str] = []
COUNT = [0]


def check(name: str, ok, detail: str = "") -> bool:
    COUNT[0] += 1
    if ok:
        print(f"  [ok] {name}")
    else:
        FAILS.append(name)
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def section(title: str):
    print(f"\n{title}")


class Recorder:
    """A stub that records its calls and returns a fixed value."""
    def __init__(self, ret=None):
        self.calls, self.ret = [], ret

    def __call__(self, *a, **kw):
        self.calls.append((a, kw))
        return self.ret(*a, **kw) if callable(self.ret) else self.ret


def write(rel: str, data):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2),
                 encoding="utf-8")


def read(rel: str):
    p = ROOT / rel
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else p.read_text(encoding="utf-8")


def target_sample() -> str | None:
    """One target-language word, taken from the pack itself (its examples and
    kinship nouns), so the cases run against any pack — never a hard-coded one."""
    import pack
    pool = [*pack.REFERENT_NOUNS, *pack.EXAMPLES.values()]
    if pack.DISTINCT_SCRIPT:
        for text in pool:
            runs = pack.target_runs(text)
            if runs:
                return max(runs, key=len)
        return None
    return next((n for n in pack.REFERENT_NOUNS if n.isalpha()), None) or "palabra"


def marked(word: str) -> str:
    """`word` as a generator would write it in a voice-form line for this pack."""
    import pack
    return word if pack.DISTINCT_SCRIPT else f"{pack.SPAN_OPEN}{word}{pack.SPAN_CLOSE}"
