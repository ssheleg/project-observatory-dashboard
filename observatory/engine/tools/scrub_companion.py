#!/usr/bin/env python3
""                                                                   

                                                                            
                                                                   

                                                                      
                                                                             
                                                                            
                                                                     

                                                                        
                                                                             
                                                         
                                                                 
                                                                       
                                                                          
                                                                           
                                                                            

                                                                        
                                                                              
                                                                          
                                                                               
                                                                            

                                                                           
                                                                          
                                             
   
from __future__ import annotations
import argparse
import datetime
import json
import os
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "collectors"))
import paths              

HOME = pathlib.Path(os.environ.get("CLAUDE_MEM_HOME", paths.source_path("companion_home", paths.HOME / "disabled/companion")))
STORES = [HOME / "claude-mem.db", HOME / "chroma" / "chroma.sqlite3"]
JOURNAL = paths.STATE / "logs" / "scrub.jsonl"
BACKUP_DIR = HOME / "backups"
                                                                          
BACKED_UP = ("claude-mem.db", "chroma.sqlite3")


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def text_columns(conn: sqlite3.Connection) -> list[tuple[str, list[str]]]:
    ""                                                                    
                                                                              
                                                   
    out = []
    for name, sql in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        if any(name.endswith(s) for s in ("_data", "_idx", "_config", "_docsize", "_content")):
            continue
                                                                                 
                                                                                  
                                                                             
                                                                              
                                                                       
        low = (sql or "").lower()
        if "using fts" in low and "content=" in low.replace(" ", ""):
            continue
        try:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')
                    if str(r[2] or "").upper() in ("TEXT", "", "VARCHAR", "CLOB", "JSON")]
        except sqlite3.Error:
            continue
        if cols:
            out.append((name, cols))
    return out


def backup(db: pathlib.Path) -> pathlib.Path | None:
    if db.name not in BACKED_UP:
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    BACKUP_DIR.chmod(0o700)
    import uuid
    dest = BACKUP_DIR / f"{db.stem}-pre-scrub-{now().replace(':', '-')}-{uuid.uuid4().hex[:12]}.db"
    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    dest.chmod(0o600)
    return dest


def scrub_store(db: pathlib.Path, values: dict[str, str], dry: bool) -> tuple[list[dict], str | None]:
    ""                                                                                
    if not db.is_file():
        return [], None
    try:
        conn = sqlite3.connect(f"file:{db}?mode={'ro' if dry else 'rw'}", uri=True, timeout=60)
    except sqlite3.Error as exc:
        return [], f"{type(exc).__name__}: {exc}"
    conn.execute("PRAGMA busy_timeout = 60000")
    rows: list[dict] = []
                                                                               
                                                                                
                                                                             
                                                                            
                              
    needles = {v.encode("utf-8", "surrogateescape"): (v, n) for v, n in values.items()}
    try:
        for table, cols in text_columns(conn):
            sel = ", ".join(f'"{c}"' for c in cols)
            try:
                cur = conn.execute(f'SELECT rowid, {sel} FROM "{table}"')
            except sqlite3.Error:
                continue
            hits: dict[tuple[str, str], int] = {}
            todo: list[tuple[str, int, str, str]] = []                                      
            while True:
                page = cur.fetchmany(500)
                if not page:
                    break
                for row in page:
                    rowid, cells = row[0], row[1:]
                    for col, cell in zip(cols, cells):
                        if cell is None:
                            continue
                        blob = cell if isinstance(cell, bytes) else str(cell).encode("utf-8", "surrogateescape")
                        for nb, (value, name) in needles.items():
                            if nb in blob:
                                hits[(col, name)] = hits.get((col, name), 0) + 1
                                todo.append((col, rowid, value, name))
            if not dry:
                for col, rowid, value, name in todo:
                    conn.execute(f'UPDATE "{table}" SET "{col}" = replace("{col}", ?, ?) WHERE rowid = ?',
                                 (value, f"[REDACTED:{name}]", rowid))
            for (col, name), n in hits.items():
                rows.append({"where": f"{table}.{col}", "name": name, "cells": n})
        if not dry:
            conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        return rows, f"{type(exc).__name__}: {exc}"
    finally:
        conn.close()
    return rows, None


def journal(entry: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    JOURNAL.chmod(0o600)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="count, write nothing")
    a = ap.parse_args(argv[1:])
    import configuration
    if not a.dry_run and not configuration.enabled("companion_remediation", section="features"):
        print("scrub: remediation is disabled; use --dry-run or explicitly enable companion_remediation")
        return 0
    import scan_leaks
    values, _homes, _skipped = scan_leaks.known_values()
    if not values:
        print("scrub: nothing to look for — no env scan, no vault, no installed key")
        return 0
    total_cells, report = 0, []
    for db in STORES:
        if not db.is_file():
            continue
        dry_rows, problem = scrub_store(db, values, dry=True)
        cells = sum(r["cells"] for r in dry_rows)
        if problem:
            print(f"scrub: {db.name}: would not open — {problem}", file=sys.stderr)
            if not a.dry_run:
                journal({"at": now(), "store": str(db), "problem": problem})
            continue
        if not cells:
            print(f"scrub: {db.name}: clean — {len(values)} known value(s), 0 cells")
            continue
        if a.dry_run:
            print(f"scrub: {db.name}: {cells} cell(s) across {len({r['where'] for r in dry_rows})} column(s) hold "
                  f"{len({r['name'] for r in dry_rows})} distinct value(s) — dry run, nothing written")
            for r in sorted(dry_rows, key=lambda r: -r["cells"])[:12]:
                print(f"    {r['where']:48} {r['name']:50} ×{r['cells']}")
            total_cells += cells
            continue
        bak = backup(db)
        rows, problem = scrub_store(db, values, dry=False)
        journal({"at": now(), "store": str(db), "backup": str(bak) if bak else None,
                 "cells": sum(r["cells"] for r in rows), "rows": rows, "problem": problem})
        print(f"scrub: {db.name}: {sum(r['cells'] for r in rows)} cell(s) rewritten"
              + (f", backup {bak.name}" if bak else "") + (f" — problem: {problem}" if problem else ""))
        total_cells += cells
        report.extend(rows)
    if not a.dry_run and report:
        print(f"scrub: {len({r['name'] for r in report})} distinct value(s) replaced by name; "
              f"re-run `./observatory.py leaks` to see the store read clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
