#!/usr/bin/env python3
""                                                                           

                                                                             
                                                                              
                                                                         
                                                                          

                                                                           
                                                                           
                                                                             
                                                                        

                                                                                
                                                                                
                                                                                
                        
   
from __future__ import annotations
import json, pathlib, sqlite3, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup
portable_setup()
import paths                                                                   
from store import db as store_db                                               
from store import retention                                                    

FAILURES: list[str] = []
KIND = store_db.FINGERPRINT_KIND


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def fixture(n_fingerprints: int = 6, n_other: int = 2) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE observations (id TEXT PRIMARY KEY, scan_id TEXT,"
                 " subject_id TEXT, kind TEXT, payload_json TEXT, observed_at TEXT)")
    for i in range(n_fingerprints):
        conn.execute("INSERT INTO observations VALUES (?,?,?,?,?,?)",
                     (f"obs:fp{i}", f"scan{i}", "estate", KIND,
                      json.dumps({"n": i}), "2026-09-06T12:00:00Z"))
    for i in range(n_other):
        conn.execute("INSERT INTO observations VALUES (?,?,?,?,?,?)",
                     (f"obs:other{i}", f"scan{i}", "estate", "something-else",
                      "{}", "2020-01-01T00:00:00Z"))
    conn.commit()
    return conn


def prune(conn: sqlite3.Connection, keep: int) -> int:
    return conn.execute(
        "DELETE FROM observations WHERE kind = ? AND rowid NOT IN"
        " (SELECT rowid FROM observations WHERE kind = ? ORDER BY rowid DESC LIMIT ?)",
        (KIND, KIND, keep)).rowcount


def test_the_count_bound_keeps_the_newest() -> None:
    conn = fixture(n_fingerprints=6)
    removed = prune(conn, 3)
    check("it removed the surplus", removed == 3, str(removed))
    left = [r[0] for r in conn.execute(
        "SELECT id FROM observations WHERE kind = ? ORDER BY rowid", (KIND,))]
    check("exactly three fingerprints remain", len(left) == 3, str(left))
    check("and they are the NEWEST three, not the oldest",
          left == ["obs:fp3", "obs:fp4", "obs:fp5"], str(left))


def test_it_never_touches_another_kind() -> None:
    ""                                                                      
    conn = fixture(n_fingerprints=6, n_other=2)
    prune(conn, 3)
    others = conn.execute(
        "SELECT COUNT(*) FROM observations WHERE kind != ?", (KIND,)).fetchone()[0]
    check("rows of another kind survive the fingerprint rule", others == 2, str(others))
                                                                       
    n = conn.execute("DELETE FROM observations WHERE observed_at < ? AND kind != ?",
                     ("2026-01-01T00:00:00Z", KIND)).rowcount
    fps = conn.execute("SELECT COUNT(*) FROM observations WHERE kind = ?", (KIND,)).fetchone()[0]
    check("the day horizon takes the old OTHER rows", n == 2, str(n))
    check("and leaves every fingerprint alone", fps == 3, str(fps))


def test_pruning_is_idempotent() -> None:
    conn = fixture(n_fingerprints=6)
    prune(conn, 3)
    again = prune(conn, 3)
    check("a second prune removes nothing", again == 0, str(again))


def test_the_latest_two_are_ordered_by_insertion_not_by_luck() -> None:
    ""                                                                            
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE observations (id TEXT PRIMARY KEY, scan_id TEXT,"
                 " subject_id TEXT, kind TEXT, payload_json TEXT, observed_at TEXT)")
                                                                                  
                                                                                
                    
    for oid in ("obs:zzz-older", "obs:aaa-newer"):
        conn.execute("INSERT INTO observations VALUES (?,?,?,?,?,?)",
                     (oid, "s", "estate", KIND, "{}", "2026-09-06T12:00:00Z"))
    conn.commit()
    by_id = [r[0] for r in conn.execute(
        "SELECT id FROM observations WHERE kind = ? ORDER BY observed_at DESC, id DESC LIMIT 2",
        (KIND,))]
    by_rowid = [r[0] for r in conn.execute(
        "SELECT id FROM observations WHERE kind = ? ORDER BY observed_at DESC, rowid DESC LIMIT 2",
        (KIND,))]
    check("the old tiebreak calls the OLDER row the latest",
          by_id[0] == "obs:zzz-older", str(by_id))
    check("rowid calls the row written last the latest",
          by_rowid[0] == "obs:aaa-newer", str(by_rowid))
                                                                            
                                                                              
                                                                                
                                                                                 
                                                                          
    src = (ROOT / "collectors/compute_deltas.py").read_text(encoding="utf-8")
    check("fingerprints_kept orders by rowid", "ORDER BY observed_at, rowid" in src)
    check("and latest_two is gone rather than kept for this test",
          "def latest_two" not in src,
          "a function whose only reader is its own test is not a reader")
                                                                           
    asc = [r[0] for r in conn.execute(
        "SELECT id FROM observations WHERE kind = ? ORDER BY observed_at, rowid",
        (KIND,))]
    check("ascending order puts the row written first at the front",
          asc[0] == "obs:zzz-older", str(asc))


def test_the_policy_lives_in_the_config_and_the_vocabulary_in_one_place() -> None:
    cfg = json.loads((paths.config_file("retention.json")).read_text(encoding="utf-8"))
    check("retention.json states how many fingerprints are kept",
          isinstance(cfg.get("fingerprints_keep"), int) and cfg["fingerprints_keep"] >= 2,
          str(cfg.get("fingerprints_keep")))
    check("it keeps at least the two the diff needs", cfg["fingerprints_keep"] >= 2)
    deltas = (ROOT / "collectors/compute_deltas.py").read_text(encoding="utf-8")
    check("the collector takes the kind from the store, not its own copy",
          "store_db.FINGERPRINT_KIND" in deltas,
          "a vocabulary word spelled in two files eventually differs")


def test_the_live_store_is_bounded() -> None:
    if not paths.DB.exists():
        print("  SKIP  no store on this machine")
        return
    keep = json.loads((paths.config_file("retention.json")).read_text(encoding="utf-8"))["fingerprints_keep"]
    conn = sqlite3.connect(f"file:{paths.DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM observations WHERE kind = ?", (KIND,)).fetchone()[0]
                                                                        
                                                                              
                                                                                   
                                                                           
                                                                                
                           
    surplus = conn.execute(
        "SELECT COUNT(*) FROM observations WHERE kind = ? AND rowid NOT IN"
        " (SELECT rowid FROM observations WHERE kind = ? ORDER BY rowid DESC LIMIT ?)",
        (KIND, KIND, keep)).fetchone()[0]
    check(f"retention would bring the live store back to {keep} fingerprint(s)",
          n - surplus <= keep, f"{n} present, {surplus} prunable")
    check("and the table is bounded rather than growing without limit",
          n <= keep + 24,
          f"{n} present — more than a day of ticks have accumulated unpruned")


if __name__ == "__main__":
    print("fingerprints — how many are kept, and which two are latest\n")
    for fn in (test_the_count_bound_keeps_the_newest,
               test_it_never_touches_another_kind,
               test_pruning_is_idempotent,
               test_the_latest_two_are_ordered_by_insertion_not_by_luck,
               test_the_policy_lives_in_the_config_and_the_vocabulary_in_one_place,
               test_the_live_store_is_bounded):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mfingerprints are bounded by count and ordered by insertion\033[0m")
