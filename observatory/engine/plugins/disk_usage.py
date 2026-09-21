#!/usr/bin/env python3
""                                                                         

                                                                            
                                                                               
                                                               

                                                                             
                                                                         
                                                                          
                                                                                
                                                                                
        
   
from __future__ import annotations
import json, os, pathlib, sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths                                                                    

                                                                                     
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", ".nuxt",
        "target", "build", "dist", ".gradle", "Pods", ".terraform", ".mypy_cache",
        ".pytest_cache", ".tox", ".DS_Store"}


def tree_bytes(root: pathlib.Path) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for name in filenames:
            if name in SKIP:
                continue
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue                                                       
            if not os.path.islink(os.path.join(dirpath, name)):
                total += st.st_size
    return total


def walk_all(folders, seen: set[str]) -> int:
    ""                                                                   
    total = 0
    for folder in folders:
        path = paths.DATA / folder
        real = str(path.resolve()) if path.exists() else ""
                                                                                
                                                                    
        if not real or real in seen or not path.is_dir():
            continue
        seen.add(real)
        total += tree_bytes(path)
    return total


def worktrees_of(project_id: str, relations: list, repos: dict) -> list[str]:
    ""                                                 

                                                                               
                                                                               
                                                             
                                                                   

                                                                              
                                                                                 
                                                                              
                                                                             
                                             
       
    mine = {r["to"] for r in relations
            if r["type"] == "implemented_by" and r["from"] == project_id}
    out: list[str] = []
    for rid in sorted(mine):
        local = (repos.get(rid) or {}).get("local") or {}
        out += list(local.get("extra_clones") or [])
    return out


def subtree_bytes(root: str) -> int:
    ""                                                                           
    total = 0
    for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        for name in filenames:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass                                                           
    return total


def reclaimable_bytes(root: pathlib.Path) -> int:
    ""                                                                                

                                                                              
                                                                            
                                                             
                                                                                    
                                                                             
                                                                                 
                                                                               
                                                                           
               

                                                                                
                                                                   

                                                                           
                                                                                
                                                                           
       
    total = 0
    for dirpath, dirnames, _filenames in os.walk(root, onerror=lambda _e: None):
        for d in [d for d in dirnames if d in SKIP]:
            total += subtree_bytes(os.path.join(dirpath, d))
        dirnames[:] = [d for d in dirnames if d not in SKIP]
    return total


def main() -> int:
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")                     
    reg = lambda name, key: json.loads(                                          
        (paths.REGISTRY / name).read_text(encoding="utf-8"))[key]
    projects = reg("projects.json", "projects")
    relations = reg("relations.json", "relations")
    repos = {r["id"]: r for r in reg("repositories.json", "repositories")}
    for p in projects:
        folders = p.get("local_folders") or []
        if not folders:
            continue
                                                                                
                                               
        seen: set[str] = set()
        total = walk_all(folders, seen)
        extra = walk_all(worktrees_of(p["id"], relations, repos), seen)
        if total:
                                                                               
                                                                                
                                                                                
                                                                              
                                                                              
            print(json.dumps({"project_id": p["id"], "metric": "disk.bytes",
                              "at": at, "value": float(total)}))
        if extra:
            print(json.dumps({"project_id": p["id"], "metric": "disk.worktree_bytes",
                              "at": at, "value": float(extra)}))
                                                                               
                                                                                
                                                        
        recl = 0
        for folder in list(folders) + worktrees_of(p["id"], relations, repos):
            path = paths.DATA / folder
            if path.is_dir():
                recl += reclaimable_bytes(path)
        if recl:
            print(json.dumps({"project_id": p["id"],
                              "metric": "disk.reclaimable_bytes",
                              "at": at, "value": float(recl)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
