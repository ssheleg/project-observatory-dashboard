#!/usr/bin/env python3
""                                                      

                                                                              
                                                                             
                                                                                  
                                                                              
                                                                             
                                                                                 
                                                                               
                                             

                                                                                 
                                                                               
                                                                            
                                                                      
                                                                              
                                                                                  
         

                                                                          
                                                                             
                                                                               
                                                                                
                                                                       

                                                                          
                                                                                
                                                                                
                                                                                
                                                                            
                                                         

                                                                        
                                                                            
                                                                              
                                                                                 
                                                                             
                                                                                
                                                                         
                         

                                                               
   
from __future__ import annotations
import json, pathlib, re, sqlite3, sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths                                                                      
import atomic                                                                     

                                                              
                                                                      
                                                                 
STORE = paths.COMPANION_DB

                                                             
                                                                             
                                                                         
                                            
WINDOW_DAYS = 365


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_index(projects: list[dict]) -> tuple[dict, dict]:
    ""                                                                           

                                                                           
                                                               
       
    index: dict[str, tuple[str, str]] = {}

    def put(key: str, pid: str, rule: str) -> None:
        k = (key or "").strip().lower()
                                                                             
                                                                               
                                  
        if k and k not in index:
            index[k] = (pid, rule)

    for p in projects:
        for folder in p.get("local_folders") or []:
            put(folder, p["id"], "local folder name")
    for p in projects:
        put(p["id"].split(":", 1)[1], p["id"], "project id slug")
    for p in projects:
        put(p.get("name") or "", p["id"], "project name")
                                                                      
                                                                               
                                                                               
                                                                                  
                             
     
                                                                             
                                                                             
             
    try:
        repos = json.loads((paths.REGISTRY / "repositories.json")
                           .read_text(encoding="utf-8"))["repositories"]
        rel = json.loads((paths.REGISTRY / "relations.json")
                         .read_text(encoding="utf-8"))["relations"]
    except (OSError, json.JSONDecodeError, KeyError):
        return index, {}
    owner_of = {r["to"]: r["from"] for r in rel if r["type"] == "implemented_by"}
    for r in repos:
        pid = owner_of.get(r["id"])
        if not pid:
            continue
        put(r["name_with_owner"].split("/")[-1], pid, "repository name")
        folder = (r.get("local") or {}).get("folder")
        if folder:
            put(folder, pid, "repository checkout folder")
    return index, {}


def exclusions() -> tuple[list[tuple[str, str]], dict[str, str]]:
    ""                                                                   

                                                                             
                                                                              
                                                                                
                                                                                
       
    f = paths.config_file('session_name_exclusions.json')
    if not f.is_file():
        return [], {}
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], {}
    shapes = [(r["pattern"], r["id"]) for r in doc.get("shape_rules", [])]
    names = {r["name"].strip().lower(): r["why"] for r in doc.get("names", [])}
    return shapes, names


def excluded(name: str, shapes: list[tuple[str, str]], names: dict[str, str]) -> str | None:
    ""                                                        
    key = (name or "").strip().lower()
    if key in names:
        return f"curated: {names[key][:80]}"
    for pattern, rule_id in shapes:
        if re.match(pattern, key):
            return f"shape {rule_id}"
    return None


def attribute(name: str, index: dict) -> tuple[str | None, str]:
    ""                                               

                                                                                  
                                                                               
                                                                               
                                                                              
                               
       
    key = (name or "").strip().lower()
    if not key:
        return None, "the session carries no project name"
    if key in index:
        pid, rule = index[key]
        return pid, rule
    if "/" in key:
        head = key.split("/", 1)[0]
        if head in index:
            pid, rule = index[head]
            return pid, f"{rule} (first path segment of {name!r})"
    return None, f"{name!r} matches no project folder, id or name"


                                                                             
                                                       
  
                                                                           
                                                                       
                                                                                
                                                                                
               
  
                                                                 
                                                                              
                                               
                                                        
                                                             
                                                                      
                                                    
  
                                                                                
                                                                           
                                                                                
                                                    


def estate_paths(*blobs: str | None) -> set[str]:
    ""                                                             

                                                                     
                                                                              
                                                                              
       
    out: set[str] = set()
    root = str(paths.DATA)
    for blob in blobs:
        for chunk in (blob or "").split("|"):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                items = json.loads(chunk)
            except ValueError:
                items = [chunk]
            if isinstance(items, str):
                items = [items]
            for item in items if isinstance(items, list) else []:
                if isinstance(item, str) and item.startswith(root + "/"):
                                                                               
                                                          
                    out.add(item[len(root) + 1:].split("/", 1)[0])
    return out


def verdict_for(folders: set[str]) -> tuple[str, list[str]]:
    ""                                                            

                                                                               
                                                                          
                                                       
       
    gone = sorted(f for f in folders if not (paths.DATA / f).is_dir())
    if gone:
        return "estate-folder-gone", gone
    if folders:
                                                                             
                                                                             
        return "folder-exists-unmatched", sorted(folders)
    return "no-path-recorded", []


