#!/usr/bin/env python3
""                                                                     

                                                                             
                                                                     

                                                                        
                                                                             
                                                                              
                                                                              
            
   
from __future__ import annotations
import json
import sys

OWNER = "agent:claude-code"


def main() -> int:
    try:
        r = json.load(sys.stdin)
    except Exception:
        return 0
    if not r.get("recorded"):
                                                                           
                                                                              
                                                                         
                                                                             
                                                                              
                                                                             
                                                                           
                                                        
         
                                                                               
        reason = r.get("reason") or ""
        if not r.get("fault"):
            return 0                                                               
        print(json.dumps({"systemMessage":
                          "Observatory could NOT record this turn: " + reason +
                          "\n\nThe facts of this turn are not in the ledger. "
                          "`store/raw/record-turn.json` holds the same reason, and "
                          "`./observatory.py findings` raises it.",
                          "suppressOutput": True}))
        return 0
    if r.get("hasWhy"):
        return 0                                                             

    mid = r.get("memoryId")
    rev = r.get("revision")
    project = r.get("project", "this project")
    files = r.get("files", 0)
    plural = "" if files == 1 else "s"
    unpushed = r.get("unpushed") or 0
    extra = f", {unpushed} unpushed commit(s)" if unpushed else ""

    message = (
        f"Observatory recorded the facts of this turn in {project}: "
        f"{files} file{plural} changed, +{r.get('insertions', 0)}/-{r.get('deletions', 0)}"
        f"{extra}. Stored as {mid}@{rev}, state proposed, with no `why`.\n\n"
        "The diff already says WHAT changed. Add WHY — one or two sentences a "
        "reader in six months could not reconstruct from the diff: the constraint "
        "that forced the shape, the alternative rejected, the trap avoided.\n\n"
        f"  observatory_record(owner=\"{OWNER}\", memory_id=\"{mid}\", "
        f"expected_revision={rev}, statement=<the same claim>, why=<the reason>)\n\n"
        "If the change genuinely needs no explanation — a typo, a rename — say so "
        "and skip it. An empty `why` on a trivial edit is honest; an invented one "
        "is worse than nothing, because it will be read as true."
    )
                                                                                
                                                                                 
                                                                            
                                                                                
    stale_bits = []
    g = r.get("graphAgeDays")
    if isinstance(g, int) and g > 7:
        stale_bits.append(f"its code graph is {g} days old — refresh it: "
                          f"/graphify . --update")
    w = r.get("wikiAgeDays")
    if isinstance(w, int) and w > 7:
        stale_bits.append(f"its wiki notes were last touched {w} days ago — if this "
                          f"work changed what the project IS (modules, scope, "
                          f"stack), update the overview note too")
    if stale_bits:
        message += ("\n\nWhile you are here — this project's recorded knowledge "
                    "is behind its code:\n  - " + "\n  - ".join(stale_bits))
    print(json.dumps({"systemMessage": message, "suppressOutput": True},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
