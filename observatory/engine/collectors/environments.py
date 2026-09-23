"""Environments, scoped by project, and the `serves` edges from deployments to them.

Contract: docs/design/DEPLOYMENTS.md, rules 1, 2 and 4, slice PB-004b (PB-128).

An environment is explicit or unknown, never guessed. Evidence, in order:

1. `override`: `config/environments.json` names the environment a deployment serves;
2. `heroku-pipeline-stage`: Heroku's own pipeline stage for the app;
3. `vault-slot`: a project's credential slots are filed under an environment;
4. `env-file`: a project's checkout holds `.env.<environment>`.

Only 1 and 2 bind a deployment to an environment (a `serves` edge). 3 and 4
show that the environment exists for the project; they say nothing about which
app serves it. An app name containing `prod` is a name, not evidence, and is
never read. A deployment without evidence 1 or 2 is listed as `unassigned` with
the reason.

An environment id is `environment:<project id>/<name>`, so two projects'
production environments are two ids. Names are normalised to one spelling
(`prod` -> `production`); a name outside the known set is not an environment.
"""
from __future__ import annotations

import json
from pathlib import Path

HEROKU_SRC = ["SRC-0013"]
VAULT_SRC = ["SRC-0014"]
ENV_SRC = ["SRC-0015"]

CANON = {
    "production": "production", "prod": "production", "live": "production",
    "staging": "staging", "stage": "staging",
    "development": "development", "dev": "development",
    "review": "review", "preview": "review",
    "test": "test", "testing": "test", "ci": "test",
    "local": "local",
}
ORDER = ("production", "staging", "review", "development", "test", "local")


def normalise(name: str | None) -> str | None:
    """The one spelling of an environment name, or None when it is not one."""
    return CANON.get((name or "").strip().lower())


def file_environment(filename: str) -> str | None:
    """`.env.production` -> production; `.env`, `.env.example`, `.env.agent-sync` -> None."""
    if not filename.startswith(".env."):
        return None
    return normalise(filename[len(".env."):].split(".", 1)[0])


def load_overrides(path: Path) -> tuple[dict[str, str], list[dict]]:
    """{deployment id: environment} from config/environments.json, and problems."""
    if not path.is_file():
        return {}, []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [{"source": "environments.json", "reason": f"unreadable: {type(exc).__name__}"}]
    out, problems = {}, []
    for dep, entry in ((doc or {}).get("deployments") or {}).items():
        name = normalise((entry or {}).get("environment") if isinstance(entry, dict) else entry)
        if name:
            out[dep] = name
        else:
            problems.append({"source": "environments.json",
                             "reason": f"{dep}: not a known environment name; expected one of {', '.join(ORDER)}"})
    return out, problems


def build(heroku_records: list[dict], heroku_scan_apps: list[dict], credentials: list[dict],
          env_files: list[dict], projects: list[dict], overrides: dict[str, str],
          override_problems: list[dict], obs_date: str) -> tuple[dict, list[dict]]:
    """(environments.json document, serves edges)."""
    envs: dict[str, dict] = {}
    edges: list[dict] = []
    unassigned: list[dict] = []
    degraded: list[dict] = list(override_problems)

    def env(project: str, name: str, kind: str) -> dict:
        eid = f"environment:{project}/{name}"
        e = envs.setdefault(eid, {"id": eid, "project": project, "name": name, "evidence": [], "deployments": []})
        if kind not in e["evidence"]:
            e["evidence"].append(kind)
        return e

    # Evidence 3 and 4: the environment exists for the project.
    for c in credentials:
        name = normalise(c.get("env"))
        if name and c.get("source") == "vault":
            for project in c.get("used_by") or []:
                env(project, name, "vault-slot")
    by_folder: dict[str, list[str]] = {}
    for p in projects:
        for folder in p.get("local_folders") or []:
            by_folder.setdefault(folder, []).append(p["id"])
    for f in env_files:
        if f.get("kind") != "env":
            continue
        name = file_environment(Path(f.get("path") or "").name)
        owners = by_folder.get(f.get("project") or "") or []
        if name and len(owners) == 1:
            env(owners[0], name, "env-file")

    # Evidence 1 and 2: a deployment serves an environment.
    scan = {a["name"]: a for a in heroku_scan_apps}
    no_pipeline_field = [a for a in heroku_scan_apps if "pipeline" not in a]
    if no_pipeline_field:
        degraded.append({"source": "heroku", "reason": f"{len(no_pipeline_field)} app(s) come from a scan that "
                         "predates pipeline stages; the next Heroku scan reads them"})
    for rec in sorted(heroku_records, key=lambda r: r["id"]):
        dep, project = rec["id"], rec.get("project")
        a = scan.get(rec.get("name")) or {}
        if dep in overrides:
            name, rule = overrides[dep], "override"
        elif normalise((a.get("pipeline") or {}).get("stage")):
            name, rule = normalise(a["pipeline"]["stage"]), "heroku-pipeline-stage"
        else:
            why = ("the scan predates pipeline stages" if "pipeline" not in a
                   else f"reading the pipeline failed ({a['pipeline_error']})" if a.get("pipeline_error")
                   else "in no Heroku pipeline, and no override in config/environments.json")
            unassigned.append({"deployment": dep, "why": why})
            continue
        if not project:
            unassigned.append({"deployment": dep, "why": f"{rule} says {name}, but no project claims this app, "
                                                         "so the environment has no project to belong to"})
            continue
        e = env(project, name, rule)
        e["deployments"].append(dep)
        edges.append({"id": f"relation:{dep}:serves:{e['id'].split(':', 1)[1]}", "type": "serves",
                      "from": dep, "to": e["id"], "rule": rule,
                      "source_refs": HEROKU_SRC})
    rows = sorted(envs.values(), key=lambda e: (e["project"], ORDER.index(e["name"])))
    for e in rows:
        e["evidence"].sort()
        e["deployments"].sort()
    doc = {
        "schema_version": 1, "updated_on": obs_date,
        "note": ("Environments scoped by project (docs/design/DEPLOYMENTS.md). A deployment serves an "
                 "environment only on an override or a provider's own statement; vault slots and "
                 ".env.<name> files show that an environment exists, not which app serves it."),
        "environments": rows,
        "unassigned": unassigned,
        "totals": {"environments": len(rows), "served": sum(1 for e in rows if e["deployments"]),
                   "deployments_assigned": len(edges), "deployments_unassigned": len(unassigned)},
        "degraded": degraded,
        "source_refs": sorted(set(HEROKU_SRC + VAULT_SRC + ENV_SRC)),
    }
    return doc, edges
