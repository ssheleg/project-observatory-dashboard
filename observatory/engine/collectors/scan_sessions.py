#!/usr/bin/env python3
""                                                      

                                                                              
                                                                             
                                                                                  
                                                                              
                                                                             
                                                                                 
                                                                               
                                             

                                                                                 
                                                                               
                                                                            
                                                                      
                                                                              
                                                                                  
         

                                                                          
                                                                             
                                                                               
                                                                                
                                                                       

                                                                          
                                                                                
                                                                                
                                                                                
                                                                            
                                                         

                                                                        
                                                                            
                                                                              
                                                                                 
                                                                             
                                                                                
                                                                         
                         

                                                               
   
from __future__ import annotations
import json, pathlib, re, sqlite3, sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths                                                                      
import atomic                                                                     

#: The store this reads. One path, and it is the plugin's own.
#: Resolved through `paths`, like every other location this repository
#: reads — see `paths.COMPANION_DB` for why it is redirectable.
STORE = paths.COMPANION_DB

#: Sessions older than this are not read. The event window in
#: `store/retention.json` is 365 days, so anything older would be written and
#: then tombstoned on the next retention pass — work for nothing, and a
#: misleading "events grew" in the meantime.
WINDOW_DAYS = 365


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_index(projects: list[dict]) -> tuple[dict, dict]:
    ""                                                                    

                                                                            
                                                                              
       
    strengths = {'local folder name': 0, 'project id slug': 1, 'project name': 2,
                 'repository name': 3, 'repository checkout folder': 4}
    best: dict[str, tuple[int, str, set[str]]] = {}

    def put(key: str, pid: str, rule: str) -> None:
        key = (key or '').strip().lower()
        if not key:
            return
        rank = strengths[rule]
        previous = best.get(key)
        if previous is None or rank < previous[0]:
            best[key] = (rank, rule, {pid})
        elif rank == previous[0]:
            previous[2].add(pid)

    valid = {p['id'] for p in projects}
    for p in projects:
        for folder in p.get('local_folders') or []:
            put(folder, p['id'], 'local folder name')
        put(p['id'].split(':', 1)[1], p['id'], 'project id slug')
        put(p.get('name') or '', p['id'], 'project name')
    try:
        repos = json.loads((paths.REGISTRY / 'repositories.json').read_text(encoding='utf-8'))['repositories']
        rel = json.loads((paths.REGISTRY / 'relations.json').read_text(encoding='utf-8'))['relations']
    except (OSError, json.JSONDecodeError, KeyError):
        repos, rel = [], []
    owners: dict[str, set[str]] = {}
    for r in rel:
        if r['type'] == 'implemented_by' and r['from'] in valid:
            owners.setdefault(r['to'], set()).add(r['from'])
    for r in repos:
        for pid in owners.get(r['id'], set()):
            put(r['name_with_owner'].split('/')[-1], pid, 'repository name')
            put((r.get('local') or {}).get('folder'), pid, 'repository checkout folder')
    index, conflicts = {}, {}
    for key, (_, rule, candidates) in sorted(best.items()):
        ordered = sorted(candidates)
        if len(ordered) == 1:
            index[key] = (ordered[0], rule)
        else:
            conflicts[key] = ordered
            index[key] = (None, f"ambiguous {rule}: {', '.join(ordered)}")
    return index, conflicts


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
    """The reason this name is not a project here, or None."""
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
                    # The estate-relative FOLDER, not the file: the question is
                    # which project this work belonged to.
                    out.add(item[len(root) + 1:].split("/", 1)[0])
    return out


def verdict_for(folders: set[str]) -> tuple[str, list[str]]:
    ""                                                            

                                                                               
                                                                          
                                                       
       
    gone = sorted(f for f in folders if not (paths.DATA / f).is_dir())
    if gone:
        return "estate-folder-gone", gone
    if folders:
        # The folders exist, so the name is an alias for work in a folder the
        # matcher did not connect — a rule to add, not a project to invent.
        return "folder-exists-unmatched", sorted(folders)
    return "no-path-recorded", []


