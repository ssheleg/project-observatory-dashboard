#!/usr/bin/env python3
""                                                                          

                                                                               
                                                                               
                                                                                 
                                                                             
                                  

                                                                       
                                                                              
                                                                        
                                                                              

                                                                            
                                                                              
             

                                               
                                                                                 
                                                                              
                                                                             
                                                                              
                                                                                  

                                                                         
                                                                             
                                                                      

                                                                      
                                                         
                                                                               

                                                                             
                                                                               
                                                                            
                
   
from __future__ import annotations
import argparse
import builtins
import importlib.util
import json
import os
import pathlib
import runpy
import shutil
import sqlite3
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import paths                                                                    
import tmp as tmpdir                                                            

                                                                             
                                                                                  
                                                                          
                                                                                
                                                        
REFUSED: dict[str, str] = {
    "notify": "sends a notification to a person, and no redirect makes an "
              "already-delivered message undelivered",
    "commit-registry": "makes a git commit in this repository",
    "commit-projection": "makes a git commit in the operator's wiki",
}

                                                                        
                                                                     
  
                                                                            
                                                                             
                                                                          
                                                                                
                                                                              
                     
SAFE_MODE: dict[str, tuple[dict[str, str], str]] = {
    "project": ({"OBSERVATORY_VAULT": "<work>/vault"},
                "the projection is written into a temporary vault, not the "
                "operator's; `paths.VAULT` exists for exactly this"),
    "agent": ({"OPENROUTER_API_KEY": "", "OBSERVATORY_KEY_FILE": "/nonexistent/key"},
              "with no credential the agent takes its documented degradation and "
              "spends nothing — the path a test drives in `test_degrades_without_credential`"),
    "index": ({"OPENROUTER_API_KEY": "", "OBSERVATORY_KEY_FILE": "/nonexistent/key"},
              "the indexer degrades to the lexical half when it cannot embed, so "
              "the vector call — the only thing that costs — never happens"),
}

                                                                               
                                                                              
                                       
TOUCHED: list[tuple[str, str]] = []


                                                                           
                                                                               
                                                                      
                                                                       
                                                                                
                                      
def _canonical() -> list[tuple[pathlib.Path, str]]:
    out = []
    for var, name in (("OBSERVATORY_DASHBOARD", "docs/projects-dashboard.html"),
                      ("OBSERVATORY_SCRATCH", "store/raw"),
                      ("OBSERVATORY_DB", "store/observatory.db"),
                      ("OBSERVATORY_REGISTRY", "registry"),
                      ("OBSERVATORY_ACKS", "collectors/finding_acks.json"),
                      ("OBSERVATORY_STATE", "store")):
        v = os.environ.get(var)
        if v:
            out.append((pathlib.Path(v).resolve(), name))
                                                                            
                                                                                  
                                                                
    return sorted(out, key=lambda kv: len(str(kv[0])), reverse=True)


REDIRECTS: list[tuple[pathlib.Path, str]] = []


def _record(mode: str, path) -> None:
    try:
        p = pathlib.Path(path).resolve()
    except (OSError, TypeError, ValueError):
        return
    kind = "w" if any(c in str(mode) for c in "wax+") else "r"
    for sandbox, name in REDIRECTS:
        if p == sandbox:
            TOUCHED.append((kind, name)); return
        if sandbox in p.parents:
            TOUCHED.append((kind, f"{name}/{p.relative_to(sandbox).as_posix()}")); return
    try:
        rel = p.relative_to(ROOT).as_posix()
    except ValueError:
        return                                                                    
    TOUCHED.append((kind, rel))


