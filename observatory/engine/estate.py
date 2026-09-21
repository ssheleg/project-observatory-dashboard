#!/usr/bin/env python3
""                                                     

                                                                               
                                                                                     
                                                                              
                                                                                 
                                                                             
                                                                 

                                                                           
                                                                                   
                                                                            
                                                                               
            

                                                                     
                                                                             
                                                                         
   
from __future__ import annotations

                                                                     
                                                                                
                                                                                 
                                  
  
                                                                           
                                                                        
                                                                                
                                                                             
                                                                           
                                                                             
                                                                                 
                                                                                
                                          
RECORDED_OWNERSHIP = frozenset({"owned", "work-bitbucket", "local-only"})


def records_events(ownership: str | None) -> bool:
    ""                                                         

                                                                              
                                                                               
                                                
    return ownership is None or ownership in RECORDED_OWNERSHIP


def why_excluded(ownership: str) -> str:
    return (f"ownership {ownership!r}; only {sorted(RECORDED_OWNERSHIP)} are recorded — "
            "a third-party clone's commits are somebody else's history")


def undeclared_owner_reason(owners: list[str], repos: int, checked_out: int) -> str:
    ""                                                                        

                                                                            
                                                                           
                                                                                 
                                                                            
                                   

                                                                             
                                                                               
                                                                     
                                                                                  
                                                                                 
                                                                            
                                                                          
                                                                         

                                                                      
                                                                              
                
       
    who = ", ".join(owners)
    head = (f"the GitHub listing returned {repos} repositor"
            f"{'y' if repos == 1 else 'ies'} under {who}, which OWNED_ORGS in "
            f"collectors/merge.py does not declare, so their projects are "
            f"reported as `external`")
    if checked_out:
        cost = (f". {checked_out} of them {'is' if checked_out == 1 else 'are'} "
                f"cloned on this machine, so work in "
                f"{'it' if checked_out == 1 else 'them'} is observed and then "
                f"dropped: `estate.records_events` refuses the commits and the "
                f"companion's recorder declines the session")
    else:
        cost = (". None of them is cloned here, so no session is being lost and "
                "the effect is classification only")
    ask = ("Add the organisation to OWNED_ORGS if it is yours"
           if len(owners) == 1 else
           "Add them to OWNED_ORGS if they are yours")
    return (head + cost + f". {ask} — that is an operator's decision, not "
            "a collector's")


                                                                                                                                                                 
 
                                                                               
                                                                              
                                                                              
  
                                                                             
                                                                              
                                                                                
                                                                        
                                                                                 
                                                                                  
                                   
  
                                                                           
                                                                               
                                                                           
                                                                               
                                                                             
                                                                              
                                                                         
ROUTINE_DELTA_KINDS = frozenset({
    "commits-changed", "dirty-changed", "last_activity_on-changed",
})

                                                                            
                                                                          
                                                                              
                                                            
_RANK = {"structural": 0, "unclassified": 1, "routine": 2}


def conclusion_class(evidence_json: str | None) -> str:
    ""                                                                       

                                                                             
                                                                               
                                                                               
                                                                            
                                                                              
                                                     

                                                                  
                                    

                                                                    
                                                                
                               
       
    import json as _json
    try:
        items = _json.loads(evidence_json or "[]")
    except (ValueError, TypeError):
        return "unclassified"
    if not isinstance(items, list) or not items:
        return "unclassified"
    kinds = set()
    for it in items:
        if isinstance(it, dict):
            k = str(it.get("kind") or "").strip()
            if k and k != "?":
                kinds.add(k)
    if not kinds:
        return "unclassified"
    return "routine" if kinds <= ROUTINE_DELTA_KINDS else "structural"


def conclusion_rank(klass: str) -> int:
    ""                                                                       
    return _RANK.get(klass, max(_RANK.values()) + 1)


                                                                                                                               
 
                                                                               
                                                                                 
                                                                                
                                                                            
                                                                             
                                                                           
 
                                                                              
 
                                                           
                                         
                                                               
 
                                                                              


                                                                              
                                                                  
  
                                                                                
                                                                          
                                                                                  
                                                                                 
                                                                         
                                                                               
                                                   
  
                                                                               
                                                                              
                           
ONE_PER_DAY_WRITERS = frozenset({
    ("observation", "agent:observer"),
})


def residue_key(record: dict) -> tuple:
    ""                                          

                                                                                
                                                                             
                                                      
       
    stamp = record.get("created_at")
    day = str(stamp)[:10] if isinstance(stamp, str) and len(str(stamp)) >= 10 else None
    if day is None:
        return ("__undated__", record.get("memory_id"))
    return (record.get("project_id"), record.get("kind"), record.get("owner"), day)


def fold_groups(records: list[dict]) -> list[dict]:
    ""                                                                         

                                                                                   
                                                                                 
                                                                                
                                                                        

                                                                               
                                                                                 
                                                                                   
                                                                                
              

                                                                           
                                                                                  
                                                                             
                                                                             
                         
       
    buckets: dict[tuple, list[dict]] = {}
    for r in records:
        buckets.setdefault(residue_key(r), []).append(r)
    out: list[dict] = []
    for key, group in buckets.items():
        if len(group) < 2 or key[0] == "__undated__":
            continue
                                                                       
        if (key[1], key[2]) not in ONE_PER_DAY_WRITERS:
            continue
        ordered = sorted(group, key=lambda r: (str(r.get("created_at") or ""),
                                               int(r.get("revision") or 0),
                                               str(r.get("memory_id") or "")))
        keep = ordered[-1]
        out.append({"key": key, "keep": keep.get("memory_id"),
                    "fold": [r.get("memory_id") for r in ordered[:-1]]})
    return sorted(out, key=lambda g: (str(g["key"][0]), str(g["key"][-1])))