def scan() -> dict:
    projects = json.loads((paths.REGISTRY / "projects.json")
                          .read_text(encoding="utf-8"))["projects"]
    index, conflicts = build_index(projects)

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

    # HELD OPEN for the verdict query below, and closed on the way out. The
    # connection was closed here, so reading the evidence needed either a second
    # open or this line moved; one connection for one read-only pass is the
    # smaller change and the store is opened `mode=ro` either way.
    ev_conn = conn

                                                                             
                                                                 
                                                                                  
                                                                              
                                                                             
                                                                               
                                               
    merged: dict[tuple[str, str], dict] = {}
    shapes, names = exclusions()
    skipped: dict[str, str] = {}
    for r in rows:
        pid, rule = attribute(r["project"], index)
        if pid is None:
            key = r['project'].strip().lower()
                                                                              
                                                                             
            candidates = conflicts.get(key) or conflicts.get(key.split('/', 1)[0])
            if candidates and rule.startswith('ambiguous '):
                u = unmatched.setdefault(r['project'], {'sessions': 0,
                    'candidates': candidates, 'reason': rule, 'session_ids': set()})
                u['sessions'] += 1
                u['session_ids'].add(r['sid'])
                continue
            # TWO outcomes, not one. A name the operator has classified as "not
            # a project here" is skipped with its reason on record; anything
            # else is UNKNOWN WORK and becomes a finding. Reporting both as
            # "unmatched" is what makes a list of eighteen names — thirty of
            # whose sessions are a plugin's own version folders — read as noise,
            # and a noisy list is one nobody opens.
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
            # `spellings`, not `names`: this used to rebind `names`, which is the
            # EXCLUSION dictionary passed to `excluded()` below. After the first
            # session that spanned two claude-mem names, every later lookup ran
            # against a set of project strings instead — so the curated
            # exclusions silently stopped applying and the home folder landed in BOTH
            # buckets, excluded once and reported twelve times. A pure function
            # returning two answers for one argument is how the shadowing
            # showed itself; the invariant that catches it is that the two
            # buckets can never share a name (tests/test_sessions.py).
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
            # NAMED, never silently empty: a shape change here would make every
            # lost project read as "no path recorded", which is the answer this
            # whole classification exists to stop being the default.
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
            "reason": f"{len(unmatched)} claude-mem project name(s) cannot be attributed to one project here, "
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
        # The unknown names and their weight, so `tools/build_findings.py` can
        # raise them without re-reading claude-mem. Sorted by sessions: the
        # question a finding answers is "how much work is unaccounted for".
        # THE VERDICT TRAVELS WITH THE COUNT. A name that matches nothing is
        # three different facts — a project this estate lost, a folder the
        # matcher failed to connect, or a name with no path evidence at all —
        # and the finding could not tell them apart because the collector did
        # not carry what distinguishes them.
        "unattributed": [
            {"name": n, "sessions": u["sessions"],
             "verdict": 'ambiguous-project' if u.get('candidates') else verdict_for(u["paths"])[0],
             "folders": verdict_for(u["paths"])[1][:6],
             **({'candidates': u['candidates'], 'reason': u['reason'],
                 'session_ids': sorted(u['session_ids'])} if u.get('candidates') else {})}
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
    # Session events are a DERIVED stream, rebuildable from claude-mem, so a key
    # change is a rewrite rather than a migration. Rows written under the old
    # `ref = session_id` are removed here; without this the store would hold two
    # key shapes for one fact and every count of them would be wrong. Stated
    # rather than done quietly, because deleting measured rows is not a detail.
    stale = conn.execute(
        "DELETE FROM events WHERE kind='session' AND ref NOT LIKE '%:project:%'")
    if stale.rowcount:
        print(f"  removed {stale.rowcount} session event(s) written under the old key shape")
    inserted = skipped = withdrawn = 0
    try:
                                                                           
                                                                               
                                                                              
        supported = {(s['session_id'], s['project_id']) for s in out['sessions']}
        ambiguous = {(sid, pid) for row in out.get('unattributed', [])
                     if row.get('verdict') == 'ambiguous-project'
                     for sid in row.get('session_ids', [])
                     for pid in row.get('candidates', [])}
        for sid, pid in sorted(ambiguous - supported):
            withdrawn += conn.execute("DELETE FROM events WHERE kind='session' AND ref=?",
                                      (f'{sid}:{pid}',)).rowcount
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
                                "sessions_ambiguous_withdrawn": withdrawn,
                                "projects": out["counts"]["projects"],
                                "unmatched_names": out["counts"]["unmatched_names"]}),
             json.dumps(out["degraded"], ensure_ascii=False), scan_id))
        conn.commit()
    finally:
        conn.close()
    print(f"  events: {inserted} new session event(s), {skipped} already present, "
          f"{withdrawn} ambiguous attribution(s) withdrawn")
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
