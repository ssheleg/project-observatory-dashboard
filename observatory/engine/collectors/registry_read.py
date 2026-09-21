#!/usr/bin/env python3
""                                                                     

                                                                              
                                                                                 
                                                                           
                                                                                  
                                                                              
                           

                                                                                
                                                                    

                                                                            
                                                                 
                                                                           
                     
                                                                           
                                                                               
                                                                    

                                                                                
                                                                                
                                                  
   
from __future__ import annotations
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths


class RegistryUnreadable(Exception):
    ""                                                                     
                                                                              
               


def read(name: str, key: str) -> list:
    ""                                                                      
    f = paths.REGISTRY / name
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RegistryUnreadable(f"{name} does not exist at {f}")
    except (ValueError, OSError) as exc:
        raise RegistryUnreadable(f"{name} could not be read: {type(exc).__name__}: {exc}")
    if not isinstance(doc, dict) or not isinstance(doc.get(key), list):
        raise RegistryUnreadable(f"{name} has no `{key}` list")
    return doc[key]
