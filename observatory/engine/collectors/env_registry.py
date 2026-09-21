#!/usr/bin/env python3
""                                                                              

                                                                             
                                                                               
                                                                              
                                                                             
                                                                                
    

                                               

                                                                   
                                                                              
                                                                              

                                                                     
                                                                           
                                                                               
                                                                                 
                                                                               
                                                                                
   
from __future__ import annotations
from collections import defaultdict

                                                                               
                                                                                 
                              
FILLABLE_FROM = ("secret", "config")

                                                                        
LISTED = 8


def sites(files: list[dict]) -> dict[str, list[dict]]:
    ""                                                     
    out: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        for v in f["variables"]:
            fp = v.get("fingerprint")
            if fp:
                out[fp].append({"project": f["project"], "path": f["path"],
                                "name": v["name"], "class": v["class"],
                                "kind": f["kind"]})
    return out


def live_names(files: list[dict]) -> dict[str, set[str]]:
    ""                                                       

                                                                               
                                                                                 
                                                             
       
    out: dict[str, set[str]] = defaultdict(set)
    for f in files:
        if f["kind"] != "env":
            continue
        for v in f["variables"]:
            if v["class"] in FILLABLE_FROM:
                out[v["name"]].add(f["project"])
    return out


def enrich(files: list[dict]) -> list[dict]:
    ""                                                                          
    by_fp = sites(files)
    live = live_names(files)
    out = []
    for f in files:
        variables = []
        for v in f["variables"]:
            row = {"name": v["name"], "class": v["class"]}
            fp = v.get("fingerprint")
            if fp:
                group = by_fp[fp]
                others = sorted({s["project"] for s in group} - {f["project"]})
                if others:
                    row["shared_with"] = others
                if len(group) > 1:
                    row["copies"] = len(group)
            elif v["class"] in ("empty", "placeholder") and f["kind"] == "env":
                                                                             
                                                                          
                                                                          
                                                                              
                                                                              
                                 
                where = sorted(live.get(v["name"], set()) - {f["project"]})
                if where:
                    row["available_in"] = where[:LISTED]
            variables.append(row)
        counts = {c: sum(1 for v in f["variables"] if v["class"] == c)
                  for c in ("secret", "config", "placeholder", "empty")}
        out.append({
            "id": "env:" + f["path"],
            "path": f["path"],
            "project": f["project"],
            "kind": f["kind"],
            "git": f["git"],
            "mode": f["mode"],
            "modified_on": f["modified_on"],
            "unparsed_lines": f["unparsed_lines"],
            "counts": {k: v for k, v in counts.items() if v},
            "variables": variables,
        })
    return out


def shared_groups(files: list[dict]) -> list[dict]:
    ""                                                    

                                                                                
                                                                                 
                                    
       
    groups = []
    for fp, group in sites(files).items():
        projects = sorted({s["project"] for s in group})
        if len(projects) < 2:
            continue
        names = sorted({s["name"] for s in group})
        groups.append({
            "projects": projects,
            "names": names,
            "sites": sorted(f"{s['path']}:{s['name']}" for s in group),
            "class": "secret" if any(s["class"] == "secret" for s in group) else "config",
            "in_templates": sum(1 for s in group if s["kind"] == "template"),
        })
                                                                       
    groups.sort(key=lambda g: (-len(g["projects"]), g["class"] != "secret",
                               g["names"][0] if g["names"] else ""))
    return groups


def document(scan: dict, obs_date: str) -> dict:
    files = enrich(scan.get("files") or [])
    groups = shared_groups(scan.get("files") or [])
    real = [f for f in files if f["kind"] == "env"]
    n_vars = sum(len(f["variables"]) for f in files)
    return {
        "schema_version": 1,
        "updated_on": obs_date,
        "note": ("Every `.env` under the estate, measured by collectors/scan_env.py "
                 "as NAMES and never as values. `class` is decided from the value "
                 "and the value is then dropped: secret, config, placeholder or "
                 "empty. `shared_with` is measured, not declared — two variables "
                 "carry it when a salted fingerprint says their values are equal, "
                 "and the salt is machine-local and gitignored so the fingerprint "
                 "itself never reaches this file. `available_in` answers the "
                 "opposite question for a slot still empty here. A `template` is a "
                 "`.env.example` and holds no live value by construction, so it is "
                 "listed apart rather than counted as an inventory."),
        "source_refs": ["SRC-0015"],
        "scanned_on": (scan.get("scanned_at") or "")[:10],
        "root": scan.get("root"),
        "totals": {
            "files": len(files),
            "env_files": len(real),
            "templates": len(files) - len(real),
            "projects": len({f["project"] for f in files if f["project"]}),
            "variables": n_vars,
            "secrets": sum(1 for f in files for v in f["variables"]
                           if v["class"] == "secret"),
            "unfilled": sum(1 for f in real for v in f["variables"]
                            if v["class"] in ("empty", "placeholder")),
            "shared_across_projects": len(groups),
            "tracked_in_git": sum(1 for f in real if f["git"] == "tracked"),
            "unignored": sum(1 for f in real if f["git"] == "loose"),
            "world_readable": sum(1 for f in real if int(f["mode"][-1]) & 0o4
                                  or int(f["mode"][-2]) & 0o4),
        },
        "files": files,
        "shared": groups,
        "degraded": scan.get("degraded") or [],
    }
