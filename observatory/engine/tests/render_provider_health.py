#!/usr/bin/env python3
"""Drive the page's health panel with a quarantine list that is not empty.

`health.provider` has only ever been `{}` on this machine, because the boundary
clears a model's mark on its next success. So a renderer for it ships untested by
construction — trap T18, a degradation nobody has watched work — unless something
plants the state the estate has not been in.

This builds the real page, patches the payload's `"provider": {}` to hold two
quarantined models, runs the page's own script through `render_dashboard.mjs`, and
asserts the health container names them. Exit 0 means the row rendered.

Kept as its own file rather than folded into the suite: it needs `node`, and a
suite that silently skips its only end-to-end assertion when node is missing
reads as green for the wrong reason.
"""
from __future__ import annotations
import json, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir                                                  # noqa: E402

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
PLANTED = {
    "vendor/first-choice": {"since": "2026-09-07T19:00:00Z", "reason": "503 from the edge"},
    "vendor/second": {"since": "2026-09-07T19:30:00Z", "reason": "no choices in the response"},
}


def main() -> int:
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-provider-"))
    page = d / "page.html"
    p = subprocess.run([PY, "dashboard/build_dashboard.py"], cwd=ROOT,
                       env=dict(os.environ, OBSERVATORY_DASHBOARD=str(page)),
                       capture_output=True, text=True, timeout=900)
    if not page.is_file():
        print(f"the page did not build: {(p.stdout + p.stderr)[-400:]}", file=sys.stderr)
        return 1

    html = page.read_text(encoding="utf-8")
    m = re.search(r'const D = (\{.*?\});\n', html, re.S)
    if not m:
        print("no payload in the page", file=sys.stderr)
        return 1
    payload = json.loads(m.group(1))
    if payload.get("health", {}).get("provider"):
        print("the LIVE quarantine list is non-empty — this fixture would not be "
              "planting anything; report the live state instead", file=sys.stderr)
        return 1
    payload["health"]["provider"] = PLANTED
    patched = html[:m.start(1)] + json.dumps(payload, ensure_ascii=False) + html[m.end(1):]
    page.write_text(patched, encoding="utf-8")

    r = subprocess.run(["node", str(ROOT / "tests/render_dashboard.mjs"), str(page)],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    try:
        got = json.loads(r.stdout)
    except ValueError:
        print(f"the harness returned no JSON: {(r.stdout + r.stderr)[-400:]}", file=sys.stderr)
        return 1
    if got.get("threw"):
        print(f"the page's script threw: {got['threw']}", file=sys.stderr)
        return 1
    health = got.get("health") or ""
    bad = []
    if "карантин" not in health:
        bad.append("the health panel has no quarantine row")
    if "vendor/first-choice" not in health:
        bad.append("the row does not name the quarantined model")
    if "2" not in health:
        bad.append("the row does not say how many models are quarantined")
    if bad:
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        print(f"health panel was: {health[:400]}", file=sys.stderr)
        return 1
    print("the health panel names both quarantined models")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
