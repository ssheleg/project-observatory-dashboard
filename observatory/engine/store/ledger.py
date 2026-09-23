#!/usr/bin/env python3
""                                                                        

                                                                               

                                                                             
                                                                     
                                                                               
                                                                              
                                                                              
                                                                              
                 
                                                                             
                                                                            
                                                                              
                  
   
from __future__ import annotations
import json, sqlite3, sys, pathlib, uuid
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from store import db as store_db                                                 

FUNCTIONS = ("working", "episodic", "semantic", "experiential")
SCOPES = ("run", "agent-private", "project", "global")

#: The lifecycle from the Fabric memory contract. A transition absent here is
#: refused; the diagram is the specification, not a suggestion.
TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed":   frozenset({"observed", "rejected"}),
    "observed":   frozenset({"supported", "archived"}),
    "supported":  frozenset({"contested", "stale", "superseded"}),
    "contested":  frozenset({"supported", "stale", "superseded"}),
    "stale":      frozenset({"supported", "archived"}),
    "superseded": frozenset({"archived"}),
    "rejected":   frozenset(),
    "archived":   frozenset(),
}
OPERATOR = "operator"

#: The longest text a single record may carry. See `append` for the
#: measurement behind the number.
MAX_TEXT = 4000


class LedgerError(Exception):
    ""                                                                


class OwnerRequired(LedgerError):
    ""                                            


class OwnerRefused(LedgerError):
    ""                                                                         


class RevisionConflict(LedgerError):
    ""                                                                                  

    def __init__(self, memory_id: str, expected: int, current: int) -> None:
        super().__init__(f"{memory_id}: expected revision {expected}, current is {current}")
        self.memory_id, self.expected, self.current = memory_id, expected, current


class IllegalTransition(LedgerError):
    ""                                                 


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def current(conn: sqlite3.Connection, memory_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM ledger WHERE memory_id = ? ORDER BY revision DESC LIMIT 1",
        (memory_id,)).fetchone()


def history(conn: sqlite3.Connection, memory_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM ledger WHERE memory_id = ? ORDER BY revision", (memory_id,)))


def _check_owner(prior: sqlite3.Row | None, writer: str) -> None:
    if not writer or not writer.strip():
        raise OwnerRequired("a write must declare its owner; there is no default")
    if prior is None:
                                                                                
                                                                                   
                                                                            
                                                                               
                                                                                 
                                                                             
                                                                                
                                                                            
               
         
                                                                             
                                                                                 
                                                                             
                                              
        if writer == OPERATOR:
            raise OwnerRefused(
                "a new record may not be created as `operator`. The operator's authority "
                "applies to records that already exist — promote or reject one with "
                "`review.py`, from a terminal. Record the observation under the identity "
                "that made it (e.g. `agent:claude-code`).")
        return
    if writer == OPERATOR:
        return
    if prior["owner"] == OPERATOR:
        raise OwnerRefused(
            f"{prior['memory_id']} is owned by the operator; {writer} may not supersede it")
    if prior["owner"] != writer:
        raise OwnerRefused(
            f"{prior['memory_id']} is owned by {prior['owner']}; {writer} may only correct its own")


def _commit_revision(conn: sqlite3.Connection, row: dict) -> int:
    ""                                                                              

                                                                         
                                                                              
                                                                             
                                                                   
                                                                           

                                                                            
                                                                                 
                                                                                
                                                               
                                                                                
                                                                       
                                                                                 
                                                                               
                                                                             
                                                                       
                                                                                
       
    tomb = conn.execute("SELECT revision FROM tombstones WHERE memory_id = ?"
                        " ORDER BY revision LIMIT 1", (row["memory_id"],)).fetchone()
    if tomb is not None:
        raise LedgerError(
            f"{row['memory_id']} is tombstoned (from revision {tomb[0]}) and takes no "
            f"further revisions — every read joins tombstones on memory_id, so this "
            f"row would be written and never served. Append a new record instead.")
    with conn:
        conn.execute(
            "INSERT INTO ledger (memory_id, revision, kind, project_id, agent_id, run_id,"
            " session_id, function, scope, statement, why, state, confidence, owner,"
            " classification, valid_from, valid_to, supersedes_json,"
            " conflicts_with_json, provenance_json, evidence_json, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (row["memory_id"], row["revision"], row["kind"], row["project_id"],
             row["agent_id"], row["run_id"], row["session_id"], row["function"],
             row["scope"], row["statement"], row["why"], row["state"], row["confidence"],
             row["owner"], row["classification"], row["valid_from"],
             row["valid_to"], json.dumps(row["supersedes"]),
             json.dumps(row["conflicts_with"]),
             json.dumps(row["provenance"], ensure_ascii=False),
             json.dumps(row["evidence"], ensure_ascii=False), row["created_at"]))
        # The version comes from the store's own vocabulary, not from a literal
        # here. This line held `1` while `store/indexer.py` filtered on its own
        # constant — two numbers that had to agree, in two files, with nothing
        # checking. See `store/db.py:PROJECTION_VERSION`.
        cur = conn.execute(
            "INSERT INTO outbox (memory_id, revision, projection_version) VALUES (?,?,?)",
            (row["memory_id"], row["revision"], store_db.PROJECTION_VERSION))
        return cur.lastrowid


