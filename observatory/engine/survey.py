#!/usr/bin/env python3
""                                                                      

                                                                          
                                           
                                                                              
                                 
   
from __future__ import annotations
import json, os, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path

import activity
import degradations
import identity
import paths
from store import db as store_db

SOURCE_OF_TRUTH = "registry"


def _load(name: str) -> dict:
    return json.loads((paths.REGISTRY / name).read_text(encoding="utf-8"))


                                                                             
                                                                          
                                                                               
                                                                                
                                                                            
                                                     
_collector_degradation = degradations.collector


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _index():
    projects = _load("projects.json")["projects"]
    repos = {r["id"]: r for r in _load("repositories.json")["repositories"]}
    members: dict[str, list[str]] = {}
    for rel in _load("relations.json")["relations"]:
        if rel["type"] == "implemented_by":
            members.setdefault(rel["from"], []).append(rel["to"])
    return projects, repos, members


def _repo_view(r: dict) -> dict:
    view = {"id": r["id"], "host": r["host"], "nameWithOwner": r["name_with_owner"]}
    for src, dst in (("visibility", "visibility"), ("default_branch", "defaultBranch"),
                     ("archived", "archived"), ("fork", "fork"),
                     ("last_pushed_on", "lastPushedOn"), ("discovered_by", "discoveredBy")):
        val = r.get(src)
        if val not in (None, ""):
            view[dst] = val
    return view


def _marks(items) -> str:
    ""                                                                            
    return ",".join("?" * len(items))


def ids_for_project(project_id: str) -> list[str]:
    ""                                                             

                                                                                     
                                                                                
                                                                           
                                                                                
                                                                                 
                                            

                                                                              
                                                                         
       
    try:
        projects = _load("projects.json")["projects"]
        for p in projects:
            if p["id"] == project_id:
                return identity.ids_for(p, projects)
    except (OSError, ValueError, KeyError):
                                                                               
                                                                                
                                                                                  
        pass
    return [project_id]


def _identity_warnings(projects: list[dict], project_id: str | None = None) -> list[dict]:
    conflicts = identity.former_conflicts(projects)
    relevant = any(project_id is None or project_id == old or project_id in owners
                   for old, owners in conflicts.items())
    if not relevant:
        return []
    return [{'source':'identity', 'reason':
             'Ambiguous links to old project identifiers were not followed; review the project/folder mapping.'}]


def _tier_vocabulary() -> list[dict]:
    ""                                                                       

                                                                               
                                                                             
                                                                               
                                                                                
                                                                              
                                                                          
                       
       
    out = [{"id": t["id"], "maxDays": t.get("max_days"), "means": t.get("means", "")}
           for t in activity.tiers()]
    cfg = activity.config()
    out.append({"id": activity.unknown_id(), "maxDays": None,
                "means": cfg.get("unknown_note", "")})
    return out


def _recent_activity(conn, renamed_to: dict[str, str], days: int) -> dict[str, dict]:
    ""                                                                    

                                                                        
                                                                                 
                                                                                 
                                                     

                                                                             
                                                                                
                                                                                
                                                                         
                                                                               
                                                   

                                                                                
                                                                              
                                                                                
                                                       
       
    out: dict[str, dict] = {}
    for r in conn.execute(
            "SELECT project_id, COUNT(*) AS weeks, SUM(commits) AS commits,"
            "       SUM(sessions) AS sessions, SUM(worked_days) AS worked,"
            "       COUNT(*) - COUNT(sessions) AS unmeasured"
            "  FROM project_week WHERE week_start >= date('now', ?)"
            " GROUP BY project_id", (f"-{days} days",)):
        pid = renamed_to.get(r["project_id"], r["project_id"])
        acc = out.setdefault(pid, {"weeks": 0, "commits": 0, "sessions": 0,
                                   "workedDays": 0, "sessionsUnmeasured": 0})
        acc["weeks"] += r["weeks"]
        acc["commits"] += r["commits"] or 0
        acc["sessions"] += r["sessions"] or 0
        acc["workedDays"] += r["worked"] or 0
        acc["sessionsUnmeasured"] += r["unmeasured"]
    return out


