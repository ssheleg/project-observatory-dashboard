#!/usr/bin/env python3
""                                                                                       

                                                                              
                                                                               
                                                                             
                                                                               
                                                                               

                                                                            
                                                                               
                                                                         
                                                                                 
                                                                             
                                                                                
                                   

                                                    

                                                                            
                                                                                 
                                                                       
                                                                             
                                                                              
                                                                             

                                                                              
                                                                          

                                                                               
                                                                          
                                                                      
                                                                                
                                                                               
                                                                            
                                       

                                                                             
                                                                              
                                                                             
                                                                          
                                                                               
                                                
   
from __future__ import annotations
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths                                                                      

                                                                                
                                                                            
                                                                  
LOG = paths.SCRATCH / "companion-faults.jsonl"

                                                                            
                                                                     
READ_TAIL = 200

                                                                            
                                                                         
FIELDS = ("at", "session", "cwd", "reason", "pid")


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append(row: dict) -> dict | None:
    ""                                                                           

                                                                              
                      
       
    try:
        doc = {k: row.get(k) for k in FIELDS if row.get(k) is not None}
        doc.setdefault("at", _iso())
        doc.setdefault("pid", os.getpid())
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
        return doc
    except Exception:                                                               
                                                                                
                                                                               
                                                                          
        return None


def _tail(lines: list[str]) -> list[str]:
    return [l for l in lines if l.strip()][-READ_TAIL:]


def parse(lines: list[str]) -> list[dict]:
    ""                                                
    out: list[dict] = []
    for line in _tail(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def unreadable(lines: list[str]) -> int:
    ""                                                                       
    n = 0
    for line in _tail(lines):
        try:
            row = json.loads(line)
        except ValueError:
            n += 1
            continue
        if not isinstance(row, dict):
            n += 1
    return n


def read(days: float = 7.0) -> tuple[list[dict], int]:
    ""                                                                      

                                                                                
                                                                               
       
    try:
        lines = LOG.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return [], 0
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    out: list[dict] = []
    for row in parse(lines):
        try:
            when = datetime.strptime(str(row.get("at") or ""), "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            out.append(row)
            continue
        if when.replace(tzinfo=timezone.utc).timestamp() >= cutoff:
            out.append(row)
    return out, unreadable(lines)


def main(argv: list[str]) -> int:
    ""                                                                     
    days = float(argv[1]) if len(argv) > 1 else 7.0
    rows, bad = read(days)
    if not rows and not bad:
        print(f"no lost turns in the last {days:g} days ({LOG})")
        return 0
    for r in rows:
        print(f"{r.get('at', '?'):22} {str(r.get('session') or '?')[:8]:9} "
              f"{r.get('cwd') or '?'}\n{' ' * 32}{r.get('reason') or '?'}")
    print(f"\n{len(rows)} lost turn(s)"
          + (f", and {bad} line(s) could not be read" if bad else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
