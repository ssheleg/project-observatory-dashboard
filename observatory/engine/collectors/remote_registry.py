#!/usr/bin/env python3
""                                                                        

                                                                             
                                                                           
                                                            

                                                                   
                                                                
                                                                   
                                                            

                                                                              
                                                                             
                                                                        
                                                                               
                                                                      

                                                                           
                                                                              
                                                                                
                                                                               
                               
   
from __future__ import annotations


def _local_index(env_scan: dict, folders: list[str]) -> dict[str, dict]:
    ""                                                                     

                                                                   
                                                                          
                                               
       
    wanted = {f.rstrip("/").rsplit("/", 1)[-1] for f in folders}
    out: dict[str, dict] = {}
    for rec in env_scan.get("files") or []:
        if rec.get("kind") != "env" or rec.get("project") not in wanted:
            continue
        for v in rec.get("variables") or []:
            row = out.setdefault(v["name"], {"class": v.get("class"),
                                             "fingerprints": set(), "paths": []})
            if v.get("fingerprint"):
                row["fingerprints"].add(v["fingerprint"])
            row["paths"].append(rec.get("path"))
    return out


def compare(app: dict, env_scan: dict, retired: list[dict]) -> dict:
    ""                                                                  
    folders = app.get("folders") or []
    local = _local_index(env_scan, folders) if folders else {}
    retired_by_fp: dict[str, dict] = {r["fingerprint"]: r for r in retired}
    rows, in_use = [], []
    seen = set()
    for v in app.get("vars") or []:
        name, cls = v["name"], v.get("class")
        seen.add(name)
        if not folders:
                                                                               
                                                                               
                                                                               
                                                             
            verdict = "no_local_checkout"
        elif name not in local:
            verdict = "remote_only"
        elif cls != "secret" or not v.get("fingerprint"):
            verdict = "not_compared"
        elif not local[name]["fingerprints"]:
            verdict = "not_compared"
        elif v["fingerprint"] in local[name]["fingerprints"]:
            verdict = "same_as_local"
        else:
            verdict = "differs"
        rows.append({"name": name, "class": cls, "verdict": verdict,
                     **({"empty": True} if v.get("empty") else {})})
        r = retired_by_fp.get(v.get("fingerprint") or "")
        if r:
            in_use.append({"name": name, "retired_on": r["retired_on"],
                           "slot": f"{r['project']}/{r['env']}/{r['name']}"})
    if folders:
        for name, row in sorted(local.items()):
            if name not in seen:
                rows.append({"name": name, "class": row["class"], "verdict": "local_only"})
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return {"app": app["app"], "compared_with": folders,
            "error": app.get("error"), "vars": rows, "counts": counts,
            "retired_in_use": in_use}


def document(scan: dict, env_scan: dict, obs_date: str) -> dict:
    apps = [compare(a, env_scan, scan.get("retired") or []) for a in scan.get("apps") or []]
    def total(word: str) -> int:
        return sum(a["counts"].get(word, 0) for a in apps)
    return {
        "schema_version": 1,
        "updated_on": obs_date,
        "note": ("What production is configured with, compared against the "
                 "checkout on this machine. NAMES, CLASSES AND VERDICTS ONLY: "
                 "the comparison is made from salted fingerprints that live in "
                 "the gitignored scan and never in this file, and the values "
                 "themselves exist only in the scanning process. `differs` is "
                 "the ordinary case for a production secret; `same_as_local` on "
                 "one is not, and neither is a value the vault has retired."),
        "source_refs": ["SRC-0013", "SRC-0015"],
        "scanned_on": (scan.get("scanned_at") or "")[:10],
        "provider": scan.get("provider"),
        "totals": {
            "apps": len(apps),
            "apps_with_a_checkout": sum(1 for a in apps if a["compared_with"]),
            "variables": sum(len(a["vars"]) for a in apps),
            "same_as_local": total("same_as_local"),
            "differs": total("differs"),
            "remote_only": total("remote_only"),
            "local_only": total("local_only"),
            "not_compared": total("not_compared"),
            "no_local_checkout": total("no_local_checkout"),
            "retired_still_deployed": sum(len(a["retired_in_use"]) for a in apps),
        },
        "apps": apps,
        "degraded": scan.get("degraded") or [],
    }
