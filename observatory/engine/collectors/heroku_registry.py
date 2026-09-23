#!/usr/bin/env python3
""                                                                         

                                         

                                                                            
                                                                             
                                                                              
                                                                         
                                                                              
                        

                                                                             
                                                                             
                                                                                
                                                                              
                                                                               
                                                       

                                                                           
                                                                           
                                                                        
                                                                                
                                     
                                                                               
                                                                                 
                                                                   
                                                                    
                                                                               
                                                                     

                                                                                
                                                                                
                                             
   
from __future__ import annotations
import json, pathlib, sys

                                                                               
                                                                               
                                                                   
                                                                              
                                                                                
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths                                            

LINKS = paths.config_file('heroku_links.json')

#: Stacks Heroku has superseded twice over. Not a judgement about whether they
#: still work — they do — but the count belongs on a screen, because the upgrade
#: is a decision somebody has to make and nothing else on this machine asks.
OLD_STACKS = {"heroku-18", "heroku-20", "heroku-22"}


def state_of(app: dict) -> str:
    ""                                                                        

                                                                               
                                                                           
                                                                           
                                                                              
                                          
       
    if app.get("suspended"):
        return "suspended"
    if app.get("scaled", 0) > 0:
        return "running" if app.get("running", 0) > 0 else "down"
    return "resources-only" if app.get("addons") else "idle"


def _repo_owner_index(repos: list[dict], relations: list[dict]) -> dict[str, str]:
    ""                                                                                   
    by_id = {r["id"]: r for r in repos}
    out: dict[str, str] = {}
    for rel in relations:
        if rel.get("type") != "implemented_by":
            continue
        repo = by_id.get(rel.get("to"))
        if repo and repo.get("name_with_owner"):
            out.setdefault(repo["name_with_owner"].lower(), rel["from"])
    return out


def _data_root() -> pathlib.Path:
    ""                                                                              
    root = pathlib.Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import paths
    return paths.DATA


def _folder_index(projects: list[dict]) -> dict[str, str]:
    ""                                                                          
    data = _data_root()
    out: dict[str, str] = {}
    for p in projects:
        for f in p.get("local_folders") or []:
            out.setdefault(str(data / f) if not f.startswith("/") else f, p["id"])
    return out


def load_verified() -> dict[str, dict]:
    ""                                                                

                                                                             
                                                                              
                                                                                
                                                  
       
    if not LINKS.is_file():
        return {}
    doc = json.loads(LINKS.read_text(encoding="utf-8"))
    out = {}
    for row in doc.get("links", []):
        if row.get("app") and row.get("project") and row.get("evidence"):
            out[row["app"]] = row
    return out


def curated_link_errors(links_doc: dict, project_ids: set[str],
                        app_names: set[str] | None = None) -> list[str]:
    ""                                                                     

                                                                          
                                                                             
                                                                       

                                                                         
                                                                              
                                                                            
                                                          
       
    out: list[str] = []
    for row in links_doc.get("links", []):
        app_name = row.get("app")
        if not row.get("evidence"):
            out.append(f"heroku_links row for {app_name} carries no evidence, so it is "
                       f"a guess rather than a verified link")
        project = row.get("project")
        if project and project not in project_ids:
            out.append(f"heroku_links names project {project} for {app_name}, which no "
                       f"longer exists — the curated link is dead and its application "
                       f"reads as unlinked")
        if app_names and app_name and app_name not in app_names:
            out.append(f"heroku_links names application {app_name}, which the scan no "
                       f"longer sees — it was deleted or renamed, and the row is stale")
    return out


def link(app: dict, repo_index: dict, folder_index: dict,
         verified: dict) -> tuple[str | None, str | None, str | None]:
    ""                                                                                 
    gh = (app.get("github") or "").lower()
    if gh and gh in repo_index:
        return repo_index[gh], "heroku-github-link", None
    for folder in app.get("local_folders") or []:
        if folder in folder_index:
            return folder_index[folder], "heroku-remote", None
                                                                             
                                                                           
                                                                               
                                                                           
    for folder in app.get("local_folders") or []:
        owners = [(len(p), pid) for p, pid in folder_index.items()
                  if folder.startswith(p.rstrip("/") + "/")]
        if owners:
            return max(owners)[1], "heroku-remote-nested", None
    row = verified.get(app["name"])
    if row:
        return row["project"], "verified", None
                                                                            
                                                                               
                                                                                
                                                                         
                                       
    if app.get("github"):
        return None, None, ("external-repo", f"Heroku deploys it from {app['github']}, "
                            f"which is not a repository this registry holds")
    if app.get("local_folders"):
        return None, None, ("folder-unclaimed", "a checkout on this machine carries its "
                            "remote, but no project claims that folder")
    return None, None, ("no-source", "Heroku names no repository, no checkout here "
                        "carries its remote, and no verified link names it")


