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


                                                                              
                                                                    
NAMESPACE_WHY = "fingerprint-namespace"


def namespace_state(scan: dict, env_scan: dict) -> tuple[str, str]:
    ""                                                                          

                                                                               
                                                                             
                                                                               
                                                  
       
    remote, local = scan.get("fingerprint_namespace"), env_scan.get("fingerprint_namespace")
    if not remote or not local:
        missing = " and ".join(
            w for w, got in (("the production scan", remote), ("the local scan", local)) if not got)
        return "absent", (f"{missing} carries no fingerprint namespace, so the salt behind "
                          f"its fingerprints is unknown")
    if remote != local:
        return "mismatched", ("the two scans fingerprint under different salts, so equal "
                              "values would not produce equal fingerprints")
    return "matched", ""


def compare(app: dict, env_scan: dict, retired: list[dict], *,
            comparable: bool = True) -> dict:
    ""                                                               

                                                                              
                                                                                
                                                                                
                          
       
    folders = app.get("folders") or []
    local = _local_index(env_scan, folders) if folders else {}
    retired_by_fp: dict[str, dict] = {r["fingerprint"]: r for r in retired}
    rows, in_use = [], []
    seen = set()
    for v in app.get("vars") or []:
        name, cls = v["name"], v.get("class")
        why = ""
        seen.add(name)
        if not folders:
            # NO CHECKOUT IS NOT A MISMATCH. An application whose source is not
            # on this disk has nothing to be compared against, and calling that
            # `remote_only` would put nineteen applications' worth of variables
            # on the board as a difference nobody can act on.
            verdict = "no_local_checkout"
        elif name not in local:
            verdict = "remote_only"
        elif cls != "secret" or not v.get("fingerprint"):
            verdict = "not_compared"
        elif not local[name]["fingerprints"]:
            verdict = "not_compared"
        elif not comparable:
                                                                              
                                                                              
                                                                              
            verdict, why = "not_compared", NAMESPACE_WHY
        elif v["fingerprint"] in local[name]["fingerprints"]:
            verdict = "same_as_local"
        else:
            verdict = "differs"
        rows.append({"name": name, "class": cls, "verdict": verdict,
                     **({"why": why} if why else {}),
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
    state, reason = namespace_state(scan, env_scan)
    comparable = state == "matched"
    apps = [compare(a, env_scan, scan.get("retired") or [], comparable=comparable)
            for a in scan.get("apps") or []]
    def total(word: str) -> int:
        return sum(a["counts"].get(word, 0) for a in apps)
                                                                          
                                                                         
                                                                              
                                                                       
                                            
    withheld = sum(1 for a in apps for v in a["vars"] if v.get("why") == NAMESPACE_WHY)
    degraded = list(scan.get("degraded") or [])
    if withheld:
        degraded.append({
            "source": "fingerprint namespace",
            "reason": reason,
            "effect": (f"{withheld} production secret(s) that both sides hold are "
                       f"reported as not compared instead of same or different; "
                       f"re-read production with `collectors/scan_remote_env.py "
                       f"store/raw/remote-env.json --force` and re-run `env`, then emit"),
        })
    return {
        "schema_version": 1,
        "updated_on": obs_date,
        "note": ("What production is configured with, compared against the "
                 "checkout on this machine. NAMES, CLASSES AND VERDICTS ONLY: "
                 "the comparison is made from salted fingerprints that live in "
                 "the gitignored scan and never in this file, and the values "
                 "themselves exist only in the scanning process. `differs` is "
                 "the ordinary case for a production secret; `same_as_local` on "
                 "one is not, and neither is a value the vault has retired. "
                 "`fingerprint_namespace` says whether the comparison was allowed "
                 "to happen at all: when the two scans do not name the same salt, "
                 "a row both sides hold reads `not_compared` with `why`, and "
                 "`withheld` counts those rows inside the `not_compared` total."),
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
            "withheld_for_namespace": withheld,
            "retired_still_deployed": sum(len(a["retired_in_use"]) for a in apps),
        },
                                                                      
                                                                            
                                             
        "fingerprint_namespace": {
            "state": state,
            "withheld": withheld,
            **({"reason": reason} if state != "matched" else {}),
            **({"action": "collectors/scan_remote_env.py store/raw/remote-env.json --force, "
                          "then ./observatory.py env and ./observatory.py emit"}
               if withheld else {}),
        },
        "apps": apps,
        "degraded": degraded,
    }
