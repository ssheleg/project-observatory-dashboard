#!/usr/bin/env python3
""                                                                                 

                                                                              
                                                                             
                                                                     

                                                                                  
                                                                             
                                                                        
                                                                        

                                                                             
                                                                             
                                                                            
                                                                              
                                                                             
                                    
                                                                           
                                                                           
                                                          
                                                                               
                                                                             
                                                                         
                                                              

                                                                         
                       
   
from __future__ import annotations

                                                                    
LISTED = 6


def _listed(names: list[str]) -> str:
    shown = sorted(names)[:LISTED]
    rest = len(names) - len(shown)
    return ", ".join(shown) + (f" and {rest} more" if rest > 0 else "")


def _short(cred: dict) -> str:
    return cred.get("name") or cred["id"].split("/")[-1]


def lifetime_cap(creds: list[dict]) -> list[dict]:
    ""                                                                          
    out = []
    for c in creds:
        if c.get("limit") in (None, 0) or c.get("limit_reset"):
            continue
        out.append({
            "type": "credential.lifetime_cap",
            "subject": c["id"],
            "severity": "warning",
            "title": f"{_short(c)} is capped for its lifetime, not per month",
            "detail": (f"Its limit is {c['limit']} with no reset, so it spends down "
                       f"once and then stops — months later, and with nothing on the "
                       f"day it happens to say why. A monthly budget behaves the same "
                       f"until it does not."
                       + (f" {c['usage']} of it is already spent."
                          if c.get("usage") else "")),
            "action": ("set `limit_reset` to monthly on the provider, or say out loud "
                       "that a lifetime cap is what this key is for"),
        })
    return out


def unclaimed(creds: list[dict]) -> list[dict]:
    ""                                                                          
    rows = [c for c in creds if not (c.get("used_by") or [])]
    if not rows:
        return []
    return [{
        "type": "credential.unclaimed",
        "subject": "estate:credentials-unclaimed",
        "severity": "info",
        "title": (f"{len(rows)} credentials belong to no project here"
                  if len(rows) > 1 else "1 credential belongs to no project here"),
        "detail": (f"Nothing measured says who uses them and nothing curated claims "
                   f"them: {_listed([_short(c) for c in rows])}. An unclaimed "
                   f"credential is one nobody will dare rotate, because the blast "
                   f"radius is unknown — which is the state a shared account drifts "
                   f"into on its own."),
        "action": ("add a row to collectors/credential_owners.json with the evidence "
                   "that proves who uses it; a row without evidence is refused"),
    }]


def untracked(creds: list[dict]) -> list[dict]:
    ""                                                                 
    out = []
    for c in creds:
        if c.get("kind") != "leaked-untracked":
            continue
        out.append({
            "type": "credential.untracked",
            "subject": c["id"],
            "severity": "warning",
            "title": f"{_short(c)} is known only because it leaked",
            "detail": (f"It was recorded where it was SEEN"
                       + (f" on {c['leaked_on']}" if c.get("leaked_on") else "")
                       + ", and the estate holds no record of the credential itself — "
                         "so after a rotation nothing here can tell whether the value "
                         "in service is the new one."),
            "action": (f"tools/vault.py put {c.get('vault_project') or '<project>'} "
                       f"{c.get('env') or '<env>'} {_short(c)} — value on stdin — then "
                       f"rotate it at its issuer"),
        })
    return out


def shared_rotation(creds: list[dict]) -> list[dict]:
    ""                                                                             
    rows = [c for c in creds if len(c.get("used_by") or []) > 1]
    if not rows:
        return []
    return [{
        "type": "credential.shared_rotation",
        "subject": "estate:credentials-shared",
        "severity": "info",
        "title": (f"{len(rows)} credentials are used by more than one project"
                  if len(rows) > 1 else
                  "1 credential is used by more than one project"),
        "detail": ("Rotating one of these changes what every project sharing it must "
                   "hold, at the same moment: "
                   + "; ".join(f"{_short(c)} → {len(c['used_by'])} projects"
                               for c in rows[:LISTED])
                   + ". That is not a defect — it is the reason the edge is recorded "
                     "at all, and the reason a rotation needs a plan rather than a "
                     "command."),
        "action": ("before rotating, list the projects on the Ключи tab and deploy "
                   "them together, or split the account so each holds its own"),
    }]


def unsigned(creds: list[dict]) -> list[dict]:
    ""                                                                

                                                                               
                                                                                
                                                                          
                                                                                  
                                                                
       
    bare = sorted(c["id"] for c in creds if not (c.get("signature") or {}).get("purpose"))
    if not bare:
        return []
    return [{
        "type": "credential.unsigned",
        "subject": "estate:credentials",
        "severity": "info",
        "title": f"{len(bare)} credential(s) carry no statement of what they are for",
        "detail": (f"{_listed([b.split(':', 1)[-1] for b in bare])}. A credential "
                   f"with no purpose cannot be retired, delegated or judged when "
                   f"it leaks — «is this still needed» has no answer, so it is "
                   f"kept forever and rotated never."),
        "action": ("`tools/sign_credential.py set <id> --purpose \"…\" --evidence "
                   "\"…\"`, or the «подписать…» button on the keys page"),
    }]


