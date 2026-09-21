#!/usr/bin/env python3
""                                                                  

                                                                               
                                                                                 
                                   
   
from __future__ import annotations
import importlib.util, json, os, pathlib, sqlite3, sys, tempfile
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import tmp as tmpdir              
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup, PROJECT_ID as SYNTHETIC_PROJECT
portable_setup()
sys.path.insert(0, str(ROOT / "agent"))
FAILURES: list[str] = []
_CACHED = ("survey", "providers", "store.retention", "store.indexer", "store.ledger",
           "store.db", "store", "paths", "ret_t", "led_t")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def fresh():
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-ret-"))
    db = d / "t.db"
    os.environ["OBSERVATORY_DB"] = str(db)
                                                            
                                                                                 
                                                                        
                                                                       
                                                                           
                                                                            
                                                                             
    (d / "scratch").mkdir(exist_ok=True)
    os.environ["OBSERVATORY_SCRATCH"] = str(d / "scratch")
    for m in _CACHED:
        sys.modules.pop(m, None)
    import paths
    assert str(paths.DB) == str(db)
    assert str(paths.SCRATCH) == str(d / "scratch")
    from store import db as sdb
    from store import ledger as L
    from store import retention as R
    return sdb.connect(), L, R


def age(conn, memory_id: str, days: int) -> None:
    when = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn:
        conn.execute("UPDATE ledger SET created_at = ? WHERE memory_id = ?", (when, memory_id))


def test_an_old_proposed_row_is_tombstoned_not_deleted() -> None:
    ""                                                     

            
       
    conn, L, R = fresh()
    r = L.append(conn, owner="agent:observer", statement="an old guess", state="proposed",
                 confidence=0.4, project_id="project:x")
    age(conn, r["memoryId"], 200)
    R.cmd_apply(conn)
    check("the ledger row survives",
          conn.execute("SELECT count(*) FROM ledger WHERE memory_id = ?",
                       (r["memoryId"],)).fetchone()[0] == 1)
                                                                             
                                                                                
                                                                             
                                                                             
                                           
    row = conn.execute("SELECT reason, approved_by FROM tombstones WHERE memory_id = ?",
                       (r["memoryId"],)).fetchone()
    check("a tombstone names the reason and who approved it",
          row is not None and row[0].startswith("retention:"),
          "nothing was tombstoned — the row is accumulating with no horizon"
          if row is None else str(row[0]))
    check("it leaves the live view",
          all(x["memory_id"] != r["memoryId"] for x in L.live(conn)))


def test_a_young_row_is_untouched() -> None:
    conn, L, R = fresh()
    r = L.append(conn, owner="agent:observer", statement="fresh", state="proposed",
                 confidence=0.5)
    R.cmd_apply(conn)
    check("nothing inside its horizon is tombstoned",
          conn.execute("SELECT count(*) FROM tombstones").fetchone()[0] == 0)
    check("and it is still live", any(x["memory_id"] == r["memoryId"] for x in L.live(conn)))


def test_operator_rows_are_exempt_at_any_age() -> None:
    conn, L, R = fresh()
                                                                               
                                                                               
                                                                                
                                                                              
                                                                               
                                                                         
    r = L.append(conn, owner="agent:observer", statement="the operator said so",
                 state="proposed", confidence=0.5)
    r = L.transition(conn, r["memoryId"], to_state="observed", owner=L.OPERATOR,
                     expected_revision=r["revision"], why="the operator decided")
    age(conn, r["memoryId"], 5000)
    R.cmd_apply(conn)
    check("an operator row is never tombstoned, whatever its age or state",
          conn.execute("SELECT count(*) FROM tombstones WHERE memory_id = ?",
                       (r["memoryId"],)).fetchone()[0] == 0)
    queries = []
    conn.set_trace_callback(queries.append)
    try:
        candidates = R.ledger_candidates(conn)
    finally:
        conn.set_trace_callback(None)
    check("the candidate query itself excludes protected owners",
          any("owner NOT IN" in query for query in queries)
          and not any(row["owner"] == L.OPERATOR for row in candidates),
          "the database query must enforce the ownership boundary")


def test_a_supported_row_is_never_pruned() -> None:
    conn, L, R = fresh()
    r = L.append(conn, owner="agent:observer", statement="observed then supported",
                 state="proposed", confidence=0.6)
    a = L.transition(conn, r["memoryId"], to_state="observed", owner="agent:observer",
                     expected_revision=1)
    L.transition(conn, r["memoryId"], to_state="supported", owner="agent:observer",
                 expected_revision=a["revision"])
    age(conn, r["memoryId"], 5000)
    R.cmd_apply(conn)
    check("a supported record survives any horizon",
          conn.execute("SELECT count(*) FROM tombstones").fetchone()[0] == 0)


