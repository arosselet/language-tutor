"""The blank clone: no config, so no lane may run — every one points at setup."""
import subprocess
import sys

from harness import ROOT, check


def case_every_lane_points_at_setup():
    """A clone with no config/tutor.json stops every entry point with the setup pointer."""
    check("the sandbox really is blank", not (ROOT / "config" / "tutor.json").exists())
    for script in ("sync_state.py", "suggest_targets.py", "morning_knock.py", "render_soak.py",
                   "run_studio.py", "show_status.py"):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--help"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        check(f"{script} refuses and names SETUP.md",
              r.returncode != 0 and "SETUP.md" in (r.stdout + r.stderr),
              f"exit {r.returncode}: {(r.stdout + r.stderr)[-160:]}")


def case_the_fixture_packs_validate_without_a_config():
    """`pack.py check` works on a blank clone and passes both worked examples."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pack.py"), "check",
                        *map(str, sorted((ROOT / "config" / "examples").glob("*.json")))],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    check("both example packs validate", r.returncode == 0, r.stdout[-300:])


def case_setup_has_what_it_needs():
    """SETUP.md, the router and every prose slot's template ship in a blank clone."""
    for rel in ("SETUP.md", "AGENTS.md", "docs/CUSTOMIZATION.md", "requirements.txt",
                "progress/profile.md.template"):
        check(f"{rel} present", (ROOT / rel).exists())


def case_the_workflow_gate_sees_every_module_off():
    """`pack.py module <name>` is what the workflows ask; a blank clone answers off."""
    for m in ("core", "audio", "phone", "timeline"):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pack.py"), "module", m],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        check(f"blank: {m} is off", r.returncode == 1, r.stdout + r.stderr)
