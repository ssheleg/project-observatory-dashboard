#!/usr/bin/env python3
""                                                                 

                                                                            
                                                                                 
                        

                                                                              
                                                                            
                                                                           
                                                                             
                 

                                                            
                                                                                  
                                                                          
   
from __future__ import annotations
import argparse, json, sqlite3, sys, pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent"))
import paths
from store import db as store_db
import store_faults
import providers

                                                                              
                                                                   
                                                                  
PROJECTION_VERSION = store_db.PROJECTION_VERSION


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_vec(conn: sqlite3.Connection) -> bool:
    ""                                                                           
                                                                                 
    try:
        import sqlite_vec
    except ImportError:
        return False
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception:
        return False
    return True


def ensure_vec_table(conn: sqlite3.Connection, dims: int) -> None:
                                                                                  
                                                                                 
                                                                                 
                                                                            
                                                                   
                                                                               
     
                                                                              
                                                                                 
                                                                                
                                                           
     
                                                                             
                                                                                
                                        
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_notes USING vec0("
        f"memory_id TEXT, revision INTEGER, embedding float[{dims}])")
    conn.commit()


def indexable(conn: sqlite3.Connection, memory_id: str, revision: int) -> sqlite3.Row | None:
    ""                                                                         
               

                                                                               
                                                                               
                                            

                                                                            
                                                                               
                                                                            
                                                                       
                                                               
                                                                            
                                                                           
                                                   
    return conn.execute(
        "SELECT l.memory_id, l.revision, l.statement, l.why, l.project_id, l.state"
        " FROM ledger l LEFT JOIN tombstones t"
        "   ON t.memory_id = l.memory_id"
        " WHERE l.memory_id = ? AND l.revision = ? AND t.memory_id IS NULL",
        (memory_id, revision)).fetchone()


def text_of(row: sqlite3.Row) -> str:
    parts = [row["statement"] or ""]
    if row["why"]:
        parts.append(row["why"])
    return "\n".join(p for p in parts if p.strip())


def index_batch(conn: sqlite3.Connection, rows: list[sqlite3.Row], have_vec: bool,
                dims: int) -> tuple[int, float, int, bool]:
    ""                                                                             

                                                                            
                                                                          
                                                                        
                                                                           
                                                                            
                                                                            
                                                                            
                                                                          
    if not rows:
        return 0, 0.0, 0, True
    written, cost, tokens = 0, 0.0, 0
    vectors = None
    if have_vec:
        try:
            res = providers.embed([text_of(r) for r in rows])
            vectors, cost, tokens = res["vectors"], res["cost"], res["tokens"]
        except providers.ProviderError as exc:
            print(f"  embedding unavailable ({type(exc).__name__}: {exc});"
                  f" writing the lexical index only — these revisions stay QUEUED so a "
                  f"later run can embed them", file=sys.stderr)
            vectors = None
                                                                              
                                                                              
                                                                                 
                                                                               
                                                                                 
                                                              
                                                                           
    with conn:
        for i, r in enumerate(rows):
            conn.execute("DELETE FROM search_notes WHERE memory_id = ? AND revision = ?",
                         (r["memory_id"], r["revision"]))
            conn.execute("INSERT INTO search_notes (memory_id, revision, statement, why)"
                         " VALUES (?,?,?,?)",
                         (r["memory_id"], r["revision"], r["statement"], r["why"] or ""))
            if vectors is not None:
                from sqlite_vec import serialize_float32
                conn.execute("DELETE FROM vec_notes WHERE memory_id = ? AND revision = ?",
                             (r["memory_id"], r["revision"]))
                conn.execute("INSERT INTO vec_notes (memory_id, revision, embedding)"
                             " VALUES (?,?,?)",
                             (r["memory_id"], r["revision"], serialize_float32(vectors[i])))
            written += 1
    return written, cost, tokens, (vectors is not None or not have_vec)


