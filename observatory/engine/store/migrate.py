#!/usr/bin/env python3
""                                                              

                                                                         
                                                                             
                                                                            
                                                                             
                                                               

                                                                               
                                                                          
                                                                           
                                                              

                                                                              
                                                                           
                                                                    
                                                                         
                                                                                 
                                                                              
                                                                         
                                      
   
from __future__ import annotations
import sqlite3
import ast, hashlib, inspect, textwrap
from datetime import datetime, timezone

UTC_Z = "%Y-%m-%dT%H:%M:%SZ"


def to_utc_z(value: str) -> str | None:
    ""                                                                       

                                                                          
                                                                               
                                                                                 
    if value.endswith("Z") and len(value) == 20:
        return value
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc).strftime(UTC_Z)


def _events_utc(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT id, occurred_at FROM events WHERE occurred_at NOT LIKE '%Z'").fetchall()
    converted, refused = 0, []
    for row in rows:
        iso = to_utc_z(row["occurred_at"] if hasattr(row, "keys") else row[1])
        if iso is None:
            refused.append(row[0])
            continue
        conn.execute("UPDATE events SET occurred_at = ? WHERE id = ?", (iso, row[0]))
        converted += 1
    note = f"{converted} event timestamp(s) normalised to UTC"
    if refused:
        note += f"; {len(refused)} carried no zone and were LEFT ALONE: {refused[:3]}"
    return note


def _drop_foreign_events(conn: sqlite3.Connection) -> str:
    ""                                                                   

                                                                               
                                                                               
                                                                               
                                          
    import json as _json
    import pathlib as _pathlib
    import sys as _sys
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))
    import estate
    import paths
    projects_file = paths.REGISTRY / "projects.json"
    if not projects_file.exists():
        return "no registry to read ownership from; nothing dropped"
    own = {p["id"]: p.get("ownership")
           for p in _json.loads(projects_file.read_text(encoding="utf-8"))["projects"]}
    foreign = [pid for pid, o in own.items() if not estate.records_events(o)]
    if not foreign:
        return "no project is outside the estate's own work"
    marks = ",".join("?" * len(foreign))
                                                                                
                                                                            
                                                                             
                                                                      
                                                                                 
                                                                             
                                                                            
                                                                             
                                                               
    n = conn.execute(f"DELETE FROM events WHERE kind = 'commit'"
                     f" AND project_id IN ({marks})", foreign).rowcount
    return f"{n} event(s) dropped from {len(foreign)} project(s) outside this estate's own work"


def _project_week_table(conn: sqlite3.Connection) -> str:
    ""                                                                       
                                                                              
    execute_statements(conn, """
      CREATE TABLE IF NOT EXISTS project_week (
        project_id TEXT NOT NULL, week TEXT NOT NULL, week_start TEXT NOT NULL,
        commits INTEGER NOT NULL, active_days INTEGER NOT NULL, authors INTEGER NOT NULL,
        first_at TEXT, last_at TEXT, computed_at TEXT NOT NULL, frozen_at TEXT,
        PRIMARY KEY (project_id, week));
      CREATE INDEX IF NOT EXISTS project_week_by_week ON project_week(week_start);
    """)
    return "project_week is available for weekly rollups"


def _metrics_table(conn: sqlite3.Connection) -> str:
    ""                                                                   
                                             
    execute_statements(conn, """
      CREATE TABLE IF NOT EXISTS metrics (
        project_id TEXT NOT NULL, metric TEXT NOT NULL, at TEXT NOT NULL,
        value REAL NOT NULL, unit TEXT NOT NULL DEFAULT '', source TEXT NOT NULL,
        payload_json TEXT, recorded_at TEXT NOT NULL,
        PRIMARY KEY (project_id, metric, at));
      CREATE INDEX IF NOT EXISTS metrics_by_metric ON metrics(metric, at);
      CREATE INDEX IF NOT EXISTS metrics_by_source ON metrics(source);
    """)
    return "metrics is available for plugin measurements"


def _project_week_sessions(conn: sqlite3.Connection) -> str:
    ""                                                                        

                                                                              
                                                                               
                                                                               
                                                                        

                                                                              
                                                                              
                                       
       
    have = {c[1] for c in conn.execute("PRAGMA table_info(project_week)")}
    added = []
    for col in ("sessions", "session_days", "worked_days"):
        if col not in have:
            conn.execute(f"ALTER TABLE project_week ADD COLUMN {col} INTEGER")
            added.append(col)
    return (f"project_week gained {', '.join(added)}" if added
            else "project_week already carries the session columns")


