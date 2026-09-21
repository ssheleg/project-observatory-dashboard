#!/usr/bin/env python3
""                                                             

                                                                              
                                                                                 
                                                                               
           

                                                                           
                                                                                 
                                                               
                                                                            
                                                                             
                                                                               
                                                                             
                                                 
                                                                            
                                                                 

                                                                        
                                                                                 
                                                                         
                                                                              
                                                                                
                                               

                                                                              
                                                                      
                                                                                
                                           
   
from __future__ import annotations
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup
portable_setup()
sys.path.insert(0, str(ROOT / "mcp"))

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def schema() -> dict:
    return json.loads(
        (ROOT / "fabric/schemas/capability-input.schema.json").read_text(encoding="utf-8"))


def cursor_note(answer: dict) -> list[str]:
    return [d["reason"] for d in answer.get("degraded") or [] if d.get("source") == "cursor"]


                                                                                                                                                 

def test_a_cursor_that_is_not_an_id_is_reported() -> None:
    import survey
    got = survey.survey({"kind": "estate"}, limit=3, cursor="!!! not an id !!!")
    check("the answer still comes", len(got.get("projects") or []) > 0,
          "a degradation, not a refusal — the page is still useful")
    notes = cursor_note(got)
    check("and the cursor is named as naming nothing", bool(notes), str(got.get("degraded"))[:200])
    if notes:
        check("with the warning that a walk will repeat itself",
              "repeat" in notes[0], notes[0][:160])


def test_a_well_formed_cursor_is_not_second_guessed() -> None:
    ""                                                                        
                                                                         
                                                                                  
    import survey
    real = survey.survey({"kind": "estate"}, limit=3, cursor=__import__("test_portable_mcp").PROJECT_ID)
    gone = survey.survey({"kind": "estate"}, limit=3,
                         cursor="project:deleted-between-pages")
    check("an existing id is not reported", not cursor_note(real), str(cursor_note(real)))
    check("and neither is a well-formed id nobody has",
          not cursor_note(gone), str(cursor_note(gone)))


def test_a_cursor_past_the_end_is_an_empty_page_not_an_error() -> None:
    import survey
    got = survey.survey({"kind": "estate"}, limit=5, cursor="zzzzzzzz")
    check("the page is empty", len(got.get("projects") or []) == 0,
          str(len(got.get("projects") or [])))
    check("there is no next cursor", got.get("nextCursor") is None, str(got.get("nextCursor")))
    check("and the total still describes the whole scope",
          got["counts"]["projects"] > 0, str(got["counts"]))


                                                                                                                                                           

def test_an_unknown_subject_is_distinguishable_from_an_empty_one() -> None:
    ""                                                                   

                                                                             
                                                                             
                                                                          
                             
    import survey
    import paths
    projects = json.loads(
        (paths.REGISTRY / "projects.json").read_text(encoding="utf-8"))["projects"]
    empty = next((p["id"] for p in projects
                  if not (p.get("local_folders") or [])), None)
    absent = survey.survey({"kind": "project", "value": "project:no-such-thing-at-all"})
    check("an id nobody has answers with no project",
          absent["counts"]["projects"] == 0, str(absent["counts"]))
    if empty is None:
        print("  NOTE  every project on this estate has a folder, so the "
              "empty-but-real state is not available here "
              "[covered: the absent case above is the half that could conflate]")
        return
    real = survey.survey({"kind": "project", "value": empty})
    check(f"a real project with nothing in it answers with itself ({empty})",
          real["counts"]["projects"] == 1, str(real["counts"]))
    check("so the two are not the same answer",
          real["counts"] != absent["counts"],
          "zero for both would make 'no such project' unreadable")


def test_the_wire_refuses_a_scope_the_schema_permits_but_cannot_mean() -> None:
    ""                                                                         
                                                                           
    sch = schema()["properties"]["scope"]
    check("the schema really does permit it",
          sch.get("required") == ["kind"],
          f"required={sch.get('required')} — if `value` became required this "
          f"case is stale and the server's guard is belt without braces")
    import importlib.util
    spec = importlib.util.spec_from_file_location("srv_inputs", ROOT / "mcp/server.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["srv_inputs"] = mod
    spec.loader.exec_module(mod)
    for kind in ("project", "owner"):
        got = mod._scope_error(kind, None)
        check(f"kind={kind} with no value is a typed error",
              isinstance(got, dict) and got.get("error") == "missing value", str(got))
        check(f"and it tells the caller what {kind} takes",
              kind in (got or {}).get("hint", ""), str(got))
    check("while estate needs no value", mod._scope_error("estate", None) is None,
          str(mod._scope_error("estate", None)))


if __name__ == "__main__":
    print("wire inputs — what a host may send and the estate never has\n")
    for fn in (test_a_cursor_that_is_not_an_id_is_reported,
               test_a_well_formed_cursor_is_not_second_guessed,
               test_a_cursor_past_the_end_is_an_empty_page_not_an_error,
               test_an_unknown_subject_is_distinguishable_from_an_empty_one,
               test_the_wire_refuses_a_scope_the_schema_permits_but_cannot_mean):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32ma permitted input gets an answer or a reason, never a silent guess\033[0m")
