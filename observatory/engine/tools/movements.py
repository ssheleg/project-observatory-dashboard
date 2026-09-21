#!/usr/bin/env python3
""                                                                             
                                          

                                                                          
                                                                              
                                                                              
                                                                        
                           

                                                                              
                                                                              
                                                                             
                                                                         
                                                                                

                                                                              
                                                                             
                                                                       
                                                                           
                                                                              
                                                                         
   
from __future__ import annotations
import json
import pathlib
import re
from datetime import datetime, timedelta, timezone

                                                                            
                                                 
SECRETISH = re.compile(r"(KEY|TOKEN|SECRET|PASS|DATABASE|DSN|CREDENTIAL|PRIVATE)", re.I)
                                                                           
WINDOW_HOURS = 2
                                  
DAYS = 7


def read_moves(leaks_path: pathlib.Path) -> list[dict]:
    ""                                                                        
                                                                           
                                                           
    moves_file = leaks_path.parent / "movements.jsonl"
    out: list[dict] = []
    for mf in (moves_file, leaks_path):
        if not mf.is_file():
            continue
        try:
            text = mf.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if mf is leaks_path and row.get("event") != "settled":
                continue
            out.append(row)
    return out


def journal_tail(leaks_path: pathlib.Path, limit: int = 30) -> list[dict]:
    ""                                                                     
                                                              
    rows = sorted(read_moves(leaks_path), key=lambda r: r.get("at") or "", reverse=True)[:limit]
    keep = ("at", "event", "secret", "of", "by", "how", "at_provider", "to", "tool")
    return [{k: r.get(k) for k in keep if r.get(k) not in (None, "")} for r in rows]


def _when(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat((stamp or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def recorded(var: str, at: str, moves: list[dict], version=None) -> bool:
    ""                                                                          
                  
    stem = var.split("_")[0].lower()
    if version is not None:
        for mv in moves:
            if f"v{version}" in json.dumps(mv, ensure_ascii=False):
                return True
    when = _when(at)
    if when is None:
        return False
    for mv in moves:
        mat = _when(mv.get("at") or "")
        if mat is None or abs((mat - when).total_seconds()) > WINDOW_HOURS * 3600:
            continue
        blob = json.dumps(mv, ensure_ascii=False).lower()
        if var.lower() in blob or f"/{stem}" in blob or f"{stem}_" in blob:
            return True
    return False


def unrecorded(hk_trail: dict[str, list], moves: list[dict],
               now: datetime | None = None, days: int = DAYS) -> list[dict]:
    ""                                                                         
                                                                                
                                                                           
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[dict] = []
    for app, trail in sorted(hk_trail.items()):
        for rel in trail or []:
            if (rel.get("at") or "") < since:
                continue
            secretish = [v for v in (rel.get("vars") or []) if SECRETISH.search(v)]
            missing = [v for v in secretish if not recorded(v, rel.get("at") or "", moves, rel.get("version"))]
            if missing:
                out.append({"app": app, "version": rel.get("version"), "at": rel.get("at"),
                            "vars": missing, "by": rel.get("by")})
    return out


def describe(row: dict) -> str:
    ""                                                      
    return (f"{row['app']} v{row.get('version')} {(row.get('at') or '')[:16]}Z: "
            f"{', '.join(row['vars'])} ({row.get('by')})")