def scan() -> dict:
    projects = json.loads((paths.REGISTRY / "projects.json")
                          .read_text(encoding="utf-8"))["projects"]
    index, _ = build_index(projects)

    degraded: list[dict] = []
    if not STORE.is_file():
        return {"scanned_on": now()[:10], "source": str(STORE), "sessions": [],
                "counts": {"sessions": 0, "projects": 0, "unmatched_names": 0},
                "degraded": [{"source": "claude-mem",
                              "reason": f"{STORE} does not exist, so no session is known; "
                                        f"activity falls back to commits alone"}]}
    try:
        conn = sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        return {"scanned_on": now()[:10], "source": str(STORE), "sessions": [],
                "counts": {"sessions": 0, "projects": 0, "unmatched_names": 0},
                "degraded": [{"source": "claude-mem",
                              "reason": f"the store is unreadable ({exc}); activity falls "
                                        f"back to commits alone"}]}

    cutoff = (datetime.now(timezone.utc).timestamp() - WINDOW_DAYS * 86400) * 1000
    sessions, unmatched = [], {}
    try:
        rows = conn.execute(
            "SELECT memory_session_id AS sid, project, min(created_at) AS started,"
            "       max(created_at) AS ended, count(*) AS prompts"
            " FROM session_summaries"
            " WHERE project IS NOT NULL AND project != ''"
            "   AND created_at_epoch >= ?"
            " GROUP BY memory_session_id, project", (cutoff,)).fetchall()
    except sqlite3.Error as exc:
        conn.close()
        return {"scanned_on": now()[:10], "source": str(STORE), "sessions": [],
                "counts": {"sessions": 0, "projects": 0, "unmatched_names": 0},
                "degraded": [{"source": "claude-mem",
                              "reason": f"the store's shape has moved ({exc}); this collector "
                                        f"reads `session_summaries(memory_session_id, project, "
                                        f"created_at, created_at_epoch)`"}]}
                                                                              
                                                                           
                                                                              
                                                                               
                                                                                
                                                                            
                                                                                 
                                                                               
                                    
     
                                                                                
                                                                                
                                                                               
                                    
    if not rows:
        try:
            total = ev_total = conn.execute(
                "SELECT count(*) FROM session_summaries").fetchone()[0]
        except sqlite3.Error:
            total = ev_total = 0
        if total:
            conn.close()
            return {"scanned_on": now()[:10], "source": str(STORE), "sessions": [],
                    "counts": {"sessions": 0, "projects": 0, "unmatched_names": 0},
                    "window_days": WINDOW_DAYS,
                    "degraded": [{"source": "claude-mem",
                                  "reason": f"the store holds {total} session "
                                            f"summaries and none fell inside the "
                                            f"{WINDOW_DAYS}-day window; the filter has "
                                            f"stopped matching — `created_at_epoch` is "
                                            f"read as milliseconds, and a renamed column "
                                            f"or a changed unit looks exactly like this. "
                                            f"Activity falls back to commits alone"}]}
        del ev_total

                                                                           
                                                                                
                                                                           
                                                                  
    ev_conn = conn

                                                                             
                                                                 
                                                                                  
                                                                              
                                                                             
                                                                               
                                               
    merged: dict[tuple[str, str], dict] = {}
    shapes, names = exclusions()
    skipped: dict[str, str] = {}
    for r in rows:
        pid, rule = attribute(r["project"], index)
        if pid is None:
                                                                               
                                                                            
                                                                           
                                                                              
                                                                                  
                                                   
            why = excluded(r["project"], shapes, names)
            if why:
                skipped[r["project"]] = why
                continue
            u = unmatched.setdefault(r["project"], {"sessions": 0})
            u["sessions"] += 1
            continue
        key = (r["sid"], pid)
        prev = merged.get(key)
        if prev is not None:
            prev["prompts"] += r["prompts"]
            prev["started_at"] = min(prev["started_at"] or "", r["started"] or "") or None
            prev["started_on"] = (prev["started_at"] or "")[:10]
            prev["ended_on"] = max(prev["ended_on"], (r["ended"] or "")[:10])
                                                                                 
                                                                                
                                                                               
                                                                         
                                                                             
                                                                               
                                                                         
                                                                          
                                                                      
            spellings = set(prev["claude_mem_project"].split(" + ")) | {r["project"]}
            prev["claude_mem_project"] = " + ".join(sorted(spellings))
            continue
        merged[key] = {
            "session_id": r["sid"],
            "project_id": pid,
            "claude_mem_project": r["project"],
            "matched_by": rule,
                                                                                
                                                                                
                                                
            "started_on": (r["started"] or "")[:10],
            "ended_on": (r["ended"] or "")[:10],
            "started_at": r["started"],
            "prompts": r["prompts"],
        }
    sessions = list(merged.values())

                                                                                 
                                                                                 
                                                                               
                                                                         
                                                     
     
                                                                                 
                                                             
    for name, u in unmatched.items():
        u["paths"] = set()
        try:
            for row in ev_conn.execute(
                    "SELECT files_read, files_modified FROM observations"
                    " WHERE project = ? AND (files_read LIKE ? OR files_modified LIKE ?)"
                    " LIMIT 200", (name, f"%{paths.DATA}/%", f"%{paths.DATA}/%")):
                u["paths"] |= estate_paths(row["files_read"], row["files_modified"])
        except sqlite3.Error as exc:
                                                                               
                                                                               
                                                                    
            degraded.append({
                "source": "claude-mem",
                "reason": f"the paths behind {name!r} could not be read "
                          f"({type(exc).__name__}: {str(exc)[:60]}), so its verdict "
                          f"is `no-path-recorded` for want of evidence rather than "
                          f"because there is none"})
    if unmatched:
        top = sorted(unmatched.items(), key=lambda kv: -kv[1]["sessions"])[:8]
        degraded.append({
            "source": "claude-mem",
            "reason": f"{len(unmatched)} claude-mem project name(s) match no project here, "
                      f"so {sum(u['sessions'] for u in unmatched.values())} session(s) are "
                      f"unattributed. Largest: "
                      + ", ".join(f"{n} ({u['sessions']})" for n, u in top)})

    ev_conn.close()
    touched = {s["project_id"] for s in sessions}
    return {
        "scanned_on": now()[:10],
        "source": str(STORE),
        "window_days": WINDOW_DAYS,
        "counts": {"sessions": len(sessions), "projects": len(touched),
                   "unmatched_names": len(unmatched),
                   "excluded_names": len(skipped)},
                                                                              
                                                                           
                                                                           
                                                                            
                                                                            
                                                                               
                                                                             
                                                       
        "unattributed": [
            {"name": n, "sessions": u["sessions"],
             "verdict": verdict_for(u["paths"])[0],
             "folders": verdict_for(u["paths"])[1][:6]}
            for n, u in sorted(unmatched.items(), key=lambda kv: -kv[1]["sessions"])],
        "excluded": [{"name": n, "why": w} for n, w in sorted(skipped.items())],
        "sessions": sorted(sessions, key=lambda s: (s["project_id"], s["session_id"])),
        "degraded": degraded,
    }


