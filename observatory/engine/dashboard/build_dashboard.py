#!/usr/bin/env python3
""                                                                              

                                                             
                                                                                          
   
from __future__ import annotations
import html, json, os, re, sys
from datetime import datetime, timedelta, timezone
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))                       
import paths                                                                    
                                                                                  
                                                                               
                                                                                
                                                                          
INV = paths.REGISTRY
OUT = paths.DASHBOARD_HTML


def load(name):
    with (INV / name).open(encoding="utf-8") as handle:
        return json.load(handle)


                                                                               
                                                                                 
                                                                              
                                                                                   
                       
WORK_WINDOWS = (7, 28)



                                                                            
                                                                               
                                                                  
AT_RISK_SYNC = ("ahead", "local-only-branch", "unpushed-and-remote-moved",
                "diverged")


def at_risk_total(repos: dict) -> dict:
    ""                                                               

                                                                           
                                                                             
                                                                                  
                                                                          
                                                                             
                                                                            
       
    risky = [r for r in repos.values()
             if (r.get("local") or {}).get("sync") in AT_RISK_SYNC]
    if not risky:
        return {}
    counted = [r for r in risky if isinstance((r.get("local") or {}).get("unpushed"), int)]
                                                                           
                                                                                
                                                                               
    nothing = [r for r in risky if (r.get("local") or {}).get("nothing_exclusive")]
    unmeasured = len(risky) - len(counted) - len(nothing)
    if not counted:
        return {"коммитов ни на одном remote":
                "нечего терять" if nothing and not unmeasured else "не измерено"}
    total = sum(r["local"]["unpushed"] for r in counted)
    if unmeasured:
        return {"коммитов ни на одном remote":
                f"{total}+ ({unmeasured} чекаут(ов) не посчитаны)"}
    return {"коммитов ни на одном remote": total}


