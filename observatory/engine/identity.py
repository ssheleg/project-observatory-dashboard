#!/usr/bin/env python3
""                                                                   

                                                              
                                                                              
                                                                        
                                                                               
                                                                              
                                                                           
                

                                                         

                                                                                      
                                                                                      
                                                                                      

                                                                            
                                                                                 
                                                        

                                                                             
                                                                               
                                                                                 
                                                     

                                                            
                                                                             
                                             

                                                                              
                                                                             
                                                                               
                                    

                                                                                
                                                               
                                                                               
                               
   
from __future__ import annotations
import re

#: The prefix a folder-anchored project's key carries. One string, one place:
#: `collectors/merge.py` used to spell `"local-" + folder` inline, and a second
#: spelling of an id rule is how one project ends up with two ids.
LOCAL_PREFIX = "local-"


def slug(s: str) -> str:
    """The registry's own slug. Moved here from `collectors/merge.py` so the
    minting and the lookup cannot drift apart."""
    return re.sub(r"[^a-z0-9.-]+", "-", s.lower()).strip("-")


def local_key(folder: str) -> str:
    """The KEY a project anchored on this folder carries (no `project:`)."""
    return slug(LOCAL_PREFIX + folder)


def local_id(folder: str) -> str:
    """The full id a project anchored on this folder carries."""
    return "project:" + local_key(folder)


# Design and contract for ids, aliases and renames: docs/design/IDENTITY.md
# (repository root). former_ids below is the one computed alias that exists today.
def former_ids(project: dict) -> list[str]:
    """The ids this project would have carried before it was published.

    Empty for a project still anchored on its folder: its own id is not a FORMER
    id, and offering it would make every lookup resolve to itself.
    """
    if (project.get("anchor") or "") == "local-folder":
        return []
    own = project.get("id") or ""
    out = []
    for folder in project.get("local_folders") or []:
        candidate = local_id(folder)
        if candidate != own and candidate not in out:
            out.append(candidate)
    return out


def ids_for(project: dict, projects: list[dict] | None = None) -> list[str]:
    ""                                                                     

                                                                                
                                                                        
       
    if projects is None:
        return [project['id']]
    return [project['id'], *sorted(old for old, current in former_index(projects).items()
                                  if current == project['id'])]


def former_claims(projects: list[dict]) -> dict[str, set[str]]:
    ""                                                                            
    claims: dict[str, set[str]] = {}
    for p in projects:
        for old in former_ids(p):
            claims.setdefault(old, set()).add(p['id'])
    return claims


def former_index(projects: list[dict]) -> dict[str, str]:
    ""                                                                            
    live = {p['id'] for p in projects}
    return {old: next(iter(owners)) for old, owners in former_claims(projects).items()
            if len(owners) == 1 and old not in live}


def former_conflicts(projects: list[dict]) -> dict[str, list[str]]:
    ""                                                                       
    live = {p['id'] for p in projects}
    out = {}
    for old, owners in former_claims(projects).items():
        candidates = owners | ({old} if old in live else set())
        if len(candidates) > 1:
            out[old] = sorted(candidates)
    return out


def resolve_former(project_id: str, projects: list[dict]) -> str | None:
    """The project that now holds this former id, or None.

    None for an id that is itself live: a resolver that returns its own input
    teaches its callers nothing, and every caller here is asking precisely
    because the id was NOT found in the registry.
    """
    return former_index(projects).get(project_id)


                                                               
                                                                                
                                                                               
                                                                       
import json
import paths
_override_file = paths.config_file("identity_overrides.json")
ID_OVERRIDE = json.loads(_override_file.read_text()).get("overrides", {}) if _override_file.exists() else {}
if not isinstance(ID_OVERRIDE, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in ID_OVERRIDE.items()):
    raise ValueError("identity_overrides must map strings to strings")


def project_id(key: str) -> str:
    """A merge key -> the registry's project id."""
    return "project:" + ID_OVERRIDE.get(key, key)
