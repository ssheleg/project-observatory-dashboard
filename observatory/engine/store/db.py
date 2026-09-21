#!/usr/bin/env python3
""                                                  

                                                                               
                                            

                                                                                 
                                                                                   
                                                                               
                                                                               
                                                                         
                                                                                
   
from __future__ import annotations
import sqlite3, sys, pathlib, uuid, os

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths

DB_PATH = paths.DB
SCHEMA = paths.ROOT / "store" / "schema.sql"

                                                                                 
                                                                                 
                                                                                
FINGERPRINT_KIND = "project-fingerprints"

                                                                                   
                                                                               
                                                                                 
                                                                                 
                                                                               
                                                                              
                                                                            
                                                                                 
PROJECTION_VERSION = 1


def connect(path: pathlib.Path | None = None) -> sqlite3.Connection:
    ""                                                                            

                                                                              
                                                                              
                                                                             
                                                        
       
    from store import migrate, compatibility
    target = pathlib.Path(path or DB_PATH)
    if target.is_symlink():
        raise migrate.CompatibilityError("Database path must not be a symbolic link")
    compatibility.preflight(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with compatibility.upgrade_lock(target):
        compatibility.preflight(target)
        fresh = not target.exists()
        if fresh:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        else:
            if not target.stat().st_mode & 0o200:
                raise PermissionError("Database is read-only; refusing to change its write permission")
            target.chmod(0o600)
        conn = sqlite3.connect(target, timeout=30)
        try:
            conn.row_factory = sqlite3.Row
            migrate.validate(conn)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not fresh and tables and migrate.needs_upgrade(conn):
                compatibility.backup(conn, target)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA secure_delete=ON")
            if "scans" not in tables:
                conn.executescript(SCHEMA.read_text(encoding="utf-8"))
                conn.commit()
            migrate.apply(conn)
            target.chmod(0o600)
            return conn
        except BaseException:
            conn.close()
            raise


def scan_id(prefix: str, at: str) -> str:
    ""                                                            

             

                                                                            
                                                                               
                                                                              
                                                                           
                             

                                                                             
                                                                            
                                                                         
                                                                              
                                                                             
                                    

                                                                      
                                                                           
                                                                             
                             
       
    return f"{prefix}-{at}-{uuid.uuid4().hex[:6]}"


def latest_scan(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT id FROM scans WHERE finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def embedding_contract(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT embedding_provider, embedding_model, dims FROM vec_meta LIMIT 1").fetchone()
    return dict(row) if row else {}
