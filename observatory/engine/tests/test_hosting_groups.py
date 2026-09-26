"""PB-130: a project's deployments are grouped by environment (docs/design/DEPLOYMENTS.md, PB-004d).

Built from synthetic data by the real emitter and dashboard, then executed by
tests/render_dashboard.mjs: a project with a production app, a staging app and
one app nothing placed shows three groups, and the unplaced one is visible as
"not specified" rather than hidden or guessed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests")); sys.path.insert(0, str(ROOT / "collectors"))
import dashboard_fixture  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" — {detail}"))
    if not ok:
        FAILS.append(name)


def seed_hosting(root: Path) -> None:
    import heroku_registry
    reg = root / "registry"
    heroku_registry.load_verified = lambda: {}
    scan = {"apps": [{"name": n, "team": "fixture-team", "monthly_cost": 7} for n in ("fx-web", "fx-staging", "fx-worker")],
            "scanned_at": "2026-09-24T00:00:00Z"}
    records, _ = heroku_registry.records(scan, [], [], [])
    for rec in records:
        rec.update(project="project:fixture-a", link_rule="verified")
    doc = heroku_registry.document(scan, records, "2026-09-24")
    (reg / "heroku-apps.json").write_text(json.dumps(doc))
    envs = [{"id": "environment:project:fixture-a/production", "project": "project:fixture-a", "name": "production",
             "evidence": ["override"], "deployments": ["heroku:fx-web"]},
            {"id": "environment:project:fixture-a/staging", "project": "project:fixture-a", "name": "staging",
             "evidence": ["override"], "deployments": ["heroku:fx-staging"]}]
    (reg / "environments.json").write_text(json.dumps({"schema_version": 1, "environments": envs, "unassigned": []}))
    (reg / "accounts.json").write_text(json.dumps({"schema_version": 1, "accounts": [
        {"id": "account:heroku/t1", "provider": "heroku", "label": "fixture-team", "resources": 3}]}))
    rel = json.loads((reg / "relations.json").read_text())
    rel["relations"] += [
        {"id": "r1", "type": "serves", "from": "heroku:fx-web", "to": envs[0]["id"], "rule": "override", "source_refs": []},
        {"id": "r2", "type": "serves", "from": "heroku:fx-staging", "to": envs[1]["id"], "rule": "override", "source_refs": []},
        {"id": "r3", "type": "in_account", "from": "heroku:fx-web", "to": "account:heroku/t1", "rule": "heroku-team", "source_refs": []}]
    (reg / "relations.json").write_text(json.dumps(rel))


def main() -> int:
    node = shutil.which("node")
    root = Path(tempfile.mkdtemp(prefix="observatory-hosting-")).resolve()
    env = dashboard_fixture.seed(root)
    seed_hosting(root)
    p = subprocess.run([dashboard_fixture.PYTHON, str(ROOT / "dashboard/build_dashboard.py")], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    check("the dashboard builds with environments and accounts in the registry", p.returncode == 0, p.stderr[-400:])
    if p.returncode:
        return 1
    sys.path.insert(0, str(ROOT / "dashboard"))
    os.environ.update(env)
    page = Path(env["OBSERVATORY_DASHBOARD"])
    html = page.read_text(encoding="utf-8")
    check("the account label travels to the page", '"account": "fixture-team"' in html or '"account":"fixture-team"' in html)
    if node is None:
        print("  SKIP  node is not installed here, so the page cannot be executed")
        return 1 if FAILS else 0
    out = subprocess.run([node, str(ROOT / "tests/render_dashboard.mjs"), str(page), "--count", 'data-env="'],
                         cwd=ROOT, capture_output=True, text=True, timeout=300)
    r = json.loads(out.stdout)
    check("the page runs without throwing", r.get("threw") is None, str(r.get("threw")))
    groups = sum(r.get("counts", {}).values())
    check("one project, three groups: production, staging and not specified", groups == 3, str(r.get("counts")))
    out2 = subprocess.run([node, str(ROOT / "tests/render_dashboard.mjs"), str(page), "--count", "environment not stated"],
                          cwd=ROOT, capture_output=True, text=True, timeout=300)
    check("the unplaced app is visible as not specified", sum(json.loads(out2.stdout).get("counts", {}).values()) == 1,
          out2.stdout[-300:])
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
