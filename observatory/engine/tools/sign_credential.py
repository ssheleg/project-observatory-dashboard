#!/usr/bin/env python3
""                                                                        

                                                                              
                                                                            
                                             

                                                                          
                                                                                  
                                                                               
                                                                              
                                                                              
                                                                       

                                                      

                                                                        
                                                                              
                                                                               
                                                              
                                                                                
                                                                                
                                                                          
                                                                              
                                                        

                                                                                  
                                                                               
   
from __future__ import annotations
import argparse
import datetime
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic                                                                   
import paths                                                                    

                                                                             
                                                                             
                                   
FILE = pathlib.Path(os.environ.get("OBSERVATORY_ANNOTATIONS",
                                   paths.config_file("credential_annotations.json")))
                                                                          
                                                                                
                                                                               
VALUE_SHAPED = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9_\-+/=]{40,})")


def today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def load() -> dict:
    ""                                                                           
                                                                              
                                                                               
                                                                              
                                                                               
    if not FILE.is_file():
        return {"schema_version": 1, "note": "", "annotations": {}}
    try:
        doc = json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"sign_credential: {FILE} exists and could not be read "
                         f"({type(exc).__name__}: {str(exc)[:120]}) — refusing to write "
                         f"over it; open it by hand, the board carries "
                         f"`credential.register_unreadable` for it")
    if not isinstance(doc, dict) or not isinstance(doc.get("annotations", {}), dict):
        raise SystemExit(f"sign_credential: {FILE} is not the register's shape — refusing "
                         f"to write over it")
    doc.setdefault("annotations", {})
    return doc


def board_ids() -> dict[str, dict]:
    try:
        doc = json.loads((paths.REGISTRY / "credentials.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {c["id"]: c for c in doc.get("credentials", [])}


def write(cred_id: str, fields: dict, *, by: str = "operator") -> dict:
    ""                                                                         
                                                            

                                                                       
       
    purpose = (fields.get("purpose") or "").strip()
    evidence = (fields.get("evidence") or "").strip()
    if not purpose:
        raise ValueError("--purpose is required: an unsigned credential is the "
                         "state this exists to end")
    if not evidence:
        raise ValueError("--evidence is required: a purpose nobody can check is a "
                         "guess that will be read as a fact")
    for field, text in (("purpose", purpose), ("evidence", evidence)):
        if VALUE_SHAPED.search(text):
            raise ValueError(f"refused: the {field} looks like it carries a value. "
                             f"This file is in git, and no later edit removes a "
                             f"credential from the history")
    ids = board_ids()
    if ids and cred_id not in ids:
        near = [i for i in ids if cred_id.split("/", 1)[0] == i.split("/", 1)[0]][:4]
        raise ValueError(f"the board carries no credential {cred_id!r}"
                         + (f" — same kind: {', '.join(near)}" if near else "")
                         + "\n  (ids are as registry/credentials.json prints them)")
    days = fields.get("rotation_days")
    if days is not None:
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValueError(f"--rotation-days must be a whole number of days, "
                             f"got {days!r}") from None
        if days < 1:
            raise ValueError("--rotation-days must be at least 1; a policy of zero "
                             "is a finding every day and a decision never")
    doc = load()
    row = dict(doc.setdefault("annotations", {}).get(cred_id) or {})
    row.update({"purpose": purpose, "evidence": evidence, "signed_on": today(),
                "signed_by": by})
    if fields.get("owner"):
        row["owner"] = str(fields["owner"]).strip()
    if days is not None:
        row["rotation_days"] = days
    if fields.get("tags"):
        row["tags"] = sorted({str(t).strip() for t in fields["tags"] if str(t).strip()})
    doc["annotations"][cred_id] = row
    doc["annotations"] = dict(sorted(doc["annotations"].items()))
    atomic.write_text(FILE, json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return row


def cmd_set(a) -> int:
    try:
        row = write(a.id, {"purpose": a.purpose, "evidence": a.evidence,
                           "owner": a.owner, "rotation_days": a.rotation_days,
                           "tags": a.tag}, by=a.by)
    except ValueError as exc:
        print(f"refused: {exc}" if not str(exc).startswith("refused")
              else str(exc), file=sys.stderr)
        return 2
    print(f"signed: {a.id}\n  for: {row['purpose'][:100]}\n"
          f"  owner: {row.get('owner', '—')}"
          + (f" · rotate every {row['rotation_days']} day(s)" if row.get("rotation_days") else "")
          + f"\n  known by: {row['evidence'][:100]}\n"
          f"  the board drops `credential.unsigned` for it at the next build")
    return 0


def cmd_show(a) -> int:
    doc = load().get("annotations") or {}
    ids = board_ids()
    if a.id:
        row = doc.get(a.id)
        if not row:
            print(f"{a.id} is not signed", file=sys.stderr)
            return 1
        print(json.dumps(row, ensure_ascii=False, indent=1))
        return 0
    if not doc:
        print("nothing is signed yet — "
              "`sign_credential.py set <id> --purpose … --evidence …`")
        return 0
    for cid, row in doc.items():
        state = "" if not ids or cid in ids else "  (no longer on the board)"
        print(f"  {cid}{state}\n     {row.get('purpose', '')[:90]}"
              f"  — {row.get('owner', 'no owner')}, {row.get('signed_on', '?')}"
              + (f", rotate every {row['rotation_days']}d" if row.get("rotation_days") else ""))
    unsigned = [i for i in ids if i not in doc]
    print(f"{len(doc)} signed, {len(unsigned)} not")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("set")
    p.add_argument("id")
    p.add_argument("--purpose", help="what it is for — required")
    p.add_argument("--evidence", help="how that is known — required")
    p.add_argument("--owner", help="a person or a team, never a file")
    p.add_argument("--rotation-days", type=int, dest="rotation_days",
                   help="opt-in: after this many days `credential.rotation_due` fires")
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--by", default="operator")
    p = sub.add_parser("show")
    p.add_argument("id", nargs="?")
    a = ap.parse_args(argv[1:])
    return {"set": cmd_set, "show": cmd_show}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