def work_stats() -> dict:
    ""                                           

                                                                                   
                                                                                                  
                                                                   

                                                                           
                                                                              
                                                                             
                                                                           
                       

                                                                                  
                                                                               
                                                                               
                                       
       
    import sqlite3
    if not paths.DB.exists():
        return {}
    out: dict[str, object] = {}
    try:
        conn = sqlite3.connect(f"file:{paths.DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return {}
    try:
        for days in WORK_WINDOWS:
            r = conn.execute(
                "SELECT count(*) c, count(DISTINCT project_id) p FROM events"
                " WHERE kind='commit' AND occurred_at >= date('now', ?)",
                (f"-{days} days",)).fetchone()
            if r is None:
                continue
                                                                                
                                                    
            out[f"коммитов за {days} дн"] = r["c"]
            out[f"проектов в работе, {days} дн"] = r["p"]
                                                                              
                                                     
        top = conn.execute(
            "SELECT project_id, count(*) c FROM events WHERE kind='commit'"
            "   AND project_id IS NOT NULL"
            f"  AND occurred_at >= date('now', '-{max(WORK_WINDOWS)} days')"
            " GROUP BY project_id ORDER BY c DESC LIMIT 1").fetchone()
        if top is not None:
            out[f"больше всего работы, {max(WORK_WINDOWS)} дн"] = (
                top["project_id"].split(":", 1)[-1])
    except sqlite3.Error as exc:
                                                                              
                                                        
        print(f"  work tiles unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {}
    finally:
        conn.close()
    return out


def _queue(conn, limit: int = 12) -> list[dict]:
    ""                                                                 

                                                                             
                                                                               
                                                                              
                              
       
                                                                               
                                                                             
                                                                              
                                                                              
                                                               
    CURRENT = ("ledger l JOIN (SELECT memory_id, MAX(revision) r FROM ledger"
               " GROUP BY memory_id) m ON m.memory_id = l.memory_id"
               " AND m.r = l.revision WHERE l.state = 'proposed'")
    return [{"id": r["memory_id"], "rev": r["revision"], "kind": r["kind"],
             "project": r["project_id"], "at": (r["created_at"] or "")[:16].replace("T", " "),
             "statement": (r["statement"] or "")[:200]}
            for r in conn.execute(
                "SELECT l.memory_id, l.revision, l.kind, l.project_id, l.created_at,"
                f" l.statement FROM {CURRENT}"
                " ORDER BY l.created_at DESC LIMIT ?", (limit,))]


def _digest(conn) -> dict:
    ""                                                                       
                                                                            
                                                                          
                                                                        
                                                                              
                                                                             
                                                                            
       
    CURRENT = ("ledger l JOIN (SELECT memory_id, MAX(revision) r FROM ledger"
               " GROUP BY memory_id) m ON m.memory_id = l.memory_id"
               " AND m.r = l.revision WHERE l.state = 'proposed'")
    horizon = 90
    try:
        cfg = json.loads((paths.config_file("retention.json")).read_text(encoding="utf-8"))
        horizon = int(cfg["ledger"]["proposed_days"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    rows = [dict(r) for r in conn.execute(
        f"SELECT l.kind, l.created_at FROM {CURRENT}")]
    by_kind = Counter((r.get("kind") or "?") for r in rows)
    now = datetime.now(timezone.utc)
    soon_n, first = 0, None
    for r in rows:
        try:
            made = datetime.strptime(r.get("created_at") or "", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        gone = made + timedelta(days=horizon)
        if gone <= now + timedelta(days=7):
            soon_n += 1
            first = gone if first is None or gone < first else first
    return {"waiting": len(rows), "by_kind": dict(by_kind.most_common()),
            "horizon_days": horizon, "erases_within_7d": soon_n,
            "first_erase_on": first.strftime("%Y-%m-%d") if first else None}


def from_store() -> dict:
    ""                                              

                                                           
                                                                                 
                                                                              
                               
                                                                                
                                                                           

                                                                         
                                                                                  
                                                                           
       
    import sqlite3
    out = {"weeks": {}, "metrics": {}, "timeline": {}, "notes": {},
       "health": {}, "degraded": "", "queue": []}
    if not paths.DB.exists():
        out["degraded"] = "нет локального хранилища — история и метрики недоступны"
        return out
    try:
        conn = sqlite3.connect(f"file:{paths.DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        out["degraded"] = f"хранилище не открылось: {type(exc).__name__}"
        return out
    try:
        out["queue"] = _queue(conn)
        out["digest"] = _digest(conn)
    except sqlite3.Error as exc:
                                                                            
                                                                              
                           
        out["queue"] = []
        out["degraded"] = (out["degraded"] or "") + f" очередь не прочиталась: {type(exc).__name__}"
    try:
                                                                            
                                                                                
        for r in conn.execute(
                "SELECT project_id, week_start, commits, sessions, worked_days"
                " FROM project_week"
                " WHERE week_start >= date('now', '-182 days') ORDER BY week_start"):
                                                                                
                                                                              
                                                                              
                                          
            out["weeks"].setdefault(r["project_id"], []).append(
                {"w": r["week_start"], "c": r["commits"],
                 "s": r["sessions"], "d": r["worked_days"]})
                                                                           
                                                                                
                                                                          
                                                                           
                                   
                                                                          
                                                                                    
                                                                                   
                                                                               
                                                                              
                                                                             
                                                                               
                        
        labels: dict[str, str] = {}
        try:
            sys.path.insert(0, str(paths.ROOT / "collectors"))
            import run_plugins
            for man in run_plugins.manifests():
                for met in man.get("metrics", []) or []:
                    lab = str(met.get("label") or "").strip()
                    if lab and met.get("name"):
                        labels[met["name"]] = lab
        except Exception as exc:                                                    
                                                                               
                                                                                  
                                         
            print(f"  metric captions unavailable: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
                                                                             
                                                              
                                                                                 
                                                                                 
                                                                               
                                                                            
                                                                              
         
                                                                             
                                                                                 
                                                              
        rows = list(conn.execute(
            "SELECT project_id, metric, unit, value, at FROM metrics"
            " ORDER BY project_id, metric, at DESC"))
        seen: dict[tuple[str, str], int] = {}
        for r in rows:
            key = (r["project_id"], r["metric"])
            rank = seen.get(key, 0)
            seen[key] = rank + 1
            if rank == 0:
                out["metrics"].setdefault(r["project_id"], []).append(
                    {"n": r["metric"], "v": r["value"], "u": r["unit"],
                     "l": labels.get(r["metric"], ""), "at": r["at"]})
            elif rank == 1:
                for m in out["metrics"][r["project_id"]]:
                    if m["n"] == r["metric"]:
                        m["p"], m["pat"] = r["value"], r["at"]
                        break
                                                                            
                                                                                 
        for r in conn.execute(
                "SELECT project_id, occurred_at, actor, payload_json FROM events"
                " WHERE kind='commit' AND project_id IS NOT NULL"
                " ORDER BY occurred_at DESC"):
            bucket = out["timeline"].setdefault(r["project_id"], [])
            if len(bucket) >= 10:
                continue
            try:
                pay = json.loads(r["payload_json"] or "{}")
            except json.JSONDecodeError:
                pay = {}
            bucket.append({"at": r["occurred_at"][:10], "who": r["actor"] or "",
                           "what": (pay.get("subject") or "")[:110],
                           "repo": pay.get("repo") or ""})
                                                                                   
                                                                               
                                                                   
                                                                             
                                                                                
                                                                        
                                                                              
                                                                            
        import survey as survey_mod
        for r in conn.execute(
                "SELECT l.project_id, l.created_at, l.statement, l.state, l.confidence"
                " FROM ledger l" + survey_mod.LIVE_LEDGER_JOIN +
                " WHERE l.project_id IS NOT NULL AND" + survey_mod.LIVE_LEDGER_WHERE +
                " ORDER BY l.created_at DESC"):
            bucket = out["notes"].setdefault(r["project_id"], [])
            if len(bucket) >= 5:
                continue
            bucket.append({"at": (r["created_at"] or "")[:10],
                           "text": (r["statement"] or "")[:400],
                           "state": r["state"] or "",
                           "conf": r["confidence"]})
        last = conn.execute(
            "SELECT started_at, finished_at, degraded_json FROM scans"
            " ORDER BY started_at DESC LIMIT 1").fetchone()
        deg = json.loads(last["degraded_json"] or "[]") if last else []
        out["health"] = {
            "last_scan": last["finished_at"] if last else "",
            "degraded_sources": len(deg),
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "weeks": conn.execute("SELECT COUNT(*) FROM project_week").fetchone()[0],
            "metrics": conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0],
            "proposed": conn.execute(
                "SELECT COUNT(*) FROM ledger l JOIN (SELECT memory_id, MAX(revision) r"
                " FROM ledger GROUP BY memory_id) m ON m.memory_id=l.memory_id"
                " AND m.r=l.revision WHERE l.state='proposed'").fetchone()[0],
                                                                                
                                                                              
                                                                                
                                                                             
                                                        
            "registry_proposals": conn.execute(
                "SELECT COUNT(*) FROM proposals WHERE status='proposed'").fetchone()[0],
        }
                                                                               
                                                                          
                                                                                  
                                 
        lag = conn.execute(
            "SELECT count(*) AS n, min(l.created_at) AS oldest FROM outbox o"
            " JOIN ledger l ON l.memory_id = o.memory_id AND l.revision = o.revision"
            " WHERE o.consumed_at IS NULL").fetchone()
        if lag and lag["n"]:
            out["health"]["projection_lag"] = lag["n"]
            out["health"]["projection_oldest"] = lag["oldest"]
                                                                             
                                                                             
                                                                               
                                                                               
                                                                             
                                       
        import datetime as _dt
        sd = paths.SCRATCH / "serverd.json"
        if sd.is_file():
            try:
                beat = json.loads(sd.read_text(encoding="utf-8"))
                at = _dt.datetime.strptime(beat.get("at", ""), "%Y-%m-%dT%H:%M:%SZ")
                age_s = int((_dt.datetime.utcnow() - at).total_seconds())
                out["health"]["server_age_s"] = age_s
                out["health"]["server_port"] = beat.get("port")
                out["health"]["server_uptime_s"] = beat.get("uptime_s")
                r = beat.get("remote") or {}
                out["health"]["server_at_risk"] = r.get("at_risk_total")
                l = beat.get("leaks") or {}
                out["health"]["leaks_open"] = l.get("open")
            except (ValueError, OSError):
                out["health"]["server_age_s"] = None
        else:
            out["health"]["server_age_s"] = -1                           
    except sqlite3.Error as exc:
        out["degraded"] = f"хранилище нечитаемо: {str(exc)[:60]}"
    finally:
        conn.close()

                                                                              
                                                                              
                                                                      
    for key, name in (("wallet", "wallet.json"), ("provider", "provider-health.json")):
        f = paths.STORE / name
        if f.is_file():
            try:
                out["health"][key] = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

                                                                              
                                                                               
                                                                                
                                                                           
                                                                              
                                                                            
                                                                      
                                       
     
                                                                                 
                                                                          
                                                                                  
                                                                            
                                                                              
                                                                
    w = out["health"].get("wallet") or {}
    if w:
        today = datetime.now(timezone.utc)
        out["health"]["spend_today"] = round(
            (w.get("days") or {}).get(today.strftime("%Y-%m-%d"), 0.0), 6)
        out["health"]["spend_month"] = round(
            (w.get("months") or {}).get(today.strftime("%Y-%m"), 0.0), 6)
        out["health"]["spend_denomination"] = w.get("denomination") or "credits"
    return out


                                                                            
                                                                                 
                                                                            
                                                                             
                                                                              
                                                                               
                                                                                
                                                                            
                                                                                
FINDINGS_ON_PAGE = 8                                                                                     


def _findings_panel(FINDINGS: dict) -> dict:
    ""                                                         

                                                                      
                                                                               
                                                                              

                                                                                
                                                                                
                                                                               
                                                                          

                                                                             
                                                                                  
                                                                              
                                                                                
                                                                     
                                                                            
                                                                

                                                                   
                                                                    
                                                                 
                                                                               
                                                                                
               
       
                                                                             
                                                                          
                                                                         
                                                                           
                                                                               
                                                                   
    open_ = [f for f in FINDINGS["findings"] if not f.get("acked")]
    per_type: dict[str, int] = {}
    items = []
    for f in open_:
        n = per_type.get(f["type"], 0)
        per_type[f["type"]] = n + 1
        items.append({**f, "folded": n >= FINDINGS_ON_PAGE})
    folded_by_type = {k: v - FINDINGS_ON_PAGE for k, v in per_type.items() if v > FINDINGS_ON_PAGE}
                                                                            
                                                                              
                                                 
    silenced = [{"id": f["id"], "type": f["type"], "severity": f["severity"],
                 "title": f["title"], "acked": f["acked"]}
                for f in FINDINGS["findings"] if f.get("acked")]
    return {"counts": FINDINGS["counts"],
            "built_at": FINDINGS.get("built_at"),
            "items": items,
            "folded_by_type": folded_by_type,
            "silenced": silenced,
            "omitted": 0}


def build():
    pdoc, rdoc = load("projects.json"), load("repositories.json")
    projects, repos = pdoc["projects"], {r["id"]: r for r in rdoc["repositories"]}
    relations = load("relations.json")["relations"]
    domains = {d["name"] for d in load("domains.json")["domains"]}
    dups = load("duplicate-repo-names.json")["groups"]

    _fd = INV / "findings.json"
    FINDINGS = json.loads(_fd.read_text(encoding="utf-8")) if _fd.is_file() else None
                                                                                
                                                                          
                                                        
    _hd = paths.REGISTRY / "heroku-apps.json"
    HEROKU = json.loads(_hd.read_text(encoding="utf-8")) if _hd.is_file() else None
                                                                               
                                                                            
                                                                                   
    _cd = paths.REGISTRY / "credentials.json"
    CREDS = json.loads(_cd.read_text(encoding="utf-8")) if _cd.is_file() else None
                                                                               
                                                                          
                                                                                
                                                                           
                                                                               
                                                                          
    KEYS: dict[str, list] = {}
    for _c in (CREDS or {}).get("credentials") or []:
        _slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(_c.get("id", "")).replace("credential:", "", 1))
        for _pid in _c.get("used_by") or []:
            KEYS.setdefault(_pid, []).append({
                "name": _c.get("name"), "kind": _c.get("kind"), "slug": _slug,
                "env": _c.get("env"), "leaked": bool(_c.get("leaked")),
                "signed": bool((_c.get("signature") or {}).get("purpose")),
                "where": (f"vault:{_c['vault_project']}" if _c.get("vault_project")
                          else f"{_c['in_project']}/{_c.get('path') or ''}" if _c.get("in_project")
                          else _c.get("source") or ""),
            })
    for _pid in KEYS:
        KEYS[_pid].sort(key=lambda k: (k["kind"] or "", (k["name"] or "").lower()))
                                                                               
                                                                             
                                                                            
                                                                            
    if CREDS is not None:
        sys.path.insert(0, str(ROOT / "tools"))
        import movements as _movements
        _leaks = Path(os.environ.get("OBSERVATORY_VAULT_DIR",
                                     paths.source_path("secret_store", paths.SECRETS) / "projects")) / "leaks.jsonl"
        _hk_trail: dict[str, list] = {}
        _hk_project: dict[str, str] = {}
        _hkf = paths.SCRATCH / "heroku.json"
        if _hkf.is_file():
            try:
                for _app in json.loads(_hkf.read_text(encoding="utf-8")).get("apps") or []:
                    if _app.get("config_releases"):
                        _hk_trail[_app["name"]] = _app["config_releases"]
            except (OSError, ValueError):
                _hk_trail = {}
        for _a in (HEROKU or {}).get("apps") or []:
            if _a.get("project"):
                _hk_project[_a["name"]] = str(_a["project"]).split(":", 1)[-1]
        CREDS["movements"] = _movements.journal_tail(_leaks, 30)
        CREDS["unrecorded"] = [{**u, "project": _hk_project.get(u["app"])}
                               for u in _movements.unrecorded(_hk_trail, _movements.read_moves(_leaks))]

                                                                           
                                                                                 
                                                                              
                                                                              
                                                          
    _ed = paths.REGISTRY / "env-inventory.json"
    ENVD = json.loads(_ed.read_text(encoding="utf-8")) if _ed.is_file() else None
                                                                                      
                                                                          
                                                                                  
                                                                               
                                                                                                   
                                                                                  
                                                          
                                                                              
                                                                           
                                                                            
                                                 
    _folder_pid = {f: p["id"] for p in pdoc["projects"] for f in (p.get("local_folders") or [])}
    _name_pid = {p["name"]: p["id"] for p in pdoc["projects"]}
    for _f in (ENVD or {}).get("files") or []:
        _pid = _folder_pid.get(_f.get("project")) or _name_pid.get(_f.get("project"))
        if not _pid:
            continue
        for _v in _f.get("variables") or []:
            if _v.get("class") not in ("secret",):
                continue
            KEYS.setdefault(_pid, []).append({
                "name": _v.get("name"), "kind": "env-file", "slug": None,
                "env": None, "leaked": False, "signed": True,                                          
                "where": _f.get("path"), "git": _f.get("git"),
                "href": "env.html#e-" + re.sub(r"[^A-Za-z0-9_.:/-]+", "-", f"{_f.get('path')}:{_v.get('name')}"),
            })
    for _pid in KEYS:
        KEYS[_pid].sort(key=lambda k: (k["kind"] or "", (k["name"] or "").lower()))

                                                                         
                                                                             
                                                                 
                                                                                
                                                                               
                                                          
    _gf = paths.REGISTRY / "google-properties.json"
    GOOGLE = json.loads(_gf.read_text(encoding="utf-8")) if _gf.is_file() else None
    TRAFFIC = {}
    for _p in (GOOGLE or {}).get("properties", []):
        if not _p.get("project"):
            continue
        row = TRAFFIC.setdefault(_p["project"], {"users_30d": 0, "properties": []})
        row["users_30d"] += _p.get("users_30d") or 0
        row["properties"].append({"name": _p.get("name"), "users_30d": _p.get("users_30d"),
                                  "sessions_30d": _p.get("sessions_30d"),
                                  "report_url": _p.get("report_url"),
                                  "admin_url": _p.get("admin_url"),
                                  "hosts": _p.get("hosts") or [],
                                  "rule": _p.get("link_rule")})
                                                                               
                                                                                 
                                                     
    import sys as _sys
    _sys.path.insert(0, str(paths.ROOT / "plugins"))
    import hostmap as _hostmap
    HOSTMAP = _hostmap.build()
    _sc = {}
    for _s in (GOOGLE or {}).get("search_console", []):
        _host = (_s.get("site") or "").replace("sc-domain:", "").replace("https://", "").replace("http://", "").strip("/")
        _owner = HOSTMAP.get(_host) or HOSTMAP.get(_host.replace("www.", ""))
        if _owner:
            _sc.setdefault(_owner, []).append({"site": _s.get("site"), "url": _s.get("console_url")})
    for _pid, _sites in _sc.items():
        TRAFFIC.setdefault(_pid, {"users_30d": 0, "properties": []})["search_console"] = _sites

    _rf = paths.REGISTRY / "remote-env.json"
    REMOTE = json.loads(_rf.read_text(encoding="utf-8")) if _rf.is_file() else None

                                                                               
                                                                              
                                                                                
    DOMAINS = load("domains.json")["domains"]
                                                                               
                                                                               
                                                 
    _zf = paths.REGISTRY / "cloudflare-zones.json"
    ZONES = load("cloudflare-zones.json")["zones"] if _zf.is_file() else None
    _mf = paths.REGISTRY / "mcp-servers.json"
    MCP = load("mcp-servers.json") if _mf.is_file() else None
    _pf = paths.REGISTRY / "products.json"
    PRODUCTS = load("products.json")["products"] if _pf.is_file() else []
    PRODUCT_OF = {}
    for pr in PRODUCTS:
        for mbr in pr["members"]:
            PRODUCT_OF.setdefault(mbr["project"], []).append(
                {"id": pr["id"], "name": pr["name"], "kind": pr["kind"], "role": mbr["role"]})
    LIVE = {}
    _lv = INV / "domain-liveness.json"
    if _lv.is_file():
        for h in json.loads(_lv.read_text(encoding="utf-8"))["hosts"]:
            LIVE[h["host"]] = {"resolves": h["resolves"], "http": h["http_status"],
                               "on": h["checked_on"]}
    members, sites, domain_owner = {}, {}, {}
    for rel in relations:
        if rel["type"] == "implemented_by":
            members.setdefault(rel["from"], []).append(rel["to"])
        elif rel["type"] == "public_domain_of":
            domain_owner.setdefault(rel["from"].split(":", 1)[1], []).append(rel["to"])
            sites.setdefault(rel["to"], []).append(rel["from"].split(":", 1)[1])

    rows = []
    for project in projects:
        ids = sorted(members.get(project["id"], []))
        rows.append({
            "id": project["id"],
            "name": project["name"],
            "owner": (project["owners"] or ["—"])[0] if len(project["owners"]) == 1
                     else ("multi" if project["owners"] else "—"),
            "owners": project["owners"],
            "ownership": project["ownership"],
            "anchor": project["anchor"],
            "lifecycle": project["lifecycle"],
            "description": project.get("description", ""),
            "stack": project.get("stack", []),
            "folders": project.get("local_folders", []),
            "last": project.get("last_activity_on", ""),
            "tier": project.get("activity_tier", ""),
            "note": project.get("canonical_page", "") if project.get("has_vault_note") else "",
            "rules": project.get("membership_rules", []),
                                                                               
                                                                           
                                                                              
                                                    
                                                                               
                                                                               
                                                                            
            "wiki_notes": project.get("vault_notes", 0),
                                                                             
                                                                               
                                      
            "sites": [{**x, "live": LIVE.get(x["host"])} for x in project.get("sites", [])],
            "products": PRODUCT_OF.get(project["id"], []),
            "repos": [{
                "nwo": repos[i]["name_with_owner"],
                "url": repos[i]["url"],
                "host": repos[i]["host"],
                "visibility": repos[i]["visibility"],
                "archived": repos[i]["archived"],
                "fork": repos[i]["fork"],
                "branch": repos[i].get("default_branch", ""),
                "path": (repos[i].get("local") or {}).get("path", ""),
                "checked_out": (repos[i].get("local") or {}).get("checked_out_branch", ""),
                "dirty": (repos[i].get("local") or {}).get("uncommitted_files", 0),
                "sync": (repos[i].get("local") or {}).get("sync", ""),
                                                                              
                                                                                
                                                                                
                                                                                
                "unpushed": (repos[i].get("local") or {}).get("unpushed"),
                "unpushedOn": (repos[i].get("local") or {}).get("unpushed_newest_on"),
                "nothing_exclusive": (repos[i].get("local") or {}).get("nothing_exclusive"),
                "pushed": repos[i].get("last_pushed_on", ""),
                "status": repos[i].get("status"),
                "supersededBy": repos[i].get("superseded_by"),
                "movedTo": repos[i].get("moved_to"),
                "statusEvidence": repos[i].get("status_evidence"),
                "language": repos[i].get("language", ""),
            } for i in ids if i in repos],
        })
    rows.sort(key=lambda r: (r["ownership"] != "owned", r["owner"].lower(), -len(r["repos"]), r["name"].lower()))

    stats = {
                                                                        
                                                             
        **work_stats(),
                                                                             
                                                                      
        **at_risk_total(repos),
        "projects": len(rows),
        "repositories": len(repos),
        "with_site": sum(1 for r in rows if r["sites"]),
        "with_note": sum(1 for r in rows if r["note"]),
        "with_folder": sum(1 for r in rows if r["folders"]),
        "no_note": sum(1 for r in rows if not r["note"]),
        "dirty": sum(1 for r in rows for x in r["repos"] if x["dirty"]),
        "unsynced": sum(1 for r in rows for x in r["repos"]
                        if x["sync"] and x["sync"] != "current"),
                                                                                 
                                                                               
                                                                    
        "inactive_repos": sum(1 for r in repos.values()
                              if r.get("status") == "inactive"),
        "dead_site": sum(1 for r in rows
                         if any(s.get("live") and not s["live"]["resolves"] for s in r["sites"])),
                                                                                
                                                                       
                                                      
        "archived": sum(1 for r in rows if r["lifecycle"] == "archived"),
        "archived_repos": sum(1 for r in repos.values() if r.get("archived")),
        "domains": len(domains),
                                                                              
                                                                               
                                                                           
                                                                                  
                                                                            
                                                                              
                                                                      
                                     
        "domains_no_row": len(domains - {s["host"] for r in rows for s in r["sites"]}),
        "owners": len({r["owner"] for r in rows}),
                                                                           
                                                                             
                                                                              
        "heroku_apps": len(HEROKU["apps"]) if HEROKU else 0,
        "heroku_unlinked": (HEROKU.get("totals", {}).get("unlinked", 0) if HEROKU else 0),
        "heroku_cost": (HEROKU.get("totals", {}).get("monthly_cost", 0) if HEROKU else 0),
        "creds": len(CREDS["credentials"]) if CREDS else 0,
        "creds_leaked": (CREDS.get("totals", {}).get("leaked_unrotated", 0) if CREDS else 0),
        "creds_unclaimed": (CREDS.get("totals", {}).get("unclaimed", 0) if CREDS else 0),
        "heroku_down": (sum(1 for a in HEROKU["apps"]
                            if a["state"] in ("down", "suspended") or a["crashed"])
                        if HEROKU else 0),
    }
                                                                           
                                                                           
                                                                            
                      
    if HEROKU:
        by_project = {}
        for a in HEROKU["apps"]:
            if a.get("project"):
                by_project.setdefault(a["project"], []).append(
                    {"name": a["name"], "state": a["state"], "cost": a["monthly_cost"],
                     "rule": a["link_rule"]})
        for r in rows:
            r["heroku"] = sorted(by_project.get(r["id"], []), key=lambda x: x["name"])
    else:
        for r in rows:
            r["heroku"] = []

    owners = [o for o, _ in Counter(r["owner"] for r in rows).most_common()]
    store = from_store()
    for r in rows:
        r["weeks"] = store["weeks"].get(r["id"], [])
        r["metrics"] = store["metrics"].get(r["id"], [])
        r["timeline"] = store["timeline"].get(r["id"], [])
        r["notes"] = store["notes"].get(r["id"], [])
                                                                                
                                                                              
                                                                          
                                                                                  
                                                                                  
                                      
    PAYLOAD = {"runtime": {"projects": str(paths.DATA), "secrets": str(paths.source_path("secret_store", paths.SECRETS)), "engine": str(paths.ROOT), "home": str(paths.HOME), "python": sys.executable, "scratch": str(paths.SCRATCH)}, "rows": rows, "stats": stats, "owners": owners, "dups": dups,
                          "queue": store.get("queue") or [],
                          "digest": store.get("digest"),
                          "health": store["health"], "store_degraded": store["degraded"],
                                                                               
                                                                                 
                                                                                  
                          "findings": (_findings_panel(FINDINGS)
                                       if FINDINGS else None),
                                                                               
                                                                         
                                                                                
                                                                             
                                                                      
                                                                        
                                                                               
                                                                          
                          "heroku": HEROKU,
                          "creds": CREDS,
                          "env": ENVD,
                          "mcp": MCP,
                          "remote": REMOTE,
                          "google": GOOGLE,
                          "traffic": TRAFFIC,
                          "keys": KEYS,
                          "zones": ZONES,
                          "products": PRODUCTS,
                          "domains": [{
                              "name": d["name"],
                              "registrar": d.get("registrar"),
                              "expires_on": (d.get("namecheap") or {}).get("expires_on"),
                              "auto_renew": (d.get("namecheap") or {}).get("auto_renew"),
                              "status": (d.get("namecheap") or {}).get("status"),
                              "live": LIVE.get(d["name"]),
                              "projects": sorted(domain_owner.get(d["name"], [])),
                          } for d in DOMAINS],
                          "updated": pdoc.get("updated_on", ""),
                          "measured": store["health"].get("last_scan", "")}
    build.last_payload = PAYLOAD                                                  
    payload = json.dumps(PAYLOAD, ensure_ascii=False)
    return (TEMPLATE.replace("__PAGE__", "").replace("__NAV__", "").replace("__CARDS__", "")
            .replace("__TITLE__", "Проекты — операторский реестр")
            .replace("__H1__", "Проекты — операторский реестр")
            .replace("__SUB__", "Реестр из подключённых источников: папки проектов, репозитории и заметки. "
                     "Каждая связь проект↔репозиторий несёт правило, которым проведена.")
            .replace("__DATA__", payload.replace("</", "<\\/")))


def build_pages(payload: dict) -> dict[str, int]:
    ""                                                                     
                                                                       
                                                  
    import shell
    paths.DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    page_tpl, css, js = shell.split_template(TEMPLATE)
    atomic.write_text(paths.DASHBOARD_DIR / shell.ASSET_CSS, css)
    atomic.write_text(paths.DASHBOARD_DIR / shell.ASSET_JS, js)
    sizes = {}
    for name, _title, _kind in shell.PAGES:
        html = shell.page_html(page_tpl, name, payload)
        atomic.write_text(paths.DASHBOARD_DIR / f"{name}.html", html)
        sizes[name] = len(html.encode("utf-8"))
    return sizes


TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script>
/* THE THEME, BEFORE FIRST PAINT (backlog D-04). The choice is the reader's —
   «система», «светлая» or «тёмная» — kept in localStorage; applying it from the
   main script at the bottom of the page would paint one theme and then the
   other. Guarded: the smoke harness has no localStorage and no matchMedia. */
(function () {
  var mode = "system";
  try { mode = localStorage.getItem("observatory.theme") || "system"; } catch (e) {}
  var dark = mode === "dark" || (mode === "system" && typeof matchMedia === "function"
             && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme-mode", mode);
})();
</script>
<style>
                                                        
                                                                              
                                                                     
                                                      
                                                   
:root {
  --bg: #f7f8fa;
  --panel: #ffffff;
  --panel-2: #f7f8fa;
  --ink: #1a1f2b;
  --muted: #5b6472;
  --border: #e6e9ef;
  --border-strong: #d7dce4;
                                                                                        
                                                                                    
                                                                                          
                               
  --accent: #2f6feb;
  --accent-weak: #eaf0fe;
  --accent-ink: #ffffff;                                              
  --ok: #1a7f37;
  --ok-weak: #e6f4ea;
  --warn: #9a6700;
  --warn-weak: #fff3d6;
  --danger: #d1242f;
  --danger-weak: #fde8e9;
  --info: #2f6feb;
  --info-weak: #eaf0fe;

  --r-control: 6px;
  --r-card: 10px;
  --r-pill: 999px;


  --motion-ease: cubic-bezier(0.2, 0, 0, 1);                                    
  --dur-hover: 0.12s;                                   

  --font-ui: -apple-system, "SF Pro", "Segoe UI", sans-serif;
  --font-data: ui-monospace, "SF Mono", Menlo, monospace;

                                                                               
                                                                             
                                                                                
                                                                            
                                                                             
                                 
  --t-chip: 11px;                  
  --t-label: 12px;                                     
  --t-body: 13px;                                        
  --t-section: 20px;                       
  --t-page: 28px;                 

                                                      
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;

  background-color: var(--bg);
  color: var(--ink);
  color-scheme: light;                                                    
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0f1218;
  --panel: #161b24;
  --panel-2: #1b212c;
  --ink: #e8ecf3;
  --muted: #8a93a6;
  --border: #232a36;
  --border-strong: #2c3441;
  --accent: #4b8bff;
  --accent-weak: #1b2740;
  --accent-ink: #0f1218;                                                             
  --ok: #3fb960;
  --ok-weak: #12281a;
  --warn: #d9a93f;
  --warn-weak: #2b2210;
  --danger: #e5534b;
  --danger-weak: #2d1517;
  --info: #4b8bff;
  --info-weak: #1b2740;
}

                                                                            
                                                                            
                                               

@media (prefers-reduced-motion: reduce) {
  :root {
    --dur-hover: 0s;
  }
}

                                                                              
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 400 var(--t-body)/1.5 var(--font-ui);
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-control); }
.mono { font-family: var(--font-data); font-variant-numeric: tabular-nums; }

                                                                              
header {
  padding: var(--space-5) var(--space-5) var(--space-4);
  background: var(--panel); border-bottom: 1px solid var(--border);
}
h1 { margin: 0 0 var(--space-1); font: 700 var(--t-page)/1.2 var(--font-ui); letter-spacing: -.01em; }
.sub { color: var(--muted); max-width: 74ch; }

                                                                             
.tiles { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
.tile {
  border: 1px solid var(--border); border-radius: var(--r-card);
  padding: var(--space-2) var(--space-3); min-width: 104px; background: var(--panel);
}
.qrow { display: grid; grid-template-columns: 128px 1fr; gap: var(--space-3);
  padding: var(--space-2) 0; border-bottom: 1px solid var(--border);
  font-size: var(--t-body); }
.qrow:last-child { border-bottom: 0; }
.qrow .qacts { margin-top: var(--space-2); display: flex; gap: var(--space-2); }
                                                                             
                                                                          
                            
.verbs { display: flex; flex-wrap: wrap; gap: 4px; }
.fbar { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center;
  margin: var(--space-2) 0 var(--space-3); }
.fbar .ftype, .fbar .fq { font: 400 var(--t-body) var(--font-ui); color: var(--ink);
  background: var(--panel); border: 1px solid var(--border); border-radius: var(--r-control);
  padding: 4px 8px; }
.fbar .fq { min-width: 220px; }
.fbar .fshown { font: 400 var(--t-chip) var(--font-data); color: var(--muted); margin-left: auto; }
.f.fhide { display: none !important; }
.f:target { background: var(--accent-weak); }
.fsubj { font-family: var(--font-data); font-size: var(--t-chip); margin-left: 6px; }
.fperma { color: var(--muted); text-decoration: none; margin-left: 6px; font-family: var(--font-data); }
.fperma:hover { color: var(--ink); }
.filters { font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  margin: var(--space-3) var(--space-5) 0; }
.filters b { color: var(--ink); font-weight: 600; }
tr:target > td { background: var(--accent-weak); }
                                                                               
                                                                   
tbody.grp.folded tr + tr { display: none; }
.grp-fold { font: inherit; color: inherit; background: none; border: 0; padding: 0;
  cursor: pointer; text-align: left; width: 100%; }
.grp-fold::before { content: "▸ "; color: var(--muted); }
.grp-fold[aria-expanded="true"]::before { content: "▾ "; }
                                                                             
                                                                          
th[data-sort] .sort { font: inherit; color: inherit; background: none; border: 0; padding: 0;
  cursor: pointer; text-align: inherit; }
th[data-sort] .sort:hover, th[data-sort] .sort:focus-visible { text-decoration: underline; }
th[aria-sort="ascending"] .sort::after { content: " ▴"; color: var(--muted); }
th[aria-sort="descending"] .sort::after { content: " ▾"; color: var(--muted); }
                                                                             
                                                                         
                                                                   
td .mono { overflow-wrap: anywhere; }
.qrow .qm { color: var(--muted); font-family: var(--font-data); font-size: var(--t-chip); }
.tile.more-tiles { cursor: pointer; border-style: dashed; font: inherit; text-align: left;
  color: var(--muted); }
.tile.more-tiles:hover { border-color: var(--accent); color: var(--ink); }
.tile b { display: block; font: 600 var(--t-section)/1.2 var(--font-data);
  font-variant-numeric: tabular-nums; }
.tile span { color: var(--muted); font-size: var(--t-label);
  text-transform: uppercase; letter-spacing: .1em; }

                                                                              
#findings { margin: var(--space-4) var(--space-5) 0; }
.fh { display: flex; align-items: baseline; gap: var(--space-3);
  font: 600 var(--t-label) var(--font-ui); text-transform: uppercase;
  letter-spacing: .1em; color: var(--muted); margin-bottom: var(--space-2); }
.fh .when { font-family: var(--font-data); text-transform: none; letter-spacing: 0; }
.flist { border: 1px solid var(--border); border-radius: var(--r-card);
  background: var(--panel); }
.f { display: flex; gap: var(--space-3); align-items: baseline; flex-wrap: wrap;
  padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border); }
.f:last-child { border-bottom: 0; }
.f .t { font-weight: 600; }
.f .d { color: var(--muted); flex: 1 1 24ch; }
.f .due { font-family: var(--font-data); font-size: var(--t-chip); color: var(--muted);
  white-space: nowrap; }
.f .act { font-size: var(--t-chip); color: var(--muted); font-style: italic; }
.tier { font-size: var(--t-chip); color: var(--muted); }
                                                                               
.flist.folded .f.finfo, .flist.folded .f.fwarning { display: none; }
button.fold { margin: var(--space-2) 0 0 var(--space-3); }
                                                                                
                                                                             
                                                                               
                                                                              
                                
.delta { font-family: var(--font-data); }
.delta.up { color: var(--warn); }
.delta.down { color: var(--ok); }
.spark { display: flex; align-items: center; gap: 4px; color: var(--muted);
         font-size: var(--t-chip); font-family: var(--font-data); }
.spark svg { display: block; }
                                                                            
                                                                         
                                                                         
.spark-sess { opacity: 0.6; }
.panel { padding: 16px; margin-bottom: 12px; }

                                                                             
                                                                              
                                                                              
                                                      
.tabs { display: flex; gap: var(--space-2); align-items: flex-end;
  border-bottom: 1px solid var(--border); margin: var(--space-4) 0 0; }
.tab { appearance: none; border: 1px solid transparent; border-bottom: 0;
  background: none; color: var(--muted); cursor: pointer;
  font: 500 var(--t-body)/1 var(--font-ui);
  padding: var(--space-2) var(--space-3); border-radius: var(--r-control) var(--r-control) 0 0;
  transition: color var(--dur-hover) var(--motion-ease); }
.tab:hover { color: var(--ink); }
.tab[aria-selected="true"] { background: var(--panel); border-color: var(--border);
  color: var(--ink); font-weight: 600; margin-bottom: -1px; }
.tab .n { font-family: var(--font-data); font-variant-numeric: tabular-nums;
  color: var(--muted); margin-left: var(--space-1); }
.seg[hidden] { display: none; }
                                                                              
                                                                              
                      
                                                                               
                                                                             
                                                                            
                                                                             
                                                                                   
.st { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
                                                                    
                                                                            
                                                                               
                                                 
.st > * { white-space: normal; }
.st i { width: 8px; height: 8px; border-radius: var(--r-pill); flex: none; }
.st-running i { background: var(--ok); }
.st-down i, .st-suspended i { background: var(--danger); }
.st-resources-only i { background: var(--warn); }
.st-idle i { background: var(--border-strong); }
.unlinked { color: var(--warn); }
.dhead { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.dmeta { font-size: var(--t-chip); color: var(--muted); margin: 0 0 8px; }
.dlist { margin: 4px 0 12px; padding-left: 18px; }
.dlist li { font-size: var(--t-chip); line-height: 1.5; }
.plink { color: inherit; text-decoration: none; border-bottom: 1px solid var(--border); }
.plink:hover, .plink:focus { border-bottom-color: var(--accent); }
.health { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 4px 16px; margin: 8px 0; }
.hrow { display: flex; justify-content: space-between; gap: 8px;
        font-size: var(--t-chip); color: var(--muted); }
.hrow b { font-family: var(--font-data); color: var(--ink); font-weight: 400; }
@media (max-width: 1100px) { #findings { margin: var(--space-4) var(--space-3) 0; } }

                                                                              
.controls {
  position: sticky; top: var(--topbar, 0px); z-index: 20;
  display: flex; flex-wrap: wrap; gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  background: var(--panel); border-bottom: 1px solid var(--border);
}
input[type=search], select {
  font: 400 var(--t-body) var(--font-ui); color: var(--ink);
  background: var(--panel); border: 1px solid var(--border-strong);
  border-radius: var(--r-control); padding: 6px var(--space-2);
}
input[type=search] { flex: 1; min-width: 240px; }
                                                                 
.seg { display: flex; flex-wrap: wrap; gap: var(--space-1); }
                                                                                
                                                                               
                                             
.view { display: flex; gap: var(--space-1); margin: var(--space-2) var(--space-5) 0; justify-content: flex-end; }
.chip-btn {
  font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  background: var(--panel); border: 1px solid var(--border-strong);
  border-radius: var(--r-pill); padding: 3px 10px; cursor: pointer;
  transition: background var(--dur-hover) var(--motion-ease),
              border-color var(--dur-hover) var(--motion-ease),
              color var(--dur-hover) var(--motion-ease);
}
.chip-btn:hover { background: var(--panel-2); }
.chip-btn[aria-pressed="true"] {
  background: var(--accent-weak); border-color: var(--accent); color: var(--ink);
}

                                                                            
                                                                       
                                                                               
                                                                                  
code.val {
  display: block; font: 400 var(--t-chip) var(--font-data);
  color: var(--ink); background: var(--danger-weak, var(--panel-2));
  border: 1px solid var(--border-strong); border-radius: var(--r-control);
  padding: 4px 6px; margin-bottom: 4px;
  word-break: break-all; user-select: all;
}

                                                                              
                                                                              
                                             
.toast {
  position: fixed; left: 50%; bottom: var(--space-5, 24px);
  transform: translateX(-50%); z-index: 40;
  font: 400 var(--t-chip) var(--font-data); color: var(--ink);
  background: var(--panel-2); border: 1px solid var(--accent);
  border-radius: var(--r-pill); padding: 8px 16px; max-width: 80vw;
}

main { padding: 0 var(--space-5) var(--space-6); }

                                                                             
                                                                            
                                                                           
                                                                            
                                                                         
                                           

                                                      
                                                                          
                                                                          
                                                                       
                                                               
.card { background: var(--panel); border: 1px solid var(--border);
  border-radius: var(--r-card); margin-top: var(--space-4); }
                                                                         

                                                                   
table { border-collapse: separate; border-spacing: 0; width: 100%;
  table-layout: fixed; }
                                                                            
                                                                             
                                                                            
                                                                           
col.c-name { width: 11%; } col.c-site { width:  8%; }
col.c-dir  { width:  9%; } col.c-repo { width: 16%; }
col.c-desc { width: 12%; } col.c-stack{ width:  8%; }
col.c-when { width: 13%; } col.c-host { width:  9%; }
col.c-users{ width:  8%; } col.c-note { width:  6%; }
thead th {
  position: sticky; top: var(--stick, 56px); z-index: 10;
  background: var(--panel-2); color: var(--muted);
  font: 600 var(--t-label) var(--font-ui);
  text-transform: uppercase; letter-spacing: .1em;
  text-align: left; padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-strong); white-space: nowrap;
}
thead th:first-child { border-top-left-radius: var(--r-card); }
thead th:last-child  { border-top-right-radius: var(--r-card); }

                                                        
tbody.grp th {
  text-align: left; padding: var(--space-3) var(--space-3) var(--space-2);
  font: 600 var(--t-label) var(--font-ui);
  text-transform: uppercase; letter-spacing: .1em; color: var(--muted);
  border-bottom: 1px solid var(--border-strong);
  border-top: 1px solid var(--border);
}
tbody.grp:first-of-type th { border-top: 0; }
tbody.grp th .n { font-family: var(--font-data); font-variant-numeric: tabular-nums;
  color: var(--muted); }
tbody td {
  padding: var(--space-2) var(--space-3); vertical-align: top;
  border-bottom: 1px solid var(--border);
}
tbody.grp tr:last-child td { border-bottom: 0; }
tbody tr { transition: background var(--dur-hover) var(--motion-ease); }
tbody tr:hover { background: var(--panel-2); }
td.num { text-align: right; font-family: var(--font-data);
  font-variant-numeric: tabular-nums; white-space: nowrap; }
                                                                            
                                                                               
                                                                          
                                                                             
                                                                       
td.num .tier, td.num .anchor { white-space: normal; }

.name { font-weight: 600; overflow-wrap: anywhere; }
.nwo, .folder { overflow-wrap: anywhere; }
                                                                             
                                                              
.more {
  font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  background: transparent; border: 1px dashed var(--border-strong);
  border-radius: var(--r-pill); padding: 1px 8px; margin-top: 2px; cursor: pointer;
  transition: background var(--dur-hover) var(--motion-ease),
              color var(--dur-hover) var(--motion-ease);
}
.more:hover { background: var(--panel-2); color: var(--ink); }
.repos.folded .item:nth-child(n+4) { display: none; }
.anchor { color: var(--muted); font-size: var(--t-chip); font-family: var(--font-data); }
.desc { color: var(--muted); max-width: 52ch;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.none { color: var(--muted); opacity: .55; }

                                                                              
.chip {
  display: inline-flex; align-items: center; gap: 5px;
  font: 400 var(--t-chip) var(--font-data); color: var(--ink);
  background: var(--panel); border: 1px solid var(--border-strong);
  border-radius: var(--r-pill); padding: 1px 8px; margin: 1px 3px 1px 0;
                                                                             
                                                                             
                                                                           
                                        
  white-space: normal;
}
.chip .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); flex: none; }
.chip.ok { background: var(--ok-weak); border-color: var(--ok); }
.chip.ok .dot { background: var(--ok); }
.chip.warn { background: var(--warn-weak); border-color: var(--warn); }
.chip.warn .dot { background: var(--warn); }
.chip.danger { background: var(--danger-weak); border-color: var(--danger); }
.chip.danger .dot { background: var(--danger); }

                                                                              
.repos { display: flex; flex-direction: column; gap: 3px; }
.repo { display: flex; align-items: baseline; gap: var(--space-2); flex-wrap: wrap; }
.repo .nwo { font-family: var(--font-data); font-size: var(--t-chip); }
                                                                               
                                                                            
.repo.sub { opacity: .62; }
.repo.sub .nwo { text-decoration: line-through; text-decoration-thickness: 1px; }
.rule {
  font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  padding-left: var(--space-3); border-left: 1px solid var(--border);
  margin-left: 2px; max-width: 60ch;
}
                                                                              
                                                                                  
.sites a { font-family: var(--font-data); font-size: var(--t-chip); display: block;
  overflow-wrap: anywhere; }
                                                                               
                                                                           
                                                                               
                                                                         
                                                                           
                                                                          
                                     
.topbar { position: sticky; top: 0; z-index: 30; display: flex; flex-wrap: wrap;
  align-items: center; gap: var(--space-2) var(--space-4);
  padding: var(--space-2) var(--space-5); background: var(--panel);
  border-bottom: 1px solid var(--border); }
.brand { font-weight: 600; color: var(--ink); text-decoration: none; font-size: var(--t-body);
  letter-spacing: .02em; padding: 6px 0; }
.theme { display: inline-flex; margin-left: auto; border: 1px solid var(--border);
  border-radius: var(--r-pill); overflow: hidden; }
.theme button { font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  background: var(--panel); border: 0; padding: 5px 10px; cursor: pointer; }
.theme button + button { border-left: 1px solid var(--border); }
.theme button[aria-pressed="true"] { background: var(--accent-weak); color: var(--ink); }
.theme button:hover { background: var(--panel-2); }
.pages { display: flex; flex-wrap: wrap; gap: var(--space-2); margin: 0; }
.pages a.pg { text-decoration: none; padding: 6px 12px; border: 1px solid var(--border);
  border-radius: var(--r-pill); background: var(--panel); color: var(--ink); font-size: var(--t-chip); }
.pages a.pg[aria-current="page"] { background: var(--ink); color: var(--panel); border-color: var(--ink); }
.pages a.pg .n { font-family: var(--font-data); font-variant-numeric: tabular-nums; margin-left: 4px; opacity: .7; }
.mods { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-3); margin: var(--space-3) 0; }
.mods a.mod { display: block; text-decoration: none; color: inherit; padding: var(--space-3); }
.mods a.mod b { display: block; margin-bottom: 4px; }
body[data-page] .tabs, body[data-page] .controls, body[data-page] .seg, body[data-page] .view { display: none; }
body[data-page="projects"] .controls, body[data-page="projects"] #seg-projects, body[data-page="projects"] #view-projects,
body[data-page="heroku"] .controls, body[data-page="heroku"] #seg-heroku,
body[data-page="domains"] .controls, body[data-page="domains"] #seg-domains,
body[data-page="creds"] .controls, body[data-page="creds"] #seg-creds,
body[data-page="env"] .controls, body[data-page="env"] #seg-env,
body[data-page="mcp"] .controls, body[data-page="mcp"] #seg-mcp,
body[data-page="traffic"] .controls, body[data-page="traffic"] #seg-traffic { display: flex; }
                                                                             
                                                                             
                                                                             
                                                         
body[data-page]:not([data-page="index"]):not([data-page="findings"]) #findings { display: none; }
body[data-page]:not([data-page="index"]):not([data-page="health"]) #tiles,
body[data-page]:not([data-page="index"]):not([data-page="health"]) #more-tiles { display: none; }
                                                                              
                                                                               
                                                                                
                                                                                
                                                             
body[data-page]:not([data-page="health"]) #observer,
body[data-page]:not([data-page="health"]) #queue-s { display: none; }
body[data-page]:not([data-page="projects"]) #reading,
body[data-page]:not([data-page="projects"]) #dups-s { display: none; }
body[data-page="index"] #out, body[data-page="findings"] #out, body[data-page="health"] #out,
body[data-page="index"] #panel, body[data-page="findings"] #panel, body[data-page="health"] #panel { display: none; }
body[data-page="findings"] .flist.folded .finfo, body[data-page="findings"] .flist.folded .fwarning { display: block; }
                                                                            
                                                                          
                                                                              
                                                                               
                                                                             
                                                                           
body[data-page="index"] header { display: flex; flex-direction: column; }
body[data-page="index"] header > #tiles { order: 1; }
body[data-page="index"] header > #work-h, body[data-page="index"] header > #work { order: 2; }
body[data-page]:not([data-page="index"]):not([data-page="health"]) #work,
body[data-page]:not([data-page="index"]):not([data-page="health"]) #work-h { display: none; }
#work-h { font-size: var(--t-chip); letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); margin: var(--space-3) 0 var(--space-2); }
.tile.name { text-decoration: none; color: inherit; }
.tile.name b { font-size: var(--t-body); }
.f.ftype-folded:not(.ftype-open) { display: none; }
.silenced { margin: 8px 0; } .silenced summary { cursor: pointer; font-size: var(--t-chip); color: var(--muted); }
.fsilenced { opacity: .75; }
.folder { font-family: var(--font-data); font-size: var(--t-chip); color: var(--muted); display: block; }

footer {
  margin-top: var(--space-6); padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border); color: var(--muted); font-size: var(--t-chip);
}
footer h3 { margin: 0 0 var(--space-1); font: 600 var(--t-label) var(--font-ui);
  text-transform: uppercase; letter-spacing: .1em; }
footer ul { margin: 0 0 var(--space-3); padding-left: var(--space-4); }
.empty { padding: var(--space-6); text-align: center; color: var(--muted); }

                                                                              
@media (max-width: 1100px) {
  table, tbody, tr, td, tbody.grp th { display: block; width: 100%; }
  thead { display: none; }
  tbody.grp th { border-top: 0; }
  tbody tr { border-bottom: 1px solid var(--border-strong); padding: var(--space-2) 0; }
  tbody td { border: 0; padding: 2px var(--space-3); }
  tbody td::before {
    content: attr(data-label); display: block;
    font: 600 var(--t-chip) var(--font-ui); text-transform: uppercase;
    letter-spacing: .1em; color: var(--muted); margin-top: var(--space-2);
  }
  td.num { text-align: left; }
  td.e { display: none; }                                             
  .desc { max-width: none; }
}
</style>
</head>
<body>
__NAV__
<header>
  <h1>__H1__</h1>
  <p class="sub">__SUB__ Измерено <span class="mono" id="upd"></span>, содержимое
  реестра менялось <span class="mono" id="content-stamp"></span>.</p>
<div class="tiles" id="tiles"></div>
  <h3 id="work-h">Движение</h3>
  <div class="tiles work" id="work"></div>
  <section id="findings"></section>
</header>

<nav class="tabs" role="tablist" aria-label="Что показывать">
  <button class="tab" type="button" id="tab-projects" role="tab" aria-selected="true"
          aria-controls="out">Проекты <span class="n" id="n-projects"></span></button>
  <button class="tab" type="button" id="tab-heroku" role="tab" aria-selected="false"
          aria-controls="out">Heroku <span class="n" id="n-heroku"></span></button>
  <button class="tab" type="button" id="tab-domains" role="tab" aria-selected="false"
          aria-controls="out">Домены <span class="n" id="n-domains"></span></button>
  <button class="tab" type="button" id="tab-creds" role="tab" aria-selected="false"
          aria-controls="out">Ключи <span class="n" id="n-creds"></span></button>
  <button class="tab" type="button" id="tab-env" role="tab" aria-selected="false"
          aria-controls="out">ENV <span class="n" id="n-env"></span></button>
  <button class="tab" type="button" id="tab-mcp" role="tab" aria-selected="false"
          aria-controls="out">MCP <span class="n" id="n-mcp"></span></button>
</nav>

<div class="controls">
  <input type="search" id="q" placeholder="Поиск: имя, описание, репозиторий, папка, домен, стек"
         aria-label="Поиск по реестру">
  <select id="owner" aria-label="Владелец"></select>
  <div class="seg" id="seg-projects" role="group" aria-label="Фильтры проектов">
    <button class="chip-btn" data-f="heroku" aria-pressed="false">есть Heroku</button>
    <button class="chip-btn" data-f="noheroku" aria-pressed="false">нет Heroku</button>
    <button class="chip-btn" data-f="site" aria-pressed="false">есть сайт</button>
    <button class="chip-btn" data-f="note" aria-pressed="false">есть заметка</button>
    <button class="chip-btn" data-f="nonote" aria-pressed="false">нет заметки</button>
    <button class="chip-btn" data-f="folder" aria-pressed="false">есть папка</button>
    <button class="chip-btn" data-f="dirty" aria-pressed="false">незакоммиченное</button>
    <button class="chip-btn" data-f="unsynced" aria-pressed="false">клон не синхронен</button>
    <button class="chip-btn" data-f="dead" aria-pressed="false">сайт не резолвится</button>
    <button class="chip-btn" data-f="drift" aria-pressed="false">объявлен живым, измерен мёртвым</button>
    <button class="chip-btn" data-f="owned" aria-pressed="false">только своё</button>
  </div>
  <!-- D-21 (DEC-0248): a VIEW switch, not a filter. «правила» changes what each
       row shows, never which rows show — so it sits outside the filter group,
       and `narrowing()`, which reads chips inside `.seg` only, does not count
       it among the filters. -->
  <div class="view" id="view-projects" role="group" aria-label="Вид таблицы">
    <button class="chip-btn" data-f="rules" aria-pressed="false" title="показать правило каждой связи проект↔репозиторий">правила: показать</button>
  </div>
  <div class="seg" id="seg-heroku" role="group" aria-label="Фильтры приложений" hidden>
    <button class="chip-btn" data-f="noproject" aria-pressed="false">нет проекта</button>
    <button class="chip-btn" data-f="nofolder" aria-pressed="false">нет папки</button>
    <button class="chip-btn" data-f="norepo" aria-pressed="false">нет репозитория</button>
    <button class="chip-btn" data-f="down" aria-pressed="false">не работает</button>
    <button class="chip-btn" data-f="waste" aria-pressed="false">платит впустую</button>
    <button class="chip-btn" data-f="stale" aria-pressed="false">год без деплоя</button>
    <button class="chip-btn" data-f="oldstack" aria-pressed="false">устаревший стек</button>
  </div>
  <div class="seg" id="seg-domains" role="group" aria-label="Фильтры доменов" hidden>
    <button class="chip-btn" data-f="d-noproject" aria-pressed="false">нет проекта</button>
    <button class="chip-btn" data-f="d-dark" aria-pressed="false">не резолвится</button>
    <button class="chip-btn" data-f="d-http" aria-pressed="false">HTTP ошибка</button>
    <button class="chip-btn" data-f="d-expiring" aria-pressed="false">истекает ≤90 дней</button>
    <button class="chip-btn" data-f="d-norenew" aria-pressed="false">без автопродления</button>
    <button class="chip-btn" data-f="d-unmeasured" aria-pressed="false">не измерен</button>
  </div>
  <div class="seg" id="seg-creds" role="group" aria-label="Фильтры ключей" hidden>
    <button class="chip-btn" data-f="c-leaked" aria-pressed="false">утекло, не ротировано</button>
    <button class="chip-btn" data-f="c-unclaimed" aria-pressed="false">ничей</button>
    <button class="chip-btn" data-f="c-shared" aria-pressed="false">общий: 2+ проекта</button>
    <button class="chip-btn" data-f="c-norotate" aria-pressed="false">никогда не ротировался</button>
    <button class="chip-btn" data-f="c-disabled" aria-pressed="false">отключён</button>
    <button class="chip-btn" data-f="c-untracked" aria-pressed="false">не в хранилище</button>
  </div>
  <div class="seg" id="seg-traffic" role="group" aria-label="Фильтры трафика" hidden>
    <button class="chip-btn" data-f="t-unclaimed" aria-pressed="false">нет проекта</button>
    <button class="chip-btn" data-f="t-linked" aria-pressed="false">привязана</button>
    <button class="chip-btn" data-f="t-quiet" aria-pressed="false">нет пользователей</button>
    <button class="chip-btn" data-f="t-app" aria-pressed="false">только приложение</button>
  </div>
  <div class="seg" id="seg-mcp" role="group" aria-label="Фильтры MCP" hidden>
    <button class="chip-btn" data-f="m-url" aria-pressed="false">ключ в URL</button>
    <button class="chip-btn" data-f="m-down" aria-pressed="false">не отвечает</button>
    <button class="chip-btn" data-f="m-auth" aria-pressed="false">нужен вход</button>
    <button class="chip-btn" data-f="m-alone" aria-pressed="false">только в одном агенте</button>
  </div>
  <div class="seg" id="seg-env" role="group" aria-label="Фильтры ENV" hidden>
    <button class="chip-btn" data-f="e-shared" aria-pressed="false">общее с другим проектом</button>
    <button class="chip-btn" data-f="e-reuse" aria-pressed="false">пусто, есть в другом проекте</button>
    <button class="chip-btn" data-f="e-git" aria-pressed="false">в git</button>
    <button class="chip-btn" data-f="e-open" aria-pressed="false">читает не только владелец</button>
    <button class="chip-btn" data-f="e-all" aria-pressed="false">+ конфиг и пустые</button>
    <button class="chip-btn" data-f="e-tpl" aria-pressed="false">+ шаблоны</button>
  </div>
</div>

<div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
<section id="panel" class="card panel" role="dialog" aria-labelledby="panel-title" hidden></section>
__CARDS__
<main id="out" aria-live="polite"></main>

<footer>
  <section id="reading">
    <h3>Как это читать</h3>
    <p>Правило под репозиторием — причина, по которой он привязан к проекту: имя папки,
    упоминание в заметке, организация, или связь, проверенная вручную. Репозиторий,
    вытеснённый другим или пустой, показан приглушённо и зачёркнуто и называет преемника —
    он не равноправен тому, что его заменил.</p>
  </section>
  <section id="observer">
    <h3>Состояние наблюдателя</h3>
    <p>Что обсерватория знает о себе: когда она смотрела в последний раз, сколько
    собрала и сколько выводов ждёт решения человека. Пусто здесь означает, что
    локального хранилища нет — реестр при этом читается по-прежнему.</p>
    <div id="health" class="health"></div>
  </section>
  <section id="queue-s">
    <h3 id="queue-h">Ждёт решения человека</h3>
    <div id="queue"></div>
  </section>
  <section id="dups-s">
    <h3 id="dups-h">Имена репозиториев у нескольких владельцев</h3>
    <ul id="dups"></ul>
  </section>
</footer>

<script>
                                                                           
                                                                             
                                                                               
const PAGE = "__PAGE__";
const TABLE_PAGES = ["projects", "domains", "heroku", "creds", "env", "mcp", "traffic"];
const D = __DATA__;
const RUNTIME = D.runtime || {};
const shellArg = value => "'" + String(value).replace(/'/g, "'\\''") + "'";
const projectFile = value => String(RUNTIME.projects || ".").replace(/\/$/, "") + "/" + value;
const secretFile = value => String(RUNTIME.secrets || ".").replace(/\/$/, "") + "/" + value;
const engineCommand = (file, args = []) =>
  (RUNTIME.home ? "env " + shellArg("OBSERVATORY_HOME=" + RUNTIME.home) + " " : "") +
  shellArg(RUNTIME.python || "python3") + " " +
  shellArg(String(RUNTIME.engine || ".").replace(/\/$/, "") + "/" + file) +
  args.map(value => " " + shellArg(value)).join("");
const toolCommand = (name, args = []) => engineCommand("tools/" + name, args);
const cliCommand = (...args) => engineCommand("observatory.py", args);
const privateInput = command => command + " < " + shellArg("/absolute/path/to/private-input");

// __SHARED_BELOW__ — the split pages keep everything above this line inline
                                                                            
                                                                               
                                                                        
                                                                              
                                       
  
                                                                             
                                                                            
                                                                           
                                                       
                                                                         
                                                                             
                                                                              
                                                                            
                                                                     
  
                                                                              
                                                                             
                                                                         
  
                                                                        
                                                                              
                                                                    
                                                                                
                                                                                
                   
for (const r of D.rows || []) {
  r.folders = r.folders || [];
  r.stack = r.stack || [];
  r.repos = r.repos || [];
  r.sites = r.sites || [];
}
const E = s => String(s == null ? "" : s).replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

                                                                                
                                                                                
                                                                          
                                                                              
                                                                           
const mq = window.matchMedia("(prefers-color-scheme: dark)");
const THEME_KEY = "observatory.theme";
function themeMode() {
  try { return localStorage.getItem(THEME_KEY) || "system"; } catch (e) { return "system"; }
}
function applyTheme(mode) {
  const dark = mode === "dark" || (mode === "system" && mq.matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme-mode", mode);
  document.querySelectorAll(".theme button[data-mode]").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
}
applyTheme(themeMode());
mq.addEventListener("change", () => { if (themeMode() === "system") applyTheme("system"); });
document.querySelectorAll(".theme button[data-mode]").forEach(b => b.addEventListener("click", () => {
  try { localStorage.setItem(THEME_KEY, b.dataset.mode); } catch (e) {}
  applyTheme(b.dataset.mode);
}));
                                                                         
                                                                                   
document.addEventListener("keydown", ev => {
  if (ev.key !== "/" || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const tag = (ev.target && ev.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return;
  const q = document.getElementById("q");
  if (q && q.offsetParent) { ev.preventDefault(); q.focus(); q.select(); }
});

                                                                            
                                                                            
                                                                              
                                                                            
document.getElementById("upd").textContent = D.measured
  ? D.measured.replace("T", " ").replace("Z", " UTC")
  : "не измерено";
const cs = document.getElementById("content-stamp");
if (cs) cs.textContent = D.updated || "—";
const S = D.stats;
                                                                             
                                                                           
                                                                               
                                                                            
                                                                             
const TILES_PRIMARY = [
  ["проектов", S.projects], ["репозиториев", S.repositories],
  ["приложений Heroku", S.heroku_apps], ["не работает", S.heroku_down],
  ["доменов", S.domains], ["сайт не резолвится", S.dead_site],
  ["клон не синхронен", S.unsynced], ["Heroku $/мес", Math.round(S.heroku_cost)],
];
const TILES_REST = [
  ["владельцев", S.owners], ["с сайтом", S.with_site], ["с папкой", S.with_folder],
  ["с заметкой", S.with_note], ["без заметки", S.no_note],
  ["архивных проектов", S.archived], ["архивных репо", S.archived_repos],
  ["неактивных репо", S.inactive_repos], ["доменов без проекта", S.domains_no_row],
  ["Heroku без проекта", S.heroku_unlinked],
                                                                              
                                                                              
                                                                               
                                                                             
            
  ["грязных рабочих копий", S.dirty], ["ключей в реестре", S.creds],
  ["ключей утекло", S.creds_leaked], ["ключей без проекта", S.creds_unclaimed],
];
                                                                           
                                                                         
                                                                             
                                                                 
const DRIFT = D.rows.filter(r => r.lifecycle === "active"
                            && (r.tier === "dormant" || r.tier === "cold")).length;
                                                                            
                                                                              
                                                                           
                                                                              
                                                                               
const WORK_KEYS = ["коммитов за 7 дн", "проектов в работе, 7 дн",
                   "коммитов за 28 дн", "проектов в работе, 28 дн",
                   "коммитов ни на одном remote"];
const TILES_WORK = WORK_KEYS.filter(k => S[k] != null).map(k => [k, S[k]]);
const tileHTML = ts => ts.map(([k, v]) =>
  `<div class="tile"><b>${v}</b><span>${k}</span></div>`).join("");
{
  const host = document.getElementById("work");
  const top = S["больше всего работы, 28 дн"];
                                                                             
                                                                         
                               
  if (host) host.innerHTML = TILES_WORK.length
    ? tileHTML(TILES_WORK) + (top
        ? `<a class="tile name" href="projects.html#project:${E(top)}"><b>${E(top)}</b>` +
          `<span>больше всего работы, 28 дн</span></a>` : "")
    : '<div class="tile"><b>—</b><span>хранилища нет, движение не измерено</span></div>';
}
                                                                             
                                                                            
                                                                         
                                
document.getElementById("tiles").innerHTML = !D.rows.length
  ? `<div class="tile empty-estate"><b>—</b><span>реестр пуст: ни одного проекта ещё не измерено —
       <button class="chip-btn" type="button" data-copy="${E(cliCommand("local"))}" title="скопировать команду">${E(cliCommand("local"))}</button>
       соберёт его из этой машины</span></div>`
  : tileHTML(TILES_PRIMARY) +
  (DRIFT ? `<a class="tile" href="projects.html?f=drift"><b>${DRIFT}</b>` +
           `<span>объявлены живыми, измерены мёртвыми</span></a>` : "") +
  `<button class="tile more-tiles" id="more-tiles" type="button" aria-expanded="false"
     ><b>+${TILES_REST.length}</b><span>ещё счётчики</span></button>`;
const MORE_TILES = document.getElementById("more-tiles");                                      
if (MORE_TILES) MORE_TILES.onclick = e => {
  const b = e.currentTarget, open = b.getAttribute("aria-expanded") === "true";
  b.setAttribute("aria-expanded", String(!open));
  if (open) { document.querySelectorAll(".tile.extra").forEach(t => t.remove());
              b.querySelector("span").textContent = "ещё счётчики"; return; }
  b.insertAdjacentHTML("beforebegin",
    tileHTML(TILES_REST).replaceAll('class="tile"', 'class="tile extra"'));
  b.querySelector("span").textContent = "свернуть";
};


                                                                              
                                                                                
                                                                                
                                                                         
const H = D.health || {};
const hb = [];
if (D.store_degraded) hb.push(["хранилище", D.store_degraded]);
if (H.last_scan) hb.push(["последний скан", H.last_scan.replace("T", " ").replace("Z", " UTC")]);
if (H.events != null) hb.push(["событий", H.events.toLocaleString("ru")]);
if (H.weeks != null) hb.push(["недельных срезов", H.weeks.toLocaleString("ru")]);
if (H.metrics != null) hb.push(["измерений плагинов", H.metrics.toLocaleString("ru")]);
                                                                         
                                                                                
if (H.server_age_s != null) {
  if (H.server_age_s === -1) hb.push(["локальный сервер", "не запущен"]);
  else if (H.server_age_s < 90) {
    const up = H.server_uptime_s >= 3600
      ? Math.floor(H.server_uptime_s / 3600) + " ч" : Math.floor(H.server_uptime_s / 60) + " мин";
    hb.push(["локальный сервер", `жив · порт ${H.server_port} · аптайм ${up}`]);
    if (H.server_at_risk != null)
      hb.push(["remote под риском", `${H.server_at_risk} чекаут(ов) с работой только на этом диске`]);
  } else hb.push(["локальный сервер", `МОЛЧИТ ${Math.floor(H.server_age_s / 60)} мин — store/logs/serverd.err`]);
}
                                                                              
                                                                              
                                                                              
                                                           
const SERVERD_FIX = {
  down: ["наблюдатель не запущен — запустить в терминале", toolCommand("serverd.py", ["--run"])],
  silent: ["наблюдатель молчит — проверить", toolCommand("serverd.py", ["--status"])],
};
if (H.leaks_open > 0) hb.push(["утечки секретов", `${H.leaks_open} не ротировано — vault.py leaks`]);
if (H.proposed != null) hb.push(["ждут решения оператора", H.proposed]);
if (H.registry_proposals) hb.push(["правок реестра предложено", H.registry_proposals]);
if (H.projection_lag) hb.push(["не проиндексировано выводов",
  `${H.projection_lag}, старейший от ${(H.projection_oldest || "").slice(0, 10)}`]);
if (H.degraded_sources) hb.push(["источников деградировало", H.degraded_sources]);
                                                                              
                                                                               
                                                                                
                       
if (H.spend_month != null)
  hb.push(["потрачено этим проектом за месяц",
           `${(+H.spend_month).toFixed(4)} ${E(H.spend_denomination || "")}`]);
if (H.spend_today != null)
  hb.push(["из них сегодня", `${(+H.spend_today).toFixed(4)}`]);
                                                                              
                                                                           
                                                                               
                                                                             
                                                                            
                                                                              
                                                                                 
                                                                              
                                                                             
                   
{
  const q = Object.keys(H.provider || {});
  if (q.length)
    hb.push([`моделей в карантине: ${q.length}`, q.slice(0, 3).join(", ")
             + (q.length > 3 ? ` и ещё ${q.length - 3}` : "")]);
}
{
  const state = H.server_age_s == null ? null
    : H.server_age_s === -1 ? "down" : H.server_age_s < 90 ? "up" : "silent";
  const fix = SERVERD_FIX[state];
  document.getElementById("health").innerHTML = (hb.length
    ? hb.map(([k, v]) => `<div class="hrow"><span>${E(k)}</span><b>${E(String(v))}</b></div>`).join("")
    : '<div class="hrow"><span>наблюдатель</span><b>данных нет</b></div>')
    + (fix ? `<div class="hrow"><span>${E(fix[0])}</span><b><span class="mono">${E(fix[1])}</span>` +
             ` <button class="chip-btn" type="button" data-copy="${E(fix[1])}">копировать</button></b></div>` : "");
}

document.getElementById("dups").innerHTML = D.dups.map(g =>
  `<li class="mono">${g.map(E).join("  ·  ")}</li>`).join("")
  || '<li class="none">нет</li>';

                                                                            
                                                                                
                                                                              
                                                                               
                                                     
let tab = "projects";

const sel = document.getElementById("owner");
                                                                               
                                                                            
                                        
const SEL_BY_TAB = {
  projects: ["все владельцы", "Владелец", () => D.owners],
  heroku:   ["все команды", "Команда",
             () => [...new Set(((D.heroku && D.heroku.apps) || []).map(a => a.team))].sort()],
  domains:  ["все регистраторы", "Регистратор",
             () => [...new Set((D.domains || []).map(d => d.registrar).filter(Boolean))].sort()],
                                                                               
                                                                            
  creds:    ["все разделы", "Раздел",
             () => CRED_SECTIONS.map(s => s[1])],
  env:      ["все проекты", "Проект",
             () => [...new Set(ENVF.map(f => f.project).filter(Boolean))].sort()],
  mcp:      ["все агенты", "Агент",
             () => [...new Set(((D.mcp && D.mcp.servers) || []).map(s => s.agent).filter(Boolean))].sort()],
  traffic:  ["все аккаунты", "Аккаунт",
             () => [...new Set(((D.google && D.google.properties) || []).map(p => p.account_name).filter(Boolean))].sort()],
};
function fillOwners() {
  const [all, label, vals] = SEL_BY_TAB[tab];
  sel.innerHTML = `<option value="">${all}</option>` +
    vals().map(o => `<option value="${E(o)}">${E(o)}</option>`).join("");
  sel.setAttribute("aria-label", label);
}
fillOwners();

                                                                            
                                                                        
                                                                               
                                                                                
const activeBy = { projects: new Set(), heroku: new Set(), domains: new Set(),
                   creds: new Set(), env: new Set(), mcp: new Set(),
                   traffic: new Set() };
let active = activeBy.projects;
document.querySelectorAll(".chip-btn[data-f]").forEach(c => c.onclick = () => {
  const on = c.getAttribute("aria-pressed") === "true";
  c.setAttribute("aria-pressed", String(!on));
  on ? active.delete(c.dataset.f) : active.add(c.dataset.f);
  render();
});
                                                                             
                                                                               
                                                                              
                                                                             
                                       
{
  const wanted = new Set(new URLSearchParams(location.search || "").getAll("f"));
                                                                            
                                                                               
  document.querySelectorAll(".chip-btn[data-f]").forEach(c => {
    if (!wanted.has(c.dataset.f)) return;
    c.setAttribute("aria-pressed", "true");
    c.dataset.fromUrl = "1";
    c.title = "включён ссылкой";
    active.add(c.dataset.f);
  });
}

const APPS = (D.heroku && D.heroku.apps) || [];
const DOMS = D.domains || [];
const LIVE_BY_HOST = h => { const d = DOMS.find(x => x.name === h); return d ? d.live : null; };
const CREDS = (D.creds && D.creds.credentials) || [];
const ENVF = (D.env && D.env.files) || [];
                                                                             
                                                                              
                                                                              
                         
const ENVV = ENVF.flatMap(f => f.variables.map(v => ({
  path: f.path, project: f.project, kind: f.kind, git: f.git, mode: f.mode,
  modified_on: f.modified_on, name: v.name, cls: v["class"],
  shared: v.shared_with || [], copies: v.copies || 1,
  available: v.available_in || [],
})));
const PROJ_NAME = new Map(D.rows.map(r => [r.id, r.name]));
function selectTab(next) {
  tab = next;
  active = activeBy[tab];
  for (const t of ["projects", "heroku", "domains", "creds", "env", "mcp"]) {
    const tb = document.getElementById("tab-" + t), sg = document.getElementById("seg-" + t);
    if (tb) tb.setAttribute("aria-selected", String(tab === t));
    if (sg) sg.hidden = tab !== t;
  }
                                                                              
                                                                            
  const vw = document.getElementById("view-projects");
  if (vw) vw.hidden = tab !== "projects";
  fillOwners();
  render();
}
                                                                           
                                                                       
                                                              
for (const t of ["projects", "heroku", "domains", "creds", "env", "mcp"]) {
  const tb = document.getElementById("tab-" + t);
  if (tb) tb.onclick = () => selectTab(t);
}
document.getElementById("q").oninput = render;
sel.onchange = render;

const hay = r => [r.name, r.description, r.owner, r.last, r.folders.join(" "),
  r.stack.join(" "), r.sites.map(s => s.host).join(" "),

                                                                            
                                   
  (r.heroku || []).map(h => h.name).join(" "),
  r.repos.map(x => x.nwo + " " + x.path).join(" ")].join(" ").toLowerCase();

function keep(r, q, owner) {
  if (q && !hay(r).includes(q)) return false;
  if (owner && r.owner !== owner) return false;
  if (active.has("site") && !r.sites.length) return false;
  if (active.has("note") && !r.note) return false;
  if (active.has("nonote") && r.note) return false;
  if (active.has("folder") && !r.folders.length) return false;
  if (active.has("dirty") && !r.repos.some(x => x.dirty)) return false;
                                                                             
                                                                    
  if (active.has("dead") &&
      !r.sites.some(s => s.live && !s.live.resolves)) return false;
  if (active.has("unsynced") &&
      !r.repos.some(x => x.sync && x.sync !== "current")) return false;
  if (active.has("owned") && r.ownership !== "owned") return false;
                                                                              
                                                                            
                        
  if (active.has("drift") &&
      !(r.lifecycle === "active" && (r.tier === "dormant" || r.tier === "cold"))) return false;
  if (active.has("heroku") && !(r.heroku || []).length) return false;
  if (active.has("noheroku") && (r.heroku || []).length) return false;
  return true;
}

                                                                              
                                                                               
                                                           
const YEAR_AGO = new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
const hayApp = a => [a.name, a.team, a.state, a.stack, a.region, a.github || "",
  a.project ? (PROJ_NAME.get(a.project) || a.project) : "",
  (a.local_folders || []).join(" "),
  (a.addons || []).map(x => x.plan).join(" ")].join(" ").toLowerCase();

function keepApp(a, q, team) {
  if (q && !hayApp(a).includes(q)) return false;
  if (team && a.team !== team) return false;
  if (active.has("noproject") && a.project) return false;
  if (active.has("nofolder") && (a.local_folders || []).length) return false;
                                                                              
                                                                               
  if (active.has("norepo") && (a.github || a.project)) return false;
  if (active.has("down") &&
      !(a.state === "down" || a.state === "suspended" || (a.crashed || []).length)) return false;
  if (active.has("waste") && a.state !== "resources-only") return false;
                                                                               
                                                                              
                                               
  if (active.has("stale") && !(a.last_deploy_on && a.last_deploy_on < YEAR_AGO)) return false;
  if (active.has("oldstack") && !a.stack_superseded) return false;
  return true;
}

const chip = (text, kind) =>
  `<span class="chip${kind ? " " + kind : ""}"><span class="dot"></span>${E(text)}</span>`;

function repoLine(x, rules) {
                                                                                
                                                                               
                                                            
  const sub = ["superseded", "placeholder", "moved"].includes(x.status);
  const bits = [];
  if (x.visibility === "public") bits.push(chip("public"));
  if (x.archived) bits.push(chip("архивный", "warn"));
  if (x.fork) bits.push(chip("форк"));
  if (x.host === "bitbucket") bits.push(chip("bitbucket"));
  if (x.dirty) bits.push(chip(x.dirty + " несохр.", "danger"));
                                                                               
                                                                          
  const SYNC = {
    "behind":             ["отстаёт", "warn"],
    "stale":              ["отстаёт", "warn"],
    "behind-or-diverged": ["отстаёт или разошёлся", "warn"],
    "diverged":           ["разошёлся", "danger"],
    "ahead":              ["не запушено", "danger"],
    "unpushed-and-remote-moved": ["не запушено, remote ушёл", "danger"],
    "local-only-branch":  ["ветка только здесь", "danger"],
    "unreachable":        ["remote недоступен", "danger"],
    "unknown":            ["состояние неизвестно", "warn"],
  };
  if (SYNC[x.sync]) {
                                                                            
    const [label, tone] = SYNC[x.sync];
    bits.push(chip(label + stakeText(x), tone));
  }
  if (x.checked_out && x.branch && x.checked_out !== x.branch)
    bits.push(chip("ветка " + x.checked_out, "warn"));
  if (x.status === "superseded")
    bits.push(chip("вытеснен → " + x.supersededBy, "warn"));
  if (x.status === "placeholder") bits.push(chip("пустой", "warn"));
  if (x.status === "moved") bits.push(chip("переехал → " + x.movedTo, "warn"));
  const rule = rules.find(s => s.startsWith(x.nwo + ":"));
                                                                              
                                                                            
  return `<div class="item"><div class="repo${sub ? " sub" : ""}">` +
    `<a class="nwo" href="${E(x.url)}" target="_blank" rel="noopener">${E(x.nwo)}</a>` +
    bits.join("") + `</div>` +
    (active.has("rules") && rule ? `<div class="rule">${E(rule.slice(x.nwo.length + 2))}</div>` : "") +
    `</div>`;
}

const NONE = '<span class="none">—</span>';
                                                                               
                                                          
const TIER_RU = {active: "активен", cooling: "остывает", dormant: "спит",
                 cold: "холодный", unknown: "дата неизвестна"};

                                                                                
                                                                                 
                                                                      
  
                                                                              
                                                                               
                                                                                
                                                                              
                                                                               
                                    
  
                                                                                
                                                                          
                                                             
function spark(weeks) {
  if (!weeks || !weeks.length) return "";
  const vals = weeks.map(w => w.c);
  const sess = weeks.map(w => (w.s == null ? null : w.s));
  const max = Math.max(...vals, ...sess.filter(v => v != null), 1);
  const total = vals.reduce((a, b) => a + b, 0);
  const stotal = sess.reduce((a, b) => a + (b || 0), 0);
  const measured = sess.some(v => v != null);
  const W = 72, H = 14, step = W / Math.max(vals.length - 1, 1);
  const line = (arr) => arr.map((v, i) => v == null ? null :
      `${(i * step).toFixed(1)},${(H - (v / max) * (H - 2)).toFixed(1)}`)
    .filter(Boolean).join(" ");
  const worked = weeks.filter(w => w.d != null && w.d > 0).length;
  const title = `${vals.length} нед., ${total} коммитов` +
    (measured ? `, ${stotal} сессий, ${worked} нед. с работой` : "");
  return `<div class="spark" title="${title}">` +
    `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true">` +
    `<polyline points="${line(vals)}" fill="none" stroke="currentColor" stroke-width="1"/>` +
    (stotal ? `<polyline points="${line(sess)}" fill="none" stroke="currentColor"` +
              ` stroke-width="1" stroke-dasharray="2 2" opacity="0.55"/>` : "") +
    `</svg><span>${total}</span>` +
    (stotal ? `<span class="spark-sess">+${stotal}с</span>` : "") +
    `</div>`;
}

                                                                            
                                                                                
                                   
                                                                              
                                                                   
function plural(n, one, few, many) {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  return b === 1 ? one : many;
}

function metrics(list) {
  if (!list || !list.length) return "";
                                                                                
                                                                             
                                                                               
                                
    
                                                                                 
                                                                              
                                 
  return list.map(m => {
    const cap = (m.l || m.n || "").trim();
    const val = m.u === "bytes" ? bytes(m.v)
              : (m.l ? `${(+m.v).toLocaleString("ru")}`
                     : `${(+m.v).toLocaleString("ru")} ${E(m.u || "")}`.trim());
                                                                              
                                                                                
                                                                            
                                                   
    let d = "";
    if (m.p != null && +m.p !== +m.v) {
      const up = +m.v > +m.p, diff = Math.abs(+m.v - +m.p);
      const shown = m.u === "bytes" ? bytes(diff) : diff.toLocaleString("ru");
      const was = m.u === "bytes" ? bytes(m.p) : (+m.p).toLocaleString("ru");
      d = ` <span class="delta ${up ? "up" : "down"}" title="было ${was}` +
          ` — ${E((m.pat || "").slice(0, 10))}">${up ? "↑" : "↓"}${shown}</span>`;
    }
    return `<div class="tier" title="${E(m.n)}">` +
           `<span class="cap">${E(cap)}</span> ${val}${d}</div>`;
  }).join("");
}

                                                                          
                                                                              
                                                                           
                                                                              
                                                                               
function stakeText(x) {
  if (typeof x.unpushed === "number" && x.unpushed > 0)
    return ` · ${x.unpushed}` + (x.unpushedOn ? ` от ${x.unpushedOn}` : "");
                                                                    
                                                                  
  if (x.nothing_exclusive) return " · ничего исключительного";
  return "";
}

function bytes(n) {
  if (!n) return "";
  const u = ["Б", "КБ", "МБ", "ГБ"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

function row(r) {
  const siteChip = s => {
                                                                              
                                                                                
                                                           
    if (!s.live) return chip("не измерено");
    if (!s.live.resolves) return chip("не резолвится", "danger");
    if (s.live.http >= 400 || s.live.http === 0) return chip("HTTP " + s.live.http, "warn");
    return "";
  };
  const sites = r.sites.length ? `<div class="sites">` + r.sites.map(s =>
      `<a href="https://${E(s.host)}" target="_blank" rel="noopener">${E(s.host)}</a>` +
      chip(s.confidence === "registry-confirmed" ? "в реестре" : "вне реестра",
           s.confidence === "registry-confirmed" ? "ok" : "warn") + siteChip(s)).join("") + `</div>`
    : NONE;
  const folders = r.folders.length
    ? r.folders.map(f => `<span class="folder">${E(projectFile(f))}</span>`).join("")
    : NONE;
  const many = r.repos.length > 3;
  const repos = r.repos.length
    ? `<div class="repos${many ? " folded" : ""}">` +
        r.repos.map(x => repoLine(x, r.rules || [])).join("") +
      `</div>` + (many
        ? `<button class="more" type="button">+${r.repos.length - 3} ещё</button>` : "")
    : NONE;
  const stack = r.stack.slice(0, 3).map(s => chip(s)).join("") +
    (r.stack.length > 3 ? chip("+" + (r.stack.length - 3)) : "");
  const note = r.note ? chip(r.wiki_notes + " зам.", "ok") : NONE;
                                                                                
                                                                               
                                                                           
                                                        
  const host = (r.heroku || []).length
    ? (r.heroku || []).map(h =>
        `<div class="st st-${E(h.state)}" title="${E(h.rule)}"><i></i>` +
        `<span class="mono">${E(h.name)}</span>` +
        (h.cost ? `<span class="anchor"> $${Math.round(h.cost)}</span>` : "") +
        `</div>`).join("")
    : NONE;
                                                                          
                                                                           
                                                                        
                                                                           
  const td = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  return `<tr>
    <td data-label="Проект"><div class="name"><a class="plink" href="#${E(r.id)}"
      >${E(r.name)}</a></div>
      <div class="anchor">${E(r.anchor)}</div></td>
    ${td("Сайт", sites)}
    ${td("Папка", folders)}
    ${td("Репозиторий", repos)}
    ${td("Описание", `<div class="desc">${E(r.description) ||
      '<span class="none">нет описания</span>'}</div>`)}
    ${td("Стек", stack || NONE)}
    ${td("Активность", (E(r.last) || NONE) +
        (r.tier ? `<div class="tier">${E(TIER_RU[r.tier] || r.tier)}</div>` : "") +
        spark(r.weeks) + metrics(r.metrics), "num")}
    ${td("Heroku", host)}
    ${                                                                       
                                                                            
                                                                              
                                                                                 
                            ""}
    ${td("Польз./30 дн", (() => {
      const tr = (D.traffic || {})[r.id];
      if (!tr) return NONE;
      const one = (tr.properties || [])[0];
      return `<span class="mono">${Number(tr.users_30d || 0).toLocaleString("ru")}</span>` +
        `<div class="anchor">${(tr.properties || []).length} prop.` +
        (one && one.report_url ? ` · <a href="${E(one.report_url)}" target="_blank" rel="noopener">GA4</a>` : "") +
        `</div>`;
    })(), "num")}
    ${td("Вики", note)}</tr>`;
}

                                                                            
                                                                                 
                                                                         
                                                      
function detail(id) {
  const r = D.rows.find(x => x.id === id);
  const box = document.getElementById("panel");
  if (!r) { box.hidden = true; box.innerHTML = ""; return; }
  const list = (items, empty, fn) => items && items.length
    ? `<ul class="dlist">${items.map(fn).join("")}</ul>`
    : `<p class="none">${empty}</p>`;
                                                                              
                                                                             
  const gone = D.store_degraded
    ? `<p class="none">${E(D.store_degraded)}</p>` : "";
  box.innerHTML = `
    <div class="dhead">
      <h2 id="panel-title">${E(r.name)}</h2>
      <button id="dclose" class="chip-btn" type="button" aria-label="Закрыть">закрыть</button>
    </div>
    <p class="dmeta">${E(r.anchor)} · ${E(r.lifecycle)} · ${E(TIER_RU[r.tier] || r.tier || "")}
      · последняя активность ${E(r.last) || "—"}</p>
    <h3>Из чего состоит</h3>
    ${                                                                          
                                                                                
                                                                             
                                                                    
      list(r.repos, "репозиториев нет", x => `<li class="mono">${E(x.nwo)}</li>`)}
    ${list(r.folders, "локальных папок нет", f => `<li class="mono">${E(f)}</li>`)}
    ${list(r.sites, "сайтов не заявлено", s => `<li class="mono">${E(s.host)}` +
        `<span class="anchor"> ${E((s.evidence || [])[0] || "")}</span></li>`)}
    <h3>Продукт</h3>
    ${(r.products || []).length
      ? `<ul class="dlist">${r.products.map(p => `<li>${E(p.name)} — ${E(p.role)}` +
          (p.kind === "suggested" ? ` <span class="anchor">предложено по общему домену, не решение</span>` : "") +
          `</li>`).join("")}</ul>`
      : `<p class="none">ни в один продукт не входит — сгруппировать: collectors/products.json</p>`}
    <h3>Что происходило</h3>
    ${gone || list(r.timeline, "коммитов в окне нет",
      c => `<li><span class="mono">${E(c.at)}</span> ${E(c.what)}
            <span class="none">${E(c.who)}</span></li>`)}
    <h3>Что заключила обсерватория</h3>
    ${gone || list(r.notes, "выводов нет",
      n => `<li><span class="mono">${E(n.at)}</span> ${E(n.text)}
            <span class="none">${E(n.state)}${n.conf != null ? ", уверенность " + n.conf : ""}</span></li>`)}
    ${                                                                       
                                                                                
                                                                            
                                                          ""}
    <h3>Аналитика</h3>
    ${(() => {
      const tr = (D.traffic || {})[r.id];
      if (!tr) return `<p class="none">ни одна property Google Analytics не привязана к этому проекту — ` +
        `назовите её в <span class="mono">plugins/config/ga4_properties.json</span>, если она есть</p>`;
      return `<ul class="dlist">` + (tr.properties || []).map(g =>
        `<li><b>${Number(g.users_30d || 0).toLocaleString("ru")}</b> польз./30 дн · ` +
        `${Number(g.sessions_30d || 0).toLocaleString("ru")} сессий — ${E(g.name || "")}` +
        `<span class="none"> · ${E(RULE_RU[g.rule] || g.rule || "")}` +
        `${(g.hosts || []).length ? " · " + E(g.hosts.slice(0, 2).join(", ")) : ""}</span> ` +
        `<a href="${E(g.report_url)}" target="_blank" rel="noopener">GA4</a>` +
        (g.admin_url ? ` · <a href="${E(g.admin_url)}" target="_blank" rel="noopener">админка</a>` : "") +
        `</li>`).join("") +
        (tr.search_console || []).map(s =>
          `<li>Search Console: <a href="${E(s.url)}" target="_blank" rel="noopener">${E(s.site)}</a></li>`).join("") +
        `</ul>`;
    })()}
    <h3>Ключи</h3>
    ${(() => {
                                                                               
                                                                               
                                                                             
                                                                                
      const ks = (D.keys || {})[r.id] || [];
      if (!ks.length) return `<p class="none">ни один кред в реестре не привязан к этому проекту — ` +
        `ничьи перечислены на <a href="creds.html">странице ключей</a></p>`;
      const KIND_RU = {"llm-api-key": "ключ LLM", "machine-secret": "машинный секрет",
                       "project-secret": "слот хранилища", "project-secret-file": "файл рядом с кодом",
                       "leaked-untracked": "известен по утечке", "env-file": "в .env проекта"};
                                                                                
                                                                               
                                                                             
                                                                             
      const GIT_RU = {tracked: chip("файл в git", "danger"), loose: chip("не в .gitignore", "warn"), ignored: "", "no-repo": ""};
      return `<ul class="dlist">` + ks.map(k =>
        `<li><a class="mono" href="${E(k.href || ("creds.html#c-" + k.slug))}">${E(k.name || "")}</a>` +
        `<span class="none"> · ${E(KIND_RU[k.kind] || k.kind || "")}${k.env ? " · " + E(k.env) : ""}` +
        `${k.where ? " · " + E(k.where) : ""}</span>` +
        (k.leaked ? ` ${chip("утечка не закрыта", "danger")}` : "") +
        (k.kind !== "env-file" && !k.signed ? ` ${chip("не подписан", "warn")}` : "") +
        (k.kind === "env-file" ? ` ${GIT_RU[k.git] || ""}` : "") +
        `</li>`).join("") + `</ul>`;
    })()}
    <h3>Что измерили плагины</h3>
    ${gone || (r.metrics && r.metrics.length
        ? `<ul class="dlist">${r.metrics.map(m => `<li><span class="mono">${E(m.l || m.n)}</span> ` +
            `${m.u === "bytes" ? bytes(m.v)
                : (+m.v).toLocaleString("ru") + (m.l ? "" : " " + E(m.u || ""))}` +
            `${m.p != null && +m.p !== +m.v
               ? ` <span class="delta ${+m.v > +m.p ? "up" : "down"}">${+m.v > +m.p ? "↑" : "↓"}` +
                 `${m.u === "bytes" ? bytes(Math.abs(m.v - m.p)) : Math.abs(m.v - m.p).toLocaleString("ru")}</span>`
               : ""}</li>`).join("")}</ul>`
        : '<p class="none">измерений нет</p>')}`;
  box.hidden = false;
  document.getElementById("dclose").onclick = () => { location.hash = ""; };
  box.scrollIntoView({block: "start"});
                                                                              
                                                                              
                                                                           
                                                                       
  const closeBtn = document.getElementById("dclose");
  if (closeBtn && closeBtn.focus) closeBtn.focus();
}

let PANEL_OPENER = null;
document.addEventListener("click", ev => {
  const a = ev.target && ev.target.closest && ev.target.closest('a.plink[href^="#project:"]');
  if (!a) return;
                                                                              
                                                                          
                                                                              
  if (PAGE && PAGE !== "projects") {
    ev.preventDefault();
    location.href = "projects.html" + a.getAttribute("href");
    return;
  }
  PANEL_OPENER = a;
});
document.addEventListener("hashchange", () => {
  if (!location.hash && PANEL_OPENER && PANEL_OPENER.focus) { PANEL_OPENER.focus(); PANEL_OPENER = null; }
});
function fromHash() {
                                                                              
                                                                     
  const raw = typeof location !== "undefined" ? (location.hash || "") : "";
  const id = decodeURIComponent(raw.replace(/^#/, ""));
                                                                              
                                                                    
  if (["projects", "heroku", "domains", "creds", "env"].includes(id)) {
    detail("");
    if (id !== tab) selectTab(id);
    return;
  }
  detail(id.startsWith("project:") ? id : "");
}
addEventListener("hashchange", fromHash);
addEventListener("keydown", e => { if (e.key === "Escape" && location.hash) location.hash = ""; });

                                                                              
                                                                              
                                                                              
                                                                             
                                                                               
                                                                               
                                                                          
                                                        
function narrowing() {
  const seg = document.getElementById("seg-" + tab);
  const chips = seg ? [...seg.querySelectorAll('.chip-btn[data-f][aria-pressed="true"]')]
    .map(b => b.textContent.trim() + (b.dataset.fromUrl ? " (из ссылки)" : "")) : [];
  const q = (document.getElementById("q") || {}).value || "";
  const s = (sel && sel.value && sel.selectedIndex >= 0) ? sel.options[sel.selectedIndex].text : "";
  return { chips, q: q.trim(), sel: s };
}
function narrowingText(n) {
  const bits = [];
  if (n.chips.length) bits.push("фильтры: " + n.chips.map(E).join(", "));
  if (n.sel) bits.push("выбрано: " + E(n.sel));
  if (n.q) bits.push(`поиск: «${E(n.q)}»`);
  return bits.join(" · ");
}
function filterLine(shown, total, unit) {
  const what = narrowingText(narrowing());
  return `<div class="filters" role="status">Показано <b>${shown}</b> из ${total}${unit ? " " + unit : ""}` +
    (what ? ` · ${what} · <button class="chip-btn" type="button" data-clear>сбросить</button>` : "") + `</div>`;
}
                                                                                
                                                                             
                                                                           
                                                                            
                            
function foldOpen(defaultOpen) {
  const n = narrowing();
  return !!(defaultOpen || n.q || n.chips.length || n.sel);
}
function grpHead(colspan, inner, open) {
  return `<tr><th colspan="${colspan}" scope="colgroup"><button class="grp-fold" type="button" aria-expanded="${open ? "true" : "false"}">${inner}</button></th></tr>`;
}
                                                                                
                                                                            
                                                                              
                                                                                
                                                                
let REVEALED = "";
function revealHash() {
  const raw = typeof location !== "undefined" ? (location.hash || "") : "";
  if (!raw || raw.startsWith("#f-") || raw.startsWith("#project:")) return;
                                                                              
                                                                            
  if (raw === REVEALED) return;
  const id = decodeURIComponent(raw.slice(1));
  let target = document.getElementById(id);
  if (!target && id.startsWith("e-") && typeof CSS !== "undefined" && CSS.escape) {
    target = document.querySelector('tr[data-file="' + CSS.escape(id.slice(2)) + '"]');
  }
  if (!target) return;
  const body = target.closest("tbody.grp.folded");
  if (body) {
    body.classList.remove("folded");
    const b = body.querySelector(".grp-fold");
    if (b) b.setAttribute("aria-expanded", "true");
  }
  if (target.scrollIntoView) target.scrollIntoView({block: "center"});
  REVEALED = raw;
}
addEventListener("hashchange", () => { REVEALED = ""; revealHash(); });
                                                                              
                                                                             
                                                                             
                                                                               
                                                                              
                                                                     
const SORT = (() => {
  try { return JSON.parse(sessionStorage.getItem("observatory.sort." + PAGE) || "{}") || {}; }
  catch (e) { return {}; }
})();
function sortTh(label, key) {
  const dir = SORT.key === key && SORT.dir ? SORT.dir : "none";
  return `<th aria-sort="${dir}" data-sort="${E(key)}"><button class="sort" type="button" title="сортировать">${label}</button></th>`;
}
function sortInPlace(list, getters) {
  const g = SORT.key && getters[SORT.key];
  if (!g) return list;
  const m = SORT.dir === "descending" ? -1 : 1;
  const copy = [...list].sort((a, b) => {
    const x = g(a), y = g(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * m;
  });
  list.splice(0, list.length, ...copy);
  return list;
}
document.addEventListener("click", ev => {
  const th = ev.target.closest && ev.target.closest("th[data-sort]");
  if (!th) return;
  const key = th.dataset.sort;
  const cur = SORT.key === key ? SORT.dir : "none";
  const next = cur === "none" ? "ascending" : cur === "ascending" ? "descending" : "none";
  SORT.key = next === "none" ? "" : key;
  SORT.dir = next === "none" ? "" : next;
  try { sessionStorage.setItem("observatory.sort." + PAGE, JSON.stringify(SORT)); } catch (e) {                      }
  render();
});
const lower = s => String(s || "").toLowerCase() || null;
const dateOr = s => (s ? String(s) : null);
const numOr = n => (typeof n === "number" ? n : (n == null || n === "" ? null : Number(n)));
function nothingFound(total, note) {
  const what = narrowingText(narrowing());
                                                                       
  if (!what) return `<p class="empty">${total ? "Ничего не найдено" : "Здесь пусто — в реестре нет ни одной строки этого вида"}${note ? ". " + note : ""}</p>`;
  return `<p class="empty">Ничего не найдено с этим сужением — ${what}. ` +
    `<button class="chip-btn" type="button" data-clear>сбросить</button>${note ? "<br>" + note : ""}</p>`;
}
document.addEventListener("click", ev => {
  const b = ev.target && ev.target.closest && ev.target.closest("[data-clear]");
  if (!b) return;
  const seg = document.getElementById("seg-" + tab);
  if (seg) seg.querySelectorAll('.chip-btn[data-f]').forEach(c => { c.setAttribute("aria-pressed", "false"); delete c.dataset.fromUrl; });
  if (active) active.clear();
  const q = document.getElementById("q"); if (q) q.value = "";
  if (sel) sel.value = "";
  render();
});

function render() {
  const out = drawTab();
  revealHash();                                                                  
  return out;
}
function drawTab() {
  if (PAGE && !TABLE_PAGES.includes(PAGE)) return;                                             
                                                                              
                                                                           
  const setN = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setN("n-projects", D.rows.length);
  setN("n-mcp", D.mcp ? (D.mcp.totals || {}).distinct_servers || 0 : "—");
  setN("n-domains", new Set([...DOMS.map(d => d.name), ...(D.zones || []).map(z => z.name)]).size);
  setN("n-heroku", APPS.length || "—");
  setN("n-creds", CREDS.length || "—");
  setN("n-env", (D.env && D.env.totals ? D.env.totals.secrets : 0) || "—");
  if (tab === "heroku") return renderHeroku();
  if (tab === "domains") return renderDomains();
  if (tab === "mcp") return renderMcp();
  if (tab === "traffic") return renderTraffic();
  if (tab === "creds") return renderCreds();
  if (tab === "env") return renderEnv();
  const q = document.getElementById("q").value.trim().toLowerCase();
  const owner = sel.value;
  const rows = D.rows.filter(r => keep(r, q, owner));
  const out = document.getElementById("out");
  if (!rows.length) { out.innerHTML = nothingFound(D.rows.length); return; }
  sortInPlace(rows, {name: r => lower(r.name), activity: r => dateOr(r.last)});
  const groups = new Map();
  rows.forEach(r => { if (!groups.has(r.owner)) groups.set(r.owner, []); groups.get(r.owner).push(r); });
  out.innerHTML = filterLine(rows.length, D.rows.length, "проектов") + `<div class="card"><table>
    <colgroup><col class="c-name"><col class="c-site"><col class="c-dir"><col class="c-repo">
      <col class="c-desc"><col class="c-stack"><col class="c-when"><col class="c-host">
      <col class="c-users"><col class="c-note"></colgroup>
    <thead><tr>
      ${sortTh("Проект", "name")}<th>Сайт</th><th>Папка</th><th>Репозиторий</th>
      <th>Описание</th><th>Стек</th>${sortTh("Активность", "activity")}<th>Heroku</th>
      <th>Польз./30 дн</th><th>Вики</th>
    </tr></thead>${[...groups].map(([owner, rs]) => `<tbody class="grp${foldOpen(false) ? "" : " folded"}">
      ${grpHead(10, `${E(owner)} <span class="n">${rs.length}</span>`, foldOpen(false))}
      ${rs.map(row).join("")}</tbody>`).join("")}</table></div>`;
}

                                                                             
                                                                               
                                                           
                                                                              
                                                                                 

                                                                              
                                                                                
                                                               
                                                                                
                                                                            
                                                                              
                                           
const TOKEN = (document.querySelector('meta[name="observatory-token"]') || {}).content;
                                                                                  
                                                                                 
                                                                                 
                                                                            
const LIVE = typeof location !== "undefined"
  && String(location.protocol || "").startsWith("http") && !!TOKEN;

                                                                             
                                                                              
                                                                             
                                                                                 
                                                                                 
                                              
function toast(text) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 4000);
}

                                                                             
                                                                             
                                                                              
                                                           
async function copyText(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {                                                                   }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.top = "-1000px";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
  document.body.removeChild(ta);
  return ok;
}

                                                                               
                                                                            
                                                                 
document.addEventListener("click", ev => {
  const btn = ev.target && ev.target.closest && ev.target.closest("[data-copy]");
  if (!btn) return;
                                                                                
                                                                             
  const what = String(btn.dataset.copy || "").replace(/\s+/g, " ").slice(0, 48);
  copyText(btn.dataset.copy).then(ok =>
    toast(ok ? `скопировано: ${what}${btn.dataset.copy.length > 48 ? "…" : ""}`
             : "буфер недоступен — скопируйте из подсказки"));
});
                                                                             
                                                                                
                                                                          
                                                                               
                                                           
document.addEventListener("click", ev => {
  const btn = ev.target && ev.target.closest && ev.target.closest("[data-act][data-cred]");
  if (!btn || btn.disabled) return;
  const c = CREDS.find(x => x.id === btn.dataset.cred);
  if (!c) { toast("строка не найдена — пересканируйте"); return; }
  credAction(btn, c);
});

async function call(action, body) {
  const r = await fetch("/api/" + action, {
    method: "POST",
                                                                                
                                                                          
                                                                            
                                                  
    headers: {"Content-Type": "application/json", "X-Observatory-Token": TOKEN,
              "X-Observatory-Caller": "page:" + (document.body.dataset.page || "index")},
    body: JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({error: "unreadable answer"}));
  if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
  return d;
}

                                                                            
                                                                             
                                      
function credAction(btn, c) {
  const act = btn.dataset.act;
  const ask = act === "revoke"
    ? `Отозвать ключ ${c.label}? Он перестанет работать немедленно и навсегда.`
    : act === "limit"
      ? `Новый месячный потолок для ${c.name || c.label}:`
      : act === "leak"
        ? `Где это значение засветилось? Одной строкой — транскрипт, лог, скрин:`
        : act === "rotate-key"
          ? `Ротировать ${c.name || c.label}? Дверь создаст новый ключ, доставит его туда же и удалит старый.`
          : act === "disable"
            ? `Отключить ${c.name || c.label}? Он перестанет тратить до «включить».`
            : null;
  if ((act === "revoke" || act === "rotate-key" || act === "disable") && !confirm(ask)) return;
                                                                      
                                                                         
  let body = ["disable", "enable", "rotate-key"].includes(act)
    ? {name: c.name || c.label} : {label: c.label};
  if (act === "limit") {
    const v = prompt(ask, String(c.limit || 100));
    if (v === null) return;
    body = {label: c.label, limit: Number(v), limit_reset: "monthly"};
  }
                                                                             
                                                                               
                                                                              
                                    
  if (act === "annotate") {
    const purpose = prompt(`Для чего нужен ${c.name || c.label}? Одной фразой:`, "");
    if (!purpose || !purpose.trim()) return;
    const evidence = prompt("Откуда это известно — конфиг, письмо, разговор, файл:", "");
    if (!evidence || !evidence.trim()) return;
    const owner = prompt("Кто за него отвечает (человек или команда, можно пусто):", "") || "";
    body = {id: c.id, purpose: purpose.trim(), evidence: evidence.trim(),
            owner: owner.trim()};
  }
                                                                             
                                                                             
                                                                              
                                                                             
                                                                       
  if (act === "mint") {
    const name = prompt("Имя ключа у провайдера (его увидит только леджер):", "");
    if (!name || !name.trim()) return;
    const limit = prompt(`Месячный потолок для ${name.trim()}, в долларах:`, "10");
    if (limit === null || !(Number(limit) > 0)) return;
    const dest = prompt("Куда доставить — observatory, claude-mem или "
                        + "vault:<проект>/<env>/<NAME>:", "vault:<проект>/prod/OPENROUTER_API_KEY");
    if (!dest || !dest.trim()) return;
    body = {name: name.trim(), limit: Number(limit), destination: dest.trim()};
  }
                                                                            
                                                                              
                                                                            
                       
  if (act === "leak") {
    const where = prompt(ask, "");
    if (!where || !where.trim()) return;
    body = {project: c.vault_project, env: c.env, name: c.name, where: where.trim()};
  }
  btn.disabled = true; btn.textContent = "…";
  call(act, body)
    .then(d => { toast(act === "annotate" ? "подписан — пересканируйте"
                       : act === "revoke" ? "отозван"
                       : act === "leak" ? "отмечен как утёкший — ротируйте у провайдера"
                       : act === "mint" ? `выпущен и доставлен в ${d.destination}`
                       : `потолок ${d.limit}/мес`);
                 btn.textContent = "готово · пересканируйте"; })
    .catch(e => { btn.disabled = false; btn.textContent = "не вышло";
                  toast(String(e.message).slice(0, 120)); });
}

                                                                               
                                                                               
                                                                              
                           
function subjectHref(subject) {
  const m = /^([a-z]+):(.+)$/.exec(String(subject || ""));
  if (!m) return null;
  const [, kind, rest] = m;
  if (kind === "domain") return ["domains.html#d-" + rest, rest];
  if (kind === "app") return ["heroku.html#a-" + rest, rest];
  if (kind === "credential") return ["creds.html#c-" + rest.replace(/[^A-Za-z0-9_.-]+/g, "-"), rest];
  if (kind === "project") return ["projects.html#project:" + rest, rest];

                                                                                
                                                                           
  if (kind === "env") return ["env.html#e-" + anchorSlug(rest), rest];
  if (kind === "mcp") return ["mcp.html#m-" + anchorSlug(rest), rest];
  return null;
}
                                                                               
                                                                               
                                                                          
function anchorSlug(s) { return String(s).replace(/[^A-Za-z0-9_.:/-]+/g, "-"); }

                                                                              
                                                                              
                                                                                
                                                               
const doorOf = c => {
  const m = /^tools\/(openrouter|cloudflare)\.py$/.exec(c.read_by || "");
  return m ? m[1] : null;
};

                                                                             
                                                                                   
                                                                               
                                        

                                                                             
                                                                            
                                                                        
                                                                               
                                                                            
                       
const ISSUE_CMD = {
  openrouter: toolCommand("openrouter.py", ["issue", "--name", "KEY_NAME", "--limit", "AMOUNT", "--to", "vault:PROJECT/prod/NAME"]),
  cloudflare: toolCommand("cloudflare.py", ["issue", "--account", "ACCOUNT_ID", "--preset", "analytics"]),
};
function credVerbs(c) {
  const door = doorOf(c);
  const n = c.name || c.label || "";
  const sign = ["подписать…", toolCommand("sign_credential.py", ["set", c.id, "--purpose", "…", "--evidence", "…"]), "annotate"];
  if (c.kind === "llm-api-key")
    return [
      sign,
      ["потолок…", toolCommand("openrouter.py", ["limit", n, "--set", "AMOUNT"]), "limit"],
      [c.disabled ? "включить" : "отключить", toolCommand("openrouter.py", [c.disabled ? "enable" : "disable", n]), c.disabled ? "enable" : "disable"],
      ["ротировать", toolCommand("openrouter.py", ["rotate", n, ...(c.leaked ? ["--leaked"] : [])]), "rotate-key"],
      ["отозвать", toolCommand("openrouter.py", ["revoke", n]), "revoke"],
    ];
  if (door)
    return [sign,
      ["пинг", toolCommand(door + ".py", ["ping"]), null],
      ["что выпущено", toolCommand(door + ".py", ["list"]), null],
      ["выпустить…", ISSUE_CMD[door], door === "openrouter" ? "mint" : null],
    ];
  if (c.vault_project) {
    const slot = [c.vault_project, c.env, c.name];
    const settle = ["закрыть утечку…", toolCommand("vault.py", ["settle", ...slot, "--how", "…"]), null];
    const rotate = ["ротировать из файла…", privateInput(toolCommand("vault.py", ["rotate", ...slot])), null];
    if (c.known_only_from_the_leak)
      return [sign, settle, ["завести слот из файла…", privateInput(toolCommand("vault.py", ["put", ...slot])), null]];
    return c.leaked ? [sign, settle, rotate]
      : [sign, ["отметить утечку…", toolCommand("vault.py", ["leak", ...slot, "--where", "…"]), "leak"], rotate];
  }
  if (c.kind === "project-secret-file") {
    const owner = (c.used_by || [])[0];
    const vaultProject = owner ? (PROJ_NAME.get(owner) || String(owner).split(":")[1]) : c.in_project;
    const slotName = String(c.name).replace(/^\.+/, "").replace(/\.[A-Za-z0-9]+$/, "")
      .replace(/[^A-Za-z0-9]+/g, "_").toUpperCase();
    const file = projectFile(c.in_project + "/" + c.path);
    return [sign,
      ["в хранилище", toolCommand("vault.py", ["put", vaultProject, "local", slotName]) + " < " + shellArg(file), null],
      ["что это", "ls -l -- " + shellArg(file), null]];
  }
  return [sign, ["что это", "ls -l -- " + shellArg(secretFile(n)), null]];
}

const CRED_SECTIONS = [
  ["door", "Двери", "админские стэши: из них выпускается всё остальное; значение не выдаётся никому"],
  ["issued", "Выпущенные ключи", "леджер двери: имя у провайдера, потолок, расход, дата выпуска"],
  ["slot", "Секреты проектов", "слоты хранилища — значение живёт в vault и идёт только через stdin"],
  ["projfile", "Секреты рядом с кодом",
   "файлы в собственной папке secrets/ проекта; " +
   "«в хранилище» переносит значение в vault через stdin, чтобы им можно было пользоваться из любого проекта"],
  ["machine", "Секреты машины", "файлы, которыми аутентифицируются сборщики и плагины этой машины"],
];
const credSection = c => doorOf(c) ? "door"
  : c.kind === "llm-api-key" ? "issued"
  : c.kind === "project-secret-file" ? "projfile"
  : c.vault_project ? "slot" : "machine";

const credCmd = c => (credVerbs(c)[0] || ["", ""])[1];

const hayCred = c => [c.id, c.name || "", c.provider || "", c.kind, c.serves || "",
  (c.used_by || []).join(" "), c.label || ""].join(" ").toLowerCase();

function keepCred(c, q, section) {
  if (q && !hayCred(c).includes(q)) return false;
  if (section && (CRED_SECTIONS.find(s => s[1] === section) || [])[0] !== credSection(c))
    return false;
  if (active.has("c-leaked") && !c.leaked) return false;
  if (active.has("c-unclaimed") && (c.used_by || []).length) return false;
                                                                                 
                                                 
  if (active.has("c-shared") && (c.used_by || []).length < 2) return false;
  if (active.has("c-norotate") && c.rotated_on) return false;
  if (active.has("c-disabled") && !c.disabled) return false;
  if (active.has("c-untracked") && c.kind !== "leaked-untracked") return false;
  return true;
}

function renderCreds() {
  const out = document.getElementById("out");
  if (!D.creds) {
    out.innerHTML = `<p class="empty">Учётные данные не сканировались — ` +
      `<span class="mono">${E(cliCommand("openrouter"))}</span></p>`;
    return;
  }
  const q = document.getElementById("q").value.trim().toLowerCase();
  const rows = CREDS.filter(c => keepCred(c, q, sel.value));
  if (!rows.length) { out.innerHTML = nothingFound(CREDS.length); return; }
  const cell = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  const cap = c => c.limit == null ? NONE
    : `<span class="mono">${c.limit}</span>` +
      `<div class="tier">${E(c.limit_reset || "без сброса")}` +
      (c.limit_reset ? "" : " " + chip("пожизненный", "warn")) +
      `</div><div class="anchor">потрачено ${(+c.usage || 0).toFixed(3)}</div>`;
  const who = c => (c.used_by || []).length
    ? (c.used_by || []).map(p =>
        `<a class="plink" href="#${E(p)}">${E(p.split(":")[1])}</a>`).join(", ") +
      ((c.used_by || []).length > 1
        ? `<div class="tier">${chip("общий · ротация затронет всех", "warn")}</div>` : "")
                                                                             
                                                                               
                                                                            
    : c.read_by
      ? `<span class="mono">${E(c.read_by)}</span><div class="anchor">читает его</div>`
      : `<span class="unlinked" title="${E(c.unclaimed_reason || "")}">ничей</span>`;
  const state = c => {
    const bits = [];
    if (c.leaked) bits.push(chip("утёк, не ротирован", "danger"));
    if (c.disabled) bits.push(chip("отключён", "warn"));
    if (c.kind === "leaked-untracked") bits.push(chip("в хранилище нет", "warn"));
                                                                             
    if (c.git === "tracked") bits.push(chip("в git", "danger"));
    if (c.git === "loose") bits.push(chip("не игнорируется", "warn"));
    if (c.kind === "project-secret-file" && String(c.mode).slice(-2) !== "00")
      bits.push(chip(`права ${E(c.mode)}`, "warn"));
    if (!bits.length) bits.push(chip("в порядке", "ok"));
                                                                                
                                                                            
                                             
    const w = String(c.leaked_where || "");
    return bits.join(" ") + (c.leaked && w
      ? `<div class="anchor" title="${E(w)}">${E(w.slice(0, 110))}${w.length > 110 ? "…" : ""}</div>`
      : "");
  };
  sortInPlace(rows, {name: c => lower(c.name)});
  const groups = new Map();
  rows.forEach(c => { const k = credSection(c);
    if (!groups.has(k)) groups.set(k, []); groups.get(k).push(c); });
  const row = c => `<tr id="c-${E(String(c.id).replace(/^credential:/, "").replace(/[^A-Za-z0-9_.-]+/g, "-"))}">
    <td data-label="Учётные данные"><div class="name">${E(c.name || c.id)}</div>
      ${                                                                   
                                                                                 
                                                                             
                                                                                 
                                                                            ""}
      <div class="anchor mono" title="${E(c.id)}">${E(c.label
        || [c.vault_project, c.env].filter(Boolean).join("/") || c.id)}</div>
      ${c.provider ? `<div class="anchor">${E(c.provider)}${c.serves ? " · " + E(c.serves) : ""}</div>` : ""}
      ${c.identity ? `<div class="anchor mono">${E(c.identity)}</div>` : ""}
      ${                                                                        
                                                                         
                                                                     ""}
      ${c.signature && c.signature.purpose
        ? `<div class="tier">${E(c.signature.purpose)}</div>` +
          `<div class="anchor">${E(c.signature.owner || "владельца нет")}` +
          `${c.signature.rotation_days ? ` · ротация раз в ${c.signature.rotation_days} дн.` : ""}` +
          ` · подписан ${E(c.signature.signed_on || "")}</div>`
        : `<div class="anchor"><span class="unlinked">не подписан — для чего он, никто не сказал</span></div>`}</td>
    ${cell("Состояние", state(c))}
    ${cell("Потолок", cap(c), "num")}
    ${cell("Проекты", who(c))}
    ${cell("Ротация", c.rotated_on
      ? E(c.rotated_on) + `<div class="anchor">×${c.rotations || 1}</div>`
                                                                        
                                                                                
                                                 
      : c.created_on
        ? `<span class="mono">выпущен ${E(c.created_on)}</span>`
        : c.installed_on
                                                                              
                                                                        
          ? `<span class="mono">лежит с ${E(c.installed_on)}</span>`
          : `<span class="unlinked">никогда</span>`)}
    ${cell("Действие", `<div class="verbs">` + credVerbs(c).map(([label, cmd, act]) =>
      LIVE && act
        ? `<button class="chip-btn" type="button" data-cred="${E(c.id)}" data-act="${E(act)}"
            >${E(label)}</button>`
        : `<button class="chip-btn" type="button" data-copy="${E(cmd)}"
            title="${E(cmd)}">${E(label)}</button>`).join(" ") + `</div>`)}</tr>`;
  const leaked = rows.filter(c => c.leaked).length;
  const howto = LIVE
    ? `кнопки действуют: страницу отдаёт <span class="mono">tools/keyserver.py</span>`
    : `кнопки отдают команду в буфер — страница открыта из файла и ничего выполнить не может;` +
      ` перед импортом замените /absolute/path/to/private-input путём к приватному файлу со значением;` +
      ` запустите <span class="mono">${E(toolCommand("keyserver.py"))}</span>, чтобы они действовали`;
                                                             
                                                                                
                                                                             
                                                                  
  out.innerHTML = filterLine(rows.length, CREDS.length, "записей") + `<div class="card"><table>
    <colgroup><col style="width:23%"><col style="width:24%"><col style="width:10%">
      <col style="width:16%"><col style="width:11%"><col style="width:16%"></colgroup>
    <thead><tr>${sortTh("Учётные данные", "name")}<th>Состояние</th><th>Потолок</th>
      <th>Проекты</th><th>Ротация</th><th>Действие</th></tr></thead>
    ${CRED_SECTIONS.map(([key, title, says]) => {
      const cs = groups.get(key) || [];
                                                                             
                                                                     
                                                                              
                                                  
      return `<tbody class="grp">
      ${grpHead(6, `${E(title)} <span class="n">${cs.length}</span><div class="anchor">${E(says)}</div>`, true)}
      ${cs.length ? cs.map(row).join("")
        : `<tr><td colspan="6" class="e">${key === "issued"
            ? "ни одного ключа ещё не выпущено — «выпустить…» на строке двери"
            : "здесь пусто"}</td></tr>`}</tbody>`;
    }).join("")}</table></div>
    <p class="dmeta">Показано ${rows.length} из ${CREDS.length} ·
      ${leaked} утёкших и не ротированных · измерено ${E(D.creds.scanned_on || "—")} ·
      значений здесь нет и быть не может: метка — это то, как ключ называет сам провайдер<br>${howto};
      запись и ротация секрета проекта отсюда <b>отказаны намеренно</b> — значение идёт только через stdin</p>
    ${movementsSection()}`;
}

                                                                           
                                                                       
                                                                           
                                                                             
                                                                             
                                                                              
                                                                           
                                                                              
                                                                                
function movementsSection() {
  const mv = (D.creds && D.creds.movements) || [];
  const un = (D.creds && D.creds.unrecorded) || [];
  const EVENT_RU = {put: "положен", rotate: "ротирован", moved: "перемещён (рукой)", settled: "утечка закрыта",
                    issue: "выпущен", disable: "отключён", enable: "включён", revoke: "отозван",
                    leak: "утечка записана"};
  const unrows = un.map(u => {
    const proj = u.project || (u.app || "").replace(/-/g, "_");
    const cmds = (u.vars || []).map(v =>
      toolCommand("vault.py", ["moved", u.project || "PROJECT", "prod", v, "--at", "heroku", "--how", `set on Heroku app ${u.app}, release v${u.version}, ${String(u.at || "").slice(0, 16)}Z by ${u.by || "?"}`]));
    return `<li><b>${E(u.app)}</b> v${E(String(u.version || ""))} · ${E(String(u.at || "").slice(0, 16))}Z · ${E(u.by || "?")}:
      <span class="mono">${(u.vars || []).map(E).join(", ")}</span>
      ${cmds.map((c, i) => `<button class="chip-btn" type="button" data-copy="${E(c)}" title="скопировать запись движения">записать ${E(u.vars[i])}</button>`).join(" ")}</li>`;
  }).join("");
  const rows = mv.map(m => `<tr>
      <td class="num"><span class="mono">${E(String(m.at || "").slice(0, 16).replace("T", " "))}</span></td>
      <td>${E(EVENT_RU[m.event] || m.event || "")}</td>
      <td><span class="mono">${E(m.secret || m.of || "")}</span></td>
      <td>${E(m.by || "")}${m.tool ? ` <span class="none">· ${E(m.tool)}</span>` : ""}</td>
      <td>${E(m.at_provider ? "у провайдера: " + m.at_provider : (m.to ? "→ " + m.to : ""))}${m.how ? `<div class="anchor">${E(String(m.how).slice(0, 160))}</div>` : ""}</td>
    </tr>`).join("");
  return `<h2 id="movements">Движения ключей</h2>
    ${un.length ? `<div class="card"><p class="dmeta">${un.length} изменение(й) на Heroku за неделю, которых нет в журнале — правило оператора: записывает тот, кто двигал, в тот же ход</p>
      <ul class="dlist">${unrows}</ul></div>` : `<p class="none">каждое движение за неделю записано — на Heroku нет изменений без строки в журнале</p>`}
    ${rows ? `<div class="card"><table><colgroup><col style="width:12%"><col style="width:12%"><col style="width:30%"><col style="width:14%"><col></colgroup>
      <thead><tr><th>Когда</th><th>Что</th><th>Ключ</th><th>Кто</th><th>Куда / как</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
      <p class="dmeta">Последние ${mv.length} движений · полный журнал: <span class="mono">${E(toolCommand("vault.py", ["movements"]))}</span></p>`
      : `<p class="none">журнал движений пуст</p>`}`;
}

                                                                             
                                                                               
                                                                                
                                                              

                                                                             
                                                                             
                                                                         
                                                                               
                                                                               
                                                                         

const CLS_RU = {secret: "секрет", config: "конфиг",
                placeholder: "заглушка", empty: "пусто"};
const CLS_KIND = {secret: "warn", config: "", placeholder: "", empty: ""};

const hayEnv = e => [e.name, e.path, e.project, e.cls,
  e.shared.join(" "), e.available.join(" ")].join(" ").toLowerCase();

                                                                           
                                                                                
                                                                               
                                                                                
                                                 
function keepEnv(e, q, project) {
  if (q && !hayEnv(e).includes(q)) return false;
  if (project && e.project !== project) return false;
  if (!active.has("e-tpl") && e.kind === "template") return false;
  if (!active.has("e-all") && e.cls !== "secret" && !e.available.length) return false;
  if (active.has("e-shared") && !e.shared.length) return false;
  if (active.has("e-reuse") && !e.available.length) return false;
  if (active.has("e-git") && e.git !== "tracked") return false;
  if (active.has("e-open") && String(e.mode).slice(-2) === "00") return false;
  return true;
}

const envKey = e => e.path + " " + e.name;

                                                                         
                                             
let ENV_ON_SCREEN = new Map();

                                                                         
                                                                                
                                                                               
                   
function envReveal(btn, e, show) {
  const cell = btn.closest("td");
  btn.disabled = true;
  btn.textContent = "…";
  call("reveal", {path: e.path, name: e.name})
    .then(d => {
      if (!show) {
        return copyText(d.value).then(ok => {
          cell.innerHTML = envActions(e);
          toast(ok ? e.name + " скопирован" : "буфер недоступен");
        });
      }
      cell.innerHTML =
        '<code class="val" tabindex="0">' + E(d.value) + '</code>' +
        '<div class="anchor"><button class="chip-btn" type="button" data-envhide="1"' +
        '>скрыть</button> <button class="chip-btn" type="button" data-copy="' +
        E(d.value) + '">копировать</button> · скроется через 30с</div>';
      const t = setTimeout(() => {
        if (cell.isConnected) cell.innerHTML = envActions(e);
      }, 30000);
      cell.dataset.timer = String(t);
    })
    .catch(err => {
      cell.innerHTML = envActions(e);
      toast(String(err.message).slice(0, 140));
    });
}

function envActions(e) {
  if (LIVE) {
    return '<button class="chip-btn" type="button" data-env="' + E(envKey(e)) +
      '" data-show="1">показать</button> <button class="chip-btn" type="button" data-env="' +
      E(envKey(e)) + '">копировать</button>';
  }
                                                                            
                                                                               
                                                                             
  const project = e.project || (String(e.path || "").includes("/") ? String(e.path).split("/")[0] : "");
  if (!project || !e.name) return '<span class="unlinked">проект или имя не определены</span>';
  return '<button class="chip-btn" type="button" data-copy="' +
    E(toolCommand("use_secret.py", ["where", project, e.name])) +
    '">скопировать команду</button>';
}

document.addEventListener("click", ev => {
  const t = ev.target;
  if (!t || !t.closest) return;
  const hide = t.closest("[data-envhide]");
  if (hide) {
    const cell = hide.closest("td");
    clearTimeout(Number(cell.dataset.timer || 0));
    const e = ENV_ON_SCREEN.get(cell.dataset.key);
    if (e) cell.innerHTML = envActions(e);
    return;
  }
  const fold = t.closest(".grp-fold");
  if (fold) {
    const body = fold.closest("tbody");
    const open = fold.getAttribute("aria-expanded") === "true";
    fold.setAttribute("aria-expanded", String(!open));
    body.classList.toggle("folded", open);
    return;
  }
  const btn = t.closest("[data-env]");
  if (!btn) return;
  const e = ENV_ON_SCREEN.get(btn.dataset.env);
  if (e) envReveal(btn, e, btn.dataset.show === "1");
});

function renderEnv() {
  const out = document.getElementById("out");
  if (!D.env) {
    out.innerHTML = '<p class="empty">Файлы окружения не сканировались — ' +
      '<span class="mono">' + E(cliCommand('env')) + '</span></p>';
    return;
  }
  const q = document.getElementById("q").value.trim().toLowerCase();
  const rows = ENVV.filter(e => keepEnv(e, q, sel.value));
  ENV_ON_SCREEN = new Map(rows.map(e => [envKey(e), e]));
  if (!rows.length) {
    out.innerHTML = nothingFound(ENVV.length, 'По умолчанию показаны только секреты ' +
      'живых файлов — «+ конфиг и пустые» и «+ шаблоны» расширяют выборку.');
    return;
  }
  const state = e => {
    const bits = [chip(CLS_RU[e.cls] || e.cls, CLS_KIND[e.cls] || "")];
    if (e.kind === "template") bits.push(chip("шаблон", ""));
    if (e.git === "tracked") bits.push(chip("в git", e.cls === "secret" ? "danger" : "warn"));
    if (e.git === "loose") bits.push(chip("не игнорируется", "warn"));
    if (String(e.mode).slice(-2) !== "00") bits.push(chip(e.mode, "warn"));
    return bits.join(" ");
  };
  const links = e => {
    if (e.shared.length) {
      return e.shared.map(p => '<a class="plink" href="#project:' + E(p) + '">' + E(p) + '</a>').join(", ") +
        '<div class="tier">' + chip("то же значение · ротация затронет всех", "warn") + '</div>';
    }
    if (e.available.length) {
      return '<span class="anchor">значение есть в:</span> ' +
        e.available.map(p => '<a class="plink" href="#project:' + E(p) + '">' + E(p) + '</a>').join(", ");
    }
    return e.copies > 1
      ? '<span class="anchor">' + e.copies + ' копии в этом же проекте</span>'
      : NONE;
  };
  sortInPlace(rows, {name: e => lower(e.name), modified: e => dateOr(e.modified_on)});
  const groups = new Map();
  rows.forEach(e => {
    if (!groups.has(e.project)) groups.set(e.project, []);
    groups.get(e.project).push(e);
  });
  const row = e => '<tr id="e-' + E(anchorSlug(e.path + ":" + e.name)) + '" data-file="' + E(anchorSlug(e.path)) + '">' +
    '<td data-label="Переменная"><div class="name mono">' + E(e.name) + '</div>' +
    '<div class="anchor mono" title="' + E(e.path) + '">' + E(e.path) + '</div></td>' +
    '<td data-label="Что это">' + state(e) + '</td>' +
    '<td data-label="Связи">' + links(e) + '</td>' +
    '<td data-label="Изменён" class="num"><span class="mono">' + E(e.modified_on) + '</span></td>' +
                                                                             
                                                                               
                                                                         
                  
    '<td data-label="Прод">' + (() => {
      const m = REMOTE_BY_FOLDER.get(e.project);
      if (!D.remote) return '<span class="anchor">не сканировалось</span>';
      if (!m) return NONE;
      const v = m.get(e.name);
      if (!v) return '<span class="unlinked">нет у прода</span>';
      const [word, kind] = VERDICT_RU[v.verdict] || [v.verdict, ""];
      return chip(word, kind) + '<div class="anchor">' + E(v.app) + '</div>';
    })() + '</td>' +
    '<td data-label="Значение" data-key="' + E(envKey(e)) + '">' + envActions(e) + '</td></tr>';
  const t = D.env.totals || {};
  const howto = LIVE
    ? '«показать» и «копировать» действуют: страницу отдаёт ' +
      '<span class="mono">tools/keyserver.py</span>, и каждое раскрытие пишется в ' +
      '<span class="mono">store/logs/keyserver.jsonl</span> до того, как файл будет прочитан'
    : 'страница открыта из файла и прочитать значение не может — кнопка отдаёт ' +
      'команду в буфер; запустите <span class="mono">' + E(toolCommand('keyserver.py')) + '</span>, ' +
      'чтобы раскрывать и копировать прямо отсюда';
  out.innerHTML = filterLine(rows.length, ENVV.length, "переменных") + '<div class="card"><table>' +
    '<colgroup><col style="width:26%"><col style="width:17%"><col style="width:20%">' +
    '<col style="width:9%"><col style="width:14%"><col style="width:14%"></colgroup>' +
    '<thead><tr>' + sortTh("Переменная", "name") + '<th>Что это</th><th>Связи</th>' + sortTh("Изменён", "modified") +
    '<th>Прод</th><th>Значение</th></tr></thead>' +
    [...groups].map(([p, es]) => {
                                                                             
                                                                               
                                                                                
                                                                            
                                                                                
                              

                                                                            
                                                                           
                                                                               
                                                                                
                                                    
                                                                                 
                                                                               
                                                                              
                                                
      const alarming = es.filter(e => e.cls === "secret" && e.git === "tracked");
      const open = !!q || !!sel.value || alarming.length > 0;
      const secrets = es.filter(e => e.cls === "secret").length;
      return '<tbody class="grp' + (open ? '' : ' folded') + '" data-envgroup="' + E(p || "-") + '">' +
      '<tr><th colspan="6" scope="colgroup"><button class="grp-fold" type="button"' +
      ' aria-expanded="' + (open ? 'true' : 'false') + '">' + E(p || "вне проекта") +
      ' <span class="n">' + es.length + ' переменных' +
      (secrets ? ' · ' + secrets + ' секретных' : '') + '</span>' +
      (alarming.length ? ' ' + chip(alarming.length + " секрет(ов) в git", "danger") : '') +
      '</button></th></tr>' +
      es.map(row).join("") + '</tbody>';
    }).join("") + '</table></div>' +
    '<p class="dmeta">Показано ' + rows.length + ' из ' + ENVV.length + ' переменных · ' +
    (t.env_files || 0) + ' живых файлов и ' + (t.templates || 0) + ' шаблонов в ' +
    (t.projects || 0) + ' проектах · ' + (t.secrets || 0) + ' читаются как секрет · ' +
    (t.shared_across_projects || 0) + ' значений делят несколько проектов · измерено ' +
    E(D.env.scanned_on || "—") + '<br>' + howto +
    '. Значений нет ни в этой странице, ни в реестре: «общее значение» установлено ' +
    'солёным отпечатком, а соль лежит вне git и не покидает машину.</p>';
}

                                                                             
                                                                             
                                                                            
               
const DAY = 864e5;
const daysUntil = iso => iso ? Math.round((Date.parse(iso) - Date.now()) / DAY) : null;
const hayDom = d => [d.name, d.registrar || "", d.status || "",
  (d.projects || []).join(" ")].join(" ").toLowerCase();

function keepDom(d, q, registrar) {
  if (q && !hayDom(d).includes(q)) return false;
  if (registrar && d.registrar !== registrar) return false;
  if (active.has("d-noproject") && (d.projects || []).length) return false;
                                                                              
                                                                              
                                         
  if (active.has("d-dark") && !(d.live && d.live.resolves === false)) return false;
  if (active.has("d-unmeasured") && d.live) return false;
  if (active.has("d-http") && !(d.live && d.live.resolves && (d.live.http >= 400 || d.live.http === 0))) return false;
  if (active.has("d-expiring")) { const n = daysUntil(d.expires_on); if (n === null || n > 90) return false; }
  if (active.has("d-norenew") && d.auto_renew !== false) return false;
  return true;
}

                                                                             
                                                                                
                                                                   
function renderMcp() {
  const out = document.getElementById("out");
  if (!D.mcp) {
    out.innerHTML = `<p class="empty">MCP не сканировался — <span class="mono">${E(cliCommand("scan-mcp"))}</span></p>`;
    return;
  }
  const q = document.getElementById("q").value.trim().toLowerCase();
  const ALL = D.mcp.servers || [];
  const rows = ALL.filter(s => (!q || [s.name, s.agent, s.scope, s.target || "", s.command || ""].join(" ").toLowerCase().includes(q))
    && (!sel.value || s.agent === sel.value)
    && (!active.has("m-url") || s.key_in_url)
    && (!active.has("m-down") || s.liveness === "failed")
    && (!active.has("m-auth") || s.liveness === "needs-auth")
    && (!active.has("m-alone") || ALL.filter(x => x.name === s.name).length === 1));
  if (!rows.length) { out.innerHTML = nothingFound(ALL.length); return; }
  const live = s => ({ connected: chip("отвечает", "ok"), failed: chip("не отвечает", "danger"),
    "needs-auth": chip("нужен вход", "warn"), "not-listed": chip("не в списке", "warn"),
    "not-probed": chip("не проверялся") })[s.liveness] || chip(s.liveness || "—");
  const keyPlace = s => s.key_in_url ? chip("в URL", "danger") : s.key_in_header ? "в заголовке" : s.key_in_env ? "в env" : NONE;
  sortInPlace(rows, {name: s => lower(s.name)});
  const groups = new Map();
  rows.forEach(s => { const k = s.agent; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(s); });
  const row = s => `<tr id="m-${E(anchorSlug(s.agent + "/" + s.name))}">
    <td data-label="Сервер"><div class="name mono">${E(s.name)}</div><div class="anchor">${E(s.scope)}</div></td>
    <td data-label="Транспорт">${E(s.transport || "—")}${s.command ? `<div class="anchor mono">${E(s.command)}${s.command_present === false ? " · нет на диске" : ""}</div>` : ""}</td>
    <td data-label="Цель"><span class="mono">${E(s.target || "")}</span></td>
    <td data-label="Ключ">${keyPlace(s)}</td>
    <td data-label="Связь">${live(s)}${s.liveness_detail ? `<div class="anchor">${E(s.liveness_detail)}</div>` : ""}</td></tr>`;
  const t = D.mcp.totals || {};
  out.innerHTML = filterLine(rows.length, ALL.length, "объявлений") + `<div class="card"><table>
    <colgroup><col style="width:22%"><col style="width:16%"><col style="width:26%"><col style="width:14%"><col style="width:22%"></colgroup>
    <thead><tr>${sortTh("Сервер", "name")}<th>Транспорт</th><th>Цель</th><th>Ключ</th><th>Связь</th></tr></thead>
    ${[...groups].map(([agent, ss]) => `<tbody class="grp">
      ${grpHead(5, `${E(agent)} <span class="n">${ss.length}</span>`, true)}
      ${ss.map(row).join("")}</tbody>`).join("")}</table></div>
    <p class="dmeta">${t.declarations || 0} объявлений · ${t.distinct_servers || 0} серверов ·
      ${t.in_one_agent_only || 0} только в одном агенте · ${t.key_in_url || 0} с ключом в URL ·
      собственный сервер обсерватории ${D.mcp.own_declared ? "объявлен" : "<b>не объявлен</b>"} ·
      скан ${E(D.mcp.scanned_on || "—")}</p>`;
}

                                                                             
                                                                               
                                                                            
                                                                           
                                                                               
                                                                             
                                     
const TRAFFIC_STANDING = { linked: ["привязан", "ok"], outside: ["вне эстейта", ""],
                           unclaimed: ["ничей", "warn"] };
const RULE_RU = { declared: "объявлено оператором", "declared-host": "хост из файла",
                  "stream-host": "по хосту потока", "app-id": "по id приложения",
                  name: "по имени property" };
function renderTraffic() {
  const out = document.getElementById("out");
  if (!D.google) {
    out.innerHTML = `<p class="empty">Аналитика не сканировалась — ` +
      `<span class="mono">${E(cliCommand("google"))}</span></p>`;
    return;
  }
  const ALL = D.google.properties || [];
  const q = document.getElementById("q").value.trim().toLowerCase();
  const rows = ALL.filter(p => (!q || [p.name, p.account_name, (p.hosts || []).join(" "),
      (p.app_ids || []).join(" "), p.project || ""].join(" ").toLowerCase().includes(q))
    && (!sel.value || p.account_name === sel.value)
    && (!active.has("t-unclaimed") || p.standing === "unclaimed")
    && (!active.has("t-linked") || p.standing === "linked")
    && (!active.has("t-quiet") || !(p.users_30d)) 
    && (!active.has("t-app") || ((p.app_ids || []).length && !(p.hosts || []).length)));
  if (!rows.length) { out.innerHTML = nothingFound(ALL.length); return; }
  const cell = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  const num = n => n == null ? NONE : `<span class="mono">${Number(n).toLocaleString("ru")}</span>`;
  sortInPlace(rows, {name: p => lower(p.name), users: p => numOr(p.users_30d)});
  const groups = new Map();
  rows.forEach(p => { const k = p.account_name || "—";
    if (!groups.has(k)) groups.set(k, []); groups.get(k).push(p); });
  const row = p => `<tr id="g-${E(String(p.id).replace(/[^A-Za-z0-9_.:-]+/g, "-"))}">
    <td data-label="Property"><div class="name">${E(p.name || p.property)}</div>
      <div class="anchor mono">${E(p.property || "")}</div>
      ${(p.hosts || []).length ? `<div class="anchor">${(p.hosts || []).slice(0, 3).map(E).join(" · ")}${p.hosts.length > 3 ? ` +${p.hosts.length - 3}` : ""}</div>` : ""}
      ${(p.app_ids || []).length ? `<div class="anchor mono">${(p.app_ids || []).slice(0, 2).map(E).join(" · ")}${p.app_ids.length > 2 ? ` +${p.app_ids.length - 2}` : ""}</div>` : ""}</td>
    ${cell("Польз./30 дн", num(p.users_30d), "num")}
    ${cell("Сессий/30 дн", num(p.sessions_30d), "num")}
    ${cell("Просмотров", num(p.views_30d), "num")}
    ${cell("Проект", p.project
      ? `<a class="plink" href="#${E(p.project)}">${E(String(p.project).split(":")[1] || p.project)}</a>` +
        `<div class="anchor" title="${E(p.link_evidence || "")}">${E(RULE_RU[p.link_rule] || p.link_rule || "")}</div>`
      : `<span class="unlinked" title="${E(p.unlinked_reason || p.boundary_why || "")}">${
          p.standing === "outside" ? "вне эстейта" : "нет проекта"}</span>`)}
    ${cell("Связь", (() => { const [w, k] = TRAFFIC_STANDING[p.standing] || [p.standing, ""];
       return chip(w, k) + (p.error ? `<div class="tier">${chip("не ответила", "warn")}</div>` : ""); })())}
    ${cell("Куда смотреть", `<div class="verbs">` +
      `<a class="chip-btn" href="${E(p.report_url)}" target="_blank" rel="noopener" title="отчёт GA4">GA4</a>` +
      (p.admin_url ? `<a class="chip-btn" href="${E(p.admin_url)}" target="_blank" rel="noopener" title="настройки property">админка</a>` : "") +
      `</div>`)}</tr>`;
  const tt = D.google.totals || {};
  const creds = (D.google.credentials || []).map(c =>
    `<a class="chip-btn" href="${E(c.console_url)}" target="_blank" rel="noopener" title="${E(c.client_email || "")}">Cloud: ${E(c.cloud_project || "")}</a>`).join(" ");
  const sites = (D.google.search_console || []).map(s =>
    `<a class="chip-btn" href="${E(s.console_url)}" target="_blank" rel="noopener">Search Console: ${E(s.site)}</a>`).join(" ");
  out.innerHTML = filterLine(rows.length, ALL.length, "property") +
    `<div class="card"><table>
    <colgroup><col style="width:26%"><col style="width:11%"><col style="width:11%"><col style="width:10%"><col style="width:14%"><col style="width:12%"><col style="width:16%"></colgroup>
    <thead><tr>${sortTh("Property", "name")}${sortTh("Польз./30 дн", "users")}<th>Сессий/30 дн</th><th>Просмотров</th>
      <th>Проект</th><th>Связь</th><th>Куда смотреть</th></tr></thead>
    ${[...groups].map(([acc, ps]) => `<tbody class="grp">
      ${grpHead(7, `${E(acc)} <span class="n">${ps.length}</span> <span class="n">${Number(ps.reduce((n, p) => n + (p.users_30d || 0), 0)).toLocaleString("ru")} польз./30 дн</span>`, true)}
      ${ps.map(row).join("")}</tbody>`).join("")}</table></div>
    <div class="verbs" style="margin: var(--space-3) var(--space-5) 0">${creds}${sites}</div>
    <p class="dmeta">Показано ${rows.length} из ${ALL.length} · ${tt.linked_to_a_project || 0} привязано,
      ${tt.unclaimed || 0} ничьих (${Number(tt.users_30d_unclaimed || 0).toLocaleString("ru")} польз.) ·
      всего ${Number(tt.users_30d || 0).toLocaleString("ru")} польз. за 30 дней ·
      измерено ${E(D.google.scanned_on || "—")}
      <button class="chip-btn" type="button" data-copy="${E(engineCommand("collectors/scan_google.py", [String(RUNTIME.scratch || ".") + "/google.json", "--force"]) + " && " + cliCommand("merge") + " && " + cliCommand("emit") + " && " + cliCommand("dashboard"))}"
        title="перечитать у Google и пересобрать страницы">обновить данные</button><br>
      Цифры кэшируются на 12 часов; время обновления зависит от числа подключённых ресурсов.
      Аналитика может обновляться с задержкой. «Ничей» — не дефект: по правилу оператора это продукт,
      которым занимается кто-то другой, — но строка есть, чтобы решение можно было принять один раз.</p>`;
}

function renderDomains() {
  const out = document.getElementById("out");
  const q = document.getElementById("q").value.trim().toLowerCase();
                                                                       
                                                                              
                                                                          
                                                                           
  const zoneBy = new Map((D.zones || []).map(z => [z.name, z]));
  const rows0 = DOMS.map(d => ({ ...d, zone: zoneBy.get(d.name) || null, source: zoneBy.has(d.name) ? "both" : "registrar" }));
  (D.zones || []).forEach(z => { if (!DOMS.some(d => d.name === z.name))
    rows0.push({ name: z.name, registrar: z.registrar ? z.registrar + " (по данным Cloudflare)" : "—",
      status: z.status, live: LIVE_BY_HOST(z.name), projects: z.project ? [z.project] : [],
      zone: z, source: "cloudflare" }); });
  const doms = rows0.filter(d => keepDom(d, q, sel.value));
  if (!doms.length) { out.innerHTML = nothingFound(rows0.length); return; }
  const PROD_BY_PROJECT = new Map(D.rows.map(r => [r.id, r.products || []]));
  const standing = d => {
    if (!d.zone) return d.projects && d.projects.length ? chip("привязан", "ok") : chip("нет проекта");
    const s = d.zone.standing;
    if (s === "linked") return chip("привязан", "ok");
    if (s === "outside") return `<span title="${E(d.zone.boundary_why || "")}">${chip("вне эстейта")}</span>`;
    if (s === "pending") return chip("ждёт слова", "warn");
    if (s === "dormant") return `<span title="DNS прочитан: апекс и www никуда не указывают">${chip("спит")}</span>`;
    if (s === "product") return chip("продукт", "ok");
    return chip("без слова", "warn");
  };
  const cfCell = d => d.zone
    ? `<span class="mono">${E(d.zone.account_label || "")}</span><div class="anchor">${E(d.zone.status || "")}${d.zone.paused ? " · paused" : ""} · ${E(d.zone.plan || "")}</div>`
    : NONE;
  const PROD_NAME = new Map((D.products || []).map(p => [p.id, p.name]));
  const prodCell = d => { const ps = (d.projects || []).flatMap(p => PROD_BY_PROJECT.get(p) || []);
    if (!ps.length && d.zone && d.zone.product) return E(PROD_NAME.get(d.zone.product) || d.zone.product);
    return ps.length ? ps.map(p => `<span title="${E(p.kind)}">${E(p.name)}${p.kind === "suggested" ? "?" : ""}</span>`).join(", ") : NONE; };
  const cell = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  const liveCell = d => {
    if (!d.live) return chip("не измерен");
    if (d.live.resolves === false) return chip("не резолвится", "danger");
                                                                               
                                                                               
    if (!d.live.http) return chip("резолвится, не отвечает", "warn");
    if (d.live.http >= 400) return chip("HTTP " + d.live.http, "warn");
    return chip("HTTP " + d.live.http, "ok");
  };
  const expiry = d => {
    const n = daysUntil(d.expires_on);
    if (n === null) return NONE;
    const word = n < 0 ? chip("истёк", "danger")
      : n <= 90 ? chip(n + " дн.", "warn") : `${n} дн.`;
    return `${E(d.expires_on)}<div class="tier">${word}` +
      (d.auto_renew === false ? " " + chip("без автопродления", "warn") : "") + `</div>`;
  };
  sortInPlace(doms, {name: d => lower(d.name), expiry: d => dateOr(d.expires_on)});
  const groups = new Map();
  doms.forEach(d => { const k = d.registrar || "—";
    if (!groups.has(k)) groups.set(k, []); groups.get(k).push(d); });
  const row = d => `<tr id="d-${E(d.name)}">
    <td data-label="Домен"><div class="name"><a href="https://${E(d.name)}"
      target="_blank" rel="noopener">${E(d.name)}</a></div>
      <div class="anchor">${E(d.status || "")}</div></td>
    ${cell("Отвечает", liveCell(d) + (d.live ? `<div class="anchor">${E(d.live.on)}</div>` : ""))}
    ${cell("Истекает", expiry(d), "num")}
    ${cell("Проект", (d.projects || []).length
      ? (d.projects || []).map(p => `<a class="plink" href="#${E(p)}">${E(p.split(":")[1])}</a>`).join(", ")
      : `<span class="unlinked">нет проекта</span>`)}
    ${cell("Связь", standing(d))}
    ${cell("Cloudflare", cfCell(d))}
    ${cell("Продукт", prodCell(d))}
    ${                                                                       
                                                                              
                                                                              
                                                                                
                                                                               ""}
    ${cell("Куда смотреть", `<div class="verbs">` +
      `<a class="chip-btn" href="https://rdap.org/domain/${E(d.name)}"
         target="_blank" rel="noopener" title="что говорит регистратор">RDAP</a>` +
      `<button class="chip-btn" type="button" data-copy="${E("dig +short " + shellArg(d.name) + " A AAAA CNAME")}"
         title="dig +short ${E(d.name)} A AAAA CNAME">DNS</button>` +
      (d.zone ? `<a class="chip-btn" href="https://dash.cloudflare.com/?to=/:account/${E(d.name)}"
         target="_blank" rel="noopener" title="зона в Cloudflare">зона</a>` : "") +
      `</div>`)}</tr>`;
  out.innerHTML = filterLine(doms.length, rows0.length, "имён") + `<div class="card"><table>
    <colgroup><col style="width:18%"><col style="width:10%"><col style="width:11%"><col style="width:13%"><col style="width:11%"><col style="width:11%"><col style="width:12%"><col style="width:14%"></colgroup>
    <thead><tr>${sortTh("Домен", "name")}<th>Отвечает</th>${sortTh("Истекает", "expiry")}<th>Проект</th><th>Связь</th><th>Cloudflare</th><th>Продукт</th><th>Куда смотреть</th></tr></thead>
    ${[...groups].map(([reg, ds]) => `<tbody class="grp">
      ${grpHead(8, `${E(reg)} <span class="n">${ds.length}</span>`, true)}
      ${ds.map(row).join("")}</tbody>`).join("")}</table></div>
    <p class="dmeta">Показано ${doms.length} из ${rows0.length} ·
      ${rows0.filter(d => !(d.projects || []).length).length} не привязано ни к одному проекту ·
      ${D.zones ? `${D.zones.length} зон Cloudflare в ${new Set(D.zones.map(z => z.account_label)).size} аккаунтах` : "Cloudflare не сканировался"} ·
      цена продления здесь не измеряется (DEC-0210)</p>`;
}

const STATE_RU = { running: "работает", down: "упало", suspended: "приостановлено",
                   "resources-only": "только ресурсы", idle: "пусто" };

                                                                                
                                                                                
                                                                                
                                                                                
const REMOTE_BY_APP = new Map(((D.remote && D.remote.apps) || []).map(a => [a.app, a]));
const REMOTE_BY_FOLDER = new Map();
for (const a of (D.remote && D.remote.apps) || [])
  for (const f of a.compared_with || []) {
    const key = String(f).replace(/\/+$/, "").split("/").pop();
    if (!REMOTE_BY_FOLDER.has(key)) REMOTE_BY_FOLDER.set(key, new Map());
    const m = REMOTE_BY_FOLDER.get(key);
    for (const v of a.vars || []) if (!m.has(v.name)) m.set(v.name, {...v, app: a.app});
  }
const VERDICT_RU = {
  same_as_local: ["то же, что локально", "danger"],
  differs: ["другое значение", "ok"],
  remote_only: ["только у прода", ""],
  local_only: ["только локально", "warn"],
  not_compared: ["не сравнивалось", ""],
  no_local_checkout: ["кода здесь нет", ""],
};

function renderHeroku() {
  const out = document.getElementById("out");
  if (!D.heroku) {
                                                                               
                                                                    
    out.innerHTML = `<p class="empty">Heroku не сканировался — ` +
      `<span class="mono">${E(cliCommand("heroku"))}</span></p>`;
    return;
  }
  const q = document.getElementById("q").value.trim().toLowerCase();
  const team = sel.value;
  const apps = APPS.filter(a => keepApp(a, q, team));
  if (!apps.length) { out.innerHTML = nothingFound(APPS.length); return; }
  const money = n => n ? "$" + Math.round(n) : "—";
  sortInPlace(apps, {name: a => lower(a.name), cost: a => numOr(a.monthly_cost)});
  const groups = new Map();
  apps.forEach(a => { if (!groups.has(a.team)) groups.set(a.team, []); groups.get(a.team).push(a); });
  const cell = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  const appRow = a => {
    const dynos = (a.formation || []).filter(f => f.qty).map(f =>
      `<div class="st">${chip(`${E(f.type)}×${f.qty}`)}<span class="mono">${E(f.size)}</span></div>`).join("");
    const crashed = (a.crashed || []).length
      ? `<div class="tier">${chip("crashed: " + E(a.crashed.join(", ")), "danger")}</div>` : "";
                                                                          
                                                                              
                                                                         
    const planName = p => String(p || "").replace(/^heroku-/, "").replace(":", " ");
    const addons = (a.addons || []).length
      ? (a.addons || []).map(x => `<div class="st"><span>${E(planName(x.plan))}</span>` +
          (x.cents ? `<span class="mono">$${x.cents / 100}</span>` : "") + `</div>`).join("")
      : NONE;
                                                                              
                                                                              
                                  
    const shared = (a.addons_attached || []).length
      ? `<div class="tier">${chip("общая с " + E(a.addons_attached.map(x => x.owner).join(", ")), "warn")}</div>` : "";
    const deploy = a.last_deploy_on
      ? E(a.last_deploy_on) + (a.last_deploy_on < YEAR_AGO ? `<div class="tier">${chip("больше года", "warn")}</div>` : "")
      : `<span class="unlinked">${a.never_deployed ? "кода не было" : "не найден"}</span>`;
                                                                                 
                                                                             
                      
    const WHY_RU = { "external-repo": "источник вне нашего GitHub",
                     "folder-unclaimed": "папку не claim'ит ни один проект",
                     "no-source": "источник неизвестен" };
    const project = a.project
      ? `<a class="plink" href="#${E(a.project)}">${E(PROJ_NAME.get(a.project) || a.project)}</a>` +
        `<div class="anchor">${E(a.link_rule)}</div>`
      : `<span class="unlinked" title="${E(a.unlinked_reason || "")}">нет проекта</span>` +
        `<div class="anchor">${E(WHY_RU[a.unlinked_kind] || a.unlinked_kind || "")}</div>`;
    const folders = (a.local_folders || []).length
      ? (a.local_folders || []).map(p =>
          `<span class="folder">${E(p.replace(/^\/Users\/[^/]+\//, "~/"))}</span>`).join("")
      : `<span class="unlinked">нет папки</span>`;
    return `<tr id="a-${E(a.name)}">
      <td data-label="Приложение"><div class="name">${a.web_url
        ? `<a href="${E(a.web_url)}" target="_blank" rel="noopener">${E(a.name)}</a>`
        : E(a.name)}</div>
        <div class="anchor">${E(a.region)} · ${E(a.stack)}${a.stack_superseded ? " · стек снят с поддержки" : ""}</div></td>
      ${cell("Состояние", `<span class="st st-${E(a.state)}"><i></i>${E(STATE_RU[a.state] || a.state)}</span>` +
        (a.maintenance ? `<div class="tier">${chip("maintenance", "warn")}</div>` : "") + crashed)}
      ${cell("Дино", dynos || NONE)}
      ${cell("Ресурсы", addons + shared)}
      ${cell("$/мес", money(a.monthly_cost), "num")}
      ${cell("Деплой кода", deploy, "num")}
      ${cell("Проект", project)}
      ${cell("Папка", folders)}
      ${                                                                       
                                                                            
                                                                          
                                                                            
                                                                            ""}
      ${cell("Прод-конфиг", (() => {
        const r = REMOTE_BY_APP.get(a.name);
        if (!D.remote) return `<span class="unlinked">не сканировалось</span>`;
        if (!r) return `<span class="unlinked">нет в скане</span>`;
        if (r.error) return chip("не ответило", "warn");
        const c = r.counts || {};
        const n = (r.vars || []).length;
        if (!r.compared_with.length)
          return `<span class="mono">${n}</span><div class="anchor">переменных; кода здесь нет, сравнить не с чем</div>`;
        return `<span class="mono">${n}</span><div class="anchor">переменных</div>` +
          (c.same_as_local ? `<div class="tier">${chip(c.same_as_local + " как локально", "danger")}</div>` : "") +
          ((r.retired_in_use || []).length
            ? `<div class="tier">${chip((r.retired_in_use || []).length + " отставных", "danger")}</div>` : "") +
          `<div class="anchor">${c.differs || 0} отличается · ${c.remote_only || 0} только тут</div>`;
      })())}
      ${cell("Команда", `<div class="verbs">` +
        [["перезапуск", `heroku ps:restart -a ${a.name}`],
         ["логи", `heroku logs -t -a ${a.name}`],
         ...(a.state === "suspended" || a.state === "resources-only"
             ? [["что это", `heroku apps:info -a ${a.name}`]] : [])]
        .map(([label, cmd]) => `<button class="chip-btn" type="button"
              data-copy="${E(cmd)}" title="${E(cmd)}">${E(label)}</button>`).join(" ")
        + `</div>`)}</tr>`;
  };
  const total = apps.reduce((n, a) => n + a.monthly_cost, 0);
  out.innerHTML = filterLine(apps.length, APPS.length, "приложений") + `<div class="card"><table>
    <colgroup><col style="width:14%"><col style="width:9%"><col style="width:6%"><col style="width:10%"><col style="width:8%"><col style="width:12%"><col style="width:12%"><col style="width:11%"><col style="width:10%"><col style="width:8%"></colgroup>
    <thead><tr>
      ${sortTh("Приложение", "name")}<th>Состояние</th><th>Дино</th><th>Ресурсы</th>
      ${sortTh("$/мес", "cost")}<th>Деплой кода</th><th>Проект</th><th>Папка</th>
      <th>Прод-конфиг</th><th>Команда</th>
    </tr></thead>${[...groups].map(([team, as]) => `<tbody class="grp">
      ${grpHead(10, `${E(team)} <span class="n">${as.length}</span> <span class="n">${money(as.reduce((n, a) => n + a.monthly_cost, 0))}/мес</span>`, true)}
      ${as.map(appRow).join("")}</tbody>`).join("")}</table></div>
    <p class="dmeta">Показано ${apps.length} из ${APPS.length} · ${money(total)}/мес ·
      измерено ${E(D.heroku.scanned_on || "—")} ·
      цена по прайс-листу on-demand, не по счёту</p>`;
}

                                                                            
                                                                            
                                                                           
document.getElementById("out").addEventListener("click", e => {
  const b = e.target.closest(".more");
  if (!b) return;
  const list = b.previousElementSibling;
  const folded = list.classList.toggle("folded");
  b.textContent = folded ? `+${list.children.length - 3} ещё` : "свернуть";
});

                                                                            
                                                                                 
const bar = document.querySelector(".controls");
const topbar = document.getElementById("topbar");
const stick = () => {
                                                                          
                                                                            
  const top = topbar ? topbar.offsetHeight : 0;
  document.documentElement.style.setProperty("--topbar", top + "px");
  document.documentElement.style.setProperty("--stick", (top + bar.offsetHeight) + "px");
};
new ResizeObserver(stick).observe(bar);
if (topbar) new ResizeObserver(stick).observe(topbar);
                                                                              
                                                                             
                                                                            
                                                                               
               
(function renderQueue() {
  const host = document.getElementById("queue"), head = document.getElementById("queue-h");
  const q = D.queue || [];
  if (!q.length) {
    head.textContent = "Ждёт решения человека";
    host.innerHTML = `<p class="none">${D.store_degraded
      ? E(D.store_degraded) : "ничего не предложено — очередь пуста"}</p>`;
    return;
  }
                                                                               
                                                             
  const total = (D.health && D.health.proposed) || q.length;
  head.textContent = `Ждёт решения человека — ${q.length} из ${total}`;
                                                                         
                                                                       
                                                                            
  const dg = D.digest || null;
  const digestLine = dg ? `<p class="dmeta" id="queue-digest">${dg.waiting} ждёт: ` +
    Object.entries(dg.by_kind || {}).map(([k, n]) => `${n} ${E(k)}`).join(", ") +
    ` · ретеншен стирает предложение через ${dg.horizon_days} дн` +
    (dg.erases_within_7d ? ` — <b>${dg.erases_within_7d}</b> уйдёт до ${E(dg.first_erase_on || "")}` : " — на этой неделе ничего не уйдёт") +
    ` · <button class="chip-btn" type="button" data-copy="${E(toolCommand("review.py", ["digest"]))}" title="скопировать команду">digest в терминале</button></p>` : "";
                                                                             
                                                                               
                                                                                
                                                                             
                                                                              
                                                    
  host.innerHTML = digestLine + q.map(r => {
    const ok = toolCommand("review.py", ["promote", r.id, "--why", ""]);
    const no = toolCommand("review.py", ["reject", r.id, "--why", ""]);
    return `<div class="qrow" id="q-${E(r.id)}">
      <span class="qm">${E(r.at)}<br>${E(r.kind)}</span>
      <span>${E(r.statement)}${r.project
        ? ` <a class="plink" href="projects.html#${E(r.project)}">${E(String(r.project).split(":")[1])}</a>` : ""}
        <div class="anchor mono">${E(r.id)} r${E(r.rev)}</div>
        <div class="qacts"><button class="chip-btn" type="button" data-copy="${E(ok)}"
             title="скопировать команду принятия">принять</button>
          <button class="chip-btn" type="button" data-copy="${E(no)}"
             title="скопировать команду отклонения">отклонить</button></div></span>
    </div>`;
  }).join("") +
    `<p class="none">Кнопка кладёт команду в буфер — решение принимается в терминале
      (<span class="mono">${E(cliCommand("review"))}</span> для списка):
      запись без терминала отклоняется намеренно, и флага <span class="mono">--yes</span> нет.</p>`;
})();

(function renderFindings() {
  const F = D.findings, host = document.getElementById("findings");
  if (!F) {
                                                                               
                                             
    host.innerHTML = `<div class="fh">находки <span class="when">не строились — ` +
      `${E(cliCommand("findings"))}</span></div>`;
    return;
  }
  const c = F.counts, when = E((F.built_at || "").slice(0, 16).replace("T", " "));
  if (!F.items.length) {
    host.innerHTML = `<div class="fh">находки <span class="when">ничего открытого · ` +
      `без изменений с ${when}</span></div>`;
    return;
  }
  const RU = { critical: ["критично", "danger"], warning: ["внимание", "warn"],
               info: ["к сведению", ""] };
  host.innerHTML = `<div class="fh">находки <span class="when">${c.critical} критично · ` +
    `${c.warning} внимание · ${c.info} к сведению` +
                                                                                
                                                                                
                                                           
                                                                                
                                                                              
                                                                            
                                                                                
    `${(F.silenced || []).length ? ` · ${F.silenced.length} заглушено` : ""}` +
                                                                             
                                                                             
                                                                             
                                                                             
                                            
    `${F.elsewhere ? ` · <a href="findings.html">подробности и ещё ${F.elsewhere} — на странице находок</a>` : ""}` +
    ` · без изменений с ${when}</span></div>` +
                                                                           
                                                                                
                                                                           
                                                                                 
                                                                                
                                                                               
                                                                               
                                                         
                                                                                
                                                                              
                                                                               
                                                                            
                                                
                                                                               
                                                                               
                                                                             
                                                                          
                                                                     
    (PAGE === "findings"
      ? `<div class="fbar" role="group" aria-label="Сужение находок">` +
        ["critical", "warning", "info"].map(s => `<button class="chip-btn" type="button" data-sev="${s}" aria-pressed="false">${RU[s][0]} <span class="n">${c[s] || 0}</span></button>`).join("") +
        `<select class="ftype" aria-label="Тип находки"><option value="">все типы</option>` +
        Object.entries(F.items.reduce((m, f) => (m[f.type] = (m[f.type] || 0) + 1, m), {})).sort()
          .map(([k, n]) => `<option value="${E(k)}">${E(k)} · ${n}</option>`).join("") +
        `</select><input type="search" class="fq" placeholder="Поиск по находкам" aria-label="Поиск по находкам">` +
        `<span class="fshown" role="status"></span></div>`
      : "") +
    (F.items.some(f => f.severity !== "critical") && PAGE !== "findings"
      ? `<button class="more fold" type="button" id="finfo" aria-expanded="false">` +
        `показать ещё ${F.items.filter(f => f.severity !== "critical").length}` +
        ` (внимание и к сведению)</button>`
      : "") +
    `<div class="flist folded">` + F.items.map(f => {
      const [word, kind] = RU[f.severity] || [f.severity, ""];
                                                                           
                                                                                
               
                                                                              
                                                                        
                                                                                  
      const cmd = toolCommand("ack.py", [f.id, "--why", ""]);
      const foldCls = f.folded ? ` ftype-folded` : "";
                                                                             
                                                                             
      const fid = "f-" + String(f.id).replace(/[^A-Za-z0-9_.:-]+/g, "-");
      const subj = subjectHref(f.subject);
      return `<div class="f${f.severity === "critical" ? "" : " f" + f.severity}${foldCls}" id="${E(fid)}" data-type="${E(f.type)}" data-sev="${E(f.severity)}">${chip(word, kind)}` +
        `<span class="t">${E(f.title)}` +
        (subj ? ` <a class="plink fsubj" href="${E(subj[0])}" title="открыть ${E(subj[1])}">→ ${E(subj[1])}</a>` : "") +
        (PAGE === "findings" ? ` <a class="fperma" href="#${E(fid)}" title="ссылка на эту строку">#</a>` : "") +
        `</span>` +
        `<span class="d">${E(f.detail)}</span>` +
        (f.deadline ? `<span class="due">до ${E(f.deadline)}</span>` : "") +
        `<span class="act">${E(f.action)}` +
        ` <button class="chip-btn ack" type="button" data-cmd="${E(cmd)}" title="скопировать команду заглушения">заглушить</button></span></div>`;
    }).join("") +
                                                                         
    Object.entries(F.folded_by_type || {}).map(([type, n]) =>
      `<button class="more fold ftype" type="button" data-type="${E(type)}" aria-expanded="false">ещё ${n} ${plural(n, "строка", "строки", "строк")} типа ${E(type)}</button>`).join("") +
    `</div>` +
                                                      
    ((F.silenced || []).length ? `<details class="silenced"><summary>заглушено ${F.silenced.length} — ` +
      `на странице и в счётчиках их нет; здесь видно, кто, когда и почему</summary>` +
      F.silenced.map(s => `<div class="f fsilenced">${chip("заглушено")}<span class="t">${E(s.title)}</span>` +
        `<span class="d">${E(s.acked.why || "без причины")} — ${E(s.acked.by || "?")}` +
        `${s.acked.until ? `, до ${E(s.acked.until)}` : ""}</span>` +
        `<span class="act"><button class="chip-btn ack" type="button" data-cmd="${E(toolCommand("ack.py", ["--undo", s.id]))}">вернуть</button></span></div>`).join("") +
      `</details>` : "");
                                                                             
                                                                             
                                                                            
                                                                           
  host.querySelectorAll("button.ack").forEach(b => b.addEventListener("click", () => {
    const cmd = b.getAttribute("data-cmd"), label = b.textContent;
    copyText(cmd).then(ok => {
      toast(ok ? `скопировано: ${cmd.slice(0, 48)}…` : "буфер недоступен — скопируйте из подсказки");
      if (ok) { b.textContent = "скопировано"; setTimeout(() => { b.textContent = label; }, 1500); }
    });
  }));
  host.querySelectorAll("button.ftype").forEach(b => b.addEventListener("click", () => {
    const type = b.getAttribute("data-type");
    const rows = host.querySelectorAll(`.f.ftype-folded[data-type="${type.replace(/"/g, '\\"')}"]`);
    const open = b.getAttribute("aria-expanded") !== "true";
    rows.forEach(r => r.classList.toggle("ftype-open", open));
    b.setAttribute("aria-expanded", String(open));
    b.textContent = open ? `свернуть ${type}` : `ещё ${rows.length} типа ${type}`;
  }));
  if (PAGE === "findings") {
    const bar = host.querySelector(".fbar");
    const sevOn = new Set();
    const rows = [...host.querySelectorAll(".flist > .f")];
    const apply = () => {
      const type = bar.querySelector(".ftype").value;
      const q = bar.querySelector(".fq").value.trim().toLowerCase();
      let shown = 0;
      rows.forEach(r => {
        const ok = (!sevOn.size || sevOn.has(r.dataset.sev)) && (!type || r.dataset.type === type)
          && (!q || r.textContent.toLowerCase().includes(q));
        r.classList.toggle("fhide", !ok);
        if (ok) shown++;
      });
                                                                              
      host.querySelectorAll("button.ftype").forEach(b => { b.hidden = !!(sevOn.size || type || q); });
      if (sevOn.size || type || q) host.querySelectorAll(".f.ftype-folded").forEach(r => r.classList.add("ftype-open"));
      const what = [];
      if (sevOn.size) what.push([...sevOn].map(s => RU[s][0]).join(", "));
      if (type) what.push("тип " + type);
      if (q) what.push(`поиск «${q}»`);
      bar.querySelector(".fshown").innerHTML = `показано ${shown} из ${rows.length}` +
        (what.length ? ` · ${E(what.join(" · "))} <button class="chip-btn" type="button" data-fclear>сбросить</button>` : "");
      let none = host.querySelector(".fnone");
      if (!shown) {
        if (!none) { none = document.createElement("p"); none.className = "empty fnone"; host.querySelector(".flist").before(none); }
        none.innerHTML = `Ничего не найдено с этим сужением — ${E(what.join(" · "))}. <button class="chip-btn" type="button" data-fclear>сбросить</button>`;
      } else if (none) none.remove();
    };
    bar.querySelectorAll("[data-sev]").forEach(b => b.addEventListener("click", () => {
      const on = b.getAttribute("aria-pressed") === "true";
      b.setAttribute("aria-pressed", String(!on));
      on ? sevOn.delete(b.dataset.sev) : sevOn.add(b.dataset.sev);
      apply();
    }));
    bar.querySelector(".ftype").addEventListener("change", apply);
    bar.querySelector(".fq").addEventListener("input", apply);
    host.addEventListener("click", ev => {
      if (!(ev.target.closest && ev.target.closest("[data-fclear]"))) return;
      sevOn.clear();
      bar.querySelectorAll("[data-sev]").forEach(b => b.setAttribute("aria-pressed", "false"));
      bar.querySelector(".ftype").value = ""; bar.querySelector(".fq").value = "";
      apply();
    });
                                                                      
    const reveal = () => {
      const target = location.hash && location.hash.startsWith("#f-") && document.getElementById(location.hash.slice(1));
      if (target) { target.classList.add("ftype-open"); target.scrollIntoView({block: "center"}); }
    };
    reveal(); window.addEventListener("hashchange", reveal);
    apply();
  }
  const fold = document.getElementById("finfo");
  if (fold) fold.addEventListener("click", () => {
    const list = host.querySelector(".flist");
    const shown = list.classList.toggle("folded") === false;
    fold.setAttribute("aria-expanded", String(shown));
    const n = F.items.filter(f => f.severity !== "critical").length;
    fold.textContent = shown ? "свернуть" : `показать ещё ${n} (внимание и к сведению)`;
  });
})();

if (PAGE) {
                                                                               
                                                                         
  const bodyEl = document.body || document.documentElement;
  if (bodyEl && bodyEl.setAttribute) bodyEl.setAttribute("data-page", PAGE);
  if (TABLE_PAGES.includes(PAGE)) { tab = PAGE; active = activeBy[tab] || new Set(); }
  for (const t of TABLE_PAGES) {
    const b = document.getElementById("tab-" + t);
    if (b) { b.onclick = () => { location.href = t + ".html"; };
             b.setAttribute("aria-selected", String(t === tab)); }
    const s = document.getElementById("seg-" + t);
    if (s) s.hidden = t !== tab;
  }
                                                                         
  if (typeof fillOwners === "function" && TABLE_PAGES.includes(PAGE)
      && typeof SEL_BY_TAB !== "undefined" && SEL_BY_TAB[tab]) fillOwners();
}
stick();
render();
                                                                   
fromHash();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(OUT, build())
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
                                                                               
                                                                    
    sizes = build_pages(build.last_payload)
    print(f"wrote {len(sizes)} page(s) under {paths.DASHBOARD_DIR}: "
          + ", ".join(f"{k} {v // 1024} KB" for k, v in sizes.items()))