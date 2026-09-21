#!/usr/bin/env python3
""                                                            

                                                      

                                                                                   
                                                                                
                                                                             
                                                   

                                                                         
                                                                                 
                                                                                
                                                                                
                                   

                                                                          
                                                                                
                                                                               
                                                                                 
                                                                             
               

                                                                                 
                                                                                 
                                                                                 
                                                                               
                                                  

                                                                                
                                                                                
                                                                                 
                                                                           
                                                                            
                                   
   
from __future__ import annotations
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup
portable_setup()
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def findings_for(health: dict | None, agent: dict | None) -> list[dict]:
    ""                                                        

                                                                               
                                                                               
                                                                              
                                                               
       
    import build_findings as B
    fn = getattr(B, "provider_findings", None)
    if fn is None:
        return [{"type": "ABSENT"}]
    return fn(health, agent)


RECENT = {"ran_at": "2026-09-07T20:00:00Z"}


                                                                                                                                                     

def test_a_quarantined_model_is_named() -> None:
    out = findings_for({"vendor/m": {"since": "2026-09-07T19:00:00Z",
                                     "reason": "a 503 from the edge"}}, RECENT)
    if out and out[0].get("type") == "ABSENT":
        check("build_findings.provider_findings exists", False,
              "the rule must be callable on documents so it can be watched working")
        return
    q = [f for f in out if "quarantin" in f["type"]]
    check("a quarantined model produces a finding", len(q) == 1, str([f['type'] for f in out]))
    if not q:
        return
    f = q[0]
    check("its subject is the MODEL, not the provider", f["subject"] == "model:vendor/m",
          f["subject"])
    check("the reason travels with it", "503" in json.dumps(f, ensure_ascii=False),
          json.dumps(f, ensure_ascii=False)[:200])
    check("severity is warning, not critical",
          f["severity"] == "warning",
          "an empty chain raises Fatal at selection and the tick findings own that")


def test_a_retired_chain_link_is_a_different_finding() -> None:
    out = findings_for({}, dict(RECENT, chain_retired=["vendor/gone"]))
    if out and out[0].get("type") == "ABSENT":
        return
    r = [f for f in out if "retired" in f["type"]]
    check("a retired chain link produces its own finding", len(r) == 1,
          str([f["type"] for f in out]))
    if r:
        check("subject is the retired id", r[0]["subject"] == "model:vendor/gone",
              r[0]["subject"])
        check("and the remedy names the chain's own file",
              "models.json" in json.dumps(r[0], ensure_ascii=False),
              "editing the chain is the fix; waiting an hour is not")
    q = [f for f in out if "quarantin" in f["type"]]
    check("a retirement is not reported as a quarantine", not q, str([f["type"] for f in out]))


                                                                                                                           

def test_empty_with_a_recent_run_is_measured_health() -> None:
    out = findings_for({}, RECENT)
    if out and out[0].get("type") == "ABSENT":
        return
    check("nothing is wrong, so nothing is reported", out == [] or all(
        f.get("severity") == "info" for f in out), str([f["type"] for f in out]))


def test_empty_with_no_run_is_not_health() -> None:
    ""                                                                          
                                                                               
                                                                            
    out = findings_for({}, None)
    if out and out[0].get("type") == "ABSENT":
        return
    claims_health = [f for f in out
                     if "health" in json.dumps(f, ensure_ascii=False).lower()
                     and "не измер" not in json.dumps(f, ensure_ascii=False)
                     and "not measured" not in json.dumps(f, ensure_ascii=False).lower()]
    check("no finding claims the models are healthy", not claims_health,
          json.dumps(claims_health, ensure_ascii=False)[:240])


def test_an_unreadable_file_degrades_rather_than_passing() -> None:
    out = findings_for(None, RECENT)
    if out and out[0].get("type") == "ABSENT":
        return
    check("an unreadable quarantine list is reported, not skipped",
          any("unread" in f["type"] or "unmeasured" in f["type"] or "degraded" in f["type"]
              for f in out),
          str([f["type"] for f in out]) + " — 'the file did not parse' and "
          "'no model is quarantined' must not look alike")


                                                                                                                   

def test_the_page_renders_a_non_empty_quarantine() -> None:
    ""                                                                            
                                                                             
                                                                           
                               
    src = (ROOT / "dashboard/build_dashboard.py").read_text(encoding="utf-8")
    check("the page script references health.provider",
          re.search(r"(H\.provider\b|\[[\"']provider[\"']\])", src) is not None,
          "the field reached the payload with no reader — measured as the only "
          "unread key of fourteen")
    import shutil
    if shutil.which("node") is None:
        print("  NOTE  node is absent; the rendered assertion cannot run here "
              "[covered: the four finding branches above run without it]")
        return
    p = subprocess.run([PY, "tests/render_provider_health.py"], cwd=ROOT,
                       capture_output=True, text=True, timeout=900)
    ok = p.returncode == 0
    check("and it renders a quarantined model into the health panel", ok,
          (p.stdout + p.stderr)[-400:])


                                                                                                               

def test_retirement_report_is_consumed_and_clears_after_recovery() -> None:
                                                                               
                                                                
    retired = findings_for({}, dict(RECENT, chain_retired=["vendor/gone"]))
    check("the report reaches the retirement finding reader",
          any(f.get("type") == "provider.chain_retired" for f in retired))
    recovered = findings_for({}, dict(RECENT, chain_retired=[]))
    check("a recovered chain clears the retirement finding",
          not any(f.get("type") == "provider.chain_retired" for f in recovered))


if __name__ == "__main__":
    print("provider health — quarantined correctly, reported nowhere\n")
    for fn in (test_a_quarantined_model_is_named,
               test_a_retired_chain_link_is_a_different_finding,
               test_empty_with_a_recent_run_is_measured_health,
               test_empty_with_no_run_is_not_health,
               test_an_unreadable_file_degrades_rather_than_passing,
               test_the_page_renders_a_non_empty_quarantine,
               test_retirement_report_is_consumed_and_clears_after_recovery):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mthe provider's health reaches a surface, and its empty state is "
          "not mistaken for good news\033[0m")