def _estate_work(conn, since: str, known: set[str] | None = None) -> dict:
    ""                                                                              

                                                                               
                                                                            
                                                                   
                                                                              
                                                                             
                                                                           

                                                                             
                                                                                
                                                                              

                                                                              
                                                                               
                                                                                
                                                             
       
    out: dict[str, int] = {}
    row = conn.execute(
        "SELECT SUM(commits) c, COUNT(DISTINCT CASE WHEN commits > 0"
        "        THEN project_id END) p"
        "  FROM project_week WHERE week_start >= ?", (since,)).fetchone()
    if row is not None:
        out["commits"] = row["c"] or 0
        out["projectsWorked"] = row["p"] or 0
    day = conn.execute(
        "SELECT COUNT(DISTINCT date(occurred_at)) d FROM events"
        " WHERE kind = 'commit' AND occurred_at >= ?", (since,)).fetchone()
    if day is not None:
        out["workedDays"] = day["d"] or 0
                                                                             
                                                                                  
                                                                              
                                                                          
                                                                                
                                                                              
                                                                                
                                                        
    if known is not None:
        rows = conn.execute(
            "SELECT project_id, SUM(commits) c FROM project_week"
            " WHERE week_start >= ? GROUP BY project_id", (since,)).fetchall()
        out["commitsUnattributed"] = sum(
            (r["c"] or 0) for r in rows if r["project_id"] not in known)
    return out


def _project_view(p: dict, repos: dict, members: dict) -> dict:
    view = {
        "id": p["id"],
        "name": p["name"],
        "ownership": p["ownership"],
        "lifecycle": p["lifecycle"],
        "repositories": [_repo_view(repos[i]) for i in sorted(members.get(p["id"], [])) if i in repos],
        "membershipRules": list(p.get("membership_rules", [])),
    }
    for src, dst in (("description", "description"), ("description_source", "descriptionSource"),
                     ("local_folders", "localFolders"), ("stack", "stack"),
                     ("last_activity_on", "lastActivityOn"), ("has_vault_note", "hasVaultNote"),
                                                                                 
                                                                              
                                                                              
                                                                          
                                                                                  
                                                                             
                     ("activity_tier", "activityTier"),
                                                                                 
                                                               
                     ("last_session_on", "lastSessionOn")):
        val = p.get(src)
        if val not in (None, "", []):
            view[dst] = val
    sites = []
    for s in p.get("sites", []):
        sites.append({"host": s["host"], "ownedDomain": s.get("owned_domain"),
                      "confidence": s["confidence"], "evidence": list(s["evidence"])})
    if sites:
        view["sites"] = sites
    return view


