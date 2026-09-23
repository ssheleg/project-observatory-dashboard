#!/usr/bin/env python3
""                                                                     

                                                                        
                                                                              
                                                                            
                                                                            
                                        

                                                                            
                                                                            
                                                                             
              
   
from __future__ import annotations
import pathlib, sqlite3, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup
portable_setup()
import paths                                                                   
from store import migrate                                                      

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def fixture() -> sqlite3.Connection:
    ""                                                                    

                                                                              
                                                                               
                                                                                
                                                                         
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE events (id TEXT PRIMARY KEY, project_id TEXT,"
                 " repo_id TEXT, kind TEXT, ref TEXT, actor TEXT,"
                 " occurred_at TEXT, payload_json TEXT)")
    return conn


def test_the_conversion_preserves_the_instant() -> None:
    cases = [
        ("2026-09-06T23:30:00+02:00", "2026-09-06T21:30:00Z"),
        ("2026-09-06T16:30:00-05:00", "2026-09-06T21:30:00Z"),
        ("2026-09-06T21:30:00Z",      "2026-09-06T21:30:00Z"),                  
        ("2026-09-07T00:30:00+03:00", "2026-09-06T21:30:00Z"),                        
    ]
    for raw, want in cases:
        got = migrate.to_utc_z(raw)
        check(f"{raw} -> {want}", got == want, str(got))
    check("the conversion is idempotent",
          migrate.to_utc_z(migrate.to_utc_z("2026-09-06T23:30:00+02:00")) == "2026-09-06T21:30:00Z")
    check("a timestamp with no zone is refused, not guessed at",
          migrate.to_utc_z("2026-09-06T21:30:00") is None,
          "every writer here stamps a zone; assuming UTC would bury the one that did not")


def test_the_defect_it_exists_for() -> None:
    ""                                                                        
    same = ["2026-09-06T23:30:00+02:00", "2026-09-06T16:30:00-05:00",
            "2026-09-07T00:30:00+03:00", "2026-09-06T21:30:00Z"]
    check("before: the same instant sorts to four different places",
          len(set(same)) == 4 and sorted(same) != [same[3]] * 4)
    after = {migrate.to_utc_z(s) for s in same}
    check("after: the same instant is one value", len(after) == 1, str(after))

    # The shape that actually broke a window: a commit made at 23:30 local on the
    # 6th is 21:30Z on the 6th. Asked for "since the 7th" the raw string answers
    # yes, because "2026-09-06T23:30:00+02:00" > "2026-09-07T00:00:00Z" is FALSE
    # — but "2026-09-07T00:30:00+03:00", the same instant, answers the other way.
    cutoff = "2026-09-07T00:00:00Z"
    raw_a, raw_b = "2026-09-06T23:30:00+02:00", "2026-09-07T00:30:00+03:00"
    check("before: two spellings of one instant fall on opposite sides of a cutoff",
          (raw_a >= cutoff) != (raw_b >= cutoff),
          f"{raw_a} >= cutoff is {raw_a >= cutoff}, {raw_b} is {raw_b >= cutoff}")
    check("after: both fall on the same side",
          (migrate.to_utc_z(raw_a) >= cutoff) == (migrate.to_utc_z(raw_b) >= cutoff))


def test_the_migration_converts_and_is_idempotent() -> None:
    conn = fixture()
    rows = [("a", "2026-09-06T23:30:00+02:00"), ("b", "2026-09-06T16:30:00-05:00"),
            ("c", "2026-09-06T21:30:00Z"), ("d", "2026-09-06T21:29:00")]
    conn.executemany("INSERT INTO events (id, occurred_at) VALUES (?,?)", rows)
    # Every row here is unattributed, which migration 0002 keeps by design: an
    # unattributed checkout is a gap in the registry, not somebody else's work.
    first = migrate.apply(conn)
    check("the migration reports what it did", first and "normalised" in first[0], str(first))
    got = dict(conn.execute("SELECT id, occurred_at FROM events").fetchall())
    check("an offset row is converted", got["a"] == "2026-09-06T21:30:00Z", got["a"])
    check("a negative offset is converted", got["b"] == "2026-09-06T21:30:00Z", got["b"])
    check("a row already in UTC is untouched", got["c"] == "2026-09-06T21:30:00Z", got["c"])
    check("a zone-less row is LEFT ALONE and named", got["d"] == "2026-09-06T21:29:00",
          got["d"])
    check("the refusal is reported, not swallowed", "LEFT ALONE" in first[0], first[0])

    second = migrate.apply(conn)
    check("running it again does nothing", second == [], str(second))
    check("and the rows are unchanged",
          dict(conn.execute("SELECT id, occurred_at FROM events").fetchall()) == got)


def test_a_new_migration_is_applied_once_and_recorded() -> None:
    conn = fixture()
    migrate.apply(conn)
    ran = []
    marker = ("9999-test-only", lambda c: (ran.append(1), "did a thing")[1])
    migrate.MIGRATIONS.append(marker)
    try:
        migrate.apply(conn)
        migrate.apply(conn)
        check("an outstanding migration runs exactly once", len(ran) == 1, f"ran {len(ran)}x")
        row = conn.execute("SELECT note FROM migrations WHERE id='9999-test-only'").fetchone()
        check("its note is recorded beside its id", row and row[0] == "did a thing", str(row))
    finally:
        migrate.MIGRATIONS.remove(marker)


def test_the_live_store_holds_one_spelling() -> None:
    ""                                                                              
    if not paths.DB.exists():
        print("  SKIP  no store on this machine")
        return
    conn = sqlite3.connect(f"file:{paths.DB}?mode=ro", uri=True)
    bad = conn.execute("SELECT COUNT(*) FROM events WHERE occurred_at NOT LIKE '%Z'").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    check("every event in the store is UTC Z", bad == 0, f"{bad} of {total} are not")
    applied = conn.execute(
        "SELECT id FROM migrations WHERE id='0001-events-occurred-at-utc'").fetchone()
    check("the migration is recorded as applied", applied is not None)


def test_the_collector_normalises_at_the_boundary() -> None:
    src = (ROOT / "collectors/scan_events.py").read_text(encoding="utf-8")
    check("scan_events converts before it inserts", "migrate.to_utc_z(iso)" in src,
          "storing %cI verbatim is what created three spellings in one column")


if __name__ == "__main__":
    print("time — one instant, one spelling\n")
    for fn in (test_the_conversion_preserves_the_instant,
               test_the_defect_it_exists_for,
               test_the_migration_converts_and_is_idempotent,
               test_a_new_migration_is_applied_once_and_recorded,
               test_the_live_store_holds_one_spelling,
               test_the_collector_normalises_at_the_boundary):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mtimestamps are one instant in one spelling\033[0m")
