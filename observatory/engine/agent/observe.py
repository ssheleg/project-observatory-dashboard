#!/usr/bin/env python3
""                                                                           

                                                                              
                                                                             

                                                                                 
                                                                          
                                                                             
                                 

                                                                       
                                                                           
                                                                               

                                                                   
                                                                                 
                                                                             
                                                                                  
                                                                                    

                                                                               
                                                        
   
from __future__ import annotations
import argparse, json, os, sys, pathlib, sqlite3
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths
from store import db as store_db
from store import ledger as L
import store_faults
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import providers
import atomic
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "collectors"))
try:
    from compute_deltas import meaning_of as _meaning
except Exception:                                                                  
    def _meaning(_kind: str) -> str:
        return ""

OWNER = "agent:observer"
                                                                            
                                                                      
AGENT_MAX_CONFIDENCE = 0.95

                                                                         
                                                                            
                                       
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
                                                                                
                                                                              
                                                                                
                                                                                 
                                                                                 
                                                                             
                                                                           
                                                                                
                                                                              
                                                                                 
                                                                       
    "required": ["worth_recording", "interpretation", "confidence", "why_not"],
    "properties": {
        "worth_recording": {
            "type": "boolean",
            "description": "False when nothing non-obvious happened. Prefer false over a "
                           "manufactured reason."},
        "interpretation": {
            "type": "string",
            "description": "One or two sentences on what the change MEANS. Empty string "
                           "when worth_recording is false."},
        "confidence": {
            "type": "number", "minimum": 0, "maximum": 1,
            "description": "How well the delta supports this reading. Below 0.5 is a guess."},
        "why_not": {
            "type": "string",
            "description": "When worth_recording is false, why the change needs no note — "
                           "name what made it mechanical. Empty string when recording."},
    },
}

SYSTEM = """You interpret changes in a software estate for its single operator.

You are given what MOVED in one project between two scans, plus the typed facts
already known about it and any reasoning already recorded. Your job is the one
thing the diff cannot contain: what the change MEANS.

Rules, and they are not stylistic:
- Do not restate the delta. "5 files changed" is already recorded; repeating it
  in prose fills the field so nobody looks again, and carries no information.
- Say `worth_recording: false` whenever nothing non-obvious happened. A mechanical
  bump, a dependency refresh, a rename — these need no interpretation, and an
  empty record is better than a manufactured one.
- Never invent a cause. You see a diff summary, not the work. If the delta
  supports two readings, say both, or say you cannot tell. A fabricated reason is
  read as true by everything downstream and nothing can distinguish it later.
- Confidence is an assessment, not permission to hide doubt. Below 0.5 means you
  are guessing, and a guess should usually be `worth_recording: false`.
- One or two sentences. This is a note in a ledger, not a report.
- Write in English so the shared ledger can be reviewed consistently. Preserve
  proper names and quoted evidence in their original language."""


                                                                            
                                                                             
                                                                                 
                                                                         
                                                                               
                                                                               
FOREIGN_LETTER_SHARE = 0.5


def non_latin_share(text: str) -> float:
    ""                                                                      

                                                                               
                                                                                
       
    letters = [ch for ch in text or "" if ch.isalpha()]
    if not letters:
        return 0.0
    latin = sum(1 for ch in letters if ord(ch) < 0x250)
    return 1.0 - latin / len(letters)


