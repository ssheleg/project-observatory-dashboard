#!/usr/bin/env python3
""                                                                   

                                                              
                                                                              
                                                                        
                                                                               
                                                                              
                                                                           
                

                                                         

                                                                                      
                                                                                      
                                                                                      

                                                                            
                                                                                 
                                                        

                                                                             
                                                                               
                                                                                 
                                                     

                                                            
                                                                             
                                             

                                                                                
                                                               
                                                                               
                               
   
from __future__ import annotations
import re

                                                                             
                                                                               
                                                                  
LOCAL_PREFIX = "local-"


def slug(s: str) -> str:
    ""                                                                      
                                                 
    return re.sub(r"[^a-z0-9.-]+", "-", s.lower()).strip("-")


def local_key(folder: str) -> str:
    ""                                                                      
    return slug(LOCAL_PREFIX + folder)


def local_id(folder: str) -> str:
    ""                                                          
    return "project:" + local_key(folder)


def former_ids(project: dict) -> list[str]:
    ""                                                                 

                                                                                
                                                                  
       
    if (project.get("anchor") or "") == "local-folder":
        return []
    own = project.get("id") or ""
    out = []
    for folder in project.get("local_folders") or []:
        candidate = local_id(folder)
        if candidate != own and candidate not in out:
            out.append(candidate)
    return out


def ids_for(project: dict) -> list[str]:
    ""                                                                     
                                                        
    return [project["id"], *former_ids(project)]


def former_index(projects: list[dict]) -> dict[str, str]:
    ""                                              

                                                                                
                                                    
       
    idx: dict[str, str] = {}
    for p in projects:
        for old in former_ids(p):
            idx.setdefault(old, p["id"])
    return idx


def resolve_former(project_id: str, projects: list[dict]) -> str | None:
    ""                                                    

                                                                             
                                                                          
                                                 
       
    return former_index(projects).get(project_id)


                                                               
                                                                                
                                                                               
                                                                       
import json
import paths
_override_file = paths.config_file("identity_overrides.json")
ID_OVERRIDE = json.loads(_override_file.read_text()).get("overrides", {}) if _override_file.exists() else {}
if not isinstance(ID_OVERRIDE, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in ID_OVERRIDE.items()):
    raise ValueError("identity_overrides must map strings to strings")


def project_id(key: str) -> str:
    ""                                             
    return "project:" + ID_OVERRIDE.get(key, key)
