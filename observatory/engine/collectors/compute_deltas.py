#!/usr/bin/env python3
""                                                                              

                                                                                  
                                                                            

                                                                              
                                                                                
                                      

                                                                                                                                
                                                                                
                                                                                   

                                                                     

                                                 
                                             
   
from __future__ import annotations
import argparse, json, sys, pathlib, uuid
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths
from collectors import registry_read
from store import db as store_db

                                                                            
                                                       
RegistryUnreadable = registry_read.RegistryUnreadable

KIND = store_db.FINGERPRINT_KIND                                      
COLLECTOR_VERSION = "compute_deltas/1"

                                                                                
                                                        
FIELD_MEANING = {
    "repos": "the set of repositories implementing it changed",
    "last_activity_on": "work happened",
    "lifecycle": "it was archived or revived",
    "ownership": "who owns it changed",
    "sites": "a public surface appeared or disappeared",
    "stack": "the technology it is built on changed",
    "vault_notes": "the wiki gained or lost notes about it",
    "dirty": "uncommitted work appeared or was resolved",
    "commits": "commits were recorded",
    "name": "it was renamed",
}

                                                                              
                                                                 
LIFECYCLE_MEANING = {
    "project-appeared": "the estate gained a project the previous scan did not hold",
    "project-disappeared": "a project the previous scan held is gone — deleted, "
                           "renamed, or its anchor withdrawn",
}


def meaning_of(kind: str) -> str:
    ""                                            

                                                                            
                                                                                 
                                                                               
                                                                            
                                  
    if kind in LIFECYCLE_MEANING:
        return LIFECYCLE_MEANING[kind]
    return FIELD_MEANING.get(kind[:-len("-changed")] if kind.endswith("-changed") else kind, "")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprints(conn) -> dict[str, dict]:
    projects = registry_read.read("projects.json", "projects")
    repos = {r["id"]: r for r in registry_read.read("repositories.json", "repositories")}
    members: dict[str, list[str]] = {}
    for rel in registry_read.read("relations.json", "relations"):
        if rel["type"] == "implemented_by":
            members.setdefault(rel["from"], []).append(rel["to"])
    commits = {r["project_id"]: r["n"] for r in conn.execute(
        "SELECT project_id, count(*) AS n FROM events WHERE kind='commit'"
        " AND project_id IS NOT NULL GROUP BY project_id")}
    out = {}
    for p in projects:
        ids = sorted(members.get(p["id"], []))
        dirty = sum((repos[i].get("local") or {}).get("uncommitted_files", 0)
                    for i in ids if i in repos)
        out[p["id"]] = {
            "name": p["name"],
            "repos": [i.split(":", 1)[1] for i in ids],
            "last_activity_on": p.get("last_activity_on", ""),
            "lifecycle": p.get("lifecycle", ""),
            "ownership": p.get("ownership", ""),
            "sites": sorted(s["host"] for s in p.get("sites", [])),
            "stack": sorted(p.get("stack", [])),
            "vault_notes": p.get("vault_notes", 0),
            "dirty": dirty,
            "commits": commits.get(p["id"], 0),
        }
    return out


                                                                                
                                                                    
CURSOR = "deltas.diffed_through"


def diffed_through(conn) -> str | None:
    row = conn.execute("SELECT value FROM cursors WHERE name = ?", (CURSOR,)).fetchone()
    return row[0] if row else None


def remember(conn, scan_id: str) -> None:
    conn.execute("INSERT INTO cursors (name, value, updated_at) VALUES (?,?,?)"
                 " ON CONFLICT(name) DO UPDATE SET value = excluded.value,"
                 " updated_at = excluded.updated_at", (CURSOR, scan_id, now()))


def fingerprints_kept(conn) -> list:
    ""                                                                        

                                                                        
                                                                                    
                                                                           
                                                                        
                                                                            
                                                                            
                                                                            
                                                                                 

                                                                               
                                                           
    return list(conn.execute(
        "SELECT id, scan_id, payload_json, observed_at FROM observations"
        " WHERE kind = ? ORDER BY observed_at, rowid", (KIND,)))


def cmd_snapshot(conn) -> int:
                                                                                 
                                                                          
                                                                                
                                                                              
    scan_id = store_db.scan_id("fingerprint", now())
    fp = fingerprints(conn)
    with conn:
        conn.execute("INSERT INTO scans (id, started_at, finished_at, collector_version,"
                     " counts_json) VALUES (?,?,?,?,?)",
                     (scan_id, now(), now(), COLLECTOR_VERSION,
                      json.dumps({"projects": len(fp)})))
        conn.execute("INSERT INTO observations (id, scan_id, subject_id, kind, payload_json,"
                     " observed_at) VALUES (?,?,?,?,?,?)",
                     (f"obs:{uuid.uuid4().hex[:16]}", scan_id, "estate", KIND,
                      json.dumps(fp, ensure_ascii=False, sort_keys=True), now()))
    print(f"fingerprinted {len(fp)} projects as {scan_id}")
    return 0


