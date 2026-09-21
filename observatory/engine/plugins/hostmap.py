#!/usr/bin/env python3
""                                                          

                                                                            
                                                                             
                                                                           
                                                                        
                                                                             
                            

                                      

                                                                      
                                                                               
                                                                

                                                                            
                                                                            
                                                               
   
from __future__ import annotations
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths                                                                    


def _load(name: str) -> dict:
    return json.loads((paths.REGISTRY / name).read_text(encoding="utf-8"))


def build() -> dict[str, str]:
    ""                                                
    out: dict[str, str] = {}
    rel = _load("relations.json")["relations"]
    for r in rel:
        if r["type"] == "public_domain_of":
            host = r["from"].split(":", 1)[1].lower()
            out.setdefault(host, r["to"])
                                                                              
                                                                             
                                                                            
                                                                          
                                                                          
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "collectors"))
    import estate_surfaces
    rank: dict[str, int] = {}
    for p in _load("projects.json")["projects"]:
        for s in p.get("sites") or []:
            host = (s.get("host") or "").lower()
            if not host:
                continue
            r = estate_surfaces.evidence_rank(s.get("evidence") or [])
            if host not in rank or r < rank[host]:
                out[host] = p["id"]
                rank[host] = r
    return out


def resolve(host: str, table: dict[str, str] | None = None) -> str | None:
    ""                                                    

                                                                              
                                                                             
                                                                          
       
    t = table if table is not None else build()
    h = (host or "").lower().strip().rstrip(".")
    if not h:
        return None
    if h in t:
        return t[h]
    if h.startswith("www.") and h[4:] in t:
        return t[h[4:]]
    parts = h.split(".")
    if len(parts) > 2:
        apex = ".".join(parts[-2:])
        if apex in t:
            return t[apex]
    return None


if __name__ == "__main__":                                                
    t = build()
    print(f"{len(t)} host(s) mapped; e.g.")
    for h in sorted(t)[:8]:
        print(f"  {h} -> {t[h]}")
