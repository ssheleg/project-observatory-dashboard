"""PB-038: an action whose outcome is unknown says so, instead of "failed".

Runs tests/action_outcome_check.mjs against the page the real dashboard builds.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import dashboard_fixture  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" — {detail}"))
    if not ok:
        FAILS.append(name)


def main() -> int:
    node = shutil.which("node")
    if node is None:
        print("  SKIP  node is not installed here, so the page cannot be executed")
        return 0
    page = dashboard_fixture.build(Path(tempfile.mkdtemp(prefix="observatory-actions-")).resolve())
    p = subprocess.run([node, str(ROOT / "tests/action_outcome_check.mjs"), str(page)],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    r = json.loads(p.stdout or "{}")
    check("the page carries call()", "error" not in r, p.stdout + p.stderr)
    expect = {"refused": "refused:", "provider refused": "refused:", "server fault": "uncertain:",
              "unreadable success": "uncertain:", "dropped": "uncertain:", "timeout": "uncertain:",
              "success": "ok"}
    for case, prefix in expect.items():
        check(f"{case} reads as {prefix.rstrip(':')}", str(r.get(case, "")).startswith(prefix), str(r.get(case)))
    check("a timeout names its wait", "no answer within" in str(r.get("timeout")), str(r.get("timeout")))
    # The same outcomes in Russian: the message is the catalog's, not a literal.
    p = subprocess.run([node, str(ROOT / "tests/action_outcome_check.mjs"), str(page), "ru"],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    ru = json.loads(p.stdout or "{}")
    check("in Russian the timeout still reads as uncertain and names its wait",
          str(ru.get("timeout", "")).startswith("uncertain:") and "нет ответа за" in str(ru.get("timeout")),
          p.stdout + p.stderr)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
