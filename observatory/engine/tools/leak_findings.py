#!/usr/bin/env python3
""                                                

                                                                              
                                                                                  
                                                                               
                                                                                 
                                                              

                                                                           
                                                                             
                                                                              
                                                                                
                                            
   
from __future__ import annotations
import re

LISTED = 6

#: Names that identify rather than authenticate. An account id, a project id, a
#: SID, a public key: holding one proves nothing, so seeing one proves little.
IDENTIFIER = re.compile(r"(_ID$|_SID$|ACCOUNT_ID|PROJECT_ID|CLIENT_ID|_PUBLIC|"
                        r"PUBLIC_|_URL$|_HOST$|_REGION$|_BUCKET$)", re.I)


def _where(path: str) -> str:
    ""                                                                    
    if "/.claude/projects/" in path:
        rest = path.split("/.claude/projects/", 1)[1]
        return "session transcript " + rest
    if "/store/logs/" in path:
        return "this project's log " + path.split("/store/logs/", 1)[1]
    return path


def _name_of(secret: str) -> str:
    return secret.split("/")[-1]


def sightings(doc: dict | None) -> list[dict]:
    hits = (doc or {}).get("hits") or []
    if not hits:
        return []
    creds = [h for h in hits if not IDENTIFIER.search(_name_of(h["secret"]))]
    ids = [h for h in hits if IDENTIFIER.search(_name_of(h["secret"]))]
    out = []
    if creds:
        subjects = sorted({h["secret"] for h in creds})
        out.append({
            "type": "secret.seen_outside_its_home",
            "subject": "estate:leak-sightings",
            "severity": "critical",
            "title": (f"{len(subjects)} credentials appear in files they do not live in"
                      if len(subjects) > 1 else
                      "1 credential appears in a file it does not live in"),
            "detail": ("Measured by searching for the values this estate actually "
                       "holds, not for anything key-shaped — so each of these is the "
                       "value itself, sitting somewhere else: "
                       + "; ".join(f"{h['secret']} in {_where(h['where'])} "
                                   f"×{h['occurrences']}" for h in creds[:LISTED])
                       + (f" and {len(creds) - LISTED} more sighting(s)"
                          if len(creds) > LISTED else "")
                       + ". A session transcript outlives the key it quotes, is "
                         "copied by every backup, and is read back by tools that "
                         "summarise it."),
            "action": ("confirm each, then `tools/vault.py leak <project> <env> "
                       "<NAME> --where \"<the file>\"` to put it on the register; "
                       "rotating is the decision that clears it"),
        })
    if ids:
        subjects = sorted({h["secret"] for h in ids})
        out.append({
            "type": "secret.identifier_seen",
            "subject": "estate:leak-identifiers",
            "severity": "info",
            "title": (f"{len(subjects)} account identifiers appear outside their files"
                      if len(subjects) > 1 else
                      "1 account identifier appears outside its file"),
            "detail": ("These matched the same search and are probably harmless: an "
                       "account id is thirty-two hex characters, which no shape test "
                       "can tell from a secret, and it is public by design. They are "
                       "listed rather than filtered because the judgement is the "
                       "operator's: "
                       + "; ".join(f"{h['secret']} in {_where(h['where'])}"
                                   for h in ids[:LISTED])
                       + (f" and {len(ids) - LISTED} more" if len(ids) > LISTED else "")
                       + "."),
            "action": ("if one of these really does authenticate, treat it as the "
                       "row above; otherwise nothing to do"),
        })
    return out


def unscanned(doc: dict | None) -> list[dict]:
    ""                                                         
    notes = (doc or {}).get("not_scanned") or []
    if not notes:
        return []
    return [{
        "type": "secret.leak_scan_blind",
        "subject": "estate:leak-scan-coverage",
        "severity": "info",
        "title": f"the leak scan did not read {len(notes)} source(s)",
        "detail": ("A clean scan is only as wide as what it opened: "
                   + "; ".join(f"{n['what']} — {n['why']}" for n in notes[:LISTED])
                   + "."),
        "action": ("`tools/scan_leaks.py --full --days 60` widens the window; a "
                   "source named here as unreadable needs its own reader"),
    }]


def findings(doc: dict | None) -> list[dict]:
    if not doc:
        return []
    if doc.get("degraded"):
        return [{
            "type": "secret.leak_scan_unmeasured",
            "subject": "estate:leak-scan-coverage",
            "severity": "warning",
            "title": "the leak scan had nothing to look for",
            "detail": ("It ran and found nothing because it knows no values on this "
                       "machine — no env scan, no vault, no installed key. A clean "
                       "report from it means UNMEASURED, and the difference is the "
                       "whole point of saying so."),
            "action": "./observatory.py env, then ./observatory.py leaks",
        }]
    return sightings(doc) + unscanned(doc)
