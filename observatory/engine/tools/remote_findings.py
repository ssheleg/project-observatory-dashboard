#!/usr/bin/env python3
""                                                                       

                                                                                
                                                             

                                                                               
                                                                              
                                                                         
                                                                              

                                                                              

                                                                          
                                                                                
                                                                         
                                                                                
                                                                      
                               
                                                                             
                                                                             
                                                                          
                                                                        

                                                                         
                                                                             
                                                                         
                                                                            
                                                                                
                 

                                                                                
                         
   
from __future__ import annotations

#: Named by name up to this many, as everywhere else on this board.
LISTED = 6


def _listed(items: list[str]) -> str:
    shown = items[:LISTED]
    rest = len(items) - len(shown)
    return ", ".join(shown) + (f" and {rest} more" if rest > 0 else "")


def findings(doc: dict | None) -> list[dict]:
    if not doc:
        return []
    apps = doc.get("apps") or []
    out: list[dict] = []

    # ── a production secret that also lives in a checkout here ──────────────
    shared = [(a["app"], [v["name"] for v in a["vars"]
                          if v["verdict"] == "same_as_local" and v.get("class") == "secret"])
              for a in apps]
    shared = [(app, names) for app, names in shared if names]
    if shared:
        shared.sort(key=lambda r: (-len(r[1]), r[0]))
        total = sum(len(n) for _a, n in shared)
        worst = _listed([f"{app} ({len(names)})" for app, names in shared])
        out.append({
            "type": "remote.same_as_local",
            "subject": "estate:remote-config",
            "severity": "warning",
            "title": (f"{total} production secret(s) hold the same value as a "
                      f"`.env` on this machine"),
            "detail": (f"Measured by comparing salted fingerprints, never values: "
                       f"{worst}. A laptop is not where a production credential "
                       f"should be recoverable from — a stolen checkout, a "
                       f"committed file or a shared screen exposes production "
                       f"directly, and the leak register cannot tell the two "
                       f"apart afterwards. A value that differs is the healthy "
                       f"case and is not reported."),
            "action": ("issue production its own value through the door and "
                       "`heroku config:set` it, or move the local one into the "
                       "vault and let `use_secret run` supply it"),
        })

    # ── a value the vault retired, still deployed ───────────────────────────
    for a in apps:
        for row in a.get("retired_in_use") or []:
            out.append({
                "type": "remote.retired_still_deployed",
                "subject": f"app:{a['app']}/{row['name']}",
                "severity": "critical",
                "title": (f"{a['app']} is still running the value retired from "
                          f"{row['slot']} on {row['retired_on']}"),
                "detail": ("The vault rotated this value away and kept the old one "
                           "as an archive; production's copy still fingerprints to "
                           "that archive. Every reason the value was rotated for is "
                           "still live in production, and the rotation reads as done "
                           "in every record here."),
                "action": (f"`heroku config:set {row['name']}=… -a {a['app']}` with the "
                           f"current value from `tools/use_secret.py`, then record it "
                           f"with `tools/vault.py moved` and delete the archive"),
            })

                                                                                                                          
                                                                           
                                                                             
                                                                           
                                                                             
                                                                     
    unbacked = [(a["app"], [v["name"] for v in a.get("vars") or []
                            if v.get("class") == "secret"
                            and v.get("verdict") in ("remote_only", "no_local_checkout")])
                for a in apps if not a.get("error")]
    unbacked = [(app, names) for app, names in unbacked if names]
    if unbacked:
        unbacked.sort(key=lambda r: (-len(r[1]), r[0]))
        total = sum(len(n) for _a, n in unbacked)
        out.append({
            "type": "remote.unbacked",
            "subject": "estate:remote-config",
            "severity": "info",
            "title": (f"{total} production secret(s) on {len(unbacked)} application(s) "
                      f"exist only at the provider"),
            "detail": (f"Worst first: {_listed([f'{app} ({len(names)})' for app, names in unbacked])}. "
                       f"Nothing on this machine fingerprints to them — no checkout, no "
                       f"vault slot — so an application deleted, a dyno reset or a "
                       f"provider account lost takes the value with it. The registry "
                       f"holds verdicts, never values (S10), which is why this is a "
                       f"count and not a copy."),
            "action": ("for each value worth keeping: `heroku config:get NAME -a <app> | "
                       "tools/vault.py put <project> prod NAME` — on stdin, by name — and "
                       "it comes back with the encrypted store backup; the row stays until "
                       "the scan can see the slot"),
        })

                                                                                                                                                        
                                                                              
                                                                            
                                                                            
                                                                                  
                                                                        
    ns = doc.get("fingerprint_namespace") or {}
    if ns.get("withheld"):
        out.append({
            "type": "remote.namespace_withheld",
            "subject": "estate:remote-config",
            "severity": "warning",
            "title": (f"{ns['withheld']} production secret(s) cannot be compared with "
                      f"this machine's"),
            "detail": (f"{ns.get('reason') or 'the two scans do not share a fingerprint namespace'}. "
                       "Both sides hold the variable and both hold a fingerprint. "
                       "They were salted differently, so equal values would not produce "
                       "equal fingerprints. They read as not compared rather than as "
                       "differing — `differs` is the ordinary verdict here, and reporting "
                       "it would make a changed salt indistinguishable from a healthy estate. "
                       "Nothing about production changed; what changed is what this machine "
                       "can prove about it."),
            "action": (ns.get("action")
                       or "re-read both inventories under one salt, then emit"),
        })

                                                                                                                  
    unreadable = [a["app"] for a in apps if a.get("error")]
    if unreadable:
        out.append({
            "type": "remote.unreadable",
            "subject": "estate:remote-config",
            "severity": "info",
            "title": f"{len(unreadable)} application(s) would not report their configuration",
            "detail": (f"{_listed(sorted(unreadable))}. Their production "
                       f"configuration is unknown here, which is not the same as "
                       f"empty: nothing on this board should be read as saying "
                       f"they hold no secrets."),
            "action": "check the account's access to them, or accept that they are somebody else's",
        })
    return out
