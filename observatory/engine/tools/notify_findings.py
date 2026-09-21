#!/usr/bin/env python3
""                                                                  

                                                                             
                                                                               
                                                                          
                                                                                
                                                                                  
                                                                              
                                                                        

                                                                                
                                                                            
                                                                           
                                                                         

                                                                                
                                                                               
                              

                                                   
   
from __future__ import annotations
import hashlib, json, pathlib, sqlite3, subprocess, sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths              
import atomic              

FINDINGS = paths.REGISTRY / "findings.json"
KIND = "finding.notified"
                                                                 
CLEARED = "finding.cleared"


def episode(con: sqlite3.Connection, fid: str) -> int:
    ""                                                                            

                                                                             
                                                                        
                                                                        
                                                                                
                                                                  
                                                                           
                                                                             
                                           

                                                                              
                                                                               
                                                                                
                                                  

                                                                              
                                                                            
                                                                              
                                                                          
       
    return con.execute("select count(*) from events where kind = ? and ref like ?",
                       (CLEARED, f"{fid}#%")).fetchone()[0]


def close_episodes(con: sqlite3.Connection, open_ids: set[str]) -> list[str]:
    ""                                                                       

                                                                             
                                                                                
                                                         
       
    notified = [r[0] for r in con.execute(
        "select ref from events where kind = ?", (KIND,))]
                                                                               
                                                                         
                                                                               
                                                                              
                                                                             
                                                          
    started: dict[str, set[int]] = {}
    for ref in notified:
        base, _, ep = ref.rpartition("#")
        if base and ep.isdigit():
            started.setdefault(base.rsplit("@", 1)[0], set()).add(int(ep))
        else:
                                                                       
            started.setdefault(ref.rsplit("@", 1)[0], set()).add(0)
    closed = []
    for fid in sorted(set(started) - open_ids):
        k = episode(con, fid)
        if k not in started[fid]:
            continue                                                       
        cur = con.execute(
            "insert or ignore into events (id, kind, ref, actor, occurred_at,"
            " payload_json) values (?,?,?,?,?,?)",
            (f"ev:cleared:{hashlib.sha256(f'{fid}#{k}'.encode()).hexdigest()[:16]}",
             CLEARED, f"{fid}#{k}", "tool:notify_findings", now_z(),
             json.dumps({"episode": k}, ensure_ascii=False)))
        if cur.rowcount:
            closed.append(f"{fid}#{k}")
    if closed:
        con.commit()
    return closed


def notify(title: str, body: str) -> tuple[bool, str]:
    ""                                                                   

                                                                        
                                                                          
                                                                        
               
       
    esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
    try:
        r = subprocess.run(
            ["osascript", "-e",
             f'display notification "{esc(body)}" with title "{esc(title)}"'],
            capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return True, "osascript accepted it"
        return False, f"osascript exited {r.returncode}: {(r.stderr or '').strip()[:160]}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _report(when: str, delivered: bool, detail: str, undelivered: list[dict]) -> None:
    ""                                                                           
    atomic.write_json(paths.SCRATCH / "notify.json", {
        "attempted_at": when, "delivered": delivered, "detail": detail,
        "undelivered": undelivered})


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    levels = {"critical", "warning"} | ({"info"} if "--include-info" in argv else set())
    if not FINDINGS.is_file():
        print("notify_findings: no findings.json — run tools/build_findings.py")
        return 0
    try:
        doc = json.loads(FINDINGS.read_text(encoding="utf-8"))
        if not isinstance(doc.get("findings"), list):
            raise ValueError("no `findings` list")
    except (ValueError, OSError) as exc:
                                                                               
                                                                                  
                                                                              
                                                             
        print(f"notify_findings: findings.json is unreadable: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        _report(now_z(), False, f"findings.json unreadable: {type(exc).__name__}", [])
        return 1
    due = [f for f in doc["findings"]
           if f["severity"] in levels and not f.get("acked")]

                                                                                
                                                                                
                                                                           
                                                                            
                                                                      
    db = paths.DB
    if not db.is_file():
        print("notify_findings: no event store; refusing to send without a way to "
              "record that it was sent")
        return 0
    con = sqlite3.connect(db)
                                                                              
                                                                         
                        
                                                                            
                                                                          
                                                                               
                                                                           
                                   
    closed = [] if dry else close_episodes(con, {f["id"] for f in doc["findings"]})
    seen = {r[0] for r in con.execute(
        "select ref from events where kind = ?", (KIND,))}

    def ref_of(f: dict) -> str:
        return f"{f['id']}@{f['severity']}#{episode(con, f['id'])}"

                                                                   
                                                                                  
                                                                              
              
    def already(f: dict) -> bool:
        r = ref_of(f)
        return r in seen or (r.endswith("#0") and r[:-2] in seen)

    fresh = [f for f in due if not already(f)]
    if not fresh:
        print(f"notify_findings: {len(due)} open, nothing new since the last run"
              + (f"; {len(closed)} finding(s) closed: {', '.join(closed)}" if closed else ""))
        con.close()
                                                                            
                                                                                 
                                                                                
                                                                          
                                                                            
                
        _report(now_z(), True, "nothing new to deliver", [])
        return 0

    crit = [f for f in fresh if f["severity"] == "critical"]
    head = (f"{len(crit)} critical" if crit else f"{len(fresh)} new") + " finding" \
           + ("s" if (len(crit) if crit else len(fresh)) != 1 else "")
    body = "; ".join(f["title"] for f in (crit or fresh)[:3])
    if len(fresh) > 3:
        body += f"; +{len(fresh) - 3} more"

    if dry:
        print(f"[dry-run] would notify: {head} — {body}")
        for f in fresh:
            print(f"  {f['severity']:8s} {f['title']}")
        con.close()
        return 0

    sent, detail = notify(f"Observatory — {head}", body)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                                                                               
                                                                                  
                                                                               
                                                                              
                                                                             
                                                
     
                                                                               
                                                                                 
                                                                                
                           
    if sent:
        for f in fresh:
            ref = ref_of(f)
            con.execute(
                "insert or ignore into events (id, kind, ref, actor, occurred_at, "
                "payload_json) values (?,?,?,?,?,?)",
                                                                            
                                                                              
                                                                               
                                                                             
                (f"ev:notify:{hashlib.sha256(ref.encode()).hexdigest()[:16]}",
                 KIND, ref, "tool:notify_findings", now,
                 json.dumps({"title": f["title"], "severity": f["severity"],
                             "delivered": True}, ensure_ascii=False)))
        con.commit()
    con.close()

                                                                          
                                                                           
                                                                          
                                                                     
    _report(now, sent, detail,
            [] if sent else [{"id": f["id"], "severity": f["severity"],
                              "title": f["title"]} for f in fresh])
    print(f"notify_findings: {len(fresh)} new/escalated, "
          f"notification {'delivered' if sent else 'NOT DELIVERED — kept fresh so a later run can try, and raised as a finding'}")
    for f in fresh:
        print(f"  {f['severity']:8s} {f['title']}")
    return 0


if __name__ == "__main__":
    import configuration
    if (True) and not configuration.enabled("notifications", "features"):
        print("Not configured: enable features.notifications explicitly")
        raise SystemExit(0)

    raise SystemExit(main(sys.argv))
