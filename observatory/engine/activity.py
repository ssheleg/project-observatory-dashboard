#!/usr/bin/env python3
""                                                                               

                                                                               
                                                                                                        
                           
                                                                               
                                                                               
                                                                               
                                                                                
                     

                                                                         
                                                                                 
                                                                                 
                                                                        

                                                                                
                                                                                   
                                                                         
   
from __future__ import annotations
import functools, json, pathlib
from datetime import date, datetime, timezone

import paths
CONFIG = paths.config_file("activity_tiers.json")


@functools.lru_cache(maxsize=1)
def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def tiers() -> list[dict]:
    return config()["tiers"]


def active_window_days() -> int:
    ""                                                                         
                          

                                                                             
                                                                                
                                                                              
                                                                               
                                                                             
               
       
    return int(tiers()[0]["max_days"])


def unknown_id() -> str:
    return config()["unknown_id"]


def tier_ids() -> list[str]:
    return [t["id"] for t in tiers()] + [unknown_id()]


def days_since(last_activity_on: str | None, *, today: date | None = None) -> int | None:
    ""                                                      

                                                                              
                                                                
    if not last_activity_on:
        return None
    try:
        seen = date.fromisoformat(str(last_activity_on)[:10])
    except ValueError:
        return None
    return ((today or datetime.now(timezone.utc).date()) - seen).days


def tier_of(last_activity_on: str | None, *, today: date | None = None) -> str:
    ""                                                                       
                                                                                 
                                                                        
    age = days_since(last_activity_on, today=today)
    if age is None:
        return unknown_id()
    for t in tiers():
        if t["max_days"] is None or age <= t["max_days"]:
            return t["id"]
    return tiers()[-1]["id"]


def describe(tier: str) -> str:
    for t in tiers():
        if t["id"] == tier:
            return t["means"]
    return config().get("unknown_note", "") if tier == unknown_id() else ""


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import paths
    projects = json.loads((paths.REGISTRY / "projects.json")
                          .read_text(encoding="utf-8"))["projects"]
    counts: dict[str, int] = {}
    for p in projects:
        t = p.get("activity_tier") or tier_of(p.get("last_activity_on"))
        counts[t] = counts.get(t, 0) + 1
    for t in tier_ids():
        if counts.get(t):
            print(f"  {t:9} {counts[t]:4}   {describe(t)[:64]}")
