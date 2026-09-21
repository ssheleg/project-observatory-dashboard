#!/usr/bin/env python3
""                                                                                  

                                                                             
                                                                             
                                                                               
                                                                            
                                                                            

                                                                               
                                                                             
                                                                              
                                                                        
                                                          

                                                                          
                                              
   
from __future__ import annotations
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plugins"))
import paths                                                                    

CURATED_PRODUCTS = paths.config_file('products.json')
BOUNDARY = paths.config_file('host_boundary.json')
SRC = ["SRC-0016"]

                                                                          
                                                                                
                                                                               
                                                                                 
                                                                
EVIDENCE_RANK = (
    ("operator-claim", 0),
    ("repo-config:", 1),
                                                                              
                                                                             
                                                                               
    ("dns:", 2),
    ("github:", 2),
    ("bitbucket:", 3),
    ("vault-overview:", 4),
)


def evidence_rank(ev: list[str]) -> int:
    best = 9
    for e in ev or []:
        for prefix, rank in EVIDENCE_RANK:
            if e.startswith(prefix):
                best = min(best, rank)
    return best


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "unnamed"


def registrable(host: str, owned: set[str]) -> str | None:
    parts = host.split(".")
    for i in range(len(parts) - 1):
        cand = ".".join(parts[i:])
        if cand in owned:
            return cand
    return None


                                                                                                                                                                                       

def host_table(projects: list[dict]) -> dict[str, tuple[str, int]]:
    ""                                                                 

                                                                          
                                                      
       
    table: dict[str, tuple[str, int]] = {}
    for p in projects:
        for s in p.get("sites") or []:
            h = (s.get("host") or "").lower()
            if not h:
                continue
            r = evidence_rank(s.get("evidence") or [])
            if h not in table or r < table[h][1]:
                table[h] = (p["id"], r)
    return table


def resolve(host: str, table: dict[str, tuple[str, int]]) -> str | None:
    h = (host or "").lower().strip(".")
    if h in table:
        return table[h][0]
    if h.startswith("www.") and h[4:] in table:
        return table[h[4:]][0]
    parts = h.split(".")
    if len(parts) > 2:
        apex = ".".join(parts[-2:])
        if apex in table:
            return table[apex][0]
    return None


                                                                            
                                                           
TARGET_SUFFIXES = (
    (".herokudns.com", "heroku"), (".herokuapp.com", "heroku"),
    (".pages.dev", "cloudflare-pages"), (".workers.dev", "cloudflare-workers"),
    (".vercel.app", "vercel"), (".vercel-dns.com", "vercel"), ("cname.vercel-dns.com", "vercel"),
    (".netlify.app", "netlify"), (".netlify.com", "netlify"),
    (".github.io", "github-pages"), (".onrender.com", "render"), (".fly.dev", "fly"),
    (".amazonaws.com", "aws"), (".cloudfront.net", "aws"), (".azurewebsites.net", "azure"),
    (".ghost.io", "ghost"), (".webflow.io", "webflow"), (".framer.app", "framer"),
    (".myshopify.com", "shopify"), (".tilda.ws", "tilda"), (".wixdns.net", "wix"),
)


def classify_target(record: dict) -> tuple[str, str] | None:
    ""                                                                             
    if record.get("type") == "CNAME":
        c = (record.get("content") or "").lower().rstrip(".")
        for suf, prov in TARGET_SUFFIXES:
            if c.endswith(suf) or c == suf.lstrip("."):
                return prov, c
        return ("cname", c) if c else None
    if record.get("type") in ("A", "AAAA"):
        return ("ip", record.get("content") or "")
    return None


def zone_targets(z: dict) -> list[dict]:
    ""                                                                  
                                                          
    out = []
    for r in z.get("records") or []:
        if "error" in r:
            continue
        name = (r.get("name") or "").lower()
        if name not in (z["name"], "www." + z["name"]):
            continue
        c = classify_target(r)
        if c:
            out.append({"name": name, "type": r["type"], "provider": c[0], "handle": c[1],
                        "proxied": r.get("proxied", False)})
    return out


def heroku_site_hints(scan_apps: list[dict], linked_apps: list[dict]) -> dict[str, dict[str, str]]:
    ""                                                               

                                                                              
                                                                               
                                                                             
                                                           
       
    proj_of = {a["name"]: a["project"] for a in linked_apps if a.get("project")}
    out: dict[str, dict[str, str]] = {}
    for a in scan_apps:
        pid = proj_of.get(a.get("name"))
        if not pid:
            continue
        for h in a.get("domains") or []:
            out.setdefault(pid, {})[h.lower()] = f"dns:heroku:{a['name']}"
    return out


def _boundary() -> dict:
    try:
        return json.loads(BOUNDARY.read_text(encoding="utf-8")).get("hosts", {})
    except (OSError, ValueError):
        return {}


                                                                                                                                                                                                                              