def cmd_index(conn: sqlite3.Connection, limit: int) -> int:
    cfg = providers.config()["embedding"]
    have_vec = load_vec(conn)
    if have_vec:
        ensure_vec_table(conn, cfg["dims"])
    else:
        print("sqlite-vec is not loadable here — the lexical index is built, the vector "
              "one is not. `./observatory.py deps` installs it.", file=sys.stderr)

                                                                              
                                                                               
                                                                             
                                                                                  
                                                                               
    ahead = conn.execute(
        "SELECT count(*) FROM outbox WHERE consumed_at IS NULL"
        " AND projection_version > ?", (PROJECTION_VERSION,)).fetchone()[0]
    if ahead:
        print(f"{ahead} outbox row(s) are stamped for a NEWER projection contract than "
              f"this indexer builds (version {PROJECTION_VERSION}). Refusing: a mixed "
              f"index answers searches from two contracts at once.", file=sys.stderr)
        return 1

    pending = list(conn.execute(
        "SELECT seq, memory_id, revision FROM outbox"
        " WHERE consumed_at IS NULL AND projection_version <= ?"
        " ORDER BY seq LIMIT ?", (PROJECTION_VERSION, limit)))
    if not pending:
                                                                                
                                                                             
                                                                              
                                                                               
                                                        
        built = conn.execute("SELECT projection_version FROM vec_meta LIMIT 1").fetchone()
        if built and built[0] != PROJECTION_VERSION:
            print(f"outbox empty, but the projections on disk were built at version "
                  f"{built[0]} and this indexer builds {PROJECTION_VERSION}. "
                  f"Run `./observatory.py reindex` — the index is stale, not current.",
                  file=sys.stderr)
            return 1
        print("outbox empty — every committed revision is already projected")
        return 0

    batch, seqs, skipped = [], [], 0
    batch_seqs: list[int] = []                                                
    done_seqs: list[int] = []                                          
    held_seqs: list[int] = []                                                        
    total_written = total_cost = total_tokens = 0
    size = int(cfg.get("batch_size", 64))

    def flush() -> None:
        nonlocal batch, batch_seqs, total_written, total_cost, total_tokens
        if not batch:
            return
        try:
            w, c, tok, vectors_ok = index_batch(conn, batch, have_vec, cfg["dims"])
        except sqlite3.Error as exc:
                                                                   
                                                                             
                                                                               
                                                               
                                                                           
                                                                            
                                                                        
             
                                                                         
                                                                                
                                                                             
                                                                            
                           
            store_faults.record("index", exc)
            raise
        total_written += w; total_cost += c; total_tokens += tok
                                                                                
                                                                            
                                                                                
                                                                                  
                                                                                
                                                                      
                                                    
        (done_seqs if vectors_ok else held_seqs).extend(batch_seqs)
        batch, batch_seqs = [], []

    for p in pending:
        row = indexable(conn, p["memory_id"], p["revision"])
        seqs.append(p["seq"])
        if row is None or not text_of(row).strip():
            skipped += 1
            done_seqs.append(p["seq"])                                         
            continue
        batch.append(row)
        batch_seqs.append(p["seq"])
        if len(batch) >= size:
            flush()
    flush()

                                                                                
                                                                                
                                                                
    with conn:
        conn.executemany("UPDATE outbox SET consumed_at = ? WHERE seq = ?",
                         [(now(), s) for s in done_seqs])
        if done_seqs:
            conn.execute("UPDATE vec_meta SET checkpointed_seq = ?", (max(done_seqs),))
    still = conn.execute(
        "SELECT count(*) FROM outbox WHERE consumed_at IS NULL").fetchone()[0]
                                                                               
                                                                               
                                                                       
    full = total_written - len(held_seqs)
    half = f", {len(held_seqs)} lexical-only" if held_seqs else ""
                                                                               
                                                                                
                                                                      
    where = "both indexes" if have_vec else "the lexical index"
    print(f"indexed {full} revision(s) into {where}{half}, skipped {skipped} "
          f"(tombstoned or empty), checkpoint "
          f"{max(done_seqs) if done_seqs else 'unchanged'}")
    if held_seqs:
        print(f"  {len(held_seqs)} revision(s) kept in the queue: the lexical index has "
              f"them, the vector one does not, and a later run will embed them",
              file=sys.stderr)
                                                                              
                                                                               
                                                                                 
    if still:
        print(f"  {still} revision(s) still queued — this run was capped at {limit}. "
              f"Run `./observatory.py index` again until it reports the outbox empty."
              if still > len(held_seqs) else
              f"  {still} revision(s) still queued.", file=sys.stderr)
    if total_tokens:
        print(f"  {total_tokens} embedding token(s), {total_cost:.8f} credits ESTIMATED "
              f"from a dated price in agent/models.json — OpenAI reports no cost")
    return 0


