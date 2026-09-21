#!/usr/bin/env python3
""                                                             

                                                                                
                                                                                 
                                                                              
                                                                               
                                                     

                                                                          
                          

                                                                               
                                                                         
                       
                                                                          
                                                                            

                                                                              
                                                                             

                                                                                   
                                       
                                       
                                       
                                                                           

                                                                                
                                                                              
                                                                                
                                                                                
                                          

                                                                            
                                                                        
                                                                               
                                                                             
                                    

                                                                        
                                                                         
   
from __future__ import annotations
import argparse, json, sqlite3, sys, pathlib
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths
from store import db as store_db
from store.db import FINGERPRINT_KIND
from store import indexer
from store import ledger

CONFIG = paths.config_file("retention.json")
APPROVED_BY = "retention"


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def cutoff(days: int) -> str:
    return iso(now() - timedelta(days=days))


                                                                               
                             
def never_states() -> tuple[str, ...]:
    return tuple(config()["ledger"].get("never") or ())


def exempt_owners() -> tuple[str, ...]:
    return tuple(config()["ledger"].get("owner_exempt") or ())


def days_left(owner: str, state: str, created_at: str) -> int | None:
    ""                                                                       

                                                                            
                                                                         
                                                                          
                                                                                 
                                                                               
                                                                        
                                                                                   
              

                                                                           
                                                                                
                                                                        
               
       
    if owner in exempt_owners() or state in never_states():
        return None
    cfg = config()["ledger"]
    horizon = cfg.get(f"{state}_days")
    if horizon is None:
                                                                              
                                                                              
                                            
        return None
    try:
        made = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return int(horizon) - (now() - made).days


def ledger_candidates(conn: sqlite3.Connection) -> list[dict]:
    ""                                                                          
                                                                   
    cfg = config()["ledger"]
    ages = {"proposed": cfg["proposed_days"], "observed": cfg["observed_days"],
            "rejected": cfg["rejected_days"]}
    out = []
    for state, days in ages.items():
        if state in cfg["never"]:
            continue
        rows = conn.execute(
            "SELECT l.memory_id, l.revision, l.state, l.owner, l.created_at,"
            "       substr(l.statement, 1, 70) AS gist"
            " FROM ledger l"
            " JOIN (SELECT memory_id, MAX(revision) r FROM ledger GROUP BY memory_id) m"
            "   ON m.memory_id = l.memory_id AND m.r = l.revision"
            " LEFT JOIN tombstones t ON t.memory_id = l.memory_id"
            " WHERE t.memory_id IS NULL"
            "   AND l.state = ?"
            "   AND l.created_at < ?"
                                                                             
                                                                             
            f"   AND l.owner NOT IN ({','.join('?' * len(cfg['owner_exempt']))})",
            (state, cutoff(days), *cfg["owner_exempt"])).fetchall()
        out += [dict(r, horizon_days=days) for r in rows]
    return out


def volatile_counts(conn: sqlite3.Connection) -> dict:
    cfg = config()
    q = lambda sql, *a: conn.execute(sql, a).fetchone()[0]                  
    return {
        "events past horizon": q("SELECT count(*) FROM events WHERE occurred_at < ?",
                                 cutoff(cfg["events_days"])),
        "observations past horizon": q(
            "SELECT count(*) FROM observations WHERE observed_at < ? AND kind != ?",
            cutoff(cfg["observations_days"]), FINGERPRINT_KIND),
        "fingerprints beyond the last few": q(
            "SELECT count(*) FROM observations WHERE kind = ? AND rowid NOT IN"
            " (SELECT rowid FROM observations WHERE kind = ? ORDER BY rowid DESC LIMIT ?)",
            FINGERPRINT_KIND, FINGERPRINT_KIND, cfg.get("fingerprints_keep", 3)),
        "deltas consumed": q("SELECT count(*) FROM deltas WHERE consumed_at IS NOT NULL"),
                                                                              
                                                                               
                                                                                
                                                                             
                                                                               
                                                                           
        "metrics past horizon": q(
            "SELECT count(*) FROM metrics WHERE at < ? AND rowid NOT IN"
            " (SELECT rowid FROM (SELECT rowid, row_number() OVER"
            "    (PARTITION BY project_id, metric ORDER BY at DESC) rn FROM metrics)"
            "  WHERE rn <= ?)",
            cutoff(cfg.get("metrics_days", 400)),
            cfg.get("metrics_keep_per_series", 2)),
    }


                                                                             
                                                                            
                                                                             
                                                                              
                                                                            
                                                                         
                                                         
NOT_A_PROJECTION = {
    "ledger": "the canon itself. A tombstone marks a revision erased; deleting "
              "the row would destroy the audit trail that says so.",
    "tombstones": "the audit trail. Retention's own record of what it erased and "
                  "who approved it.",
    "outbox": "a queue of POINTERS, no text. The indexer already refuses a "
              "tombstoned revision, so a pending row cannot re-index erased "
              "text — verified in `store/indexer.py`, not assumed.",
}


