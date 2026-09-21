#!/usr/bin/env python3
""                                                                                    

                                                                      
                                                                          
                                                                             
                                                             
   
from __future__ import annotations
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup, PROJECT_ID as SYNTHETIC_PROJECT
portable_setup()

sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir                                                            

PY = sys.executable
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def sandbox() -> tuple[dict, pathlib.Path]:
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-ack-"))
    shutil.copytree(__import__("paths").REGISTRY, d / "registry")                                                                       
    shutil.copytree(__import__("paths").SCRATCH, d / "raw")
    acks = d / "finding_acks.json"
    acks.write_text(json.dumps({"note": "fixture", "acks": []}), encoding="utf-8")
    env = dict(os.environ, OBSERVATORY_REGISTRY=str(d / "registry"),
               OBSERVATORY_SCRATCH=str(d / "raw"), OBSERVATORY_ACKS=str(acks))
    return env, acks


def ack(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(ROOT / "tools/ack.py"), *args], env=env,
                          capture_output=True, text=True, timeout=120)


def test_the_verb_refuses_what_would_hide_something_else() -> None:
    env, acks = sandbox()
    board = json.loads((pathlib.Path(env["OBSERVATORY_REGISTRY"]) / "findings.json").read_text())
    some = board["findings"][0]["id"]
    p = ack(env, some)
    check("no reason, no ack", p.returncode == 2 and "--why is required" in p.stderr, p.stderr[-120:])
    p = ack(env, "made.up:nothing", "--why", "x")
    check("an id the board does not carry is refused, ids' shape explained",
          p.returncode == 1 and "carries no finding" in p.stderr and "<type>:<subject>" in p.stderr,
          p.stderr[-160:])
    p = ack(env, some, "--why", "x", "--until", "2020-01-01")
    check("a date already past is refused", p.returncode == 2 and "already past" in p.stderr, p.stderr[-120:])
    check("and none of that wrote a row", json.loads(acks.read_text())["acks"] == [])


def build(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(ROOT / "tools/build_findings.py")], env=env,
                          capture_output=True, text=True, timeout=600)


def test_an_ack_lands_reaches_the_board_and_can_be_undone() -> None:
    env, acks = sandbox()
    reg = pathlib.Path(env["OBSERVATORY_REGISTRY"])
                                                                              
                                                                        
                                                                              
                                                                          
                                                                            
                                                            
    b = build(env)
    check("the builder runs over the sandbox", b.returncode == 0, (b.stdout + b.stderr)[-200:])
    board = json.loads((reg / "findings.json").read_text())
    target = next(f for f in board["findings"] if f["severity"] == "info")["id"]
    p = ack(env, target, "--why", "known and accepted for now", "--by", "operator")
    check("the ack is recorded and says what it silenced", p.returncode == 0
          and "silenced:" in p.stdout and target in p.stdout, p.stdout[-200:] + p.stderr[-200:])
    rows = json.loads(acks.read_text())["acks"]
    check("one row, with id, why, by and the date", len(rows) == 1 and rows[0]["id"] == target
          and rows[0]["why"] == "known and accepted for now" and rows[0]["by"] == "operator"
          and len(rows[0].get("on", "")) == 10, str(rows))
    p = ack(env, target, "--why", "a second reason")
    check("acking again replaces the row rather than adding a twin",
          len(json.loads(acks.read_text())["acks"]) == 1
          and json.loads(acks.read_text())["acks"][0]["why"] == "a second reason", "")
                              
    b = build(env)
    check("the builder runs again with the ack in place", b.returncode == 0,
          (b.stdout + b.stderr)[-200:])
    after = json.loads((reg / "findings.json").read_text())
    row = next((f for f in after["findings"] if f["id"] == target), None)
    check("the finding now carries its ack, with the reason",
          row is not None and row.get("acked", {}).get("why") == "a second reason", str(row and row.get("acked")))
    check("and the counts no longer include it",
          after["counts"].get("info", 0) == board["counts"].get("info", 0) - 1,
          f"{board['counts']} -> {after['counts']}")
    p = ack(env, "--list")
    check("--list names it as silenced", "silenced" in p.stdout and target in p.stdout, p.stdout[-200:])
    p = ack(env, "--undo", target)
    check("undo removes the row", p.returncode == 0 and json.loads(acks.read_text())["acks"] == [], p.stderr)
    p = ack(env, "--undo", target)
    check("a second undo says there was nothing", p.returncode == 1)


if __name__ == "__main__":
    print("silencing a finding — on the record, reaching the page, reversible\n")
    for fn in (test_the_verb_refuses_what_would_hide_something_else,
               test_an_ack_lands_reaches_the_board_and_can_be_undone):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32ma silence that nobody can see later is refused; this one is on the record\033[0m")
