#!/usr/bin/env python3
""                                                                         

                                                                            
                                                                                
                                                                           
                                                                            
                                                                           
                                                                            
                                                                                
                                                                               
                 

                                                                             
                                                                           
                                                                                
                                                                               
                  
   
from __future__ import annotations
import json
from pathlib import Path


def folders(path: str | Path) -> list[dict]:
    ""                                                    
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return doc
    return list(doc.get("folders") or [])


def degraded(path: str | Path) -> list[dict]:
    ""                                                                     
                                                                               
                          
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return []
    return list(doc.get("degraded") or [])