def cmd_rebuild(conn: sqlite3.Connection) -> int:
    ""                                                   

                                                                          
                                                                        
       
    have_vec = load_vec(conn)
    cfg = providers.config()["embedding"]
    with conn:
        conn.execute("DELETE FROM search_notes")
        if have_vec:
            conn.execute("DROP TABLE IF EXISTS vec_notes")
        conn.execute("UPDATE outbox SET consumed_at = NULL")
                                                                            
                                                                                 
                                                                           
                                                                            
        conn.execute("UPDATE outbox SET projection_version = ?", (PROJECTION_VERSION,))
        conn.execute("UPDATE vec_meta SET checkpointed_seq = 0, projection_version = ?",
                     (PROJECTION_VERSION,))
    if have_vec:
        ensure_vec_table(conn, cfg["dims"])
    n = conn.execute("SELECT count(*) FROM outbox WHERE consumed_at IS NULL").fetchone()[0]
    print(f"projections dropped; {n} outbox row(s) re-queued at version {PROJECTION_VERSION}")
                                                                                
                                                                               
                                                                             
    CAP = 10_000
    rc = cmd_index(conn, limit=CAP)
    left = conn.execute(
        "SELECT count(*) FROM outbox WHERE consumed_at IS NULL").fetchone()[0]
    if left:
        print(f"{left} revision(s) still unprojected — the rebuild cap is {CAP} per run. "
              f"Run `./observatory.py index` again until it reports the outbox empty.",
              file=sys.stderr)
    return rc


def cmd_status(conn: sqlite3.Connection) -> int:
    have_vec = load_vec(conn)
    counts = {
        "ledger revisions": conn.execute("SELECT count(*) FROM ledger").fetchone()[0],
        "tombstoned": conn.execute("SELECT count(*) FROM tombstones").fetchone()[0],
        "outbox pending": conn.execute(
            "SELECT count(*) FROM outbox WHERE consumed_at IS NULL").fetchone()[0],
        "lexical rows": conn.execute("SELECT count(*) FROM search_notes").fetchone()[0],
    }
    if have_vec:
        try:
            counts["vector rows"] = conn.execute("SELECT count(*) FROM vec_notes").fetchone()[0]
        except sqlite3.Error:
            counts["vector rows"] = "table absent"
    else:
        counts["vector rows"] = "sqlite-vec not loadable"
    meta = conn.execute("SELECT * FROM vec_meta LIMIT 1").fetchone()
    for k, v in counts.items():
        print(f"  {k:<20} {v}")
    if meta:
        print(f"  contract             {meta['embedding_provider']}/"
              f"{meta['embedding_model']} dims={meta['dims']} "
              f"checkpoint={meta['checkpointed_seq']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["index", "rebuild", "status"])
    ap.add_argument("--limit", type=int, default=500)
    a = ap.parse_args()
    conn = store_db.connect()
    try:
        if a.command == "index":
            return cmd_index(conn, a.limit)
        if a.command == "rebuild":
            return cmd_rebuild(conn)
        return cmd_status(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    import configuration
    if (len(sys.argv) < 2 or sys.argv[1] in {"index", "reindex"}) and not configuration.enabled("embeddings", "features"):
        print("Not configured: enable features.embeddings explicitly")
        raise SystemExit(0)

    raise SystemExit(main())