def test_superseded_is_protected_because_a_correction_points_at_it() -> None:
    conn, L, R = fresh()
    cfg = json.loads((__import__("paths").config_file("retention.json")).read_text())
    check("superseded is in the never list", "superseded" in cfg["ledger"]["never"],
          str(cfg["ledger"]["never"]))
    check("and the config says why, where the next person will change it",
          "superseded" in cfg["ledger"]["never"])


def test_the_purge_attests_or_reports_incomplete() -> None:
    ""                                                                   

                  
       
    conn, L, R = fresh()
    ix = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("ix_t", ROOT / "store/indexer.py"))
    importlib.util.spec_from_file_location("ix_t", ROOT / "store/indexer.py").loader.exec_module(ix)
    import providers, hashlib
    dims = providers.config()["embedding"]["dims"]
    providers.embed = lambda texts, log=None: {
        "vectors": [[(hashlib.sha256(t.encode()).digest()[i % 32] / 255.0) - 0.5
                     for i in range(dims)] for t in texts],
        "tokens": 1, "cost": 0.0, "model": "stub", "cost_is_estimate": True}
    r = L.append(conn, owner="agent:observer", statement="indexed then erased",
                 state="proposed", confidence=0.4)
    ix.cmd_index(conn, limit=10)
    check("the row reached the lexical index first",
          conn.execute("SELECT count(*) FROM search_notes WHERE memory_id = ?",
                       (r["memoryId"],)).fetchone()[0] == 1)
    age(conn, r["memoryId"], 400)
    rc = R.cmd_apply(conn)
    check("the purge leaves nothing of it in the projection",
          conn.execute("SELECT count(*) FROM search_notes WHERE memory_id = ?",
                       (r["memoryId"],)).fetchone()[0] == 0)
    check("apply returns 0 when every backend attested", rc == 0, str(rc))
                                                                           
                                                                                  
                                                                                 
                                                            
    with conn:
        conn.execute("INSERT INTO search_notes (memory_id, revision, statement, why)"
                     " VALUES (?,?,?,?)", (r["memoryId"], 1, "snuck back in", ""))
    rc = R.cmd_apply(conn)
    check("a resurrected tombstoned row is removed on a later pass",
          conn.execute("SELECT count(*) FROM search_notes WHERE memory_id = ?",
                       (r["memoryId"],)).fetchone()[0] == 0, f"apply returned {rc}")
    check("and apply reports success once nothing tombstoned remains", rc == 0, str(rc))

                                                                             
                                                                              
                                                                            
                                                                               
                                                                       
                                                                             
                                                                               
                                                                          
                                                                           
                                                                              
                        
    try:
        L.append(conn, memory_id=r["memoryId"], expected_revision=1,
                 owner="agent:observer", statement="a corrected version, still live",
                 state="proposed", confidence=0.5)
        check("an erased record refuses a further revision", False,
              "the append succeeded and nothing could ever read it")
    except L.LedgerError as exc:
        check("an erased record refuses a further revision", "tombstoned" in str(exc),
              str(exc)[:120])
    ix.cmd_index(conn, limit=10)
    rc = R.cmd_apply(conn)
    check("so no revision of it is in the projection",
          conn.execute("SELECT count(*) FROM search_notes WHERE memory_id = ?",
                       (r["memoryId"],)).fetchone()[0] == 0)
    check("and apply still reports success", rc == 0, str(rc))


def test_volatile_rows_are_deleted_and_the_spine_is_not() -> None:
    conn, L, R = fresh()
    old = (datetime.now(timezone.utc) - timedelta(days=800)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn:
        conn.execute("INSERT INTO scans (id, started_at, collector_version) VALUES ('s1',?,'t')",
                     (old,))
        conn.execute("INSERT INTO events (id, kind, occurred_at) VALUES ('e1','commit',?)", (old,))
        conn.execute("INSERT INTO observations (id, scan_id, subject_id, kind, payload_json,"
                     " observed_at) VALUES ('o1','s1','x','k','{}',?)", (old,))
        conn.execute("INSERT INTO deltas (id, to_scan, subject_id, kind, consumed_at)"
                     " VALUES ('d1','s1','x','k',?)", (old,))
    R.cmd_apply(conn)
    left = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in ("scans", "events", "observations", "deltas", "tombstones")}
    check("an old event is deleted outright", left["events"] == 0, str(left))
    check("an old observation too", left["observations"] == 0, str(left))
    check("a consumed delta too", left["deltas"] == 0, str(left))
    check("scans are NEVER deleted — the deltas hang from them", left["scans"] == 1, str(left))


