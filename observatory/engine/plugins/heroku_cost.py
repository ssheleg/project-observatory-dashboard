#!/usr/bin/env python3
""                                                                           

                                                                             
                                                                                
                                                                               
                                    

                                                                        
                                                                          
                                                                          
                                                                               
                                                 

                                                                                 
                                                                               
                                                                              
                                               
   
from __future__ import annotations
import json, pathlib, sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths              


def main() -> int:
    doc = paths.REGISTRY / "heroku-apps.json"
    if not doc.is_file():
        # The runner treats a missing requirement as a skip with a reason, and
        # this is the same rule one level in: no scan means no samples, never a
        # row of zero. A zero would be a claim that the project costs nothing.
        return 0
    apps = json.loads(doc.read_text(encoding="utf-8")).get("apps", [])

                                                                                
                                                                                
                                      
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

    cost: dict[str, float] = {}
    dynos: dict[str, int] = {}
    for a in apps:
        pid = a.get("project")
        if not pid:
            # An unlinked application is a real cost and it belongs to no
            # project, so it cannot be a row here. `heroku.orphan_app` is where
            # that money is reported, and it names the total.
            continue
        cost[pid] = cost.get(pid, 0.0) + float(a.get("monthly_cost") or 0)
        dynos[pid] = dynos.get(pid, 0) + int(a.get("scaled") or 0)

    for pid in sorted(cost):
        # A project whose applications are all scaled to zero still has a row,
        # because `0` measured is a different claim from no row at all — and it
        # is the row that shows a bill going to nothing after a shutdown.
        print(json.dumps({"project_id": pid, "metric": "heroku.cost_usd_month",
                          "at": at, "value": round(cost[pid], 2)}))
        print(json.dumps({"project_id": pid, "metric": "heroku.dynos",
                          "at": at, "value": float(dynos.get(pid, 0))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