def rotation_due(creds: list[dict], today: str) -> list[dict]:
    ""                                                            

                                                                          
                                                                           
                                                                            
                                                                    
       
    import datetime
    out = []
    for c in creds:
        days = (c.get("signature") or {}).get("rotation_days")
        if not days:
            continue
        since = c.get("rotated_on") or c.get("created_on") or c.get("installed_on")
        if not since:
            continue
        try:
            age = (datetime.date.fromisoformat(today)
                   - datetime.date.fromisoformat(str(since)[:10])).days
        except ValueError:
            continue
        if age <= days:
            continue
        out.append({
            "type": "credential.rotation_due",
            "subject": c["id"],
            "severity": "warning",
            "title": (f"{_short(c)} was last set {age} day(s) ago and its own "
                      f"policy says every {days}"),
            "detail": (f"The policy is this credential's own — `rotation_days` in "
                       f"its signature — and it is {age - days} day(s) past. "
                       f"{'It was rotated' if c.get('rotated_on') else 'It has never been rotated; the date is when it was created'} "
                       f"on {str(since)[:10]}."),
            "action": ("rotate it through its door, then `tools/vault.py moved` "
                       "if the value went anywhere else"),
        })
    return out


def project_file_exposed(creds: list[dict]) -> list[dict]:
    ""                                                                       

                                                                               
                                                                              
                                                                                
                                                                               
                                                                            

                                                                         
                                                                                
                                                                           
                                                                             
       
    files = [c for c in creds if c.get("kind") == "project-secret-file"]
    if not files:
        return []
    out = []
    tracked = sorted(f"{c['in_project']}/{c['path']}" for c in files if c.get("git") == "tracked")
    if tracked:
        out.append({
            "type": "credential.project_file_in_git",
            "subject": "estate:project-secrets",
            "severity": "critical",
            "title": f"{len(tracked)} secret file(s) beside the code are tracked by git",
            "detail": (f"{_listed(tracked)}. The value is in the repository's history and "
                       f"on every clone of it; removing the file from the working tree "
                       f"does not remove it from the history, so rotation is the remedy "
                       f"and `git rm --cached` plus a .gitignore line is the part that "
                       f"stops it happening twice."),
            "action": "rotate what it holds, then `git rm --cached` it and ignore the path",
        })
    loose = sorted(f"{c['in_project']}/{c['path']}" for c in files if c.get("git") == "loose")
    if loose:
        out.append({
            "type": "credential.project_file_unignored",
            "subject": "estate:project-secrets",
            "severity": "warning",
            "title": f"{len(loose)} secret file(s) beside the code are neither tracked nor ignored",
            "detail": (f"{_listed(loose)}. One `git add -A` from the row above, and "
                       f"indistinguishable from a safe file in every listing that does "
                       f"not ask git the second question."),
            "action": "add the path to that repository's .gitignore",
        })
    open_mode = sorted(f"{c['in_project']}/{c['path']} ({c['mode']})" for c in files
                       if str(c.get("mode", "")).endswith(("4", "5", "6", "7"))
                       and str(c.get("mode", ""))[-2:] != "00")
    if open_mode:
        out.append({
            "type": "credential.project_file_readable",
            "subject": "estate:project-secrets",
            "severity": "warning",
            "title": f"{len(open_mode)} secret file(s) beside the code are readable by more than their owner",
            "detail": f"{_listed(open_mode)}. One `chmod 600` loop, not N decisions.",
            "action": "`chmod 600` them",
        })
    return out


def findings(doc: dict | None) -> list[dict]:
    ""                                                                               
                                                                              
    if not doc:
        return []
    creds = doc.get("credentials") or []
    if not creds:
        return []
                                                                           
                                                                               
                            
    today = (doc.get("scanned_on") or doc.get("updated_on") or "")[:10]
    broken = doc.get("registers_unreadable") or []
                                                                             
                                                                           
                                                                               
    annotations_ok = not any("annotations" in str(b.get("register", "")) for b in broken)
    return (register_unreadable(broken) + lifetime_cap(creds) + unclaimed(creds)
            + untracked(creds) + shared_rotation(creds)
            + (unsigned(creds) if annotations_ok else [])
            + project_file_exposed(creds)
            + (rotation_due(creds, today) if today else []))


def register_unreadable(broken: list[dict]) -> list[dict]:
    ""                                                                        

                                                                             
                                                                               
                                                                                 
                                                                             
                                                                           
                                  
       
    out = []
    for b in broken:
        out.append({
            "type": "credential.register_unreadable",
            "subject": f"register:{b.get('register')}",
            "severity": "warning",
            "title": f"the curated register {b.get('register')} exists and could not be read",
            "detail": (f"{b.get('problem')}. Everything in it — signatures, curated "
                       f"memberships — is absent from this build, and the rules that "
                       f"would have named that absence are withheld so the board does "
                       f"not report a file's syntax as an estate of unsigned keys."),
            "action": (f"open {b.get('path')} by hand; `tools/sign_credential.py` refuses "
                       f"to write over a file it cannot read, so nothing was lost by a "
                       f"later write"),
        })
    return out
