#!/usr/bin/env python3
""                                                                    

                                                                              
                                                                               
                                                                         
                                                                           
                                                                        
                                                                             
                                                                            
         

                                                                              
                                                                            
                                                                             
                                                

                                                                             
                                                                               
                                                         

                                                      
                                                        
   
from __future__ import annotations
import pathlib, sqlite3, sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths              

                                                                              
                                                                            
KEEP = 3
PREFIX = "observatory.db.backup-"


                                                                             
                                                                              
                                                                                
                                                               
COMPANIONS = ("-wal", "-shm", "-journal")


def existing(store: pathlib.Path) -> list[pathlib.Path]:
    ""                                                                                
    return sorted((p for p in store.glob(PREFIX + "*")
                   if not p.name.endswith(COMPANIONS)), reverse=True)


def take(db: pathlib.Path, stamp: str) -> pathlib.Path:
    dest = db.parent / f"{PREFIX}{stamp}"
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    return dest


def main(argv: list[str]) -> int:
    db = paths.DB
    store = db.parent
    if "--list" in argv:
        rows = existing(store)
        if not rows:
            print("no backup exists — the store's history lives on one disk in one file")
            return 0
        for p in rows:
            print(f"  {p.name}  {p.stat().st_size / 1e6:.1f} MB")
        return 0
    if not db.is_file():
                                                                             
                                                                           
                                 
        print("no store to back up", file=sys.stderr)
        return 0
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
                                                                               
                                                          
    if (store / f"{PREFIX}{stamp}").exists():
        print(f"backup {stamp} already exists")
        return 0
    dest = take(db, stamp)
    size = dest.stat().st_size
    if size == 0:
        dest.unlink()
        print("the backup came out empty and was removed; nothing was pruned",
              file=sys.stderr)
        return 1
                                                                            
                                                    
    dropped = []
    for old in existing(store)[KEEP:]:
                                                                            
                                                       
        for suffix in ("",) + COMPANIONS:
            companion = old.with_name(old.name + suffix)
            if companion.exists():
                companion.unlink()
        dropped.append(old.name)
    print(f"backup {dest.name}: {size / 1e6:.1f} MB, "
          f"{len(existing(store))} kept" + (f", pruned {len(dropped)}" if dropped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