def append(
    conn: sqlite3.Connection,
    *,
    owner: str,
    statement: str,
    kind: str = "note",
    memory_id: str | None = None,
    expected_revision: int | None = None,
    project_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    function: str = "episodic",
    scope: str = "project",
    state: str = "proposed",
                                                                          
                                                                                 
                                                                              
                                                                            
                                                                              
                                                                              
                                                                              
                                                                               
                                                                              
                                                              
    why: str | None = None,
    confidence: float | None = None,
    classification: str = "project-internal",
    valid_from: str | None = None,
    valid_to: str | None = None,
    conflicts_with: list[str] | None = None,
    provenance: list[dict] | None = None,
    evidence: list[dict] | None = None,
) -> dict:
    ""                                                                           

                                                                          
                                                                                
       
    if function not in FUNCTIONS:
        raise LedgerError(f"unknown function {function!r}; expected one of {FUNCTIONS}")
    if scope not in SCOPES:
        raise LedgerError(f"unknown scope {scope!r}; expected one of {SCOPES}")
    if confidence is not None and not (0 < confidence <= 1):
        raise LedgerError("confidence must be in (0, 1]")
                                                                               
                                                                             
                                                                             
                                                                               
                                                                              
                                                                                 
                                                                               
                                  
     
                                                                               
                                                                           
                                                          
                                                                             
                                                                  
                                                                                
                                                                          
                                                                               
                                                                            
                                                                             
                                                                               
                                       
    if not (statement or "").strip():
        raise LedgerError(
            "a record must carry a statement. An empty conclusion cannot be "
            "reviewed, indexed or corrected — if there is nothing to say, do not "
            "append.")
    for field, value in (("statement", statement), ("why", why)):
        if value is not None and len(value) > MAX_TEXT:
            raise LedgerError(
                f"{field} is {len(value):,} characters; the limit is {MAX_TEXT:,}. "
                f"A record is the minimal claim, not a transcript — link the "
                f"transcript as evidence instead. The live ledger's longest "
                f"statement is 406 characters.")
    if owner != OPERATOR and state != "proposed" and memory_id is None:
        raise LedgerError(
            f"{owner} may not create a record already in state {state!r}; "
            "an automated writer proposes and something else promotes")

    new = memory_id is None
    mid = memory_id or f"mem:{uuid.uuid4().hex[:16]}"
    prior = None if new else current(conn, mid)
    if not new and prior is None:
        raise LedgerError(f"{mid} does not exist; omit memory_id to create it")
    _check_owner(prior, owner)

    if prior is not None:
        if expected_revision is None:
            raise RevisionConflict(mid, -1, prior["revision"])
        if expected_revision != prior["revision"]:
            raise RevisionConflict(mid, expected_revision, prior["revision"])
        if state != prior["state"] and state not in TRANSITIONS[prior["state"]]:
            raise IllegalTransition(
                f"{mid}: {prior['state']} -> {state} is not a lifecycle edge; "
                f"from {prior['state']} the legal moves are "
                f"{sorted(TRANSITIONS[prior['state']]) or 'none — it is terminal'}")

    revision = 1 if prior is None else prior["revision"] + 1
    supersedes = [] if prior is None else [f"{mid}@{prior['revision']}"]
    created = _now()

    cursor = _commit_revision(conn, dict(
        memory_id=mid, revision=revision, kind=kind, project_id=project_id,
        agent_id=agent_id, run_id=run_id, session_id=session_id, function=function,
        scope=scope, statement=statement, why=why, state=state, confidence=confidence,
        owner=owner, classification=classification, valid_from=valid_from,
        valid_to=valid_to, supersedes=supersedes, conflicts_with=conflicts_with or [],
        provenance=provenance or [], evidence=evidence or [], created_at=created))
    return {"memoryId": mid, "revision": revision, "state": state, "owner": owner,
            "supersedes": supersedes, "consistencyCursor": cursor, "createdAt": created}


