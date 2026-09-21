#!/usr/bin/env python3
""                                                            

                                                                               
                                                                         
                                                                             
                                                                            
                                                                              
                    

                                                                                  
                                                                                
                                                                               
                             

                                                          

                                                                  
                              
                                                                                    
                                                                       
                                                                                 

                                                                                 
                                                                               
                                                                        
                                                                          
                                                                           
                                                                                
   
from __future__ import annotations
import argparse, json, pathlib, sqlite3, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths                                                                      
import atomic                                                                     
import proposals                                                                  
from store import db as store_db                                                  
from store import ledger as L                                                     
from store import retention as _retention                              

NEXT = {"proposed": "observed", "observed": "supported"}


def latest(conn) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT l.* FROM ledger l JOIN (SELECT memory_id, MAX(revision) rev FROM ledger "
        "GROUP BY memory_id) m ON l.memory_id = m.memory_id AND l.revision = m.rev "
        "ORDER BY l.created_at DESC").fetchall()


def require_terminal(action: str) -> None:
    if not sys.stdin.isatty():
        sys.exit(
            f"review: refusing to {action} without a terminal.\n"
            f"  Everything written here is owned by `operator` — exempt from retention, "
            f"and unsupersedable by any agent.\n"
            f"  Minting that authority from a script would let anything with shell "
            f"access forge it. Run this yourself; there is no --yes.")


def shown(value, width: int = 0) -> str:
    ""                                                                      

                                                                                
                                                                               
                                                                             
                                                                             
                  

                                                                              
                                                                           
                                                                                  
                                              
       
    if value is None:
        mark = "—"
    elif isinstance(value, float):
        mark = f"{value:.2f}"
    else:
        mark = str(value)
    return mark.rjust(width) if width else mark


def cmd_list(conn, args) -> int:
    rows = [r for r in latest(conn)
            if (not args.state or r["state"] == args.state)
            and (not args.kind or r["kind"] == args.kind)]
    if not rows:
        print("nothing matches")
        return 0
    by_state: dict[str, int] = {}
    for r in rows:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    print("  ".join(f"{k}={v}" for k, v in sorted(by_state.items())), "\n")
    for r in rows:
        conf = f"{shown(r['confidence'], width=4)}"
        print(f"{r['memory_id']}  r{r['revision']:<3} {r['state']:<9} {conf}  "
              f"{r['owner']:<20} {r['kind']:<11} {(r['project_id'] or '')[:28]:<28} "
              f"{(r['statement'] or '')[:60]}")
    return 0


def report_proposals(conn) -> int:
    ""                                                  

                                                                                   
                                                                                   
                                                                                
                                            

                                                                               
                                                                                
                                                                             
                                                                             
                                               
       
    try:
        pending = conn.execute(
            "SELECT id, target_id, status, created_at, substr(patch_json, 1, 90) AS patch"
            " FROM proposals WHERE status = 'proposed' ORDER BY created_at").fetchall()
    except sqlite3.Error as exc:
        print(f"\nproposals unreadable: {exc}")
        return 0
    if not pending:
        print("\nno registry proposals are pending")
        return 0
    plural = "" if len(pending) == 1 else "s"
    print(f"\n{len(pending)} registry proposal{plural} awaiting a decision:")
    for r in pending:
        print(f"  {r['created_at'][:10]}  {r['target_id']}  {r['patch']}")
        print(f"       {r['id']}")
    return len(pending)