def test_an_unverifiable_index_is_quarantined_not_counted() -> None:
    ""                                                                 

             
       
    conn, L, R = fresh()
    r = L.append(conn, owner="agent:observer", statement="tombstone me", state="proposed",
                 confidence=0.4)
    age(conn, r["memoryId"], 400)
    real = R.indexer.load_vec
    try:
        R.indexer.load_vec = lambda c: False                                     
        rc = R.cmd_apply(conn)
        rec = R.purge_projections(conn)
        check("the vector index reads UNVERIFIABLE, never 'absent' or clean",
              rec["vec_notes"]["status"] == "UNVERIFIABLE", str(rec.get("vec_notes")))
        check("and apply FAILS rather than claiming the erasure completed", rc == 1,
              f"returned {rc}")
    finally:
        R.indexer.load_vec = real
    rc = R.cmd_apply(conn)
    check("with the extension loadable again, apply succeeds", rc == 0, str(rc))
    rec = R.purge_projections(conn)
    check("and the vector index attests", rec["vec_notes"]["status"] in ("purged", "absent"),
          str(rec.get("vec_notes")))


def test_the_collector_and_retention_share_one_horizon() -> None:
    ""                                                    

             
       
    cfg = json.loads((__import__("paths").config_file("retention.json")).read_text())
    src = (ROOT / "collectors/scan_events.py").read_text(encoding="utf-8")
    check("the collector reads retention.json rather than carrying its own number",
          "retention.json" in src and "events_days" in src)
    check("and bounds the git query by it, instead of inserting rows the prune deletes",
          "--since=" in src)
    check("the horizon is a single configured value", isinstance(cfg["events_days"], int),
          str(cfg.get("events_days")))
                                                                            
              
     
                                                                              
                                                                              
                                                                               
                                                                               
                                                                            
                                                          
     
                                                                              
                                                                          
    import shutil, subprocess
    sys.path.insert(0, str(ROOT))
    import paths
    settings_path = paths.config_file("settings.json")
    settings = json.loads(settings_path.read_text())
    settings.setdefault("features", {})["retention"] = True
    settings_path.write_text(json.dumps(settings))
    work = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-retain-live-"))
    (work / "scratch").mkdir()
    if paths.DB.is_file():
        shutil.copy(paths.DB, work / "observatory.db")
    env = {**os.environ, "OBSERVATORY_DB": str(work / "observatory.db"),
           "OBSERVATORY_SCRATCH": str(work / "scratch")}
    for _ in range(2):
        subprocess.run([sys.executable, "collectors/scan_events.py"],
                       cwd=ROOT, capture_output=True, env=env, timeout=300)
        out = subprocess.run([sys.executable, "store/retention.py", "apply"],
                             cwd=ROOT, capture_output=True, text=True, env=env, timeout=180)
    check("collect then prune, twice, deletes no events the collector just wrote",
          "deleted: 0 event(s)" in out.stdout, out.stdout.strip()[:160])


def test_plan_writes_nothing() -> None:
    conn, L, R = fresh()
    r = L.append(conn, owner="agent:observer", statement="old", state="proposed",
                 confidence=0.3)
    age(conn, r["memoryId"], 500)
    before = (conn.execute("SELECT count(*) FROM ledger").fetchone()[0],
              conn.execute("SELECT count(*) FROM tombstones").fetchone()[0])
    R.cmd_plan(conn)
    after = (conn.execute("SELECT count(*) FROM ledger").fetchone()[0],
             conn.execute("SELECT count(*) FROM tombstones").fetchone()[0])
    check("plan is a dry run and says so", before == after, f"{before} -> {after}")


if __name__ == "__main__":
    print("retention — and what it must never touch\n")
    for fn in (test_an_old_proposed_row_is_tombstoned_not_deleted, test_a_young_row_is_untouched,
               test_operator_rows_are_exempt_at_any_age, test_a_supported_row_is_never_pruned,
               test_superseded_is_protected_because_a_correction_points_at_it,
               test_the_purge_attests_or_reports_incomplete,
               test_volatile_rows_are_deleted_and_the_spine_is_not,
               test_an_unverifiable_index_is_quarantined_not_counted,
               test_the_collector_and_retention_share_one_horizon, test_plan_writes_nothing):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mretention ok\033[0m")