def transition(conn: sqlite3.Connection, memory_id: str, *, to_state: str,
               owner: str, expected_revision: int, why: str | None = None) -> dict:
    ""                                                                              
    prior = current(conn, memory_id)
    if prior is None:
        raise LedgerError(f"{memory_id} does not exist")
    return append(
        conn, memory_id=memory_id, expected_revision=expected_revision, owner=owner,
        statement=prior["statement"], kind=prior["kind"], project_id=prior["project_id"],
        agent_id=prior["agent_id"], run_id=prior["run_id"], session_id=prior["session_id"],
        function=prior["function"], scope=prior["scope"], state=to_state,
        why=why or prior["why"], confidence=prior["confidence"],
        classification=prior["classification"], valid_from=prior["valid_from"],
        valid_to=prior["valid_to"],
        conflicts_with=json.loads(prior["conflicts_with_json"]),
        provenance=json.loads(prior["provenance_json"]),
        evidence=json.loads(prior["evidence_json"]))


def corroborate(conn: sqlite3.Connection, memory_id: str, *, by: str, check: dict,
                expected_revision: int) -> dict:
    ""                                                                     

                                                                        
                                                                          
                                                                                 
                                                                                
                                                                                
                                                         

                                                                          
                                   

                                                                               
                                                                              
                                                                         
                   
                                                                                
                                                                               
                                                                           
                                         
                                                                         
                                                                               
                                                                             
                  

                                                                          
                                                                               
                           
       
    prior = current(conn, memory_id)
    if prior is None:
        raise LedgerError(f"{memory_id} does not exist")
    if not by or not by.strip():
        raise OwnerRequired("a corroboration must name who checked; there is no default")
    if by == OPERATOR:
        raise OwnerRefused(
            "the operator approves through review, not corroboration: a decision "
            "recorded as a measurement cannot be told apart from one later")
    if by == prior["owner"]:
        raise OwnerRefused(
            f"{memory_id} is owned by {prior['owner']}, which is also the corroborator; "
            "a second witness cannot be the first one")
    if prior["state"] != "proposed":
        raise IllegalTransition(
            f"{memory_id} is {prior['state']!r}; corroboration promotes only from "
            f"'proposed'")
    if expected_revision != prior["revision"]:
        raise RevisionConflict(memory_id, expected_revision, prior["revision"])
    if not check or "how" not in check:
        raise LedgerError("check must describe how the claim was verified: {'how': ...}")

    revision = prior["revision"] + 1
    created = _now()
    cursor = _commit_revision(conn, dict(
        memory_id=memory_id, revision=revision, kind=prior["kind"],
        project_id=prior["project_id"], agent_id=prior["agent_id"],
        run_id=prior["run_id"], session_id=prior["session_id"],
        function=prior["function"], scope=prior["scope"], statement=prior["statement"],
        why=prior["why"], state="observed", confidence=prior["confidence"],
        owner=prior["owner"], classification=prior["classification"],
        valid_from=prior["valid_from"], valid_to=prior["valid_to"],
        supersedes=[f"{memory_id}@{prior['revision']}"],
        conflicts_with=json.loads(prior["conflicts_with_json"]),
        provenance=json.loads(prior["provenance_json"]) +
                   [{"source": "corroboration", "by": by, "at": created}],
        evidence=json.loads(prior["evidence_json"]) + [dict(check, kind="corroboration")],
        created_at=created))
    return {"memoryId": memory_id, "revision": revision, "state": "observed",
            "owner": prior["owner"], "corroboratedBy": by,
            "consistencyCursor": cursor, "createdAt": created}