def cmd_digest(conn, args) -> int:
    ""                                                                 

                                                                            
                                                                               
                                                                                   
                                                                                 
                                                                         

                                                                                 
                                                                          
                                                                                
                                                                               
                                                                          
                   
       
    import json as _json
    import sqlite3 as _sq
                                                                           
                                                                                   
                                                                                
    conn = _sq.connect(f"file:{paths.DB}?mode=ro", uri=True)
    conn.row_factory = _sq.Row
    horizon = 90
    try:
        cfg = _json.loads(paths.config_file("retention.json").read_text(encoding="utf-8"))
        horizon = int(cfg["ledger"]["proposed_days"])
    except Exception:
        pass
    rows = conn.execute(
        "SELECT l.memory_id, l.project_id, l.kind, l.owner, l.created_at,"
        "       l.confidence, l.revision, l.evidence_json,"
        "       substr(l.statement, 1, 150) AS gist"
        " FROM ledger l JOIN (SELECT memory_id, MAX(revision) rev FROM ledger"
        "   GROUP BY memory_id) m ON l.memory_id = m.memory_id AND l.revision = m.rev"
        " LEFT JOIN tombstones t ON t.memory_id = l.memory_id"
        " WHERE t.memory_id IS NULL AND l.state = 'proposed'"
        " ORDER BY l.project_id, l.created_at DESC").fetchall()
    if not rows:
        print("no ledger conclusion is waiting for a decision")
        report_proposals(conn)
        return 0

    from datetime import datetime, timezone, timedelta
    from collections import Counter as _Counter

    def _ord(stamp) -> float:
        ""                                                                    
                                                          
        try:
            return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc).timestamp()
        except (TypeError, ValueError):
            return 0.0
    _cls: dict[str, str] = {}
    now = datetime.now(timezone.utc)
    by_project: dict[str, list] = {}
    for r in rows:
        by_project.setdefault(r["project_id"] or "(no project)", []).append(r)

    soon = []
                                                                              
                                                                           
                                                                                
                                                                              
                                                                                
                                                                            
                                                                       
                                              
    import estate
    for pid, items in by_project.items():
        for r in items:
            _cls[r["memory_id"]] = estate.conclusion_class(r["evidence_json"])
    shape = _Counter(_cls.values())
    print(f"{len(rows)} conclusion(s) waiting, across {len(by_project)} project(s): "
          f"{shape.get('structural', 0)} rest on a structural change, "
          f"{shape.get('routine', 0)} on the working tree's own rhythm"
          + (f", {shape['unclassified']} on evidence this cannot read"
             if shape.get("unclassified") else "")
          + f". Retention tombstones a `proposed` row after {horizon} days"
          + (f", except rows owned by {', '.join(_exempt)}, which it never "
             f"erases — those are marked `kept` and still wait for a decision."
             if (_exempt := _retention.exempt_owners()) else "."))
                                                                           
                                                                              
                                                                                
                                                                         
                 
    _fold = estate.fold_groups([dict(r) for r in rows])
    _extra = sum(len(g["fold"]) for g in _fold)
    if _extra:
        print(f"{_extra} of them are superseded readings of a day the one-per-day "
              f"policy now corrects in place, in {len(_fold)} group(s). "
              f"`review.py reject-group <project> <day>` folds one group, from a "
              f"terminal — one decision instead of {_extra}.")
    print()

    def _project_key(kv):
        ""                                                                    
                                                                                  
                                                                           
        pid_, its = kv
        best = min((estate.conclusion_rank(_cls[r["memory_id"]]) for r in its),
                   default=99)
        oldest = min((r["created_at"] or "9999" for r in its), default="9999")
        return (best, oldest, pid_)

    for pid, items in sorted(by_project.items(), key=_project_key):
        ages, kept = [], 0
        for r in items:
            try:
                made = datetime.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
                                                                          
                                                                             
                                                                                 
                                                                        
                         
            left = _retention.days_left(r["owner"], "proposed", r["created_at"])
            if left is None:
                kept += 1
                continue
            ages.append(left)
            if left <= 14:
                soon.append((left, r["memory_id"], pid))
                                                                          
                                                                          
                                                                                 
                                           
        window = (f"{min(ages)}–{max(ages)}d left" if ages
                  else "no deadline" if kept else "age unknown")
        if kept:
            window += f", {kept} kept"
        klasses = _Counter(_cls[r["memory_id"]] for r in items)
        label = ", ".join(f"{n} {k}" for k, n in sorted(
            klasses.items(), key=lambda kv: estate.conclusion_rank(kv[0])))
        print(f"  {len(items):3}  {pid}   ({window}; {label})")
                                                                              
                                                                            
                                                                                  
                                                                            
                                                                        
        newest = min(items, key=lambda r: (estate.conclusion_rank(_cls[r["memory_id"]]),
                                           -_ord(r["created_at"])))
        print(f"       {_cls[newest['memory_id']]}: {newest['gist']}")
                                                                            
                                                                                
                                                                          
                                
        print(f"       {newest['memory_id']}  "
              f"confidence {shown(newest['confidence'])}")
    if soon:
        print(f"\n{len(soon)} row(s) will be ERASED UNREVIEWED within 14 days:")
        for left, mid, pid in sorted(soon)[:10]:
            print(f"  {left:3}d  {mid}  {pid}")
    report_proposals(conn)

    print("\nPromote or reject one with `review.py promote <memory_id>` — from a "
          "terminal, because operator authority is not mintable from a script.")
    return 0


