#!/usr/bin/env python3
"""Ask SQLite whether the store is structurally sound, and record the answer.

                                                                               
                                                                           
                                                                            
                                                                          
                                                                                   
                             

                                                                    
                                                                               
                                                                              
                                                                                 
                           

                                                                          
                                          

    PRAGMA quick_check         15 / 15 / 15 ms
    PRAGMA integrity_check    204 / 89 / 87 ms      (first run cold)

                                                                          
                                                                           
                                                                                 
                                                                                 
                                                                                   
                                                                             
                      

                                                                          
                                                                               
                                                                                   
                                                                               
                                                                            
                                                                              
                                 

    quick_check       61 ms  ->  malformed inverted index for FTS5 table main.search_notes
    integrity_check   91 ms  ->  malformed inverted index for FTS5 table main.search_notes

                                                                                   
                                                                                
                                                                             
                                                                             
                                                                          
                              

FOUR verdicts, because three of them are not `ok` for different reasons and a
reader acting on them does different things:

    ok           SQLite verified every page and index
    damaged      it opened and the check reported problems — the detail is
                 SQLite's own text
    unopenable   `file is not a database`; a fact about the FILE, and reporting
                 it as a failed integrity check sends a reader looking for a
                 damaged page in something that has no pages
    absent       there is no store yet, which is a fresh clone rather than a fault

    check_store.py            check and write the receipt
    check_store.py --print    also print the verdict
"""
from __future__ import annotations
import argparse, json, pathlib, sqlite3, sys, time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic                                                       # noqa: E402
import paths                                                        # noqa: E402

                                                                           
                                                                            
                                                                               
                                                                                
                                           
PRAGMA = "integrity_check"

#: How many of SQLite's lines to keep. It reports one per problem and a badly
#: damaged file produces thousands; the finding needs enough to name the shape.
MAX_LINES = 8


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def inspect(db: pathlib.Path) -> dict:
    """The verdict, the reason, and what it cost to find out."""
    if not db.is_file():
        return {"verdict": "absent", "detail": f"{db} does not exist",
                "took_ms": 0, "bytes": 0}
    size = db.stat().st_size
    started = time.perf_counter()
    try:
                                                                               
                                                                             
                                  
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return {"verdict": "unopenable", "detail": f"{type(exc).__name__}: {exc}",
                "took_ms": round((time.perf_counter() - started) * 1000, 1),
                "bytes": size}
    try:
        rows = [r[0] for r in conn.execute(f"PRAGMA {PRAGMA}").fetchall()]
    except sqlite3.DatabaseError as exc:
        # `file is not a database` arrives HERE, not at connect: SQLite opens
        # lazily, so the header is read on the first statement.
        return {"verdict": "unopenable", "detail": f"{type(exc).__name__}: {exc}",
                "took_ms": round((time.perf_counter() - started) * 1000, 1),
                "bytes": size}
    finally:
        conn.close()
    took = round((time.perf_counter() - started) * 1000, 1)
    if rows == ["ok"]:
        return {"verdict": "ok", "detail": "", "took_ms": took, "bytes": size}
    kept = rows[:MAX_LINES]
    detail = "; ".join(kept)
    if len(rows) > MAX_LINES:
        detail += f" (+{len(rows) - MAX_LINES} more line(s) not shown)"
    return {"verdict": "damaged", "detail": detail, "took_ms": took, "bytes": size}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", action="store_true", dest="show",
                    help="print the verdict as well as recording it")
    args = ap.parse_args(argv[1:])

    result = inspect(paths.DB)
    doc = {"ran_at": now(), "pragma": PRAGMA, **result}
    try:
        paths.SCRATCH.mkdir(parents=True, exist_ok=True)
        atomic.write_json(paths.SCRATCH / "integrity.json", doc)
    except Exception as exc:                                        # noqa: BLE001
        # NAMED, never fatal. A check that cannot write its receipt has still
        # learned something, and the tick must not stop because a scratch file
        # would not open.
        print(f"the integrity receipt could not be written: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)

    if result["verdict"] == "ok":
        if args.show:
            print(f"store ok — {PRAGMA} in {result['took_ms']:.0f} ms over "
                  f"{result['bytes'] / 1024 ** 2:.1f} MiB")
        return 0
    if result["verdict"] == "absent":
        if args.show:
            print("no store yet — nothing to check, which is a fresh clone "
                  "rather than a fault")
        return 0
    # NON-ZERO, so a person running it by hand learns from the exit code too.
    # The TICK records the step and continues by its own design — a cycle that
    # writes into a suspect store makes it worse, but the collectors' scratch
    # output does not need the store to succeed.
    print(f"store {result['verdict'].upper()}: {result['detail'][:300]}",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