def tombstone(conn: sqlite3.Connection, memory_id: str, *, reason: str,
              approved_by: str) -> dict:
    ""                                                                  

                                                                          
                                                                                
                                                                               
                                                                                
                                                                          
                                                                              
                                                            

                                                                             
                                                                                 
                                                                          
                                                                            
                                                                                
                                                         

                                                                         
                                                                            
                                                              

                                                                                
                                                                       
       
    row = current(conn, memory_id)
    if row is None:
        raise LedgerError(f"{memory_id} does not exist")
    if not approved_by or not approved_by.strip():
        raise OwnerRequired("an erasure must name who approved it")
    revisions = [r["revision"] for r in history(conn, memory_id)]
    now = _now()
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO tombstones (memory_id, revision, reason, approved_by,"
            " created_at) VALUES (?,?,?,?,?)",
            [(memory_id, rev, reason, approved_by, now) for rev in revisions])
    return {"memoryId": memory_id, "revision": row["revision"],
            "revisions": revisions, "reason": reason, "approvedBy": approved_by,
            "note": "every revision tombstoned; ledger rows retained; purge the "
                    "derived projections and collect receipts"}


def live_count(conn: sqlite3.Connection, project_id: str | None = None,
               states: tuple[str, ...] = ("supported", "contested", "observed",
                                          "proposed")) -> int:
    ""                                                           

                                                                                 
                                                                                
                                                                              
                                                                 
       
    sql = ("SELECT count(*) FROM ledger l JOIN (SELECT memory_id, MAX(revision) r"
           " FROM ledger GROUP BY memory_id) m ON l.memory_id = m.memory_id"
           " AND l.revision = m.r LEFT JOIN tombstones t"
           " ON t.memory_id = l.memory_id WHERE t.memory_id IS NULL")
    args: list = []
    if project_id:
        sql += " AND l.project_id = ?"
        args.append(project_id)
    sql += f" AND l.state IN ({','.join('?' * len(states))})"
    args += list(states)
    return conn.execute(sql, args).fetchone()[0]


def live(conn: sqlite3.Connection, project_id: str | None = None,
         states: tuple[str, ...] = ("supported", "contested", "observed", "proposed"),
         limit: int = 100, cursor: str | None = None) -> list[dict]:
    ""                                                

                                                                               
                                                                         
                                                                             
                                                                        
       
    sql = ("SELECT l.* FROM ledger l JOIN (SELECT memory_id, MAX(revision) r FROM ledger"
           " GROUP BY memory_id) m ON l.memory_id = m.memory_id AND l.revision = m.r"
           " LEFT JOIN tombstones t ON t.memory_id = l.memory_id"
           " WHERE t.memory_id IS NULL")
    args: list = []
    if project_id:
        sql += " AND l.project_id = ?"
        args.append(project_id)
    sql += f" AND l.state IN ({','.join('?' * len(states))})"
    args += list(states)
                                                                     
                                                                             
                                                                             
                                                                           
                                                                                
                                                                    
    if cursor:
        at, _, mid = cursor.partition("|")
        sql += " AND (l.created_at, l.memory_id) < (?, ?)"
        args += [at, mid]
    sql += " ORDER BY l.created_at DESC, l.memory_id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args)]


def live_cursor(row: dict) -> str:
    ""                                             
    return f"{row['created_at']}|{row['memory_id']}"


def proposals_add(conn: sqlite3.Connection, *, target_id: str, patch: dict,
                  evidence: list[dict], owner: str) -> dict:
    ""                                                             

                                                                              
                                                                             
                                                                                 
       
    if not owner or not owner.strip():
        raise OwnerRequired("a proposal must declare its owner")
    pid = f"prop:{uuid.uuid4().hex[:16]}"
    with conn:
        conn.execute(
            "INSERT INTO proposals (id, target_id, patch_json, evidence_json, status,"
            " created_at) VALUES (?,?,?,?, 'proposed', ?)",
            (pid, target_id, json.dumps(patch, ensure_ascii=False),
             json.dumps({"owner": owner, "evidence": evidence}, ensure_ascii=False), _now()))
    return {"proposalId": pid, "targetId": target_id, "status": "proposed", "owner": owner}
