#!/usr/bin/env python3
""                                                                             

                                                                              
                                                                     

                                                                                  
                                                                               
                                                                                
                                                                      
                                                                             
                                                                           
                                                                                
                                                                                
                                                                 
                                                                                
                                                                                
                                                                             
                                                                                  
                                                                                
                                                                              
                                                                            
                                                                             
                                                                                
                                                                 

                                                                               
              
   
from __future__ import annotations

                                                                    
LISTED = 6


def _listed(names: list[str]) -> str:
    shown = sorted(names)[:LISTED]
    rest = len(names) - len(shown)
    return ", ".join(shown) + (f" and {rest} more" if rest > 0 else "")


def _real(doc: dict) -> list[dict]:
    ""                                                               
    return [f for f in doc.get("files", []) if f.get("kind") == "env"]


def tracked_in_git(doc: dict) -> list[dict]:
    ""                                                       
    out = []
    for f in _real(doc):
        if f.get("git") != "tracked":
            continue
        secrets = [v["name"] for v in f.get("variables", [])
                   if v.get("class") == "secret"]
        out.append({
            "type": "env.tracked_in_git",
            "subject": f["id"],
            "severity": "critical" if secrets else "warning",
            "title": f"{f['path']} is committed to git",
            "detail": (f"It is a live env file, not a template, and git tracks it — "
                       f"so its contents are in the repository's history and on "
                       f"every clone of it."
                       + (f" {len(secrets)} of its variables read as credentials: "
                          f"{_listed(secrets)}." if secrets else
                          " None of its variables reads as a credential, which is "
                          "why this is a warning rather than an incident.")
                       + " Removing the file from the working tree does not remove "
                         "it from the history."),
            "action": ("rotate what it holds, then `git rm --cached` it and add the "
                       "path to .gitignore; record the exposure with "
                       "`tools/vault.py leak --where` so the debt stays visible"),
        })
    return out


def unignored(doc: dict) -> list[dict]:
    ""                                                                     
    rows = [f for f in _real(doc) if f.get("git") == "loose"]
    if not rows:
        return []
    return [{
        "type": "env.unignored",
        "subject": "estate:env-unignored",
        "severity": "warning",
        "title": (f"{len(rows)} env files are untracked but not ignored"
                  if len(rows) > 1 else "1 env file is untracked but not ignored"),
        "detail": ("git does not carry them today and nothing stops it carrying them "
                   f"tomorrow: {_listed([f['path'] for f in rows])}. In `git status` "
                   "they are indistinguishable from a file that is safely ignored, "
                   "and `git add -A` does not ask."),
        "action": "add each path to its repository's .gitignore",
    }]


def world_readable(doc: dict) -> list[dict]:
    ""                                                              
    rows = [f for f in _real(doc)
            if any(v.get("class") == "secret" for v in f.get("variables", []))
            and f.get("mode", "0600")[-2:] != "00"]
    if not rows:
        return []
    return [{
        "type": "env.world_readable",
        "subject": "estate:env-modes",
        "severity": "warning",
        "title": (f"{len(rows)} env files holding credentials are readable beyond their owner"
                  if len(rows) > 1 else
                  "1 env file holding credentials is readable beyond its owner"),
        "detail": ("Their mode grants group or other read, so any process on this "
                   "machine that is not this user can read the values: "
                   + _listed([f"{f['path']} ({f['mode']})" for f in rows])
                   + ". A backup agent, a sync client and a second account all "
                     "qualify, and none of them announces itself."),
        "action": "chmod 600 each of them; nothing that reads an env file needs more",
    }]


def shared_secret(doc: dict) -> list[dict]:
    ""                                                                              
    groups = [g for g in doc.get("shared", []) if g.get("class") == "secret"]
    if not groups:
        return []
    widest = max(groups, key=lambda g: len(g["projects"]))
    return [{
        "type": "env.shared_secret",
        "subject": "estate:env-shared",
        "severity": "info",
        "title": (f"{len(groups)} credentials are held by more than one project"
                  if len(groups) > 1 else
                  "1 credential is held by more than one project"),
        "detail": ("Measured by value, not by name, which is why "
                   + ", ".join(widest["names"][:3])
                   + (" are one credential under " + str(len(widest["names"]))
                      + " names across " + str(len(widest["projects"]))
                      + " projects" if len(widest["names"]) > 1 else
                      " is one credential across " + str(len(widest["projects"]))
                      + " projects")
                   + ". Rotating any of these changes what every project sharing it "
                     "must hold, at the same moment. The widest: "
                   + _listed(widest["projects"]) + "."),
        "action": ("open the ENV tab, and where a group is genuinely one account, "
                   "record it in collectors/credential_owners.json with these sites "
                   "as the evidence — equal values prove equality, not intent"),
    }]


def reusable_slot(doc: dict) -> list[dict]:
    ""                                                               
    rows = [(f["path"], v["name"], v["available_in"])
            for f in _real(doc) for v in f.get("variables", [])
            if v.get("available_in")]
    if not rows:
        return []
    return [{
        "type": "env.reusable_slot",
        "subject": "estate:env-reusable",
        "severity": "info",
        "title": (f"{len(rows)} empty credential slots have a value in another project"
                  if len(rows) > 1 else
                  "1 empty credential slot has a value in another project"),
        "detail": ("Each of these is a variable this project declares and leaves "
                   "blank while another project here holds a live one under the same "
                   "name: "
                   + _listed([f"{p}:{n} (in {w[0]})" for p, n, w in rows])
                   + ". Same name is not same account — a staging key and a "
                     "production key share a name by design — so this is where to "
                     "look, not what to copy."),
        "action": ("open the ENV tab and reveal the value in the project that has "
                   "one; the reveal is audited and the value never reaches this page"),
    }]


def findings(doc: dict | None) -> list[dict]:
    ""                                                                            
                                                                        
    if not doc or not doc.get("files"):
        return []
    return (tracked_in_git(doc) + unignored(doc) + world_readable(doc)
            + shared_secret(doc) + reusable_slot(doc))