def zone_rows(scan: dict, domains: list[dict], projects: list[dict],
              products: list[dict] | None = None) -> list[dict]:
    owned = {d["name"] for d in domains}
    by_name = {d["name"]: d for d in domains}
    table = host_table(projects)
    boundary = _boundary()
                                                                           
                                                                               
                                                                    
    prod_of: dict[str, str] = {}
    prod_name: dict[str, str] = {}
    for pr in products or []:
        if pr.get("kind") != "curated":
            continue
        for dom in pr.get("domains") or []:
            prod_of[dom.lower()] = pr["id"]; prod_name[pr["id"]] = pr["name"]
    out = []
    for z in scan.get("zones", []):
        name = z["name"]
        reg = by_name.get(name)
        pid = resolve(name, table)
        b = boundary.get(name) or {}
                                                                             
                                                                            
                                                    
        targets = zone_targets(z)
        readable = not any("error" in r for r in (z.get("records") or []))
        if pid:
            standing = "linked"
        elif b.get("status") == "outside":
            standing = "outside"
        elif b.get("status") == "pending":
            standing = "pending"
        elif name in prod_of or any(name.endswith("." + dm) for dm in prod_of):
            standing = "product"
        elif readable and z.get("records") is not None and not targets:
                                                                           
                                                                      
                                                                             
                                                                           
                                                          
            standing = "dormant"
        else:
            standing = "unclassified"
        out.append({
            "id": f"zone:{name}", "name": name,
            "account": z.get("account_name"), "account_label": z.get("account_label"),
            "status": z.get("status"), "paused": z.get("paused"), "plan": z.get("plan"),
            "registered_domain": f"domain:{name}" if reg else None,
            "registrar": (reg or {}).get("registrar") or z.get("original_registrar"),
            "in_domain_registry": bool(reg),
            "project": pid, "standing": standing,
            "product": (prod_of.get(name)
                        or next((prod_of[dm] for dm in prod_of if name.endswith("." + dm)), None)),
            "boundary_why": b.get("why"), "candidates": b.get("candidates") or [],
            "created_on": z.get("created_on"), "modified_on": z.get("modified_on"),
            "targets": targets,
            "hosted_on": sorted({x["provider"] for x in targets if x["provider"] not in ("ip", "cname")}),
            "dns_readable": readable,
            "source_refs": SRC,
        })
    return out


def zones_document(scan: dict, rows: list[dict], obs_date: str) -> dict:
    by = {}
    for r in rows:
        by[r["standing"]] = by.get(r["standing"], 0) + 1
    return {
        "schema_version": 1, "updated_on": obs_date,
                                                                              
                                                                               
                                                            
        "scanned_on": (scan.get("scanned_at") or "")[:10] or None,
        "accounts": scan.get("accounts", []),
        "note": ("Every Cloudflare zone the estate holds a token for, joined to the "
                 "domain registry, the projects and the operator's boundary file. "
                 "`standing` is the one word the dashboard sorts on: linked (a "
                 "project's surface), outside (ruled beyond the estate's edge), "
                 "pending (the operator owes a word), product (a curated product claims "
                 "it while no single project does), dormant (DNS read, apex and www "
                 "point nowhere — a parked name), unclassified (nobody has spoken)."),
        "degraded": scan.get("degraded", []),
        "zones": rows,
        "totals": {"zones": len(rows), "by_standing": by,
                   "in_domain_registry": sum(1 for r in rows if r["in_domain_registry"]),
                   "linked": by.get("linked", 0)},
        "source_refs": SRC,
    }


                                                                                                                                                                                                                        