def records(scan: dict, projects: list[dict], repos: list[dict],
            relations: list[dict]) -> tuple[list[dict], list[dict]]:
    ""                                                                           
    repo_index = _repo_owner_index(repos, relations)
    folder_index = _folder_index(projects)
    verified = load_verified()
    apps, edges = [], []
    for a in sorted(scan.get("apps", []), key=lambda x: x["name"]):
        project, rule, why = link(a, repo_index, folder_index, verified)
        rec = {
            "id": "heroku:" + a["name"],
            "name": a["name"],
            "team": a.get("team") or "personal",
            "region": a.get("region"),
            "stack": a.get("stack"),
            "stack_superseded": a.get("stack") in OLD_STACKS,
            "state": state_of(a),
            "maintenance": bool(a.get("maintenance")),
            "scaled": a.get("scaled", 0),
            "running": a.get("running", 0),
            "crashed": a.get("crashed") or [],
            "formation": a.get("formation") or [],
            "addons": a.get("addons") or [],
            "addons_attached": a.get("addons_attached") or [],
            "monthly_cost": a.get("monthly_cost", 0),
            "dyno_cost": a.get("dyno_cost", 0),
            "addon_cost": a.get("addon_cost", 0),
            "last_deploy_on": ((a.get("last_deploy") or {}).get("at") or "")[:10] or None,
            # What is running, as the release says it. Never the configured branch.
            "deployed_commit": ({"sha": a["last_deploy"]["commit"], "release": a["last_deploy"].get("version"),
                                 "source": "heroku-release-description"}
                                if (a.get("last_deploy") or {}).get("commit") else None),
            "last_release_on": ((a.get("last_release") or {}).get("at") or "")[:10] or None,
            "never_deployed": a.get("last_deploy") is None
                              and not a.get("deploy_beyond_window"),
            "github": a.get("github"),
            "auto_deploy": a.get("auto_deploy"),
            "local_folders": a.get("local_folders") or [],
            "web_url": a.get("web_url"),
            "project": project,
            "link_rule": rule,
        }
        if why:
            rec["unlinked_kind"], rec["unlinked_reason"] = why
        apps.append(rec)
        if project:
            edges.append({"id": f"relation:{project.split(':',1)[1]}:deployed-to:{a['name']}",
                          "type": "deployed_to", "from": project, "to": rec["id"],
                          "rule": rec.get("link_rule"), "source_refs": ["SRC-0013"]})
    return apps, edges


def document(scan: dict, apps: list[dict], obs_date: str) -> dict:
    linked = sum(1 for a in apps if a["project"])
    return {
        "schema_version": 1,
        "updated_on": obs_date,
        "note": ("What Heroku says is running, measured by collectors/scan_heroku.py. "
                 "`monthly_cost` is the published on-demand rate times what is scaled "
                 "plus billed_price for add-ons this application OWNS — an upper bound, "
                 "not an invoice, and add-ons attached from another application are "
                 "listed separately because their owner is billed for them. Every "
                 "`project` carries the `link_rule` that made it; an application no "
                 "rule reaches says why in `unlinked_reason` rather than being guessed."),
        "source_refs": ["SRC-0013"],
        "scanned_on": (scan.get("scanned_at") or "")[:10],
        "account": scan.get("account"),
        "teams": scan.get("teams") or [],
        "price_list": scan.get("price_list") or {},
        "totals": {
            "apps": len(apps),
            "linked_to_a_project": linked,
            "unlinked": len(apps) - linked,
            "dynos": sum(a["scaled"] for a in apps),
            "monthly_cost": round(sum(a["monthly_cost"] for a in apps), 2),
            "by_state": {s: sum(1 for a in apps if a["state"] == s)
                         for s in ("running", "down", "suspended",
                                   "resources-only", "idle")},
        },
        "apps": apps,
        "remotes_to_unknown_apps": scan.get("remotes_to_unknown_apps") or [],
        "degraded": scan.get("degraded") or [],
    }