class _Answer:
    ""                                                                     

    def __init__(self, d: dict) -> None:
        self.worth_recording = bool(d.get("worth_recording"))
        self.interpretation = (d.get("interpretation") or "").strip()
        self.confidence = float(d.get("confidence") or 0.0)
        self.why_not = d.get("why_not")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def project_facts(pid: str) -> dict:
    try:
        projects = json.loads((paths.REGISTRY / "projects.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    for p in projects["projects"]:
        if p["id"] == pid:
            return {k: p.get(k) for k in
                    ("name", "description", "ownership", "lifecycle", "stack",
                     "local_folders", "membership_rules")}
    return {}


def already_recorded(conn, pid: str) -> list[str]:
    return [r["statement"] for r in conn.execute(
        "SELECT statement FROM ledger WHERE project_id = ? ORDER BY created_at DESC LIMIT 5",
        (pid,))]


def fold(deltas: list) -> list[dict]:
    ""                                                                       

                                                                              
                                                                                     
                                                                                 
                                                                                
                                                                              
                                                                           
                                                                                 
                                                                             
                                                                           
                                                     

                                                                              
                                                                                 
                                                                          

                                                                            
                                                                            
                                                                               
                                                                               
                                                   
       
    out: dict[str, dict] = {}
    for i, d in enumerate(sorted(deltas, key=lambda r: r.get("seq", 0))):
        m = out.get(d["kind"])
        if m is None:
            out[d["kind"]] = {"kind": d["kind"], "before_json": d["before_json"],
                              "after_json": d["after_json"], "changes": 1, "at": i}
        else:
            m["after_json"] = d["after_json"]
            m["changes"] += 1
    return sorted(out.values(), key=lambda m: m["at"])


def build_prompt(pid: str, deltas: list, facts: dict, prior: list[str]) -> str:
    lines = [f"# Project\n{pid}", "", "## Typed facts already known",
             json.dumps(facts, ensure_ascii=False, indent=1), "", "## What moved"]
    for m in fold(deltas):
                                                                                 
                                                                            
                                                                                  
                                                                              
                                                                         
        means = _meaning(m["kind"])
                                                                          
                                                                                 
                                                                               
        span = f"   (over {m['changes']} changes)" if m["changes"] > 1 else ""
        lines.append(f"- {m['kind']}: {m['before_json']} -> {m['after_json']}"
                     + span + (f"   ({means})" if means else ""))
    if prior:
        lines += ["", "## Already recorded about this project (do not repeat)"]
        lines += [f"- {s[:200]}" for s in prior]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=20, help="projects per run")
    ap.add_argument("--model", default=None,
                    help="override the configured chain with one model id. The caller is the "
                         "highest of the three selection levels and the choice is logged.")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be sent and spend nothing")
    args = ap.parse_args()

    conn = store_db.connect()
    try:
                                                                             
                                                                                  
                                                                              
                                                                              
                                                                             
                           
        faults: list[dict] = []

        def note_fault(pid: str, kind: str, reason) -> None:
            ""                                        

                                                                                 
                                                                               
                                                                   
               
            faults.append({"project": pid, "kind": kind,
                           "reason": (f"{type(reason).__name__}: {reason}"
                                      if isinstance(reason, BaseException)
                                      else str(reason))[:200]})
                                                                              
                                                                               
                                                                               
                                                                                 
                                                                               
                                                                                
            if kind == "store":
                store_faults.record("agent", reason if isinstance(reason, BaseException)
                                    else None,
                                    detail=f"project {pid}" if isinstance(reason, BaseException)
                                    else f"project {pid}: {reason}")

        def report(halted: str | None, rec: int = 0, skip: int = 0, fail: int = 0,
                   bad: int = 0, mute: int = 0,
                   retired: list[str] | None = None,
                   handled: list[str] | None = None,
                   waiting: list[str] | None = None, foreign: int = 0) -> None:
            ""                                            

                                                                       
                                                                                
                                                                             
                                                                              
                                                                               
                                                                            
                                                                          
               
                                                                                   
                                                                                
                                                                           
                                                                                
                                               
            left = conn.execute(
                "SELECT count(*) n, count(DISTINCT subject_id) projects,"
                "       min(s.started_at) since FROM deltas d"
                " LEFT JOIN scans s ON s.id = d.to_scan"
                " WHERE d.consumed_at IS NULL").fetchone()
            atomic.write_json(paths.SCRATCH / "agent.json", {
                "ran_at": now(), "recorded": rec, "skipped": skip, "failed": fail,
                                                                             
                                                                             
                                                                        
                                                                            
                "malformed": bad, "unreasoned": mute,
                                                                                
                                                                                
                                                                                 
                "faults": faults,
                "chain_retired": retired or [],
                "halted_by": halted,
                "unconsumed": left["n"] if left else 0,
                "projects_unconsumed": left["projects"] if left else 0,
                "oldest_unconsumed_scan": (left["since"] if left else None),
                                                                         
                                                                             
                                                                              
                                                                              
                                                                                
                                                                             
                                                                           
                                                                             
                                                        
                "not_english": foreign,
                "projects_handled": handled or [],
                "projects_waiting": waiting or [],
                "waiting_count": len(waiting or [])})

                                                                               
                                                                                 
                                                                              
                                                                          
                                                                    
        rows = [dict(r) for r in conn.execute(
            "SELECT rowid AS seq, id, subject_id, kind, before_json, after_json"
            " FROM deltas WHERE consumed_at IS NULL ORDER BY rowid")]
        if not rows:
            print("no unconsumed deltas — nothing moved, and this run spent nothing")
                                                                                
                                                                  
                                                                              
                                                                               
                                                                         
            report(None)
            return 0

        by_project: dict[str, list] = {}
        for r in rows:
            by_project.setdefault(r["subject_id"], []).append(r)
                                                                                 
                                                                                  
                                                                            
                                                                             
                                                                             
                                                                  
                                                                             
                                                                            
         
                                                                            
                                                                        
        order = sorted(by_project, key=lambda pid: (min(r["seq"] for r in by_project[pid]), pid))
        projects = order[:args.limit]
        waiting = order[args.limit:]
        print(f"{len(rows)} delta(s) across {len(by_project)} project(s); "
              f"this run takes {len(projects)}, oldest first"
              + (f"; {len(waiting)} project(s) wait for the next run" if waiting else ""))

                                                                                
                              
        if args.dry_run:
            for pid in projects:
                p = build_prompt(pid, by_project[pid], project_facts(pid),
                                 already_recorded(conn, pid))
                print(f"\n{'=' * 70}\n{p}")
            print(f"\n--- dry run: {len(projects)} prompt(s), 0 tokens spent")
                                                                              
                                                                           
                                                                      
                                                    
            return 0

                                                                              
                                                                               
                                                                                   
                                                                                
                                                                                 
                                                                             
                                                                                 
                                               
        if not providers.have_key():
            print(f"DEGRADED: {providers.key_status()}\n"
                  f"The collectors already recorded the facts; only the interpretation is "
                  f"missing. {len(rows)} delta(s) stay unconsumed and will be interpreted "
                  f"on the next run.", file=sys.stderr)
            report(f"no credential: {providers.key_status()}")
            return 0

        stop = providers.check_budget()
        if stop:
            print(f"DEGRADED: {stop}. Deltas are left unconsumed for the next run; "
                  f"collectors are unaffected.", file=sys.stderr)
            report(f"spend guardrail: {stop}")
            return 0

        recorded = failed = skipped = malformed = unreasoned = foreign = 0
                                                                            
                                                                               
                                                                                
                                                                                
                                            
        retired_models: list[str] = []
        try:
            _chain, _lvl, _prov = providers.resolve_chain()
            retired_models = list((_chain[0] if _chain else {}).get("chain_retired") or [])
            if retired_models:
                print(f"  chain: {len(retired_models)} configured model(s) are not in "
                      f"the catalogue and were skipped: {', '.join(retired_models)}",
                      file=sys.stderr)
        except Exception as exc:
                                                                                
                                                               
            print(f"  chain could not be resolved for the report: {exc}", file=sys.stderr)
        halted_by = None
        first_call = True
        for pid in projects:
            prompt = build_prompt(pid, by_project[pid], project_facts(pid),
                                  already_recorded(conn, pid))
            try:
                result = providers.complete(
                    [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
                    schema_name="interpretation", schema=SCHEMA,
                    requested=args.model,
                                                                                  
                                                                             
                                                                     
                    log=(lambda m: print(m)) if first_call else (lambda m: None))
                first_call = False
            except providers.BudgetExceeded as exc:
                print(f"  guardrail mid-run: {exc}; the rest stays unconsumed",
                      file=sys.stderr)
                halted_by = f"spend guardrail: {exc}"
                break
            except providers.CredentialError as exc:
                halted_by = f"credential refused: {exc}"
                print(f"  DEGRADED: the credential was refused — {exc}\n"
                      f"  No model is marked unhealthy: the key is the fault, not the model. "
                      f"Every delta stays unconsumed.", file=sys.stderr)
                note_fault(pid, "credential", exc)
                failed += 1; break
            except providers.Fatal as exc:
                print(f"  {pid}: fatal — {exc}", file=sys.stderr)
                note_fault(pid, "model-fatal", exc)
                failed += 1; break
            except providers.Retryable as exc:
                print(f"  {pid}: every model failed — {exc}", file=sys.stderr)
                note_fault(pid, "model-unavailable", exc)
                failed += 1; break
            except Exception as exc:
                print(f"  {pid}: {type(exc).__name__}: {exc}", file=sys.stderr)
                note_fault(pid, "unexpected", exc)
                failed += 1; continue

            parsed = _Answer(result["parsed"])
            model_used, spent_here = result["model"], result["cost"]
            ids = [d["id"] for d in by_project[pid]]

                                                                         
                                                                              
                                                                            
                                                                      
                                                                          
                                                                                
                                                                             
                      
             
                                                                              
                                                                               
            if parsed.worth_recording and not parsed.interpretation:
                malformed += 1
                note_fault(pid, "malformed", "the answer contradicted its own schema")
                failed += 1
                print(f"  {pid}: MALFORMED — worth_recording with no interpretation; "
                      f"the deltas stay unconsumed", file=sys.stderr)
                continue

            if not parsed.worth_recording:
                with conn:
                    conn.executemany("UPDATE deltas SET consumed_at = ? WHERE id = ?",
                                     [(now(), i) for i in ids])
                skipped += 1
                                                                            
                                                                               
                                                                                
                                                                               
                                                                               
                                                  
                 
                                                                                 
                                                                                 
                                                                               
                                                                            
                                                               
                if not (parsed.why_not or "").strip():
                    unreasoned += 1
                print(f"  {pid}: declined — {parsed.why_not or 'NO REASON GIVEN (a gap)'}")
                continue
                                                                                   
                                                                               
                                                                                
                                                                                 
                                                                           
                                                                                  
                                                                               
                                        
             
                                                                                  
                                                                                
                                                                                 
                                                                                
                                     
            try:
                prior = conn.execute(
                                                                                
                                                                                   
                    "SELECT memory_id, MAX(revision) AS revision, statement FROM ledger"
                    " WHERE project_id = ? AND kind = 'observation' AND owner = ?"
                    "   AND substr(created_at, 1, 10) = ?"
                    "   AND memory_id NOT IN (SELECT memory_id FROM tombstones)"
                    " GROUP BY memory_id ORDER BY revision DESC LIMIT 1",
                    (pid, OWNER, now()[:10])).fetchone()
            except sqlite3.DatabaseError as exc:
                                                                                  
                                                                                  
                                                                                 
                                                                         
                                                                          
                                                  
                 
                                                                                
                                                                            
                                                                                 
                                                                               
                                                                              
                                                                              
                                                                           
                                                                              
                                                                           
                                       
                print(f"  {pid}: the store could not be read for the duplicate "
                      f"check — {type(exc).__name__}: {str(exc)[:80]}. Its delta "
                      f"stays unconsumed; the other projects proceed.",
                      file=sys.stderr)
                note_fault(pid, "store", exc)
                failed += 1
                continue
            if prior is not None and prior["statement"] == parsed.interpretation:
                                                                                
                                                                                   
                with conn:
                    conn.executemany("UPDATE deltas SET consumed_at = ? WHERE id = ?",
                                     [(now(), i) for i in ids])
                skipped += 1
                print(f"  {pid}: unchanged since this morning's reading — not re-recorded")
                continue
                                                                              
                                                                          
                                                                       
                                                                               
                                                    
                                                                             
                                                                              
                                                                           
                                                                                 
                                                                              
                                                                               
                                                           
            if non_latin_share(parsed.interpretation) > FOREIGN_LETTER_SHARE:
                foreign += 1
                print(f"  {pid}: NOT IN ENGLISH — recorded, and counted; every "
                      f"reader of this ledger is English-language",
                      file=sys.stderr)
            stored_confidence = max(0.01, min(AGENT_MAX_CONFIDENCE,
                                              parsed.confidence))
            try:
                res = L.append(
                    conn, owner=OWNER, kind="observation",
                    memory_id=prior["memory_id"] if prior else None,
                    expected_revision=prior["revision"] if prior else None,
                    statement=parsed.interpretation, project_id=pid,
                    function="episodic", scope="project", state="proposed",
                                                                                  
                                                                                 
                                                                                   
                                                                                     
                    confidence=stored_confidence,
                                                                                
                                                                       
                                                                            
                                                                             
                                                                                  
                                                                     
                    provenance=[{"source": "agent/observe", "model": model_used,
                                 "cost_credits": round(spent_here, 8),
                                 "selection_level": result["selection_level"],
                                 "deltas": len(by_project[pid]),
                                 "movements": len(fold(by_project[pid]))}],
                    evidence=[{"uri": f"delta:{d['id']}", "kind": d["kind"]}
                              for d in by_project[pid]])
            except L.LedgerError as exc:
                print(f"  {pid}: ledger refused the write — {exc}", file=sys.stderr)
                note_fault(pid, "ledger", exc)
                failed += 1; continue
            with conn:
                conn.executemany("UPDATE deltas SET consumed_at = ? WHERE id = ?",
                                 [(now(), i) for i in ids])
            recorded += 1
            print(f"  {pid}: {res['memoryId']}@{res['revision']} proposed "
                  f"(confidence {stored_confidence:.2f}, {model_used}, "
                  f"{spent_here:.6f} credits)")
            if result["stop"]:
                print(f"  guardrail now says stop: {result['stop']}; the rest stays unconsumed")
                break

        w = providers.wallet_state()
                                                                                 
                                                                                   
                                                                                 
                                                                                 
                                                                                 
                                                                                
                                                                                 
        report(halted_by, recorded, skipped, failed, malformed, unreasoned,
               retired_models, handled=list(projects), waiting=list(waiting),
               foreign=foreign)
        print(f"\nrecorded {recorded} · skipped {skipped} · failed {failed}")
                                                                            
                                                                             
                                                                            
                                                                            
                                                                           
                                                                          
        print(f"wallet: {w['local_today']:.6f} of {w['daily_ceiling']:.2f} "
              f"{w['denomination']} today, "
              f"{w['local_month']:.4f} of {w['monthly_ceiling']:.2f} this month, "
              f"{w['window_spend']:.6f} in the last {w['window_minutes']}min "
              f"(ceiling {w['velocity_ceiling']:.2f})"
              + (f" · the shared KEY shows {w['key_today']:.2f} today, "
                 f"{w['key_month']:.2f} this month"
                 if w.get('key_today') is not None else ""))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    import configuration
    if (True) and not configuration.enabled("agent", "features"):
        print("Not configured: enable features.agent explicitly")
        raise SystemExit(0)

    raise SystemExit(main())