def load_curated() -> tuple[dict, list[str]]:
    try:
        doc = json.loads(CURATED_PRODUCTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, []
    return doc.get("products", {}), doc.get("roles", [])


def curated_errors(products: dict, roles: list[str], project_ids: set[str]
                   ) -> tuple[list[str], list[str]]:
    ""                                

                                                                                    
                                                                            
                                                                              
                                                                           
                                                                                
                                                                            
                                                                           
       
    bad, missing = [], []
    for pid, p in products.items():
        if not pid.startswith("product:"):
            bad.append(f"{pid}: id is not namespaced `product:`")
        if not p.get("name"):
            bad.append(f"{pid}: no name")
        if not p.get("why"):
            bad.append(f"{pid}: no why — a grouping nobody can judge later")
        for m, role in (p.get("members") or {}).items():
            if m not in project_ids:
                missing.append(f"{pid}: member {m} is not a project in this registry")
            if role not in roles:
                bad.append(f"{pid}: role {role!r} for {m} is not one of {roles}")
    return bad, missing


def suggested_products(projects: list[dict], domains: list[dict],
                       curated: dict) -> list[dict]:
    ""                                                                   

                                                                       
                                                                              
                                                                            
                             
       
    owned = {d["name"] for d in domains}
    already = {m for p in curated.values() for m in (p.get("members") or {})}
    by_apex: dict[str, dict[str, set[str]]] = {}
    for p in projects:
        if p["id"] in already:
            continue
        for s in p.get("sites") or []:
            h = (s.get("host") or "").lower()
            apex = registrable(h, owned) or (".".join(h.split(".")[-2:]) if h.count(".") >= 1 else None)
            if not apex:
                continue
            by_apex.setdefault(apex, {}).setdefault(p["id"], set()).add(h)
    out = []
    for apex, members in sorted(by_apex.items()):
        if len(members) < 2:
            continue
        out.append({
            "id": f"product:suggested-{slug(apex)}", "name": apex, "kind": "suggested",
            "members": [{"project": m, "role": "other"} for m in sorted(members)],
            "domains": sorted({h for hs in members.values() for h in hs}),
            "why": (f"{len(members)} projects claim hosts under {apex}; a shared "
                    f"registrable domain is the cheapest sign of one product — promote "
                    f"or dismiss in collectors/products.json"),
            "source_refs": SRC,
        })
    return out


def products_document(projects: list[dict], domains: list[dict], obs_date: str
                      ) -> tuple[dict, list[dict], list[str]]:
    ""                                              
    curated, roles = load_curated()
    ids = {p["id"] for p in projects}
    errors, missing = curated_errors(curated, roles, ids)
    rows, edges = [], []
    for pid, p in sorted(curated.items()):
        members = [{"project": m, "role": r} for m, r in sorted((p.get("members") or {}).items())
                   if m in ids]
        rows.append({"id": pid, "name": p["name"], "kind": "curated",
                     "members": members, "domains": sorted(p.get("domains") or []),
                     "why": p["why"], "said_on": p.get("said_on"), "source_refs": SRC})
        for m in members:
            if m["project"] in ids:
                edges.append({"id": f"relation:{m['project'].split(':', 1)[1]}:part-of:"
                                    f"{pid.split(':', 1)[1]}",
                              "type": "part_of", "from": m["project"], "to": pid,
                              "role": m["role"], "source_refs": SRC})
    rows += suggested_products(projects, domains, curated)
    doc = {
        "schema_version": 1, "updated_on": obs_date,
        "note": ("Several projects, folders and domains that are one thing to a user. "
                 "`kind: curated` rows are the operator's decisions from "
                 "collectors/products.json and carry `part_of` edges; `kind: suggested` "
                 "rows are derived from a shared registrable domain and carry none — "
                 "an inference labelled as one."),
        "roles": roles, "products": rows,
                                                                             
                                                                                 
                            
        "degraded": [{"source": "collectors/products.json", "reason": m} for m in missing],
        "totals": {"products": len(rows),
                   "curated": sum(1 for r in rows if r["kind"] == "curated"),
                   "suggested": sum(1 for r in rows if r["kind"] == "suggested"),
                   "projects_grouped": len({m["project"] for r in rows for m in r["members"]})},
        "source_refs": SRC,
    }
    return doc, edges, errors


                                                                                                                                                                                                                  

LIVENESS = ("connected", "failed", "needs-auth", "not-listed", "not-probed")


def mcp_rows(scan: dict) -> list[dict]:
    ""                                                                   
                                                                            
    out = []
    for r in scan.get("servers") or []:
        if not r.get("name"):
            continue
        scope = r.get("scope") or "user"
        out.append({
            "id": f"mcp:{r['agent']}/{slug(scope)}/{slug(r['name'])}",
            "name": r["name"], "agent": r["agent"], "scope": scope,
            "declared_in": r.get("declared_in"),
            "transport": r.get("transport"), "target": r.get("target"),
            "command": r.get("command"), "command_present": r.get("command_present"),
            "key_in_url": bool(r.get("key_in_url")),
            "key_in_header": bool(r.get("key_in_header")),
            "key_in_env": bool(r.get("key_in_env")),
            "liveness": r.get("liveness") if r.get("liveness") in LIVENESS else "not-probed",
            "liveness_detail": r.get("liveness_detail"),
            "source_refs": ["SRC-0017"],
        })
    return out


def mcp_document(scan: dict, rows: list[dict], obs_date: str) -> dict:
    by: dict[str, int] = {}
    for r in rows:
        by[r["liveness"]] = by.get(r["liveness"], 0) + 1
    names = {}
    for r in rows:
        names.setdefault(r["name"], set()).add(r["agent"])
    return {
        "schema_version": 1, "updated_on": obs_date,
        "scanned_on": (scan.get("scanned_at") or "")[:10] or None,
        "note": ("Every MCP server an agent on this machine is told to reach — Claude "
                 "Code (user and project scopes, plugins, claude.ai connectors), "
                 "Cursor, opencode — with its transport, its target minus any query "
                 "string, where its key sits (URL, header, env: booleans only), and "
                 "Claude's own liveness verdict where Claude was the agent asked."),
        "own_server": scan.get("own_server"), "own_declared": bool(scan.get("own_declared")),
        "degraded": scan.get("degraded", []),
        "servers": rows,
        "totals": {"declarations": len(rows), "distinct_servers": len(names),
                   "by_liveness": by,
                   "in_one_agent_only": sum(1 for a in names.values() if len(a) == 1),
                   "key_in_url": sum(1 for r in rows if r["key_in_url"])},
        "source_refs": ["SRC-0017"],
    }