def install() -> None:
    real_open, real_p_open = builtins.open, pathlib.Path.open
    real_rt, real_wt = pathlib.Path.read_text, pathlib.Path.write_text
    real_rb, real_wb = pathlib.Path.read_bytes, pathlib.Path.write_bytes
    real_connect, real_replace = sqlite3.connect, os.replace
    real_copy, real_copy2 = shutil.copy, shutil.copy2

    def op(file, mode="r", *a, **k):
        _record(mode, file)
        return real_open(file, mode, *a, **k)

    def p_open(self, mode="r", *a, **k):
        _record(mode, self)
        return real_p_open(self, mode, *a, **k)

    builtins.open = op
    pathlib.Path.open = p_open
    pathlib.Path.read_text = lambda self, *a, **k: (_record("r", self), real_rt(self, *a, **k))[1]
    pathlib.Path.write_text = lambda self, *a, **k: (_record("w", self), real_wt(self, *a, **k))[1]
    pathlib.Path.read_bytes = lambda self, *a, **k: (_record("r", self), real_rb(self, *a, **k))[1]
    pathlib.Path.write_bytes = lambda self, *a, **k: (_record("w", self), real_wb(self, *a, **k))[1]
                                                                           
                                                                              
                                                                             
    def connect(target, *a, **k):
                                                                                 
                                                                               
                                                       
        s = str(target)
        if s.startswith("file:"):
            path, _, query = s[len("file:"):].partition("?")
            _record("r" if "mode=ro" in query else "w", path)
        else:
            _record("w", target)
        return real_connect(target, *a, **k)

    sqlite3.connect = connect
                                                                            
                                                                             
                                                     
    os.replace = lambda src, dst, *a, **k: (_record("w", dst), real_replace(src, dst, *a, **k))[1]
    shutil.copy = lambda s, d, *a, **k: (_record("r", s), _record("w", d), real_copy(s, d, *a, **k))[2]
    shutil.copy2 = lambda s, d, *a, **k: (_record("r", s), _record("w", d), real_copy2(s, d, *a, **k))[2]


def steps() -> dict[str, list[str]]:
    spec = importlib.util.spec_from_file_location("obs_trace", ROOT / "observatory.py")
    obs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obs)
    return obs.STEPS


def declared() -> dict[str, dict[str, list[str]]]:
    spec = importlib.util.spec_from_file_location("tp_trace", ROOT / "tests/test_pipeline.py")
    tp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tp)
    return tp.ARTEFACTS


def run(step: str, cmd: list[str], work: pathlib.Path) -> dict:
    ""                                                            

                                                                              
                                                                          
                                                                           
                                                                        
                                                                            
                                                                           
                                                                               
                                                                           
                                                                               

                                                                                
                                                                       

                                                                              
                                                                            
       
    script = next((c for c in cmd if isinstance(c, str) and c.endswith(".py")), None)
    if script is None:
        return {"step": step, "skipped": "no python script in the command"}
    argv = [script] + [c for c in cmd[cmd.index(script) + 1:]]
    env_before = dict(os.environ)
    (work / "raw").mkdir(parents=True, exist_ok=True)
    (work / "state").mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "store").glob("*.json"):
        shutil.copy2(f, work / "state" / f.name)
    for f in (ROOT / "store/raw").glob("*"):
        if f.is_file():
            shutil.copy2(f, work / "raw" / f.name)
                                                                           
                                                                               
                                                                            
                                                                        
                                                                              
                               
    if (ROOT / "store/observatory.db").is_file():
        shutil.copy2(ROOT / "store/observatory.db", work / "t.db")
    shutil.copytree(paths.REGISTRY, work / "registry", dirs_exist_ok=True)
    if (ROOT / "collectors/finding_acks.json").is_file():
        shutil.copy2(ROOT / "collectors/finding_acks.json", work / "acks.json")
    env = dict(os.environ)
    env.update({"OBSERVATORY_DB": str(work / "t.db"),
                "OBSERVATORY_SCRATCH": str(work / "raw"),
                "OBSERVATORY_DASHBOARD": str(work / "page.html"),
                "OBSERVATORY_STATE": str(work / "state"),
                                                                              
                                                                           
                                                                              
                                                                              
                                                             
                "OBSERVATORY_REGISTRY": str(work / "registry"),
                "OBSERVATORY_ACKS": str(work / "acks.json"),
                "OBSERVATORY_TRACE_OUT": str(work / "touched.json")})
    for var, value in (SAFE_MODE.get(step, ({}, ""))[0]).items():
        env[var] = value.replace("<work>", str(work))
    if step in SAFE_MODE:
        (work / "vault" / "inventory").mkdir(parents=True, exist_ok=True)
    os.environ.clear()
    os.environ.update(env_before)
    p = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()),
                        "--child", script] + argv[1:],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=3600)
    out = work / "touched.json"
    if not out.is_file():
        return {"step": step, "outcome": f"the child left no observation: "
                                         f"{(p.stdout + p.stderr)[-200:]}",
                "reads": [], "writes": []}
    seen = json.loads(out.read_text(encoding="utf-8"))
    return {"step": step, "outcome": f"exit {p.returncode}",
            "reads": sorted({x[1] for x in seen if x[0] == "r"}),
            "writes": sorted({x[1] for x in seen if x[0] == "w"})}