def projection_tables(conn: sqlite3.Connection) -> list[str]:
    ""                                                                       
                                                                               

                                                                               
                                                                                
                                                                               
                   
       
    out = []
    for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"):
        if name.startswith("sqlite_") or name in NOT_A_PROJECTION:
            continue
        try:
            cols = {c[1] for c in conn.execute(f"PRAGMA table_info({name})")}
        except sqlite3.Error:
            continue
        if {"memory_id", "revision"} <= cols:
            out.append(name)
    return sorted(out)


def scrub(conn: sqlite3.Connection) -> dict:
    ""                                                                          

                                                                            
                                                                           
                                                                           
                                                                                 
                         

                                                                            
                                                                              
                                                                                 
                                                                            
                                                                           
                         
       
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                                                                           
                                                                     
        prior, conn.isolation_level = conn.isolation_level, None
        try:
            conn.execute("VACUUM")
        finally:
            conn.isolation_level = prior
    except sqlite3.Error as exc:
        return {"scrubbed": False,
                "detail": f"the file was NOT compacted: {type(exc).__name__}: "
                          f"{str(exc)[:120]}. The rows are gone from every index "
                          f"and `secure_delete` zeroed what it could reach, but "
                          f"pages freed earlier may still hold text. Re-run "
                          f"`./observatory.py retention-apply` when nothing else "
                          f"is writing."}
    return {"scrubbed": True,
            "detail": "WAL checkpointed and the file vacuumed, so no freed page "
                      "holds erased text"}


def purge_projections(conn: sqlite3.Connection) -> dict:
    ""                                                                          

                                                                             
                                                                              
                                                                            
                                                                                  
                                                                                
                                                   

                                                                              
                                                               
       
                                                                               
                                                                               
                                                                               
                                                                               
                                               
    have_vec = indexer.load_vec(conn)
    pairs = [(r["memory_id"], r["revision"]) for r in
             conn.execute("SELECT memory_id, revision FROM tombstones")]
    receipts = {}
                                                                           
                                                                                 
                                                                                 
                                                          
    tables = projection_tables(conn)
    if "vec_notes" not in tables:
        tables.append("vec_notes")
    for table in sorted(tables):
        if table == "vec_notes" and not have_vec:
                                                                              
                                                                           
                                                          
            receipts[table] = {"status": "UNVERIFIABLE",
                               "detail": "sqlite-vec is not loadable here, so this index "
                                         "cannot be purged or attested"}
            continue
        try:
            before = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        except sqlite3.Error as exc:
            receipts[table] = {"status": "absent",
                               "detail": f"the table does not exist: {str(exc)[:60]}"}
            continue
        removed = 0
        with conn:
            for mid, rev in pairs:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE memory_id = ? AND revision = ?", (mid, rev))
                removed += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        after = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                                                                                
                                                                  
         
                                                                             
                                                                                
                                                                       
                                                                                  
                                                                       
                                                                              
                                                                        
         
                                                                             
                                                                              
                                                                                   
                                                                                 
                      
        left = conn.execute(
            f"SELECT count(*) FROM {table} t JOIN tombstones tb"
            f"   ON tb.memory_id = t.memory_id AND tb.revision = t.revision").fetchone()[0]
        left_record = conn.execute(
            f"SELECT count(*) FROM {table} t WHERE t.memory_id IN"
            f" (SELECT memory_id FROM tombstones)").fetchone()[0]
        receipts[table] = {"status": "purged" if not (left or left_record) else "INCOMPLETE",
                           "before": before, "after": after, "removed": removed,
                           "tombstoned_rows_remaining": left,
                           "tombstoned_records_remaining": left_record}
    return receipts


