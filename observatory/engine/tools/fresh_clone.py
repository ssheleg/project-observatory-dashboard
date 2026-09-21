#!/usr/bin/env python3
""                                                                         

                                                                                 
                                                                               
                                                                                 
                                                                                 
                                                                       
                           

                                                                
                                                               

                                                                                
                                                                                 
                                                                                
                                     

                                                                                 
                                                                                   
                                                                         
                                                                        
                          
   
from __future__ import annotations
import importlib.util
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
                                                                             
                                                                              
                                                                         
sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir                                                              


def steps() -> list[str]:
    spec = importlib.util.spec_from_file_location("obs", ROOT / "observatory.py")
    obs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obs)
    return [s for s in obs.GROUPS["check"] if s.startswith("test-")]


def env_for(tmp: pathlib.Path) -> dict:
    ""                                                                      

                                                                            
                                                                               
                                                                                
                                                                                  
                                          
       
    (tmp / "raw").mkdir(parents=True, exist_ok=True)
    (tmp / "docs").mkdir(parents=True, exist_ok=True)
    return {**os.environ,
            "OBSERVATORY_DB": str(tmp / "absent.db"),
            "OBSERVATORY_SCRATCH": str(tmp / "raw"),
            "OBSERVATORY_DASHBOARD": str(tmp / "docs" / "page.html")}


def main(argv: list[str]) -> int:
    want = argv[1:] or steps()
    tmp = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-fresh-"))
    env = env_for(tmp)
    red: list[str] = []
    for step in want:
        p = subprocess.run([PY, str(ROOT / "observatory.py"), step], cwd=ROOT,
                           env=env, capture_output=len(want) > 1, text=True,
                           timeout=1800)
        ok = p.returncode == 0
        print(f"{'ok  ' if ok else 'RED '} {step}")
        if not ok:
            red.append(step)
            if len(want) > 1:
                for line in (p.stdout + p.stderr).splitlines():
                    if line.strip().startswith("FAIL") or "Error" in line:
                        print(f"        {line.strip()[:150]}")
                        break
    print(f"\n{len(want) - len(red)} of {len(want)} step(s) pass as a fresh clone "
          f"sees them")
    if red:
        print("A step that goes red here reads an ABSENCE as a FAILURE. Guard it "
              "with tests/live_estate.needs(), naming where the property IS "
              "asserted, or drive it against a store the test builds itself.")
    return 1 if red else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
