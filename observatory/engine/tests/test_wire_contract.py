#!/usr/bin/env python3
""                                                   

                                                              

                                                                              
                                                                              
                                                                             
                                                                                 
                                                                                  
                                    

                                                                             
                                                                                  
                                                                                 
                                                                 

                                                                            
                                                                            
                                                                      
   
from __future__ import annotations
import json
import jsonschema, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup
portable_setup()
import paths                                                                    

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def tool_parameters() -> dict[str, list[str]]:
    ""                                                                   

                                                                     
                                                                                  
                                                                
       
    import ast
    tree = ast.parse((ROOT / "mcp/server.py").read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("observatory_"):
            args = node.args
            out[node.name] = [a.arg for a in (args.posonlyargs + args.args + args.kwonlyargs)]
    return out


def test_every_declared_input_is_reachable_on_the_wire() -> None:
    ""                                                                         

                                                                         
                                                                                 
                                                                          
                                                                                 
                                       

                                                                           
                                                                           
                                                                                
                                                                               
                             

                                                                                   
                                                                        
       
    manifest = json.loads((ROOT / "fabric-agent.json").read_text(encoding="utf-8"))
    params = tool_parameters()
    for cap in manifest.get("capabilities") or []:
        schema_path = ROOT / "fabric/schemas" / cap["inputSchema"].rsplit("/", 1)[-1]
        declared = set((json.loads(schema_path.read_text(encoding="utf-8"))
                        .get("properties") or {}).keys())
        tools = [f.split(":", 1)[1] for f in cap["profile"]["requiredFeatures"]
                 if f.startswith("tool:")]
        reachable: set[str] = set()
        for t in tools:
            reachable |= set(params.get(t) or [])
        missing = sorted(declared - reachable)
        check(f"{cap['name']}: every declared property is a parameter of "
              f"{' or '.join(tools)}", not missing,
              f"{missing} — a host that compiles the input schema sends these "
              f"names, and a parameter this server does not declare is IGNORED "
              f"rather than refused")


def pinned_store() -> "sqlite3.Connection":
    ""                                                                    

                                                                            
                                                                         
                                                                         
                                                             
       
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript((ROOT / "store/schema.sql").read_text(encoding="utf-8"))
    for sid, fin in (("scan-old-0001", "2026-09-01T00:00:00Z"),
                     ("scan-new-0002", "2026-09-08T00:00:00Z")):
        conn.execute("INSERT INTO scans (id, started_at, finished_at, "
                     "collector_version) VALUES (?,?,?,'test')", (sid, fin, fin))
    conn.commit()
    return conn


def test_the_pin_is_recorded_and_says_it_is_not_honoured() -> None:
    ""                                                       

                                                                              
                                                                                
                                                                                
                                                                             
                                                                                
                                                                            
                                        

                                                                               
                                                                               
                                                            
       
    sys.path.insert(0, str(ROOT))
    import survey as survey_mod
    import inspect
    sig = inspect.signature(survey_mod.survey)
    check("survey takes as_of_scan_id", "as_of_scan_id" in sig.parameters)
    check("and a connection, which is what makes this testable",
          "conn" in sig.parameters, str(sorted(sig.parameters)))

    conn = pinned_store()
    scope = {"kind": "estate"}
    plain = survey_mod.survey(scope, conn=conn)
    check("with no pin, `scanId` is the latest finished scan",
          plain["scanId"] == "scan-new-0002", plain["scanId"])

    def pin_notes(ans):
        return [d["reason"] for d in ans["degraded"]
                if d["source"] == "store" and "scan-" in d["reason"]
                or d["source"] == "store" and "no-such" in d["reason"]]

    same = survey_mod.survey(scope, conn=conn, as_of_scan_id="scan-new-0002")
    check("pinning to the latest scan changes nothing and says nothing",
          same["scanId"] == plain["scanId"] and same["counts"] == plain["counts"]
          and not pin_notes(same), str(pin_notes(same))[:200])

    old = survey_mod.survey(scope, conn=conn, as_of_scan_id="scan-old-0001")
    check("pinning to an older recorded scan returns the CURRENT estate",
          old["counts"] == plain["counts"], f"{old['counts']} vs {plain['counts']}")
    check("and `scanId` reports the scan the answer reflects, not the pin",
          old["scanId"] == "scan-new-0002", old["scanId"])
    notes = pin_notes(old)
    check("and the answer says the pin was not honoured", bool(notes), "silence "
          "here is the defect: today's estate under yesterday's stamp is the one "
          "outcome a caller cannot detect")
    check("naming the scan asked for",
          any("scan-old-0001" in n for n in notes), str(notes)[:200])
    check("and why", any("not versioned per scan" in n for n in notes), str(notes)[:200])

    unknown = survey_mod.survey(scope, conn=conn, as_of_scan_id="no-such-scan")
    check("a pin to an unrecorded scan degrades too",
          any("no-such-scan" in n for n in pin_notes(unknown)),
          str(pin_notes(unknown))[:200])
    check("and still reports the scan it reflects",
          unknown["scanId"] == "scan-new-0002", unknown["scanId"])
    conn.close()


def test_no_document_still_promises_the_pin_filters() -> None:
    ""                                                                         
                                                                                
              
    for rel, phrase in (
            ("fabric/schemas/capability-input.schema.json",
             "Answer from a recorded scan instead of the latest one"),
            ("fabric/FABRIC-CONFORMANCE.md",
             "Paging is only reproducible under"),
            ("mcp/server.py", "so a repeated call returns the same result"),
            ("mcp/server.py", "so the walk is over one fixed scan"),
            ("survey.py", "is what makes\n    a multi-page read reproducible")):
        text = (ROOT / rel).read_text(encoding="utf-8")
        check(f"{rel} no longer promises a filter",
              phrase.replace("\\n", "\n") not in text, phrase[:60])


def test_search_cannot_spend_past_the_ceiling() -> None:
    src = (ROOT / "survey.py").read_text(encoding="utf-8")
    check("the search path checks the budget before embedding",
          "providers.check_budget()" in src,
          "embed() charges the wallet; nothing was checking first")
    idx = src.find("check_budget")
    emb = src.find("providers.embed(")
    check("and it checks BEFORE it spends", idx != -1 and emb != -1 and idx < emb,
          f"check at {idx}, spend at {emb}")
    check("a reached guardrail degrades rather than refusing",
          "spend guardrail reached" in src,
          "the lexical half must still answer, with the reason in `degraded`")

    # Driven: the answer must name the reason when a guardrail is up.
    import survey as survey_mod
    result = survey_mod.search("a probe of the guardrail", limit=2)
    sources = [d.get("source") for d in result.get("degraded", [])]
    check("the result carries a degraded list at all", isinstance(result.get("degraded"), list),
          str(result.keys()))
    if "vector" in sources:
        reason = next(d["reason"] for d in result["degraded"] if d["source"] == "vector")
        check("and when the vector half is skipped the reason is stated", bool(reason), reason)


def test_the_ceiling_message_does_not_blame_the_wrong_spender() -> None:
    ""                                                                         
                                                                        
                                                                                 
                                                                               
                                                                         
    src = (ROOT / "agent/providers.py").read_text(encoding="utf-8")
    check("the message names the spender that decided",
          "spent today by THIS project" in src,
          "a ceiling on this system's own spend must say so")
    check("and shows the key's figure as context",
          "another consumer" in src and "the key itself shows" in src,
          "the two figures differ by orders of magnitude and the difference is "
          "the story")
    check("the caps read this project's journal, not the provider's counters",
          'today, month = s["local_today"], s["local_month"]' in src,
          "the provider's counters measure a shared key")
    check("while the key's own limit is still the outer stop",
          's.get("key_remaining") is not None and s["key_remaining"] <= 0' in src,
          "at zero nothing can be bought, whoever spent it")

def test_the_served_instructions_describe_the_served_surface() -> None:
    src = (ROOT / "mcp/server.py").read_text(encoding="utf-8")
    tools = src.count("@server.tool()")
                                                                            
                                                                                 
                                                                                
                                                       
    check("the server serves nine tools", tools == 9, str(tools))
    block = src.split("instructions=(", 1)[1].split("),", 1)[0]
    check("the instructions no longer claim read-only", "Read-only" not in block)
    check("they state that two tools write", "WRITE:" in block)
    check("and that the credential reader cannot return a value",
          "CANNOT return a value" in block,
          "an agent decides from this string whether to open the file itself")
    check("they warn that search spends", "SPENDS" in block,
          "an LLM client decides what to call from this string")
    check("and that nothing here can promote", "promote" in block)



def test_every_fixture_validates_against_the_schema_it_accompanies() -> None:
    ""                                                            

                                                                            
                                                                               
                                                                          
                                                                             
                                                                              
                                                                                  
                                                 

                                                                                
                                                                                 
                                                                               
                                                                             
                 
       
    manifest = json.loads((ROOT / "fabric-agent.json").read_text(encoding="utf-8"))
    seen = 0
    for cap in manifest.get("capabilities") or []:
        schema_uri = cap.get("inputSchema") or ""
        schema_path = ROOT / "fabric/schemas" / schema_uri.rsplit("/", 1)[-1]
        if not schema_path.is_file():
            check(f"{cap['name']}: its input schema resolves locally", False,
                  str(schema_path))
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for probe in cap["profile"].get("probes") or []:
            uri = probe.get("inputFixture") or ""
            fixture = ROOT / "fabric/fixtures" / uri.rsplit("/", 1)[-1]
            if not fixture.is_file():
                check(f"{probe.get('id')}: its fixture resolves locally", False,
                      str(fixture))
                continue
            seen += 1
            try:
                jsonschema.validate(
                    json.loads(fixture.read_text(encoding="utf-8")), schema)
                ok, why = True, ""
            except jsonschema.ValidationError as exc:
                ok, why = False, exc.message[:120]
            check(f"{probe['id']} sends what {cap['name']} declares it accepts",
                  ok, why)
    check(f"every declared fixture was checked ({seen})", seen >= 6,
          f"{seen} — the manifest declares six probes")



def test_the_probe_runner_sends_the_fixture_verbatim() -> None:
    ""                                                                

                                                                      
                                                                             
                                                                              
                                                                              
                                                                           
                                                                                
                                                                            
                                         

                                                                             
                                                                                   
                                               
       
    import ast
    manifest = json.loads((ROOT / "fabric-agent.json").read_text(encoding="utf-8"))
    declared: set[str] = set()
    for cap in manifest.get("capabilities") or []:
        schema = json.loads((ROOT / "fabric/schemas" /
                             cap["inputSchema"].rsplit("/", 1)[-1]).read_text(encoding="utf-8"))
        declared |= set((schema.get("properties") or {}).keys())
    tree = ast.parse((ROOT / "tools/run_probes.py").read_text(encoding="utf-8"))
    bad: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "call_tool" and len(node.args) >= 2):
            continue
        payload = node.args[1]
        if not isinstance(payload, ast.Dict):
            continue
        # CONSTRUCTING IS ALLOWED — the record probe's negative cases must build
        # a payload the fixture does not contain — but only out of names the
        # contract declares. A key no input schema knows is a translation, and a
        # translation is what made the receipt describe the runner.
        for k in payload.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str) \
                    and k.value not in declared:
                bad.append(f"line {node.lineno}: {k.value!r}")
    check("every key the runner sends is one the contract declares", not bad,
          f"{bad} — a name no input schema knows is a rewrite, and the receipt "
          f"would describe it rather than what a host sending the declared shape "
          f"receives")


if __name__ == "__main__":
    print("the wire — declared, reachable, metered and described\n")
    for fn in (test_every_declared_input_is_reachable_on_the_wire,
               test_the_pin_is_recorded_and_says_it_is_not_honoured,
               test_no_document_still_promises_the_pin_filters,
               test_search_cannot_spend_past_the_ceiling,
               test_the_ceiling_message_does_not_blame_the_wrong_spender,
               test_the_served_instructions_describe_the_served_surface,
               test_every_fixture_validates_against_the_schema_it_accompanies,
               test_the_probe_runner_sends_the_fixture_verbatim):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mwhat the wire declares is what the wire does\033[0m")
