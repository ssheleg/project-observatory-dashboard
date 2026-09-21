#!/usr/bin/env python3
""                                                                

                                                                                  
                                                                                
                

                                                                               
                                                                              
                                                                                
                                 

                                                      
                                                                         
                                                                            
                                                                                  
                                                
   
from __future__ import annotations
import argparse, json, re, sqlite3, subprocess, sys, pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic                                                                    
import paths                                                                     

OWNER = "agent:claude-code"
MAX_SUBJECTS = 8


                                                                                
                                                                                 
                                                                              
                                                     
NOT_A_FAULT = (
    "not a git repository",
    "not in the registry",
    "nothing changed",
    "unchanged since the last turn",
    "no session id",
                                                                              
                                                                                
                                                                              
                                                                           
                                                                               
                                                                             
                                                          
    "project ownership is",
)


                                                                       
                                                                                
                                                                               
                                                           
_session_id = ""
_cwd = ""


def out(payload: dict) -> int:
    ""                                                                     

                                                                             
                                                                           
                                                                    
                                                                                 
                                                                          
                                                                               
                  
       
    print(json.dumps(payload, ensure_ascii=False))
    reason = payload.get("reason") or ""
                                                                              
                                                                                
                                                                                
                                                                                
                                                                             
                               
    payload = {**payload,
               "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "session": _session_id or "",
               "fault": bool(reason) and not any(k in reason for k in NOT_A_FAULT)}
    try:
        atomic.write_json(paths.SCRATCH / "record-turn.json", payload)
    except Exception as exc:                                                      
                                                                              
                                                                                  
                                                                        
                                                                              
                                                           
        print(f"the record-turn receipt could not be written: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)

                                                                             
                                                                             
                                                                                  
                                                                           
                                                                           
                                                                          
                                                              
    if payload["fault"]:
        try:
            import companion_faults                                                 
            kept = companion_faults.append(
                {"at": payload["at"], "session": payload["session"],
                 "cwd": _cwd, "reason": reason})
            where = companion_faults.LOG
        except Exception as exc:                                                   
            kept, where = None, f"the fault log ({type(exc).__name__}: {exc})"
        if kept is None:
                                                                              
                                                                                
                                                                             
                                                                              
            print(f"the lost turn could not be added to {where}: the receipt is "
                  f"now its only record", file=sys.stderr)
    return 0


def _fault(exc: BaseException) -> int:
    ""                                                                 

                                                                             
                                                                             
                                                                                 
                                                                                  
                                                                                
                                                                               
                                                                 
       
    if isinstance(exc, sqlite3.Error):
        try:
            import store_faults                                                     
            store_faults.record("companion.record_turn", exc)                 
        except Exception:                                                          
            pass                                                                   
    return out({"recorded": False, "reason": f"{type(exc).__name__}: {exc}"})


def git(cwd: pathlib.Path, *args: str) -> str:
    try:
        p = subprocess.run(["git", "-C", str(cwd), *args],
                           capture_output=True, text=True, timeout=20)
    except Exception:
        return ""
    return p.stdout if p.returncode == 0 else ""


def repo_id_for(cwd: pathlib.Path) -> tuple[str | None, str | None]:
    ""                                                                             
    try:
        repos = json.loads((paths.REGISTRY / "repositories.json").read_text(encoding="utf-8"))
    except Exception:
        return None, None
    remote = git(cwd, "remote", "get-url", "origin").strip()
    nwo = None
    m = re.search(r"(?:github\.com|bitbucket\.org)[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", remote)
    if m:
        nwo = f"{m.group(1)}/{m.group(2)}"
    top = git(cwd, "rev-parse", "--show-toplevel").strip()
    for r in repos["repositories"]:
        if nwo and r["name_with_owner"] == nwo:
            return r["id"], top
        local = r.get("local") or {}
        if top and local.get("path") == top:
            return r["id"], top
    return None, top


                                                                        
                                                                              
                                           
  
                                                          
                                                                         
                                                                             
                                                                               
                                                                             
                                                                           
                                                                        
                                                         
import estate                                                                    
records_events = estate.records_events


def _knowledge_age(top: pathlib.Path) -> dict:
    ""                                                                     

                                                                             
                                                                               
                                                       
       
    import datetime as _dt
    out: dict = {"graphAgeDays": None, "wikiAgeDays": None}
    gj = top / "graphify-out" / "graph.json"
    if gj.is_file():
        try:
            out["graphAgeDays"] = max(0, int(
                (_dt.datetime.now(_dt.timezone.utc)
                 - _dt.datetime.fromtimestamp(gj.stat().st_mtime, _dt.timezone.utc)
                 ).total_seconds() // 86400))
        except OSError:
            pass
    vf = paths.SCRATCH / "vault.json"
    if vf.is_file():
        try:
            rows = json.loads(vf.read_text(encoding="utf-8"))
            row = next((r for r in rows if r.get("folder") == top.name), None)
            stamp = (row or {}).get("notes_updated_on")
            if stamp:
                out["wikiAgeDays"] = max(0, (
                    _dt.datetime.now(_dt.timezone.utc).date()
                    - _dt.date.fromisoformat(stamp)).days)
        except (OSError, ValueError, TypeError):
            pass
    return out


def project_for(repo_id: str) -> tuple[str | None, str | None]:
    ""                                                                     
    import paths
    try:
        rels = json.loads((paths.REGISTRY / "relations.json").read_text(encoding="utf-8"))
        projects = {p["id"]: p for p in
                    json.loads((paths.REGISTRY / "projects.json").read_text(encoding="utf-8"))["projects"]}
    except Exception:
        return None, None
    for rel in rels["relations"]:
        if rel["type"] == "implemented_by" and rel["to"] == repo_id:
            pid = rel["from"]
            return pid, (projects.get(pid) or {}).get("ownership")
    return None, None


def diff_facts(cwd: pathlib.Path) -> dict:
    ""                                                                    
    porcelain = [l for l in git(cwd, "status", "--porcelain").splitlines() if l.strip()]
    numstat = [l for l in git(cwd, "diff", "HEAD", "--numstat").splitlines() if l.strip()]
    ins = dele = 0
    for line in numstat:
        parts = line.split("\t")
        if len(parts) >= 2:
            ins += int(parts[0]) if parts[0].isdigit() else 0
            dele += int(parts[1]) if parts[1].isdigit() else 0
    files = sorted({l[3:].split(" -> ")[-1].strip() for l in porcelain})
    head = git(cwd, "rev-parse", "--short", "HEAD").strip()
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD").strip()
    unpushed = [l for l in git(cwd, "log", "--oneline", "@{u}..HEAD").splitlines() if l.strip()] \
        if git(cwd, "rev-parse", "--abbrev-ref", "@{u}").strip() else []
    return {"files": files, "insertions": ins, "deletions": dele, "head": head,
            "branch": branch, "unpushed": [u[:120] for u in unpushed[:MAX_SUBJECTS]]}


def statement_of(facts: dict, repo_id: str) -> str:
    n = len(facts["files"])
    bits = [f"{repo_id.split(':', 1)[1]} on {facts['branch'] or '?'}: "
            f"{n} file{'s' if n != 1 else ''} changed, "
            f"+{facts['insertions']}/-{facts['deletions']}"]
    if facts["unpushed"]:
        bits.append(f"{len(facts['unpushed'])} unpushed commit(s)")
    shown = facts["files"][:MAX_SUBJECTS]
    bits.append("touched: " + ", ".join(shown) + ("…" if n > len(shown) else ""))
    return " | ".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--session-id", default="")
    args = ap.parse_args()
                                                                               
                                                                                
                                                                               
    global _session_id, _cwd
    _session_id = args.session_id or ""
    _cwd = args.cwd or ""

    cwd = pathlib.Path(args.cwd)
    if not cwd.is_dir():
        return out({"recorded": False, "reason": "cwd does not exist"})
    if not git(cwd, "rev-parse", "--git-dir").strip():
        return out({"recorded": False, "reason": "not a git repository"})

    repo_id, top = repo_id_for(cwd)
    if repo_id is None:
        return out({"recorded": False,
                    "reason": "this repository is not in the registry; run "
                              "./observatory.py scan merge emit to add it"})
    facts = diff_facts(pathlib.Path(top or cwd))
    if not facts["files"] and not facts["unpushed"]:
        return out({"recorded": False, "reason": "nothing changed"})

    from store import db as store_db
    from store import ledger as L
    project_id, ownership = project_for(repo_id)
    if not estate.records_events(ownership):
        return out({"recorded": False,
                    "reason": f"project ownership is {ownership!r}; only "
                              f"{sorted(estate.RECORDED_OWNERSHIP)} are recorded"})
    project_id = project_id or repo_id
    statement = statement_of(facts, repo_id)
    evidence = [{"uri": f"repo:{repo_id}", "head": facts["head"], "branch": facts["branch"]},
                {"uri": "git:status --porcelain", "files": facts["files"][:40]}]

                                                                               
                                                                          
                                                                            
                                                                               
                                                                               
                                                                              
                                                                            
                                                              
    if not args.session_id:
        return out({"recorded": False,
                    "reason": "no session id: a row keyed to no session cannot be "
                              "revised, so every turn would add one to the review "
                              "queue instead of correcting the last",
                    "project": project_id})

    conn = store_db.connect()
    try:
        prior = None
        if args.session_id:
                                                                               
                                                                              
                                                                              
                                                                              
                                                                                
            row = conn.execute(
                "SELECT l.memory_id, l.revision, l.why, l.statement, l.state"
                " FROM ledger l JOIN (SELECT memory_id, MAX(revision) r FROM ledger"
                "   WHERE session_id = ? AND kind = 'session' GROUP BY memory_id) m"
                "  ON m.memory_id = l.memory_id AND m.r = l.revision"
                " WHERE l.memory_id NOT IN (SELECT memory_id FROM tombstones)"
                " ORDER BY l.revision DESC LIMIT 1", (args.session_id,)).fetchone()
            prior = row if row and row["memory_id"] else None
                                                                            
         
                                                                                 
                                                                              
                                                                                    
                                                                        
                                                                      
                                                                                
                                                                               
                                                                               
                                                                             
                                                                                
                                                                     
         
                                                                                
                                                                             
                                                                              
                                                                                 
                                                                             
                                                                                 
                                              
        continues = None
        if prior is not None and (prior["state"] or "") != "proposed":
            continues = prior["memory_id"]
            prior = None
        if prior is not None and prior["statement"] == statement:
                                                                           
                                                                        
                                                                             
            return out({"recorded": False, "reason": "unchanged since the last turn",
                        "memoryId": prior["memory_id"], "revision": prior["revision"],
                        "hasWhy": bool(prior["why"]), "project": project_id})
        result = L.append(
            conn, owner=OWNER, kind="session", statement=statement,
            why=prior["why"] if prior else None,
            memory_id=prior["memory_id"] if prior else None,
            expected_revision=prior["revision"] if prior else None,
            project_id=project_id, session_id=args.session_id or None,
            function="episodic", scope="project", state="proposed",
                                                                              
                                                                                   
                                                                            
                                                                            
                                                                            
                                                                                
                                                                      
            confidence=None, evidence=evidence,
            provenance=[{"source": "observatory-log/Stop", "measured": True,
                         **({"continues": continues} if continues else {})}])
        has_why = bool(prior and prior["why"])
        return out({"recorded": True, "memoryId": result["memoryId"],
                    "revision": result["revision"], "hasWhy": has_why,
                    "continues": continues,
                    "project": project_id, "files": len(facts["files"]),
                    "insertions": facts["insertions"], "deletions": facts["deletions"],
                    "unpushed": len(facts["unpushed"]),
                                                                                  
                                                                               
                                                                                  
                                                                               
                                                                              
                                                                              
                                                                               
                                 
                    **_knowledge_age(pathlib.Path(top or cwd))})
    except Exception as exc:
        return _fault(exc)
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:                                                                
                                                                               
                                                                                   
                                                                               
                        
        _fault(exc)
        raise SystemExit(0)