def _collector_cursors(conn: sqlite3.Connection) -> str:
    ""                                                                      

                                                                               
                                                                              
                                                                             
                                                                              
                                                                                
                                                                             
                          
       
    conn.execute("CREATE TABLE IF NOT EXISTS cursors ("
                 " name TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
                                                                               
                                                                           
                                                                              
                                                                               
                                                               
    try:
        row = conn.execute("SELECT to_scan FROM deltas ORDER BY rowid DESC LIMIT 1").fetchone()
    except sqlite3.Error as exc:
        return f"cursors is available; nothing to seed from ({str(exc)[:60]})"
    if row is None:
        return "cursors is available; no delta on record, so nothing to seed"
    conn.execute("INSERT OR IGNORE INTO cursors (name, value, updated_at) VALUES (?,?,?)",
                 ("deltas.diffed_through", row[0],
                  datetime.now(timezone.utc).strftime(UTC_Z)))
    return f"cursors seeded: deltas.diffed_through = {row[0]}"


                                                                               
                                                 
def _drop_retention_policy(conn: sqlite3.Connection) -> str:
    ""                                                           

                                                                              
                                                                                 
                                                                       
                                                                 
                                       

                                                                               
                                                                             
                                                                            
                                                                              
                                                                      
                                                                            
                                                                               
                                               

                                                                          
                        
       
    cols = [r[1] for r in conn.execute("PRAGMA table_info(ledger)")]
    if "retention_policy" not in cols:
        return "ledger.retention_policy was already absent"
    conn.execute("ALTER TABLE ledger DROP COLUMN retention_policy")
    return (f"dropped ledger.retention_policy from {len(cols)} columns; "
            f"nothing read it and `append` wrote a constant")


MIGRATIONS: list[tuple[str, object]] = [
    ("0001-events-occurred-at-utc", _events_utc),
    ("0002-drop-events-outside-the-estate", _drop_foreign_events),
    ("0003-project-week-rollup", _project_week_table),
    ("0004-plugin-metrics", _metrics_table),
    ("0005-project-week-sessions", _project_week_sessions),
    ("0006-collector-cursors", _collector_cursors),
    ("0007-drop-inert-retention-policy", _drop_retention_policy),
]


class CompatibilityError(RuntimeError):
    ""                                                                         


def execute_statements(conn: sqlite3.Connection, script: str) -> None:
    ""                                                    
    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            conn.execute(pending)
            pending = ""
    if pending.strip():
        raise ValueError("Incomplete migration SQL")


def checksum(fn: object) -> str:
                                                                                 
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(
                    node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def validate(conn: sqlite3.Connection) -> set[str]:
    ""                                                                            
    if sqlite3.sqlite_version_info < (3, 37, 0):
        raise CompatibilityError("SQLite 3.37 or newer is required")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > len(MIGRATIONS):
        raise CompatibilityError("Database schema is newer than this executable; restore a compatible backup to downgrade")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    done = {r[0] for r in conn.execute("SELECT id FROM migrations")} if "migrations" in tables else set()
    known = dict(MIGRATIONS)
    if done - known.keys():
        raise CompatibilityError("Database contains migrations unknown to this executable")
    if "migration_checksums" in tables:
        for mid, digest in conn.execute("SELECT id, checksum FROM migration_checksums"):
            if mid not in known or mid not in done or checksum(known[mid]) != digest:
                raise CompatibilityError("Applied migration code does not match its recorded checksum")
    return done


def needs_upgrade(conn: sqlite3.Connection) -> bool:
    done = validate(conn)
    if done != {mid for mid, _ in MIGRATIONS}:
        return True
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "migration_checksums" not in tables:
        return True
    recorded = {r[0] for r in conn.execute("SELECT id FROM migration_checksums")}
    return recorded != done or conn.execute("PRAGMA user_version").fetchone()[0] != len(MIGRATIONS)


def apply(conn: sqlite3.Connection) -> list[str]:
    ""                                                                       

                                                                               
                                                                           
                                                                                 
       
    if not needs_upgrade(conn):
        return []
    nested = conn.in_transaction
    conn.execute("SAVEPOINT observatory_migrations" if nested else "BEGIN IMMEDIATE")
    try:
        done = validate(conn)                                                     
        conn.execute("CREATE TABLE IF NOT EXISTS migrations ("
                     " id TEXT PRIMARY KEY, applied_at TEXT NOT NULL, note TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS migration_checksums ("
                     " id TEXT PRIMARY KEY REFERENCES migrations(id), checksum TEXT NOT NULL)")
        notes = []
        for mid, fn in MIGRATIONS:
            if mid not in done:
                note = fn(conn)
                conn.execute("INSERT INTO migrations (id, applied_at, note) VALUES (?,?,?)",
                             (mid, datetime.now(timezone.utc).strftime(UTC_Z), note))
                notes.append(f"{mid}: {note}")
            conn.execute("INSERT OR IGNORE INTO migration_checksums (id, checksum) VALUES (?,?)",
                         (mid, checksum(fn)))
        conn.execute(f"PRAGMA user_version={len(MIGRATIONS)}")
        if nested:
            conn.execute("RELEASE SAVEPOINT observatory_migrations")
        else:
            conn.commit()
        return notes
    except BaseException:
        if nested:
            conn.execute("ROLLBACK TO SAVEPOINT observatory_migrations")
            conn.execute("RELEASE SAVEPOINT observatory_migrations")
        else:
            conn.rollback()
        raise


if __name__ == "__main__":
    import pathlib, sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from store import db as store_db
    conn = store_db.connect()
    applied = apply(conn)
    print("\n".join(applied) if applied else "every migration is already applied")
    left = conn.execute("SELECT COUNT(*) FROM events WHERE occurred_at NOT LIKE '%Z'").fetchone()[0]
    print(f"events not in UTC Z: {left}")
    raise SystemExit(1 if left else 0)