def survey(scope: dict | None = None, include_external: bool = False,
           as_of_scan_id: str | None = None, conn: sqlite3.Connection | None = None,
           limit: int | None = None, cursor: str | None = None) -> dict:
    ""                                                        

                                                                            
                                                                                  
                                                                           
                                       

                                                                                
                                                                               
                                                                          
                                                                              
                                                                                 
                                                                             
               

                                                                             
                                                                               
                                                                                
                                                                                 
                                                                         
                                                                            
                                                                             
       
    scope = scope or {"kind": "estate"}
    kind = scope.get("kind", "estate")
    projects, repos, members = _index()
    degraded: list[dict] = _identity_warnings(projects, scope.get('value') if kind == 'project' else None)

    owned = None
    if conn is None:
        try:
            conn = store_db.connect()
        except Exception as exc:                                                    
            degraded.append({"source": "store", "reason": f"unavailable: {exc}"})
        else:
            owned = conn
    scan_id = "registry-only"
    if conn is not None:
        latest = store_db.latest_scan(conn)
                                                                                  
                                                                               
                                                                              
                                                                                
                                                                                 
                                                                                
                                                                                  
                                                                             
                          
         
                                                                               
                                                                               
                                                                               
                                                                              
                                                                               
              
         
                                                                                 
                                                                                
                                                                    
                                                                    
        if as_of_scan_id and as_of_scan_id != latest:
            row = conn.execute("SELECT id FROM scans WHERE id = ?", (as_of_scan_id,)).fetchone()
            if row is None:
                degraded.append({"source": "store",
                                 "reason": f"scan {as_of_scan_id} is not recorded; answered "
                                           f"from the registry as it is now"})
            else:
                degraded.append({"source": "store",
                                 "reason": f"scan {as_of_scan_id} is recorded, but the "
                                           f"registry is not versioned per scan, so this "
                                           f"answer carries the CURRENT estate and `scanId` "
                                           f"names the scan it reflects"})
        if latest:
            scan_id = latest
        else:
            degraded.append({"source": "store",
                             "reason": "no scan recorded yet; answered from the registry alone"})

    selected = projects
    if kind == "project":
        selected = [p for p in projects if p["id"] == scope.get("value")]
    elif kind == "owner":
        selected = [p for p in projects if scope.get("value") in p.get("owners", [])]
    if not include_external:
        selected = [p for p in selected if p["ownership"] != "external"]

                                                                             
                                                                         
                                                                            
                                                                       
    selected = sorted(selected, key=lambda p: p["id"])
    total_projects = len(selected)
    page = selected
    next_cursor = None
    if cursor:
                                                                       
                                                                                 
                                                                                
                                                                             
                                                                           
                                                                                
                                                                 
         
                                                                          
                                                                              
                                                                            
                                                                               
                                                         
        if not str(cursor).startswith("project:"):
            degraded.append({"source": "cursor",
                             "reason": f"cursor {str(cursor)[:40]!r} is not a "
                                       f"project id, so it names no position in "
                                       f"this list; the page starts from the "
                                       f"beginning and a walk using it will "
                                       f"repeat what it has already seen"})
        page = [p for p in page if p["id"] > cursor]
    if limit is not None:
                                                                                 
                                                                           
                                                                                
        if limit < 1:
            raise ValueError(f"limit must be at least 1; got {limit}")
        more = page[limit:]
        page = page[:limit]
        if more and page:
            next_cursor = page[-1]["id"]

                                                                              
                                                                                 
                                                                                
                                                                              
                                                             
    recent: dict[str, dict] = {}
    window: dict | None = None
    estate_work: dict | None = None
    if conn is not None:
        days = activity.active_window_days()
        project_rows = list(projects.values()) if isinstance(projects, dict) else projects
        renamed_to = identity.former_index(project_rows)
        try:
            recent = _recent_activity(conn, renamed_to, days)
            window = {"windowDays": days}
            first = conn.execute(
                "SELECT MIN(week_start) FROM project_week WHERE week_start >= "
                "date('now', ?)", (f"-{days} days",)).fetchone()[0]
            if first:
                window["weeksFrom"] = first
                                                                                
                                                                         
                try:
                    known = {p['id'] for p in project_rows} | set(renamed_to)
                    work = _estate_work(conn, first, known)
                except sqlite3.Error as exc:
                    degraded.append({"source": "events",
                                     "reason": f"the estate's own work could not be "
                                               f"counted: {type(exc).__name__}"})
                else:
                    if work:
                        estate_work = {"windowDays": days, "weeksFrom": first, **work}
        except sqlite3.Error as exc:
            degraded.append({"source": "rollup",
                             "reason": f"the weekly rollup could not be summed: "
                                       f"{type(exc).__name__}: {exc}"})
    views = []
    for p in page:
        v = _project_view(p, repos, members)
                                                                                
                                                                     
        if p["id"] in recent:
            v["recentActivity"] = recent[p["id"]]
        views.append(v)
                                                                           
                                                                               
                                                                         
    all_views_repos = {rid for p in selected for rid in members.get(p["id"], [])}
    seen_repos = all_views_repos or {r["id"] for v in views for r in v["repositories"]}
    owners = {o for p in selected for o in p.get("owners", [])}

                                                                              
                                                                                  
                                                                                
                                                                               
                                           
    thin = sum(1 for i in seen_repos
               if repos[i]["host"] == "bitbucket"
               and repos[i].get("discovered_by") == "local-remote-only")
    if thin:
        reasons = _collector_degradation("bitbucket.json")
        if reasons:
            for d in reasons:
                degraded.append({"source": d["source"],
                                 "reason": f"{d['reason']} — {thin} repositories are "
                                           f"therefore known only from a local remote"})
        else:
            degraded.append({"source": "bitbucket",
                             "reason": f"{thin} repositories carry no listing data; the "
                                       f"bitbucket collector has not run against this "
                                       f"registry yet"})

                                                                                
                                                                                 
                                               
    if any(p.get("sites") for p in selected):
        if not (paths.SCRATCH / "domains_live.json").is_file():
            degraded.append({"source": "domains",
                             "reason": "no domain scan has run, so no site is known to "
                                       "resolve or not; run `./observatory.py domains`"})
        else:
            degraded.extend(_collector_degradation("domains_live.json"))

                                                                           
                                                                                
                                                                               
                                                                             
                 
    for d in _collector_degradation("gh/_degraded.json"):
        degraded.append({"source": d.get("source", "github"),
                         "reason": f"{d.get('reason', 'the listing failed')} — the "
                                   f"previous listing for that owner is still in use"})

    result = {
        "surveyedAt": _now(),
        "activityTiers": _tier_vocabulary(),
        "scanId": scan_id,
        "scope": scope,
        "counts": {"projects": total_projects, "repositories": len(seen_repos),
                   "owners": len(owners)},
        **({"recentActivityWindow": window} if window else {}),
        **({"estateWork": estate_work} if estate_work else {}),
        "projects": views,
        "evidence": [s["id"] for s in _load("sources.json")["sources"]],
        "degraded": degraded,
    }
    if next_cursor:
        result["nextCursor"] = next_cursor
    if owned is not None:
        owned.close()
    return result


                                                                        
                                                                                 
                                                                                
                                                                              
                                                                                
                                      