def cmd_show(conn, args) -> int:
    hist = L.history(conn, args.memory_id)
    if not hist:
        sys.exit(f"review: {args.memory_id} does not exist")
    cur = hist[-1]
    print(f"{cur['memory_id']}  revision {cur['revision']}  state {cur['state']}")
    print(f"  owner       {cur['owner']}   "
          f"confidence {shown(cur['confidence'])}")
    print(f"  project     {cur['project_id']}   kind {cur['kind']}   "
          f"function {cur['function']}   scope {cur['scope']}")
    print(f"  statement   {cur['statement']}")
    print(f"  why         {shown(cur['why'])}")
    for label, blob in (("provenance", cur["provenance_json"]),
                        ("evidence", cur["evidence_json"])):
        for item in json.loads(blob or "[]"):
            print(f"  {label:<11} {json.dumps(item, ensure_ascii=False)[:140]}")
    print(f"  history     " + " -> ".join(f"r{h['revision']}:{h['state']}" for h in hist))
    nxt = NEXT.get(cur["state"])
    print(f"\n  next        {'promote -> ' + nxt if nxt else 'terminal; nothing to promote'}")
    return 0


def cmd_promote(conn, args) -> int:
    require_terminal("promote")
    cur = L.current(conn, args.memory_id)
    if cur is None:
        sys.exit(f"review: {args.memory_id} does not exist")
    nxt = NEXT.get(cur["state"])
    if not nxt:
        sys.exit(f"review: {args.memory_id} is {cur['state']!r}; there is nothing above it")
    out = L.transition(conn, args.memory_id, to_state=nxt, owner=L.OPERATOR,
                       expected_revision=cur["revision"],
                       why=args.why or cur["why"])
    print(f"promoted {args.memory_id}: {cur['state']} -> {out['state']} "
          f"(revision {out['revision']}, owner {out['owner']})")
    return 0


def cmd_reject(conn, args) -> int:
    require_terminal("reject")
    cur = L.current(conn, args.memory_id)
    if cur is None:
        sys.exit(f"review: {args.memory_id} does not exist")
    out = L.transition(conn, args.memory_id, to_state="rejected", owner=L.OPERATOR,
                       expected_revision=cur["revision"], why=args.why)
    print(f"rejected {args.memory_id} (revision {out['revision']}). "
          f"Retention drops a rejected record after 30 days; the revisions stay.")
    return 0


def cmd_reject_group(conn, args) -> int:
    ""                                                                        

                                                                              
                                                                                    
                                                                               
                                                                                 
                                    

                                                                               
                                                                                
                                                                                  
                                                                   

                                                                               
                                                                              
                                                                       
       
    require_terminal("reject a whole group")
    import estate
    rows = [dict(r) for r in conn.execute(
        "SELECT l.memory_id, l.project_id, l.kind, l.owner, l.created_at, l.revision"
        " FROM ledger l JOIN (SELECT memory_id, MAX(revision) rev FROM ledger"
        "   GROUP BY memory_id) m ON l.memory_id = m.memory_id AND l.revision = m.rev"
        " LEFT JOIN tombstones t ON t.memory_id = l.memory_id"
        " WHERE t.memory_id IS NULL AND l.state = 'proposed'"
        "   AND l.project_id = ? AND substr(l.created_at, 1, 10) = ?",
        (args.project, args.day))]
    groups = [g for g in estate.fold_groups(rows)]
    if not groups:
        print(f"review: nothing to fold for {args.project} on {args.day} — "
              f"{len(rows)} waiting record(s), no (project, kind, owner, day) group "
              f"holds more than one")
        return 0
    done = 0
    for g in groups:
        print(f"keeping {g['keep']} — the latest reading of {args.day}")
        for mid in g["fold"]:
            cur = L.current(conn, mid)
            if cur is None:
                print(f"  {mid}: gone")
                continue
            L.transition(conn, mid, to_state="rejected", owner=L.OPERATOR,
                         expected_revision=cur["revision"],
                         why=args.why or (
                             f"folded into {g['keep']}: one record per project per day "
                             f"is the policy since 2026-09-07, and this record exists "
                             f"only because an earlier version appended one per tick"))
            done += 1
            print(f"  rejected {mid}")
    print(f"\n{done} record(s) rejected, {len(groups)} group(s) folded. Retention "
          f"drops a rejected record after 30 days; the revisions stay.")
    return 0


def cmd_tombstone(conn, args) -> int:
    require_terminal("tombstone")
    cur = L.current(conn, args.memory_id)
    if cur is None:
        sys.exit(f"review: {args.memory_id} does not exist")
    L.tombstone(conn, args.memory_id, reason=args.why, approved_by=L.OPERATOR)
    print(f"tombstoned {args.memory_id}. The ledger row stays — an erasure leaves "
          f"a trace, and a missing audit trail is indistinguishable from a bug.")
    return 0


