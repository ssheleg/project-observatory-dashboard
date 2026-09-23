#!/usr/bin/env python3
""                                                                            

                                                                           
                                                                                
                                                                                
                                                                               
                                                               

                                     

                                                                                  
                                                                        
                                                                             
                                                                             
                                                                         
                                                                               
                                                            
                                                                                  
                                                                           
                                                                              
                                                                                
                                                                          
                                                                                   
                                                                               
                                                                                
                                                           

                                                                               
                                                                                 
   
from __future__ import annotations
from datetime import date

                                                                             
                                                                                 
                                                                                  
                                                                              
                                                                                 
                                                                         
                                                                           
                              
STALE_AFTER_DAYS = 2

#: Listed by name up to this many; beyond it the row says how many more. Same
#: number as the other aggregates on the board, so a reader learns one rule.
LISTED = 6


def _listed(names: list[str]) -> str:
    shown = sorted(names)[:LISTED]
    rest = len(names) - len(shown)
    return ", ".join(shown) + (f" and {rest} more" if rest > 0 else "")


def app_down(apps: list[dict]) -> list[dict]:
    ""                                                           
    out = []
    for a in apps:
        if a["state"] not in ("down", "suspended") and not a.get("crashed"):
            continue
        suspended = a["state"] == "suspended"
        what = ("Heroku has SUSPENDED this application"
                if suspended else
                f"its dyno(s) {', '.join(a['crashed'])} are crashed"
                if a.get("crashed") else
                "it is scaled and nothing came up")
        # The last deploy is the operator's first question — a crash the day
        # after a deploy is a bad release, a crash two years after one is a
        # dependency or a platform change underneath it.
        since = (f"; the last code deploy was {a['last_deploy_on']}"
                 if a.get("last_deploy_on") else
                 "; no code was ever deployed to it")
        out.append({
            "type": "heroku.app_down",
            "subject": a["id"],
            "severity": "critical" if suspended else "warning",
            "title": (f"{a['name']} is paid for and not serving"),
            "detail": (f"{what}{since}. It bills ${a['monthly_cost']:.0f} a month "
                       f"and belongs to "
                       + (f"{a['project'].split(':', 1)[1]}" if a.get("project")
                          else "no project this registry holds") + "."),
            "action": ("ask Heroku support why it was suspended, or delete the "
                       "application and its add-ons"
                       if suspended else
                       f"heroku logs -a {a['name']} --tail, then restart it or "
                       f"scale it to zero and stop paying"),
        })
    return out


def paying_for_nothing(apps: list[dict]) -> list[dict]:
    ""                                                                                  
    out = []
    for a in apps:
        if a["state"] != "resources-only":
            continue
        plans = ", ".join(x["plan"] for x in a.get("addons", []))
        never = a.get("never_deployed")
        out.append({
            "type": "heroku.paying_for_nothing",
            "subject": a["id"],
            "severity": "warning",
            "title": f"{a['name']} pays for resources it cannot use",
            "detail": (f"No dyno is scaled, and {plans} still bills "
                       f"${a['monthly_cost']:.0f} a month."
                       + (" Code was never deployed to this application at all — "
                          "its whole history is the release that provisioned the "
                          "database." if never else "")),
            "action": ("delete the add-on, or scale a dyno if this was meant to be "
                       "running"),
        })
    return out


def orphan_app(apps: list[dict]) -> list[dict]:
    ""                                                                                            
    orphans = [a for a in apps
               if not a.get("project") and a["state"] in ("running", "down", "suspended")]
    if not orphans:
        return []
    cost = sum(a["monthly_cost"] for a in orphans)
                                                                                
                                                                              
                                                                             
                                                                           
    row = {
        "type": "heroku.orphan_app",
        "subject": "estate:heroku-orphans",
        "severity": "warning",
        "title": (f"{len(orphans)} running applications belong to no project here"
                  if len(orphans) > 1 else
                  "1 running application belongs to no project here"),
        "detail": (f"Heroku is running them and this registry cannot say what they "
                   f"are for: {_listed([a['name'] for a in orphans])}. Together "
                   f"${cost:.0f} a month. A link is only made where something was "
                   f"measured — Heroku's own Deploy tab, or a checkout carrying the "
                   f"application's git remote — so an orphan means neither exists, "
                   f"not that nobody looked."),
        "action": ("open the Heroku tab and filter to «нет проекта»; where you know "
                   "the answer, add it to collectors/heroku_links.json with the "
                   "evidence that proves it"),
    }
    return [row]


def no_local_clone(apps: list[dict]) -> list[dict]:
    ""                                                                                            
    absent = [a for a in apps if not a.get("local_folders")]
    if not absent:
        return []
    teams: dict[str, int] = {}
    for a in absent:
        teams[a["team"]] = teams.get(a["team"], 0) + 1
    whole = sorted(t for t, n in teams.items()
                   if n == sum(1 for a in apps if a["team"] == t))
    return [{
        "type": "heroku.no_local_clone",
        "subject": "estate:heroku-unclonned",
        "severity": "info",
        "title": f"{len(absent)} of {len(apps)} Heroku applications have no checkout here",
        "detail": ("Nothing on this machine can read or rebuild them; the source is "
                   "wherever it was last pushed from."
                   + (f" Entire team(s) absent: {', '.join(whole)}." if whole else "")
                   + " A laptop is not a backup, so this is a fact about reach rather "
                     "than about risk to the code."),
        "action": ("clone what you expect to work on; for the rest this row is the "
                   "record that they live elsewhere"),
    }]


def snapshot_stale(doc: dict, age: int) -> list[dict]:
    ""                                                                    

                                                                               
                                                                              
                                                                            
                                    
       
    return [{
        "type": "heroku.snapshot_stale",
        "subject": "estate:heroku-snapshot",
        "severity": "warning",
        "title": f"the Heroku snapshot is {age} days old, so nothing is being said about it",
        "detail": (f"`registry/heroku-apps.json` was measured on {doc.get('scanned_on')} "
                   f"and every rule about applications is withheld past "
                   f"{STALE_AFTER_DAYS} days. A crashed dyno reported from a stale "
                   f"scan may have been restarted, and one that crashed since is "
                   f"invisible — both are worse than an admitted gap."),
        "action": "./observatory.py heroku, then ./observatory.py emit findings",
    }]


def findings(doc: dict | None, today: date | None = None) -> list[dict]:
    ""                                                                                

                                                                                
                                                                             
                                                                           
                                                                          
                                
       
    if not doc:
        return []
    apps = doc.get("apps") or []
    if not apps:
        return []
    # THE AGE OF THE EVIDENCE DECIDES WHETHER THERE IS ANYTHING TO SAY.
    scanned = doc.get("scanned_on")
    if scanned:
        try:
            age = (today or date.today()) - date.fromisoformat(scanned)
        except ValueError:
            age = None
        if age is not None and age.days > STALE_AFTER_DAYS:
            return snapshot_stale(doc, age.days)
    rows = app_down(apps) + paying_for_nothing(apps) + orphan_app(apps) + no_local_clone(apps)
    # EVERY ROW NAMES THE DAY IT WAS MEASURED. Without it a reader cannot tell a
    # crash that happened an hour ago from one the scan saw two days ago, and the
    # remedy for the two is not the same.
    if scanned:
        for row in rows:
            row["detail"] = row["detail"].rstrip() + f" Measured {scanned}."
    return rows