def written_by_anyone(decl: dict) -> list[str]:
    ""                                                                             

                                                                              
                                                                           
                                                                             
                                                                              
                                          
       
    return sorted({w for io in decl.values() for w in io["writes"]})


def compare(step: str, seen: dict, decl: dict) -> list[str]:
    ""                                                   

                                                                                  
                                                                                
                 
       
    say = decl.get(step) or {"reads": [], "writes": []}
    out: list[str] = []
                                                                             
                                                                              
                                                                              
                               
    exempt = ("store/observatory.db",)

    def covered(path: str, names: list[str]) -> bool:
        return any(path == n or path.startswith(n.rstrip("/") + "/") for n in names)

    for p in seen.get("writes", []):
        if p not in exempt and not covered(p, say["writes"]):
            out.append(f"{step} WRITES {p}, undeclared")
    produced = written_by_anyone(decl)
    other = 0
    for p in seen.get("reads", []):
        if p in exempt:
            continue
                                                                                 
                                                                    
        if covered(p, say["reads"]) or covered(p, say["writes"]):
            continue
        if covered(p, produced):
            out.append(f"{step} READS {p}, undeclared — and some step WRITES it")
        else:
            other += 1
    if other:
                                                                               
                                                                             
        out.append(f"{step} also read {other} file(s) no step writes "
                   f"(source, fixtures, checked-in inputs) — not an ordering risk")
    for p in say["writes"]:
        if not any(q == p or q.startswith(p.rstrip("/") + "/") for q in seen.get("writes", [])):
            out.append(f"{step} declares a write of {p} and did not write it")
    return out


def child(argv: list[str]) -> int:
    ""                                                                    

                                                                                
                                                                                 
                          
       
    REDIRECTS[:] = _canonical()
    install()
    script, rest = argv[0], argv[1:]
    sys.argv = [script] + rest
    code = 0
    try:
        runpy.run_path(str(ROOT / script), run_name="__main__")
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:                                                  
        print(f"trace_opens: {type(exc).__name__}: {exc}", file=sys.stderr)
        code = 1
    dest = os.environ.get("OBSERVATORY_TRACE_OUT")
    if dest:
        pathlib.Path(dest).write_text(json.dumps(TOUCHED), encoding="utf-8")
    return code


def main(argv: list[str]) -> int:
    if len(argv) > 2 and argv[1] == "--child":
        return child(argv[2:])
    ap = argparse.ArgumentParser(description=(__doc__ or 'Trace file access in an isolated diagnostic run.').splitlines()[0])
    ap.add_argument("steps", nargs="*")
    ap.add_argument("--all", action="store_true", help="every step the graph declares")
    ap.add_argument("--json", help="write the raw observation here")
    args = ap.parse_args(argv[1:])
    all_steps, decl = steps(), declared()
    want = list(decl) if args.all else args.steps
    if not want:
        ap.error("name a step, or pass --all")

    reports, drift = [], []
    for step in want:
        if step not in all_steps:
            print(f"  {step}: no such step"); continue
        if step in SAFE_MODE:
            print(f"  {step:20} traced in SAFE MODE — {SAFE_MODE[step][1]}")
        if step in REFUSED:
            print(f"  {step:20} REFUSED — {REFUSED[step]}")
            reports.append({"step": step, "refused": REFUSED[step]})
            continue
        work = pathlib.Path(tmpdir.mkdtemp(prefix=f"observatory-trace-{step}-"))
        r = run(step, all_steps[step], work)
        reports.append(r)
        if "skipped" in r:
            print(f"  {step:14} SKIP {r['skipped']}"); continue
        d = compare(step, r, decl)
        drift += d
        print(f"  {step:14} {r['outcome']:12} {len(r['reads'])} read(s), "
              f"{len(r['writes'])} write(s), {len(d)} disagreement(s)")
        for line in d:
            print(f"      - {line}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(reports, indent=2), encoding="utf-8")
    skipped = [r["step"] for r in reports if "refused" in r]
    if skipped:
        print(f"\n{len(skipped)} step(s) NOT traced, because running them would act "
              f"on the world: {', '.join(skipped)}. Their declarations rest on the "
              f"source derivations alone.")
    print(f"\n{len(drift)} disagreement(s) between the graph and what ran. "
          "A clean report means nothing undeclared passed through PYTHON — a "
          "subprocess or a C extension opening its own files is invisible here.")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
