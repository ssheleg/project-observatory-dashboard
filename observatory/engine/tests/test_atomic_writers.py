#!/usr/bin/env python3
""                                                                          

                                                                             
                                                                                
                                                                                
                         

                                                                                
                                                                      
                                                                
                                                                             
                                                                  
                                                                              
                                                                                
                                                         

                                                                             
                                                      

                                                                             
                                                                        
                                                                              
   
from __future__ import annotations
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup, PROJECT_ID as SYNTHETIC_PROJECT
portable_setup()

sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir                                                              

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def half_write(dest: pathlib.Path, text: str) -> None:
    ""                                                                         
    with dest.open("w", encoding="utf-8") as fh:
        fh.write(text[:len(text) // 2])
        raise OSError(28, "No space left on device")


                                                                                                                                                   

def test_a_plain_write_that_stops_halfway_destroys_the_destination() -> None:
    ""                                                                   
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-atomic-"))
    dest = d / "queue.json"
    good = json.dumps({"findings": [{"id": "a"}, {"id": "b"}]}, indent=1)
    dest.write_text(good, encoding="utf-8")
    try:
        half_write(dest, good)
    except OSError:
        pass
    after = dest.read_text(encoding="utf-8")
    check("the previous content is gone", after != good, f"{len(after)} bytes")
    broke = False
    try:
        json.loads(after)
    except ValueError:
        broke = True
    check("and what is left will not parse", broke,
          "a truncation that happens to land on valid JSON is the worse case "
          "atomic.py's docstring names")


def test_atomic_write_text_leaves_the_destination_untouched() -> None:
    import atomic
    fn = getattr(atomic, "write_text", None)
    if fn is None:
        check("atomic.write_text exists", False,
              "three of the five tracked writers are not JSON and had nowhere "
              "to go")
        return
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-atomic2-"))
    dest = d / "shape.md"
    dest.write_text("the previous document\n", encoding="utf-8")
                                                                         
                                                                       
                                                                            
                                                                         
                                                                           
                                                                       
                
    real_fsync = os.fsync
    raised = False
    try:
        os.fsync = lambda fd: (_ for _ in ()).throw(
            OSError(28, "No space left on device"))
        fn(dest, "a new document")
    except OSError:
        raised = True
    finally:
        os.fsync = real_fsync
    check("the failure is not swallowed", raised,
          "a writer that hides ENOSPC is worse than one that truncates")
    check("the destination still holds the previous document",
          dest.read_text(encoding="utf-8") == "the previous document\n",
          dest.read_text(encoding="utf-8")[:60])
    leftovers = [f.name for f in d.iterdir() if f.name != "shape.md"]
    check("and no temp file is left behind", not leftovers, str(leftovers))


def test_it_adds_no_trailing_newline_of_its_own() -> None:
    ""                                                                          
                                                                               
                                                                                 
                                             
    import atomic
    if not hasattr(atomic, "write_text"):
        return
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-atomic3-"))
    p = atomic.write_text(d / "x.jsonl", '{"a":1}\n{"b":2}\n')
    check("what was handed over is what landed",
          p.read_text(encoding="utf-8") == '{"a":1}\n{"b":2}\n',
          repr(p.read_text(encoding="utf-8")))


                                                                                                                                           

                                                                               
                                                                                
                                                      
TRACKED_SOURCES = ("tools/build_findings.py", "tools/export_ledger.py",
                   "tools/fabric_hash.py", "tools/registry_shape.py",
                   "dashboard/build_dashboard.py", "tools/run_probes.py",
                   "agent/providers.py")


def test_no_tracked_artefact_is_written_by_a_plain_write() -> None:
    ""                                                                      
                                      
    import subprocess
    TRACKED = {
        "tools/build_findings.py": "registry/findings.json",
        "tools/export_ledger.py": "registry/ledger.jsonl",
        "tools/fabric_hash.py": "fabric-agent.json",
        "tools/registry_shape.py": "docs/REGISTRY_SHAPE.md",
        "dashboard/build_dashboard.py": "docs/projects-dashboard.html",
        "tools/run_probes.py": "fabric/probe-receipts.json",
    }
    sys.path.insert(0, str(ROOT / "tests"))
    import source_reader
    for rel, artefact in TRACKED.items():
        code = source_reader.code_keeping_strings(
            (ROOT / rel).read_text(encoding="utf-8"))
        plain = [l.strip() for l in code.splitlines()
                 if ".write_text(" in l and "atomic.write_text" not in l]
        check(f"{rel} writes {artefact} through atomic",
              not plain, str(plain[:2]))
                                                                           
    import paths
    for artifact in (paths.REGISTRY / "findings.json", paths.REGISTRY / "ledger.jsonl",
                     paths.DOCS / "REGISTRY_SHAPE.md"):
        check("generated artifact stays in private workspace", artifact.is_relative_to(paths.HOME)
              and not artifact.is_relative_to(ROOT), str(artifact.name))
    check("the shipped contract manifest remains a source asset", (ROOT / "fabric-agent.json").is_file())


def test_the_spend_journal_is_atomic_now() -> None:
    ""                                                                     
    sys.path.insert(0, str(ROOT / "tests"))
    import source_reader
    code = source_reader.code_keeping_strings(
        (ROOT / "agent/providers.py").read_text(encoding="utf-8"))
    plain = [l.strip()[:70] for l in code.splitlines()
             if ".write_text(" in l and "atomic" not in l]
    check("no provider state is written by a plain write", not plain, str(plain[:2]))
    check("and the wallet goes through atomic", "atomic.write_json(WALLET" in code,
          "the file whose loss is in the decision log")



def test_every_caller_of_atomic_actually_binds_the_name() -> None:
    ""                                                 

                                                                                 
                                                                                
                                                                                
                                                                                
                                                                                    
                        

                                                                              
                                                                              
                                                                       
               
       
    import ast
    for rel in sorted(set(TRACKED_SOURCES)):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        uses = any(isinstance(n, ast.Attribute) and getattr(n.value, "id", "") == "atomic"
                   for n in ast.walk(tree))
        if not uses:
            continue
        bound = any((isinstance(n, ast.Import) and any(a.name == "atomic" for a in n.names))
                    or (isinstance(n, ast.ImportFrom) and n.module == "atomic")
                    for n in ast.walk(tree))
        check(f"{rel} imports the atomic it calls", bound,
              "the write path raises NameError the first time it is reached")


def test_the_manifest_stamper_can_actually_write() -> None:
    ""                                                                         
                                                                            
              
    import shutil, subprocess
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-stamp-"))
                                                                             
                                                                          
                                      
    work = d / "repo"
    work.mkdir()
    (work / "tools").mkdir()
    shutil.copy(ROOT / "tools/fabric_hash.py", work / "tools/fabric_hash.py")
    shutil.copy(ROOT / "atomic.py", work / "atomic.py")
    doc = json.loads((ROOT / "fabric-agent.json").read_text(encoding="utf-8"))
    doc["provider"]["contentHash"] = "sha256:" + "0" * 64
    (work / "fabric-agent.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    PYX = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
    p = subprocess.run([PYX, str(work / "tools/fabric_hash.py")], cwd=work,
                       capture_output=True, text=True, timeout=300)
    check("the stamper exits clean", p.returncode == 0, (p.stdout + p.stderr)[-300:])
    after = json.loads((work / "fabric-agent.json").read_text(encoding="utf-8"))
    stamped = after["provider"]["contentHash"]
    check("and replaced the placeholder with a real digest",
          stamped.startswith("sha256:") and stamped != "sha256:" + "0" * 64, stamped)
    p2 = subprocess.run([PYX, str(work / "tools/fabric_hash.py"), "--check"], cwd=work,
                        capture_output=True, text=True, timeout=300)
    check("which its own --check then agrees with", p2.returncode == 0,
          (p2.stdout + p2.stderr)[-200:])


if __name__ == "__main__":
    print("atomic writers — the module existed and fourteen writers did not call it\n")
    for fn in (test_a_plain_write_that_stops_halfway_destroys_the_destination,
               test_atomic_write_text_leaves_the_destination_untouched,
               test_it_adds_no_trailing_newline_of_its_own,
               test_no_tracked_artefact_is_written_by_a_plain_write,
               test_the_spend_journal_is_atomic_now,
               test_every_caller_of_atomic_actually_binds_the_name,
               test_the_manifest_stamper_can_actually_write):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32ma write that cannot finish costs the write, not the file\033[0m")
