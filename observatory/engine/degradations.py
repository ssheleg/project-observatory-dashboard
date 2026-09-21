#!/usr/bin/env python3
""                                                                            

                                                                                
                                                                               
                                                         

                                                                                
                                                                                
                                                                             
                                                                               
                                                                              
                                                           

                                                                              
                                                                               
                                                                               
                                      
   
from __future__ import annotations
import json

import paths


def collector(name: str) -> list[dict]:
    ""                                                              

                                                                       
                                                                                
                                                                              
                                                                        
       
    f = paths.SCRATCH / name
    if not f.is_file():
        return []
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError):
                                                                               
                                                                       
        return [{"source": name, "reason": "collector output is unreadable"}]
    if isinstance(doc, list):
        return list(doc)
    return list(doc.get("degraded") or [])

                                                                              
                                                                            
                                                                               
                                                                             
                                                                             
         
OWN_READER = {
    "model.json": "tools/build_findings.py builds `model.degraded` with the "
                  "remedy for a `gh` failure and its own deduplication",
}


def every_collector() -> dict[str, list[dict]]:
    ""                                                                      

                                                                              
                                                                               
                                                                              
                                                                            
                                                                            
                                                                         
                                                                            
                                                           

                                                                                
                                                                             
       
    out: dict[str, list[dict]] = {}
    if not paths.SCRATCH.is_dir():
        return out
    for f in sorted(paths.SCRATCH.glob("*.json")):
        if f.name in OWN_READER:
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            out[f.name] = [{"source": f.name,
                            "reason": "collector output is unreadable"}]
            continue
                                                                          
                                                                                 
                                                                            
                           
        if isinstance(doc, dict) and isinstance(doc.get("degraded"), list) and doc["degraded"]:
            out[f.name] = list(doc["degraded"])
    return out
