#!/usr/bin/env python3
""                                                                                     

                                                                                
                                                                                
                                                                            
                                                                           
                                                                             
                                                                              
                                                           

                                                                         

                                                                                
                                                                                
                                                                   
                                                                               
                                                                                
                                                                          
                                                       

                                                                             
                                                                               
                                                                              
                                                                               
                                             
   
from __future__ import annotations
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))
import paths                                            

                                                                            
                                                                            
                                                                        
                                                                    
                                                                               
                                                                               
                                                                       
CONSOLES_PATH = paths.config_file('google_consoles.json')


def consoles(path: pathlib.Path = CONSOLES_PATH) -> dict[str, str]:
    ""                                                                         
                                                                            
    import json
    keys = ("ga4_report", "ga4_admin", "search_console_site", "cloud_project")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    return {k: str(doc.get(k) or "") for k in keys}


def _fill(template: str, **parts: str) -> str | None:
    return template.format(**parts) if template else None


def _norm(s: str) -> str:
    ""                                                            
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def declared_map(path: pathlib.Path) -> dict[str, dict]:
    ""                                                           
    import json
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {row["property"]: row for row in doc.get("properties") or [] if row.get("property")}


def boundary(path: pathlib.Path) -> dict[str, dict]:
    ""                                                                

                                                                              
                                                                                
                                               
       
    import json
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
                                                                                
                                                                               
    hosts = doc.get("hosts") or {}
    if isinstance(hosts, list):
        return {(r.get("host") or "").lower(): r for r in hosts if isinstance(r, dict)}
    return {str(k).lower(): v for k, v in hosts.items() if isinstance(v, dict)}


def match(prop: dict, declared: dict, host_owner, names: dict[str, str]) -> tuple[str | None, str, str]:
    ""                                                  
    d = declared.get(prop["property"])
    if d and d.get("project"):
        return d["project"], "declared", f"collectors/… ga4_properties.json: {d.get('_why', 'operator')}"
    if d and d.get("host"):
        owner = host_owner(d["host"])
        if owner:
            return owner, "declared-host", f"the file names host {d['host']}, which the registry serves"
    for h in prop.get("hosts") or []:
        owner = host_owner(h)
        if owner:
            return owner, "stream-host", f"the property's own web stream is {h}, which the registry serves"
    for app in prop.get("app_ids") or []:
        tail = _norm(app.split(".")[-1])
        if len(tail) >= 4 and tail in names:
            return names[tail], "app-id", f"the app stream {app} ends in the project's own name"
    nm = _norm(prop.get("name") or "")
    if nm and nm in names:
        return names[nm], "name", f"the property is called {prop.get('name')!r}, which is the project's name"
    return None, "", ""


def rows(scan: dict, projects: list[dict], declared_path: pathlib.Path) -> list[dict]:
    ""                                                                         
                                                                               
                           
    import hostmap
    table = hostmap.build()
    def owner_of(host: str):
        return hostmap.resolve(host, table)
    declared = declared_map(declared_path)
    outside = boundary(paths.config_file('host_boundary.json'))
                                                                             
                                                                          
    names: dict[str, str] = {}
    for p in projects:
        names.setdefault(_norm(p["name"]), p["id"])
        for f in p.get("local_folders") or []:
            names.setdefault(_norm(pathlib.Path(f).name), p["id"])
    urls = consoles()
    out = []
    for prop in scan.get("properties") or []:
        pid = (prop.get("property") or "").split("/")[-1]
        aid = (prop.get("account") or "").split("/")[-1]
        project, rule, why = match(prop, declared, owner_of, names)
                                                                                 
                                                                              
                                                                                
                                                  
        hosts = prop.get("hosts") or []
        said = [outside[h] for h in hosts if h in outside]
        if project:
            standing, why_out = "linked", None
        elif hosts and len(said) == len(hosts):
            standing, why_out = "outside", said[0].get("why")
        else:
            standing, why_out = "unclaimed", None
        out.append({
            "id": f"ga4:{pid}",
            "property": prop.get("property"),
            "name": prop.get("name"),
            "account": prop.get("account"),
            "account_name": prop.get("account_name"),
            "hosts": prop.get("hosts") or [],
            "app_ids": prop.get("app_ids") or [],
            "users_30d": prop.get("users_30d"),
            "sessions_30d": prop.get("sessions_30d"),
            "views_30d": prop.get("views_30d"),
            "project": project,
            "standing": standing,
            "boundary_why": why_out,
            "link_rule": rule or None,
            "link_evidence": why or None,
            "unlinked_reason": None if standing != "unclaimed" else (
                "no project in this registry serves any host or app this property "
                "declares, and no curated row names one — by the operator's estate "
                "rule that means somebody else runs it, or it is not being worked on"),
            "report_url": _fill(urls["ga4_report"], pid=pid),
            "admin_url": _fill(urls["ga4_admin"], aid=aid, pid=pid) if aid else None,
            "read_with": prop.get("read_with"),
            **({"error": prop["error"]} if prop.get("error") else {}),
        })
    out.sort(key=lambda r: (-(r.get("users_30d") or 0), r["name"] or ""))
    return out


def document(scan: dict, prop_rows: list[dict], obs_date: str) -> dict:
    urls = consoles()
    sites = []
    for s in scan.get("search_console") or []:
        site = s.get("site") or ""
        sites.append({**s, "console_url": _fill(urls["search_console_site"], site=site)})
    creds = [{**c, "console_url": _fill(urls["cloud_project"], project=c.get("cloud_project"))}
             for c in scan.get("credentials") or []]
    linked = [r for r in prop_rows if r["project"]]
    return {
        "schema_version": 1,
        "updated_on": obs_date,
        "note": ("Every Google Analytics property this machine's service accounts "
                 "can see, joined to a project by what the property itself "
                 "declares — a web stream's host through plugins/hostmap.py, an "
                 "app stream's bundle id, the display name — with the operator's "
                 "own mapping file outranking all three. `users_30d` is active "
                 "users over the last thirty complete days. A property no project "
                 "claims is named, not hidden: by the operator's estate rule it "
                 "belongs to somebody else or is not being worked on."),
        "source_refs": ["SRC-0019"],
                                                                                
                                                                               
                                                                              
        "scanned_on": (scan.get("scanned_at") or "")[:10],
        "totals": {
            "properties": len(prop_rows),
            "accounts": len(scan.get("accounts") or []),
            "linked_to_a_project": len(linked),
            "outside_the_estate": sum(1 for r in prop_rows if r["standing"] == "outside"),
            "unclaimed": sum(1 for r in prop_rows if r["standing"] == "unclaimed"),
            "users_30d_unclaimed": sum(r.get("users_30d") or 0 for r in prop_rows
                                       if r["standing"] == "unclaimed"),
            "users_30d": sum(r.get("users_30d") or 0 for r in prop_rows),
            "search_console_sites": len(sites),
            "by_rule": {rule: sum(1 for r in prop_rows if r["link_rule"] == rule)
                        for rule in sorted({r["link_rule"] for r in prop_rows if r["link_rule"]})},
        },
        "credentials": creds,
        "accounts": scan.get("accounts") or [],
        "properties": prop_rows,
        "search_console": sites,
        "degraded": scan.get("degraded") or [],
    }