LIVE_LEDGER_JOIN = (
    " JOIN (SELECT memory_id, MAX(revision) r FROM ledger GROUP BY memory_id) m"
    "   ON m.memory_id = l.memory_id AND m.r = l.revision"
    " LEFT JOIN tombstones t ON t.memory_id = l.memory_id")
LIVE_LEDGER_WHERE = " t.memory_id IS NULL"


def project_detail(project_id: str, timeline_limit: int = 10,
                   weeks: int = 26, notes_limit: int = 10) -> dict:
    ""                                                                         

                                                                               
                                                                                  
                                                                         
                                                                               
                                                                                
                                                                             
                                                                         
                              

                                                                               
                                                                               
                        
       
                                                                              
                                                                             
                                                                            
                         
    result = survey({"kind": "project", "value": project_id}, include_external=True)
    if not result["projects"]:
        return {"error": "unknown project", "projectId": project_id,
                "hint": "call observatory_status to list what exists",
                "degraded": result["degraded"]}
    out = {"surveyedAt": result["surveyedAt"], "scanId": result["scanId"],
           "project": result["projects"][0],
           "activity": {"weeks": [], "totals": {}},
           "measurements": [], "notes": [], "findings": [],
           "recentEvents": [],
           "evidence": result["evidence"], "degraded": list(result["degraded"])}
    if timeline_limit:
        tl = timeline(project_id, limit=timeline_limit)
        out["recentEvents"] = tl["events"]
        out["degraded"] += [d for d in tl["degraded"] if d not in out["degraded"]]

                                                                             
                                                                            
                                       
    pids = ids_for_project(project_id)

    try:
        conn = store_db.connect()
    except sqlite3.Error as exc:
        out["degraded"].append({"source": "store",
                                "reason": f"the store did not open: {type(exc).__name__}"})
        conn = None
    if conn is not None:
        try:
            for r in conn.execute(
                    "SELECT week_start, commits, sessions, worked_days, frozen_at,"
                    "       active_days, authors"
                    f" FROM project_week WHERE project_id IN ({_marks(pids)})"
                    "   AND week_start >= date('now', ?) ORDER BY week_start",
                    (*pids, f"-{weeks * 7} days")):
                                                                             
                                                                              
                                                 
                out["activity"]["weeks"].append(
                    {"weekStart": r["week_start"], "commits": r["commits"],
                     "sessions": r["sessions"], "workedDays": r["worked_days"],
                     "activeDays": r["active_days"], "authors": r["authors"],
                                                                                
                                                                                 
                                                                          
                     "frozenAt": r["frozen_at"]})
            wk = out["activity"]["weeks"]
            out["activity"]["totals"] = {
                "weeks": len(wk),
                "commits": sum(w["commits"] or 0 for w in wk),
                "sessions": sum(w["sessions"] or 0 for w in wk
                                if w["sessions"] is not None),
                "workedDays": sum(w["workedDays"] or 0 for w in wk
                                  if w["workedDays"] is not None),
                "sessionsUnmeasured": sum(1 for w in wk if w["sessions"] is None)}
            if not wk:
                out["degraded"].append({
                    "source": "rollup",
                    "reason": f"no weekly rollup for this project in the last {weeks} "
                              f"week(s); `./observatory.py rollup` computes it"})

                                                                                
                                                                          
                              
                                                                            
                                                                              
                                                                                 
                                                                              
                                                                              
                                                      
            for r in conn.execute(
                    "SELECT m.metric, m.unit, m.value, m.at, m.source,"
                    "       (SELECT value FROM metrics q WHERE q.project_id = m.project_id"
                    "          AND q.metric = m.metric AND q.at < m.at"
                    "        ORDER BY q.at DESC LIMIT 1) AS prev_value,"
                    "       (SELECT at FROM metrics q WHERE q.project_id = m.project_id"
                    "          AND q.metric = m.metric AND q.at < m.at"
                    "        ORDER BY q.at DESC LIMIT 1) AS prev_at"
                    " FROM metrics m"
                    f" JOIN (SELECT metric, MAX(at) at FROM metrics"
                    f" WHERE project_id IN ({_marks(pids)})"
                    "       GROUP BY metric) l ON l.metric = m.metric AND l.at = m.at"
                    f" WHERE m.project_id IN ({_marks(pids)})"
                    " ORDER BY m.metric", (*pids, *pids)):
                prev = r["prev_value"]
                out["measurements"].append(
                    {"metric": r["metric"], "unit": r["unit"], "value": r["value"],
                     "at": r["at"], "source": r["source"],
                     "previous": prev, "previousAt": r["prev_at"],
                     "change": None if prev is None else r["value"] - prev})

            for r in conn.execute(
                    "SELECT l.memory_id, l.revision, l.created_at, l.statement, l.why,"
                    "       l.state, l.confidence, l.owner FROM ledger l"
                    + LIVE_LEDGER_JOIN +
                    f" WHERE l.project_id IN ({_marks(pids)}) AND" + LIVE_LEDGER_WHERE +
                    " ORDER BY l.created_at DESC LIMIT ?", (*pids, notes_limit)):
                out["notes"].append(
                    {"memoryId": r["memory_id"], "revision": r["revision"],
                     "createdAt": r["created_at"], "statement": r["statement"],
                     "why": r["why"], "state": r["state"],
                     "confidence": r["confidence"], "owner": r["owner"]})
        except sqlite3.Error as exc:
            out["degraded"].append({"source": "store",
                                    "reason": f"the store is unreadable: {str(exc)[:80]}"})
        finally:
            conn.close()

                                                                             
                                                                                
                                                                            
                                          
                                                                        
                                                                               
                                                                                
                                                                                  
                                                                               
    mine = {project_id}
    for r in out["project"].get("repositories", []):
        mine.add(r.get("id", ""))
        nwo = r.get("nameWithOwner") or ""
        if nwo:
            mine.add(f"clone:{nwo.split('/')[-1]}")
    try:
        doc = json.loads((paths.REGISTRY / "findings.json").read_text(encoding="utf-8"))
        for f in doc.get("findings", []):
            if f.get("acked") or (f.get("subject") or "") not in mine:
                continue
            row = {k: f[k] for k in ("type", "severity", "title", "action") if k in f}
                                                                             
                                                                            
                                                                               
                            
            row["subject"] = f.get("subject")
            row["aboutThisProject"] = f.get("subject") == project_id
            out["findings"].append(row)
    except (ValueError, OSError) as exc:
        out["degraded"].append({"source": "findings",
                                "reason": f"findings.json is unreadable: "
                                          f"{type(exc).__name__}"})
    return out


