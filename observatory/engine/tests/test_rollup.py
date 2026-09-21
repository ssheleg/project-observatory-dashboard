#!/usr/bin/env python3
""                                                          

                                                                                  
                                                                                
                                                                              
       

                                                                             
                                                                                
                                                                                
                                                          

                                                                                 
                                                                                 
   
from __future__ import annotations
import pathlib, sqlite3, sys
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup
portable_setup()
from store import rollup                                                        

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def fixture() -> sqlite3.Connection:
    ""                                                   

                                                                              
                                                                               
                                                                             
                                                                                  
                                                                           
                                                                              
                                                                             
       
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
      CREATE TABLE events (id TEXT PRIMARY KEY, project_id TEXT, repo_id TEXT,
        kind TEXT, ref TEXT, actor TEXT, occurred_at TEXT, payload_json TEXT);
    """)
    schema = (ROOT / "store/schema.sql").read_text(encoding="utf-8")
    start = schema.index("CREATE TABLE IF NOT EXISTS project_week")
    end = schema.index(";", schema.index(");", start))
    conn.executescript(schema[start:end + 1])
    return conn


def add(conn, pid: str, day: str, n: int, actor: str = "a") -> None:
    for i in range(n):
        conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
                     (f"commit:{pid}{day}{actor}{i}", pid, "r", "commit", f"{day}{i}",
                      actor, f"{day}T12:00:0{i % 10}Z", "{}"))
    conn.commit()


def test_the_week_key_is_iso_not_sqlites_idea_of_one() -> None:
    ""                                                                           
                                                                                  
                                                          
    week, monday = rollup.week_of("2027-01-01T12:00:00Z")
    check("2027-01-01 falls in 2026-W53", week == "2026-W53", week)
    check("and its Monday is 2026-12-28", monday == "2026-12-28", monday)
    week, monday = rollup.week_of("2026-09-06T12:00:00Z")               
    check("a Sunday belongs to the week that started on Monday",
          monday == "2026-08-31", monday)


def test_it_counts_what_it_says_it_counts() -> None:
    conn = fixture()
    add(conn, "project:x", "2026-09-01", 3, actor="ann")              
    add(conn, "project:x", "2026-09-03", 2, actor="bob")                          
    rollup.refresh(conn, today=date(2026, 9, 7))
    row = conn.execute("SELECT * FROM project_week WHERE project_id='project:x'").fetchone()
    check("one row for the week", row is not None)
    check("commits are summed", row["commits"] == 5, str(row["commits"]))
    check("active days are distinct dates, not commits", row["active_days"] == 2,
          str(row["active_days"]))
    check("authors are distinct actors", row["authors"] == 2, str(row["authors"]))
    check("it is not frozen while the window still covers it", row["frozen_at"] is None)


def test_refreshing_twice_changes_nothing() -> None:
    conn = fixture()
    add(conn, "project:x", "2026-09-01", 4)
    rollup.refresh(conn, today=date(2026, 9, 7))
    before = [tuple(r) for r in conn.execute(
        "SELECT project_id, week, commits, active_days, authors FROM project_week")]
    rollup.refresh(conn, today=date(2026, 9, 7))
    after = [tuple(r) for r in conn.execute(
        "SELECT project_id, week, commits, active_days, authors FROM project_week")]
    check("a second refresh writes the same values", before == after, f"{before} vs {after}")
    check("and does not duplicate the row", len(after) == 1, str(len(after)))


def test_a_partly_covered_week_is_not_written_at_all() -> None:
    ""                                                                            
    conn = fixture()
    add(conn, "project:x", "2026-09-02", 5)
                                                                               
    stats = rollup.refresh(conn, today=date(2026, 9, 7))
    n = conn.execute("SELECT COUNT(*) FROM project_week").fetchone()[0]
    check("with a wide window the week is written", n == 1, str(n))
    check("and the run reports how many partial weeks it skipped",
          "partial_weeks_skipped" in stats, str(stats))


def test_the_aggregate_OUTLIVES_its_events() -> None:
    ""                                   
    conn = fixture()
    old_day = "2025-09-15"                                                 
    add(conn, "project:x", old_day, 7)
    rollup.refresh(conn, today=date(2026, 9, 7))
    row = conn.execute("SELECT commits, frozen_at FROM project_week").fetchone()
    check("the old week is recorded while it is still covered",
          row and row["commits"] == 7, str(tuple(row) if row else None))
    check("and is not frozen yet", row["frozen_at"] is None)

                                                         
    later = date.fromisoformat(old_day) + timedelta(days=400)
    rollup.refresh(conn, today=later)
    row = conn.execute("SELECT commits, frozen_at FROM project_week").fetchone()
    check("the row survives the window moving past it", row["commits"] == 7,
          str(row["commits"]))
    check("and is now frozen", row["frozen_at"] is not None)

                                                                                  
    conn.execute("DELETE FROM events")
    conn.commit()
    rollup.refresh(conn, today=later)
    row = conn.execute("SELECT commits, frozen_at FROM project_week").fetchone()
    check("with every event deleted the aggregate is STILL 7", row["commits"] == 7,
          f"a recompute read no events and would have written 0; got {row['commits']}")
    check("the store can still answer what happened that week",
          conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
          and row["commits"] == 7)


def test_a_frozen_row_is_never_rewritten_even_with_events_present() -> None:
    ""                                                                 
    conn = fixture()
    add(conn, "project:x", "2025-09-15", 7)
    rollup.refresh(conn, today=date(2026, 9, 7))
    later = date(2026, 12, 1)
    rollup.refresh(conn, today=later)                                 
    add(conn, "project:x", "2025-09-16", 99)                                           
    rollup.refresh(conn, today=later)
    row = conn.execute("SELECT commits FROM project_week").fetchone()
    check("a frozen week ignores rows that arrive afterwards", row["commits"] == 7,
          f"{row['commits']} — a frozen answer that still moves is not frozen")


def test_the_horizon_comes_from_the_one_file_that_owns_it() -> None:
    src = (ROOT / "store/rollup.py").read_text(encoding="utf-8")
    check("the rollup reads retention.json rather than its own constant",
          "retention.json" in src or 'RETENTION' in src)
    check("and the collector and pruner read the same one",
          "events_days" in src,
          "three readers, one horizon — the arrangement trap T25 exists to enforce")


if __name__ == "__main__":
    print("rollup — statistics that survive their own source\n")
    for fn in (test_the_week_key_is_iso_not_sqlites_idea_of_one,
               test_it_counts_what_it_says_it_counts,
               test_refreshing_twice_changes_nothing,
               test_a_partly_covered_week_is_not_written_at_all,
               test_the_aggregate_OUTLIVES_its_events,
               test_a_frozen_row_is_never_rewritten_even_with_events_present,
               test_the_horizon_comes_from_the_one_file_that_owns_it):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mthe aggregate outlives the rows it came from\033[0m")
