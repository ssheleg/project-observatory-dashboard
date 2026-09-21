#!/usr/bin/env python3
""                                                    

                                                                

                                                                       
                                                                            
                                                                       
                                                                       
                                                                        

                                                                                 
                                                                               
                                                                                   
                                                                                
                                                                                 
                        

                                                                                

                                                                          
                                                                                
                                                                             
             

                                                                              
                                                                           
                                                                               
                                                                            

                                                                                 
                                                                              
                                                                                
                                                                                
                                                                     

                                                                           
                                                                                 
                                                                                  
                                                                            
                       

                                                                          
                                                                             
                                                                              
                                                                                 
                                                                          
                                                         
   
from __future__ import annotations
import json, os, pathlib, shutil, subprocess, sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths                                                                      

                                                                                
                                                                                   
                                                               
LOG = paths.SCRATCH / "store-faults.jsonl"

                                                                             
                                                                              
                                             
READ_TAIL = 200

                                                                           
                                                                    
HOLDER_TIMEOUT_S = 2.0


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _size(p: pathlib.Path) -> int | None:
    try:
        return p.stat().st_size
    except OSError:
        return None


def _holders(db: pathlib.Path) -> tuple[int | None, str]:
    ""                                                                    

                                                                              
                                                                               
                                                            
       
    try:
        p = subprocess.run(["lsof", "-t", str(db)], capture_output=True, text=True,
                           timeout=HOLDER_TIMEOUT_S)
    except FileNotFoundError:
        return None, "lsof is not installed on this machine"
    except subprocess.TimeoutExpired:
        return None, f"lsof did not answer within {HOLDER_TIMEOUT_S:.0f}s"
    except OSError as exc:
        return None, f"lsof could not run: {type(exc).__name__}"
                                                                         
    return len([x for x in p.stdout.split() if x.strip()]), ""


def record(op: str, exc: BaseException | None = None, *, detail: str = "") -> dict | None:
    ""                                                                          

                                                                             
                                                                                  
                                                                             
                             
       
    try:
        db = paths.DB
        holders, holders_why = _holders(db)
        try:
            usage = shutil.disk_usage(db.parent)
            free_bytes, total_bytes = usage.free, usage.total
        except OSError:
            free_bytes, total_bytes = None, None
        row = {
            "at": _iso(),
            "op": str(op)[:60],
            "error": (f"{type(exc).__name__}: {exc}" if exc is not None
                      else str(detail))[:300],
                                                                               
                                                              
            "sqlite_errorname": getattr(exc, "sqlite_errorname", None),
            "sqlite_errorcode": getattr(exc, "sqlite_errorcode", None),
            "db_bytes": _size(db),
            "wal_bytes": _size(db.with_name(db.name + "-wal")),
            "shm_bytes": _size(db.with_name(db.name + "-shm")),
            "free_bytes": free_bytes,
            "total_bytes": total_bytes,
            "holders": holders,
            "pid": os.getpid(),
        }
        if holders is None and holders_why:
            row["holders_why"] = holders_why
        if detail and exc is not None:
            row["detail"] = str(detail)[:200]
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row
    except Exception:                                                               
                                                                                
                                                                                 
                                                                                
                                     
        return None


def recent(days: float = 7.0) -> list[dict]:
    ""                                                             

                                                                                
                                                                      
       
    try:
        lines = LOG.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    out: list[dict] = []
    for line in lines[-READ_TAIL:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        stamp = str(row.get("at") or "")
        try:
            when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
                                                                               
                                                                               
                                                            
            out.append(row)
            continue
        if when.timestamp() >= cutoff:
            out.append(row)
    return out


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="the store's fault history")
    ap.add_argument("--days", type=float, default=7.0)
    args = ap.parse_args(argv)
    rows = recent(args.days)
    if not rows:
        print(f"no store fault recorded in the last {args.days:.0f} day(s) — "
              f"the log begins when the instrument was installed, and the four "
              f"incidents that preceded it live in store/logs/tick.log")
        return 0
    print(f"{len(rows)} store fault(s) in the last {args.days:.0f} day(s)"
          + (f" (the last {READ_TAIL} lines were consulted)"
             if len(rows) >= READ_TAIL else ""))
    for r in rows:
        free = r.get("free_bytes")
        print(f"  {r.get('at')}  {r.get('op'):10} {r.get('sqlite_errorname') or '-':16}"
              f" free {free / 2**30:.2f} GiB" if isinstance(free, int) else
              f"  {r.get('at')}  {r.get('op')}  free unknown")
        print(f"      {r.get('error', '')[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