def credentials(project_id: str) -> dict:
    ""                                                                         

                                                                           
                                                                              
                                                                          
                                                                            
                                                 

                                                                               
                                                                                
                                                                            
                                                                
       
    slug = project_id.split(":", 1)[1] if project_id.startswith("project:") else project_id
    out: dict = {"projectId": f"project:{slug}", "project": slug,
                 "env": [], "vault": [], "degraded": []}

    doc_path = paths.REGISTRY / "env-inventory.json"
    if not doc_path.is_file():
        out["degraded"].append({
            "source": "env-inventory",
            "reason": "registry/env-inventory.json does not exist — `./observatory.py "
                      "env` builds it",
            "effect": "no env file is known for this project, which is not the same "
                      "as it having none"})
    else:
        try:
            doc = json.loads(doc_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            doc = {"files": []}
            out["degraded"].append({
                "source": "env-inventory",
                "reason": f"unreadable: {type(exc).__name__}",
                "effect": "the env half of this answer is empty for a reason that is "
                          "not absence"})
        for f in doc.get("files", []):
            if f.get("project") != slug:
                continue
            for v in f.get("variables", []):
                row = {"name": v["name"], "class": v["class"], "file": f["path"],
                       "kind": f["kind"]}
                if v.get("shared_with"):
                    row["shared_with"] = v["shared_with"]
                if v.get("available_in"):
                    row["available_in"] = v["available_in"]
                out["env"].append(row)

    vault = Path(os.environ.get(
        "OBSERVATORY_VAULT_DIR",
        paths.source_path("secret_store", paths.SECRETS) / "projects")) / slug
    if not vault.parent.is_dir():
        out["degraded"].append({
            "source": "vault",
            "reason": f"{vault.parent} does not exist on this machine",
            "effect": "managed slots are unknown, so a name absent below may still "
                      "exist"})
    elif vault.is_dir():
        for envdir in sorted(p for p in vault.iterdir() if p.is_dir()):
            for slot in sorted(envdir.iterdir()):
                if slot.is_file() and not slot.name.startswith(".") \
                        and slot.name != "meta.json":
                    out["vault"].append({"name": slot.name, "env": envdir.name})

    out["totals"] = {
        "env_variables": len(out["env"]),
        "secrets": sum(1 for r in out["env"] if r["class"] == "secret"),
        "unfilled": sum(1 for r in out["env"]
                        if r["class"] in ("empty", "placeholder")),
        "vault_slots": len(out["vault"]),
    }
    out["use"] = (f"tools/use_secret.py run {slug} <NAME> -- <command>  "
                  "# injects named values and redacts exact matches from captured output; "
                  "not a sandbox against encoded output or network transmission")
    out["never"] = "Do not print a credential value into a transcript or public report."
    return out


def timeline(project_id: str, since: str | None = None, limit: int = 100) -> dict:
                                                                               
                                                                              
                                                                             
                                                                  
                                                                          
                                                                               
                                                                               
                                      
    try:
        conn = store_db.connect()
    except sqlite3.Error as exc:
        return {"projectId": project_id, "since": since, "events": [],
                "degraded": [{"source": "events",
                              "reason": f"the store did not open: "
                                        f"{type(exc).__name__}: {str(exc)[:80]}"}]}
    try:
        pids = ids_for_project(project_id)
        sql = ("SELECT kind, ref, actor, occurred_at, payload_json FROM events"
               f" WHERE project_id IN ({_marks(pids)})")
        args: list = list(pids)
        if since:
            sql += " AND occurred_at >= ?"
            args.append(since)
        sql += " ORDER BY occurred_at DESC LIMIT ?"
        args.append(limit)
                                                                              
                                                                                    
                                                                               
                                                                                
                                                                              
                                                                             
                     
        rows = []
        for r in conn.execute(sql, args):
            try:
                payload = json.loads(r["payload_json"] or "{}")
            except ValueError:
                payload = {}
            rows.append({"kind": r["kind"], "ref": r["ref"], "actor": r["actor"],
                         "occurredAt": r["occurred_at"], "payload": payload})
        try:
            degraded = _identity_warnings(_load('projects.json')['projects'], project_id)
        except (OSError, ValueError, KeyError):
            degraded = []
        if not conn.execute("SELECT 1 FROM events LIMIT 1").fetchone():
            degraded.append({"source": "events",
                             "reason": "the event store is empty; run collectors/scan_events.py"})
        return {"projectId": project_id, "since": since, "events": rows,
                "degraded": degraded}
    except sqlite3.Error as exc:
        return {"projectId": project_id, "since": since, "events": [],
                "degraded": [{"source": "events",
                              "reason": f"the store is unreadable: {str(exc)[:80]}"}]}
    finally:
        conn.close()


def fts_query(query: str) -> str:
    ""                                                                        

                                                                          
                                                                            
                                                                            
                                 

                                                           
                                                           
                                                 
                                                           
                                                             
                                                   

                                                                               
                                                                             
                                                                                    
                                                                       

                                                                               
                                                                          
                                                                             
                                                                              
                           

                                                                                 
                                                                                  
                                                                               
                                                         
       
    terms = [t for t in re.findall(r"[\w'-]+", query, flags=re.UNICODE) if t]
    if not terms:
                                                                                
                                                                                
                                                                          
                                              
        return '""'
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)


                                                                              
                                                                            
                                                                                    
                                                                            
                                                                                 
                                                                               
                                                                
  
                                                                               
                                                                                
                                                                                    
                                                                              
                             
RETRIEVAL_WIDTH = 300


