#!/usr/bin/env python3
""                                                                      

                                                                                
                                                                               
                                                                               
                                                                     
                                                                                 
                                                                                 

                                                                                 
                                                                              
                                                                               
                                                    

                                                                               
                                                                                   
                                                                              

                                                                          
                                                                              
                                                                           
                                                                    

                                                                        
                                                                             
                                                                               
                                                                                
                           
   
from __future__ import annotations
import json

import paths

                                                                 
LANDS_IN = {
    "project:": ("project_overrides.json", "projects"),
    "repository:": ("repo_overrides.json", "repositories"),
}

                                                                              
                                                                              
                                                                             
                                                     
PROVENANCE = {"why", "proposed_by", "accepted_on", "evidence"}


def _fields(name: str, key: str) -> set[str]:
    try:
        doc = json.loads((paths.config_file(name)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    out: set[str] = set()
    for row in (doc.get(key) or {}).values():
        if isinstance(row, dict):
            out |= set(row)
    return out - PROVENANCE


def appliable() -> dict[str, set[str]]:
    ""                                                                      

                                                                          
                                                                                
                                                                              
                                         
       
    return {prefix: _fields(name, key) for prefix, (name, key) in LANDS_IN.items()}


def refusal(target_id: str, patch: dict, evidence: list) -> str:
    ""                                                       

                                                                               
                                                                                
       
    if not evidence:
        return ("a patch with no evidence is a guess. Attach at least one "
                "resolvable reference — a commit sha, a file path, a URI — "
                "because the operator deciding this cannot re-derive what you saw")
    prefix = next((p for p in LANDS_IN if target_id.startswith(p)), "")
    if not prefix:
        kinds = ", ".join(sorted(LANDS_IN))
        if target_id.startswith("domain:"):
            return ("domains are not derived: `registry/domains.json` is the "
                    "operator's transcription of documents they supplied, and "
                    "there is no overrides file an accepted change could land in. "
                    "Send it to them as a note instead")
        return f"only {kinds} can be proposed against; `{target_id}` is neither"
    if not patch:
        return "an empty patch proposes nothing"
    allowed = appliable()[prefix]
    if not allowed:
        return (f"nothing has ever been overridden for a {prefix.rstrip(':')}, so "
                f"this function cannot tell which fields are appliable. The "
                f"operator adds the first row by hand")
    unknown = sorted(set(patch) - allowed)
    if unknown:
        return (f"{', '.join(unknown)} cannot be applied: an accepted proposal "
                f"lands in {LANDS_IN[prefix][0]}, which supplies "
                f"{', '.join(sorted(allowed))}. Anything else is either derived "
                f"from the scan — the emitter recomputes it on the next tick — or "
                f"provenance the decision writes rather than the caller")
    return ""


def known_target(target_id: str, registry_ids: set[str]) -> bool:
    return target_id in registry_ids