def report(**fields) -> None:
    ""                                                             

                                                                               
                                                                               
                                                                          
                                                                                
                                          
       
    doc = {"ran_at": iso(), **fields}
    try:
        paths.SCRATCH.mkdir(parents=True, exist_ok=True)
        (paths.SCRATCH / "retention.json").write_text(
            json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        print(f"could not write the retention receipt: {exc}", file=sys.stderr)


def cmd_plan(conn: sqlite3.Connection) -> int:
    cfg = config()
    cands = ledger_candidates(conn)
    print("ledger — would be tombstoned (the row itself is KEPT):")
    if not cands:
        print("    nothing past its horizon")
    for c in cands[:40]:
        print(f"    {c['memory_id']} rev{c['revision']} [{c['state']}] "
              f"owner={c['owner']} age>{c['horizon_days']}d")
        print(f"      {c['gist']}")
    if len(cands) > 40:
        print(f"    … and {len(cands) - 40} more")
    print("\nvolatile — would be deleted outright:")
    for k, v in volatile_counts(conn).items():
        print(f"    {k:<28} {v}")
    exempt = conn.execute(
        "SELECT count(*) FROM ledger WHERE owner IN"
        f" ({','.join('?' * len(cfg['ledger']['owner_exempt']))})",
        tuple(cfg["ledger"]["owner_exempt"])).fetchone()[0]
    protected = conn.execute(
        "SELECT count(*) FROM ledger WHERE state IN"
        f" ({','.join('?' * len(cfg['ledger']['never']))})",
        tuple(cfg["ledger"]["never"])).fetchone()[0]
    print(f"\nexempt regardless of age: {exempt} operator-owned revision(s), "
          f"{protected} in a protected state")
    print("nothing was written — this is `plan`")
    return 0


def cmd_apply(conn: sqlite3.Connection) -> int:
    cands = ledger_candidates(conn)
    cfg = config()
                                                                          
                                                                         
                                                                                
                                                                              
                                                                                
                                                                           
    records = 0
    tombstoned = 0
    for c in cands:
        t = ledger.tombstone(
            conn, c["memory_id"],
            reason=f"retention: {c['state']} older than {c['horizon_days']} days",
            approved_by=APPROVED_BY)
        records += 1
        tombstoned += len(t["revisions"])
                                                                         
                                                                             
                     
    receipts = purge_projections(conn)

    with conn:
        ev = conn.execute("DELETE FROM events WHERE occurred_at < ?",
                          (cutoff(cfg["events_days"]),)).rowcount
                                                                                 
                                                                                
                                                                              
                                                                               
                                                                            
        ob = conn.execute("DELETE FROM observations WHERE observed_at < ? AND kind != ?",
                          (cutoff(cfg["observations_days"]), FINGERPRINT_KIND)).rowcount
        fp = conn.execute(
            "DELETE FROM observations WHERE kind = ? AND rowid NOT IN"
            " (SELECT rowid FROM observations WHERE kind = ? ORDER BY rowid DESC LIMIT ?)",
            (FINGERPRINT_KIND, FINGERPRINT_KIND, cfg.get("fingerprints_keep", 3))).rowcount
        ob += fp
        dl = conn.execute("DELETE FROM deltas WHERE consumed_at IS NOT NULL").rowcount
                                                                              
                                                                               
                                                                       
        mt = conn.execute(
            "DELETE FROM metrics WHERE at < ? AND rowid NOT IN"
            " (SELECT rowid FROM (SELECT rowid, row_number() OVER"
            "    (PARTITION BY project_id, metric ORDER BY at DESC) rn FROM metrics)"
            "  WHERE rn <= ?)",
            (cutoff(cfg.get("metrics_days", 400)),
             cfg.get("metrics_keep_per_series", 2))).rowcount

                                                                            
                                                                         
                      
    removed_any = tombstoned or ev or ob or dl or mt or any(
        r.get("removed") for r in receipts.values())
    scrubbing = (scrub(conn) if removed_any else
                 {"scrubbed": None, "detail": "nothing was removed, so there is "
                                              "nothing to scrub"})

                                                                               
                                                                                
                                                                             
                                                                         
                                                                              
    report(tombstoned=tombstoned, records=records, events=ev, observations=ob,
           deltas=dl, metrics=mt, receipts=receipts, scrub=scrubbing)

    print(f"tombstoned {records} record(s), {tombstoned} revision(s) — every row retained")
    print(f"deleted: {ev} event(s), {ob} observation(s), {dl} consumed delta(s), "
          f"{mt} metric row(s)")
    print(f"file scrub: {scrubbing['detail']}")
    bad: list[str] = []
    if any(r.get("status") != "absent" for r in receipts.values()):
        print("projection purge receipts:")
        for table, r in receipts.items():
            print(f"    {table:<14} {r}")
        bad = [t for t, r in receipts.items()
               if r.get("status") in ("INCOMPLETE", "UNVERIFIABLE")]
    else:
        print("projection purge: no index is present to purge")

                                                                            
                                                                                
                                                                               
                                                                              
                                                                              
                                   
    if scrubbing["scrubbed"] is False:
        print(f"\nTHE BYTES WERE NOT SCRUBBED — {scrubbing['detail']}",
              file=sys.stderr)
        return 1
    if bad:
        print(f"\nAN ERASURE IS NOT COMPLETE — {', '.join(bad)}. A projection either "
              f"still holds a tombstoned revision or cannot be checked at all. "
              f"`./observatory.py deps` installs the vector extension; "
              f"`./observatory.py reindex` rebuilds from canon.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["plan", "apply"])
    a = ap.parse_args()
    conn = store_db.connect()
    try:
        if a.command == "plan":
            return cmd_plan(conn)
        try:
            return cmd_apply(conn)
        except sqlite3.Error as exc:
                                                                              
                                                                             
                                                                               
                                                                                
                                                                               
                                                                           
                                                                     
             
                                                                                
                                                                                
                                          
            report(tombstoned=0, events=0, observations=0, deltas=0, receipts={},
                   scrub={"scrubbed": False,
                          "detail": f"the pass did not complete: "
                                    f"{type(exc).__name__}: {str(exc)[:120]}. "
                                    f"Nothing was scrubbed, and whatever this "
                                    f"pass would have erased is still there."},
                   failed=f"{type(exc).__name__}: {str(exc)[:200]}")
            print(f"retention did not complete: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    import configuration
    if ("apply" in sys.argv) and not configuration.enabled("retention", "features"):
        print("Not configured: enable features.retention explicitly")
        raise SystemExit(0)

    raise SystemExit(main())