def search(query: str, project_id: str | None = None, limit: int = 10) -> dict:
    ""                                                                           

                                                                            
                                                             

                                                                               
                                                                         
                                                                          
                                                                               
                                                             
       
    import sys as _sys, pathlib as _pathlib
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent / "agent"))
    from store import indexer

    conn = store_db.connect()
    degraded: list[dict] = []
    hits: dict[tuple[str, int], dict] = {}
                                                                                
    vector_order: list[tuple[str, int]] = []
    lexical_order: list[tuple[str, int]] = []
    try:
        have_vec = indexer.load_vec(conn)
                                                                                
        if have_vec:
            try:
                import providers
                from sqlite_vec import serialize_float32
                                                                                
                                                                                 
                                                                      
                                                                          
                                                                                 
                 
                                                                          
                                                                                
                                                                                
                                                    
                stop = providers.check_budget()
                if stop:
                    raise RuntimeError(f"spend guardrail reached — {stop}")
                vec = providers.embed([query])["vectors"][0]
                sql = ("SELECT v.memory_id, v.revision, v.distance FROM ("
                       "  SELECT memory_id, revision, distance FROM vec_notes"
                       "  WHERE embedding MATCH ? ORDER BY distance LIMIT ?) v")
                for r in conn.execute(sql, (serialize_float32(vec), RETRIEVAL_WIDTH)):
                    key = (r["memory_id"], r["revision"])
                    vector_order.append(key)
                    hits[key] = {
                        "memoryId": r["memory_id"], "revision": r["revision"],
                        "distance": round(r["distance"], 6), "matched": ["vector"]}
            except Exception as exc:
                degraded.append({"source": "vector",
                                 "reason": f"{type(exc).__name__}: {exc}"})
        else:
            degraded.append({"source": "vector",
                             "reason": "sqlite-vec is not loadable here"})

                                                                               
                                                                              
        try:
            fts = ("SELECT memory_id, revision, rank FROM search_notes"
                   " WHERE search_notes MATCH ? ORDER BY rank LIMIT ?")
            for r in conn.execute(fts, (fts_query(query), RETRIEVAL_WIDTH)):
                k = (r["memory_id"], r["revision"])
                lexical_order.append(k)
                if k in hits:
                    hits[k]["matched"].append("lexical")
                    hits[k]["rank"] = round(r["rank"], 6)
                else:
                    hits[k] = {"memoryId": r["memory_id"], "revision": r["revision"],
                               "rank": round(r["rank"], 6), "matched": ["lexical"]}
        except sqlite3.Error as exc:
            degraded.append({"source": "lexical", "reason": str(exc)})

                                                                                
                                                                           
                                                                                
                                                                                 
                                                                                   
                                                                        
                                                                                 
                                                                                
                                             
        try:
            lag = conn.execute(
                "SELECT count(*) AS n, min(l.created_at) AS oldest FROM outbox o"
                " JOIN ledger l ON l.memory_id = o.memory_id AND l.revision = o.revision"
                " WHERE o.consumed_at IS NULL").fetchone()
            if lag and lag["n"]:
                since = f", the oldest committed {lag['oldest']}" if lag["oldest"] else ""
                degraded.append({
                    "source": "projection",
                    "reason": f"{lag['n']} committed revision(s) are not indexed yet"
                              f"{since}; this answer cannot include them"})
        except sqlite3.Error as exc:
            degraded.append({"source": "projection", "reason": f"lag unknown: {exc}"})

                                                                                
        out, contested = [], []
        for (mid, rev), h in hits.items():
            row = conn.execute(
                "SELECT l.*, t.memory_id AS tomb FROM ledger l"
                " LEFT JOIN tombstones t ON t.memory_id = l.memory_id"
                " WHERE l.memory_id = ? AND l.revision = ?", (mid, rev)).fetchone()
            if row is None or row["tomb"] is not None:
                continue                                                   
            if project_id and row["project_id"] != project_id:
                continue
            out.append({**h, "projectId": row["project_id"], "state": row["state"],
                        "owner": row["owner"], "confidence": row["confidence"],
                        "statement": row["statement"], "why": row["why"],
                        "createdAt": row["created_at"],
                        "conflictsWith": json.loads(row["conflicts_with_json"] or "[]")})
            if row["state"] == "contested":
                contested.append(mid)
                                                                            
                                                                
                                                                         
                                                                               
                                                                             
                                                                              
                                                                                   
                                                                 
         
                                                                               
                                                                            
                                                                              
                                                                           
                                                                                      
                                                        
        RRF_K = 60
        fused: dict[tuple[str, int], float] = {}
        for ordered in (vector_order, lexical_order):
            for position, key in enumerate(ordered):
                fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + position + 1)
        for h in out:
            h["score"] = round(fused.get((h["memoryId"], h["revision"]), 0.0), 8)
        out.sort(key=lambda h: -h["score"])
        return {"query": query, "projectId": project_id, "count": len(out[:limit]),
                                                                                
                                                                                
                                                                            
                                                                              
                                                                             
                "total": len(out), "truncated": len(out) > limit,
                "results": out[:limit], "contested": contested, "degraded": degraded,
                "note": ("conflicting records are returned together and are not ranked; "
                         "absence from this result is not proof that a record does not "
                         "exist, and `degraded` names every path that could not run")}
    finally:
        conn.close()
