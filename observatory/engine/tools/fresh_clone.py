#!/usr/bin/env python3
"""Run every test step as a FRESH CLONE would see it, and name what breaks.

`store/observatory.db` and `store/raw/` are gitignored, and so is the built page:
a clone has the registry and none of them. A test step that asserts on live rows
without asking whether the estate could produce them reads that state as a broken
build — it reads an ABSENCE as a FAILURE, which is the inversion this repository
refuses everywhere else.

    tools/fresh_clone.py            # every test step, pass/fail
    tools/fresh_clone.py test-hook  # one step, with its output

**Not a gate step, deliberately.** It runs one subprocess per test step and takes
minutes; adding that to every `check` would buy an invariant that moves only when
somebody writes a new suite. Run it when you add one, or when a contributor says
the suite is red on a clean checkout.

**What it does NOT simulate.** The registry is the real one — a clone has that,
because `registry/*.json` is committed — and the projects root is the real one,
because no redirect can invent the projects on disk. So a suite that reads the
operator's checkouts still reads them; what changes is everything the store and
the collectors' receipts hold.
"""
from __future__ import annotations
import importlib.util
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
# THROUGH `tests/tmp`, which registers the removal. A bare `tempfile.mkdtemp`
# leaves its directory behind, and `tools/check_paths.py` refuses one for that
# reason — on a volume with 4.4 GiB free the rule earns its keep twice.
sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir                                                              


def steps() -> list[str]:
    spec = importlib.util.spec_from_file_location("obs", ROOT / "observatory.py")
    obs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obs)
    return [s for s in obs.GROUPS["check"] if s.startswith("test-")]


def env_for(tmp: pathlib.Path) -> dict:
    """A store that is not there, a scratch with no receipts, no built page.

    The page is redirected too, and that is not a detail: without it a suite
    that rebuilds the dashboard writes the OPERATOR'S page from an empty store,
    and the work tiles vanish from the surface a person opens.
    """
    (tmp / "raw").mkdir(parents=True, exist_ok=True)
    (tmp / "docs").mkdir(parents=True, exist_ok=True)
    return {**os.environ,
            "OBSERVATORY_DB": str(tmp / "absent.db"),
            "OBSERVATORY_SCRATCH": str(tmp / "raw"),
            "OBSERVATORY_DASHBOARD": str(tmp / "docs" / "page.html")}


def main(argv: list[str]) -> int:
    want = argv[1:] or steps()
    tmp = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-fresh-"))
    env = env_for(tmp)
    red: list[str] = []
    for step in want:
        p = subprocess.run([PY, str(ROOT / "observatory.py"), step], cwd=ROOT,
                           env=env, capture_output=len(want) > 1, text=True,
                           timeout=1800)
        ok = p.returncode == 0
        print(f"{'ok  ' if ok else 'RED '} {step}")
        if not ok:
            red.append(step)
            if len(want) > 1:
                for line in (p.stdout + p.stderr).splitlines():
                    if line.strip().startswith("FAIL") or "Error" in line:
                        print(f"        {line.strip()[:150]}")
                        break
    print(f"\n{len(want) - len(red)} of {len(want)} step(s) pass as a fresh clone "
          f"sees them")
    if red:
        print("A step that goes red here reads an ABSENCE as a FAILURE. Guard it "
              "with tests/live_estate.needs(), naming where the property IS "
              "asserted, or drive it against a store the test builds itself.")
    return 1 if red else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