def pair(conn) -> tuple[object, object, list[str], int]:
    ""                                                             

                                                                                
                                                                          

                                                                              
                                                                                
                                                                           
                                                                               
                                                                                
                                                                             
                                                                           
                                                                          
                                                                      
                                                                               
                                                   

                                                                                 
                                                                           
                                                                              
                                                                               
                                                                                
                                                      

                                                                               
                                   
       
    kept = fingerprints_kept(conn)
    notes: list[str] = []
    if not kept:
        return None, None, ["no fingerprint on record"], 0
    to_row = kept[-1]
    through = diffed_through(conn)
    if through == to_row["scan_id"]:
        return None, to_row, ["already diffed through this fingerprint"], 0
    if len(kept) == 1:
        return None, to_row, ["only one fingerprint on record"], 0
    by_scan = {r["scan_id"]: i for i, r in enumerate(kept)}
    if through is None:
                                                                                  
                                                                                
                                                                          
                                                                                
                                                                                 
                                                                        
        from_row = kept[0]
    elif through in by_scan:
        from_row = kept[by_scan[through]]
    else:
                                                                                
                                                                             
                                                                                 
                                                                              
                                                                                
               
        from_row = kept[0]
        notes.append(f"the last diffed fingerprint ({through}) has been pruned; "
                     f"comparing from the oldest one still kept ({from_row['scan_id']}) — "
                     f"changes before it are not recoverable")
    folded = by_scan[to_row["scan_id"]] - by_scan[from_row["scan_id"]] - 1
    if folded > 0:
        notes.append(f"{folded} intermediate fingerprint(s) were never diffed; their "
                     f"changes are folded into this comparison rather than lost")
    return from_row, to_row, notes, folded


def cmd_diff(conn) -> int:
    old, new, notes, folded = pair(conn)
    if new is None:
        print("no fingerprint yet — run `snapshot` first", file=sys.stderr)
        return 1
    if old is None:
        print(notes[0] if notes else "nothing to compare against yet")
        print(f"{conn.execute('SELECT count(*) FROM deltas WHERE consumed_at IS NULL')
                .fetchone()[0]} unconsumed delta(s) waiting for the agent")
        return 0
    for note in notes:
        print(f"  NOTE: {note}")
    a = json.loads(old["payload_json"])
    b = json.loads(new["payload_json"])

    written = 0
    with conn:
        for pid in sorted(set(a) | set(b)):
            before, after = a.get(pid), b.get(pid)
            if before == after:
                continue
            if before is None:
                kinds = [("project-appeared", None, after)]
            elif after is None:
                kinds = [("project-disappeared", before, None)]
            else:
                                                                             
                                                                        
                                                                     
                                                                            
                                                                          
                                                                                 
                                                                              
                                                          
                 
                                                                          
                                                                               
                                                                              
                                      
                kinds = [(f"{f}-changed", before.get(f), after.get(f))
                         for f in sorted(set(before) | set(after))
                         if before.get(f) != after.get(f)]
            for kind, was, is_ in kinds:
                conn.execute(
                    "INSERT INTO deltas (id, from_scan, to_scan, subject_id, kind,"
                    " before_json, after_json) VALUES (?,?,?,?,?,?,?)",
                    (f"delta:{uuid.uuid4().hex[:16]}", old["scan_id"], new["scan_id"], pid,
                     kind, json.dumps(was, ensure_ascii=False),
                     json.dumps(is_, ensure_ascii=False)))
                written += 1
                                                                            
                                                                                
                                                                            
                                                                 
        remember(conn, new["scan_id"])
    pending = conn.execute(
        "SELECT count(*) FROM deltas WHERE consumed_at IS NULL").fetchone()[0]
    print(f"{written} delta(s) written between {old['scan_id']} and {new['scan_id']}"
          + (f", folding {folded} intermediate generation(s)" if folded > 0 else ""))
    print(f"{pending} unconsumed delta(s) waiting for the agent")
    if written == 0:
        print("nothing moved — the agent will not be called, and that costs nothing")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["snapshot", "diff", "pending"])
    args = ap.parse_args()
    conn = store_db.connect()
    try:
        if args.command == "snapshot":
                                                                             
                                                                                 
                                                                          
                                                                       
            try:
                return cmd_snapshot(conn)
            except RegistryUnreadable as exc:
                print(f"NOT fingerprinted — {exc}", file=sys.stderr)
                print("The registry is the subject of this measurement; a snapshot "
                      "taken without it would read as an estate that lost every "
                      "project.", file=sys.stderr)
                return 1
        if args.command == "diff":
            return cmd_diff(conn)
                                                                           
                                                                               
                                                                                
                                                                      
        CAP = 60
        total = conn.execute(
            "SELECT count(*) FROM deltas WHERE consumed_at IS NULL").fetchone()[0]
        rows = list(conn.execute(
            "SELECT subject_id, kind, before_json, after_json FROM deltas"
            " WHERE consumed_at IS NULL ORDER BY subject_id LIMIT ?", (CAP,)))
        for r in rows:
            print(f"  {r['subject_id']:<48} {r['kind']:<26} "
                  f"{r['before_json'][:40]} -> {r['after_json'][:40]}")
        print(f"{len(rows)} shown of {total} unconsumed"
              + (f" — {total - len(rows)} not listed, capped at {CAP}"
                 if total > len(rows) else ""))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