def _proposal(conn, pid: str) -> dict:
    row = conn.execute(
        "SELECT id, target_id, patch_json, evidence_json, status, created_at"
        " FROM proposals WHERE id = ?", (pid,)).fetchone()
    if row is None:
        sys.exit(f"review: proposal {pid} does not exist")
    if row["status"] != "proposed":
        sys.exit(f"review: proposal {pid} is already {row['status']!r}")
    return dict(row)


def cmd_proposal_accept(conn, args) -> int:
    ""                                                                     

                                                                           
                                                                       
                                                                                
                                                                           
                                                                            
                      

                                                                        
                                                                               
                                                                               
                                                                     
       
    require_terminal("accept a registry proposal")
    row = _proposal(conn, args.id)
    patch = json.loads(row["patch_json"] or "{}")
                                                                                   
                                                                             
                                                                             
                                        
    stored = json.loads(row["evidence_json"] or "[]")
    evidence = (stored.get("evidence") if isinstance(stored, dict) else stored) or []
    why = proposals.refusal(row["target_id"], patch, evidence)
    if why:
                                                                           
                                                                      
                                                                           
                                                                               
        sys.exit(f"review: this proposal cannot be applied — {why}")
    prefix = next(p for p in proposals.LANDS_IN if row["target_id"].startswith(p))
    name, key = proposals.LANDS_IN[prefix]
    f = paths.config_file(name)
    doc = json.loads(f.read_text(encoding="utf-8"))
    before = doc[key].get(row["target_id"], {})
    merged = {**before, **patch}
                                                                             
                                                                               
                                                                                
                                                                    
    merged["why"] = args.why
    merged["proposed_by"] = f"{row['id']} ({row['created_at']})"
    merged["evidence"] = evidence
    doc[key][row["target_id"]] = merged
    atomic.write_json(f, doc)
    with conn:
        conn.execute("UPDATE proposals SET status='accepted', decided_by=?,"
                     " decided_note=?, decided_at=? WHERE id=?",
                     (L.OPERATOR, args.why, L._now(), row["id"]))
    print(f"accepted {row['id']}: {', '.join(sorted(patch))} -> "
          f"collectors/{name}#{row['target_id']}")
    print("The registry changes on the next emit, not now — `./observatory.py "
          "emit` applies it, and the diff is what you commit.")
    return 0


def cmd_proposal_reject(conn, args) -> int:
    require_terminal("reject a registry proposal")
    row = _proposal(conn, args.id)
    with conn:
        conn.execute("UPDATE proposals SET status='rejected', decided_by=?,"
                     " decided_note=?, decided_at=? WHERE id=?",
                     (L.OPERATOR, args.why, L._now(), row["id"]))
    print(f"rejected {row['id']} against {row['target_id']}. The row stays with "
          f"the reason, so the same patch arriving again can be recognised.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--state", default="proposed")
    p.add_argument("--kind"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("digest", help="the queue grouped, with what retention will erase")
    p.set_defaults(fn=cmd_digest)
    p = sub.add_parser("show"); p.add_argument("memory_id"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("promote"); p.add_argument("memory_id")
    p.add_argument("--why"); p.set_defaults(fn=cmd_promote)
    for name, fn in (("reject", cmd_reject), ("tombstone", cmd_tombstone)):
        p = sub.add_parser(name); p.add_argument("memory_id")
        p.add_argument("--why", required=True,
                       help="not optional: a decision with no reason cannot be "
                            "reviewed by the person who finds it later")
        p.set_defaults(fn=fn)
    p = sub.add_parser("reject-group",
                       help="reject a (project, day) group's superseded readings, "
                            "keeping its latest — one decision instead of many")
    p.add_argument("project"); p.add_argument("day")
    p.add_argument("--why", help="optional here: the default reason names the policy "
                                 "that made these records unnecessary")
    p.set_defaults(fn=cmd_reject_group)
                                                                         
                                                                         
                                                          
    for name, fn in (("accept-proposal", cmd_proposal_accept),
                     ("reject-proposal", cmd_proposal_reject)):
        p = sub.add_parser(name, help="decide a registry proposal from "
                                      "`observatory_propose`")
        p.add_argument("id")
        p.add_argument("--why", required=True,
                       help="not optional: an override with no argument behind it "
                            "is a value the next reader cannot maintain")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    conn = store_db.connect()
    conn.row_factory = sqlite3.Row
    try:
        return args.fn(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