def to_events(out: dict) -> int:
    ""                                                

                                                                                
                                                                             
                                                                             
                                                                               
                     

                                                                                  
                                                                               
                                                                                
                                                                          
                                                                
       
    from store import db as store_db
    conn = store_db.connect()
    scan_id = store_db.scan_id("sessions", now())
                                                                                
                                                                             
                                                                                
                                                                            
                                                                               
    stale = conn.execute(
        "DELETE FROM events WHERE kind='session' AND ref NOT LIKE '%:project:%'")
    if stale.rowcount:
        print(f"  removed {stale.rowcount} session event(s) written under the old key shape")
    inserted = skipped = 0
    try:
        conn.execute("INSERT INTO scans (id, started_at, collector_version) VALUES (?,?,?)",
                     (scan_id, now(), "scan_sessions/1"))
        for s in out["sessions"]:
            cur = conn.execute(
                "INSERT OR IGNORE INTO events (id, project_id, repo_id, kind, ref, actor,"
                " occurred_at, payload_json) VALUES (?,?,?,?,?,?,?,?)",
                                                                                
                                                                               
                                                                               
                                                                             
                                                                              
                                                                                 
                                                                              
                                                                              
                (f"session:{s['session_id']}:{s['project_id']}", s["project_id"], None,
                 "session", f"{s['session_id']}:{s['project_id']}", "operator",
                 s["started_at"] or s["started_on"],
                 json.dumps({"prompts": s["prompts"], "matchedBy": s["matched_by"],
                             "claudeMemProject": s["claude_mem_project"]},
                            ensure_ascii=False)))
            inserted += cur.rowcount
            skipped += 1 - cur.rowcount
        conn.execute(
            "UPDATE scans SET finished_at = ?, counts_json = ?, degraded_json = ? WHERE id = ?",
            (now(), json.dumps({"sessions_inserted": inserted,
                                "sessions_already_present": skipped,
                                "projects": out["counts"]["projects"],
                                "unmatched_names": out["counts"]["unmatched_names"]}),
             json.dumps(out["degraded"], ensure_ascii=False), scan_id))
        conn.commit()
    finally:
        conn.close()
    print(f"  events: {inserted} new session event(s), {skipped} already present")
    return inserted


def main(argv: list[str]) -> int:
    import configuration
    if not configuration.enabled("sessions"):
        print("sessions: not configured (integration disabled)")
        return 0
    dest = pathlib.Path(argv[1]) if len(argv) > 1 else paths.SCRATCH / "sessions.json"
    out = scan()
    atomic.write_json(dest, out)
    c = out["counts"]
    print(f"{c['sessions']} session(s) across {c['projects']} project(s) -> {dest}")
    if "--no-events" not in argv:
        to_events(out)
    for d in out["degraded"]:
        print(f"  DEGRADED {d['source']}: {d['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
