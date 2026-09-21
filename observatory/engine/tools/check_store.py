#!/usr/bin/env python3
""                                                                           

                                                                               
                                                                           
                                                                            
                                                                          
                                                                                   
                             

                                                                    
                                                                               
                                                                              
                                                                                 
                           

                                                                          
                                          

                                              
                                                                    

                                                                          
                                                                           
                                                                                 
                                                                                 
                                                                                   
                                                                             
                      

                                                                          
                                                                               
                                                                                   
                                                                               
                                                                            
                                                                              
                                 

                                                                                          
                                                                                          

                                                                                   
                                                                                
                                                                             
                                                                             
                                                                          
                              

                                                                             
                                            

                                                     
                                                                            
                                  
                                                                               
                                                                            
                                                            
                                                                                  

                                                         
                                                    
   
from __future__ import annotations
import argparse, json, pathlib, sqlite3, sys, time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic                                                                   
import paths                                                                    

                                                                           
                                                                            
                                                                               
                                                                                
                                           
PRAGMA = "integrity_check"

                                                                             
                                                                               
MAX_LINES = 8


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def inspect(db: pathlib.Path) -> dict:
    ""                                                          
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
    except Exception as exc:                                                      
                                                                             
                                                                              
                         
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
                                                                             
                                                                                
                                                                             
                                                
    print(f"store {result['verdict'].upper()}: {result['detail'][:300]}",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
