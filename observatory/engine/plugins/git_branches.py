#!/usr/bin/env python3
""                                                       

                                                                               
                                                                           
                                                                          
                                                                               
                                                                                
                                                                            
           
   
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths                                                                      


def branches(folder: pathlib.Path) -> int | None:
    ""                                                                     
    try:
        p = subprocess.run(["git", "-C", str(folder), "branch", "--list"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return len([l for l in p.stdout.splitlines() if l.strip()])


def main() -> int:
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    projects = json.loads(
        (paths.REGISTRY / "projects.json").read_text(encoding="utf-8"))["projects"]
    for pr in projects:
        total, seen = 0, False
        for folder in pr.get("local_folders") or []:
            n = branches(paths.DATA / folder)
            if n is not None:
                total += n
                seen = True
                                                                             
                                                                                
               
        if seen:
            print(json.dumps({"project_id": pr["id"], "metric": "git.branches",
                              "at": at, "value": float(total)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
