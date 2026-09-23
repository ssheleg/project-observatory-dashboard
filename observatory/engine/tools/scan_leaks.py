#!/usr/bin/env python3
""                                                            

                                                                             
                                                                              
                                                                               

                                                                            
                                                                                   
                                                                                 
                                                                              
                                                                               
                                                                               
                                                                           
                                                                             

                                                                                 
                         

                                                                             
                                       
                                                                        
                                                                  

                                                                                
                                                                                 
                                                                                  
                                                                           
                                                                                
                                                                                 
                                                        

                                                                                 
                                                                       
                                                                                
                                                                          
                                                         

                                                                          
                                                                                
                                                                         
                                                                                
                                          
   
from __future__ import annotations
import argparse
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "collectors"))
import atomic              
import paths              

STATE = paths.SCRATCH / "leak-scan-state.json"
OUT = paths.SCRATCH / "leak-scan.json"
VAULT = pathlib.Path(os.environ.get(
    "OBSERVATORY_VAULT_DIR",
    paths.source_path("secret_store", paths.SECRETS) / 'projects'))
SESSIONS = pathlib.Path(os.environ.get(
    "OBSERVATORY_SESSIONS", paths.SESSIONS))

                                                                               
                                                                                
                                                                                
                      
MIN_LEN = 12


def searchable(value: str) -> bool:
    ""                                                          

                                                                               
                                                                               
                                                                            
                                                                                 
                                                                                

                                                                                 
                                                                                
                                                                                 
                                                  
       
    import scan_env
    return len(value) >= MIN_LEN and scan_env.looks_secret(value)

#: How much of one file to read at a time, with an overlap so a value split
#: across two reads is still found.
CHUNK = 1 << 20

#: The four destinations `tools/install_key.py` owns, plus the observatory's own.
DESTINATIONS = {
    "observatory": paths.STORE / ".openrouter-key",
    "claude-mem": paths.source_path("companion_home", paths.HOME / "disabled/companion") / ".env",
    "gateway": paths.source_path("secret_store", paths.SECRETS) / 'openrouter',
    "provisioning": paths.source_path("secret_store", paths.SECRETS) / 'openrouter-provisioning',
}


def _read(p: pathlib.Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def known_values() -> tuple[dict[str, str], list[dict], list[dict]]:
    ""                                                                           
    values: dict[str, str] = {}
    homes: list[dict] = []
    skipped: list[dict] = []
    import scan_env

    # 1. the env inventory's secrets, read back out of their own files
    scan_path = paths.SCRATCH / "env.json"
    if scan_path.is_file():
        doc = json.loads(scan_path.read_text(encoding="utf-8"))
        for f in doc.get("files", []):
            wanted = {v["name"] for v in f.get("variables", [])
                      if v.get("class") == "secret"}
            if not wanted:
                continue
            path = paths.DATA / f["path"]
            text = _read(path)
            if text is None:
                skipped.append({"what": f["path"], "why": "unreadable now"})
                continue
            homes.append({"path": str(path)})
            for name, value in scan_env.parse(text)[0]:
                if name not in wanted:
                    continue
                if not searchable(value):
                    skipped.append({"what": f"{f['path']}:{name}",
                                    "why": ("shorter than 12 characters"
                                            if len(value) < MIN_LEN else
                                            "its shape is not distinctive enough for "
                                            "a text match to be evidence")})
                    continue
                values.setdefault(value, f"{f['project']}/{name}")

    # 2. the vault's slots
    if VAULT.is_dir():
        for slot in sorted(VAULT.glob("*/*/*")):
            if not slot.is_file() or slot.name.startswith(".") or slot.name == "meta.json":
                continue
            text = _read(slot)
            if text is None:
                continue
            value = text.strip()
            homes.append({"path": str(slot)})
            if not searchable(value):
                skipped.append({"what": f"vault:{slot.parent.parent.name}/{slot.name}",
                                "why": ("shorter than 12 characters"
                                        if len(value) < MIN_LEN else
                                        "its shape is not distinctive enough for a "
                                        "text match to be evidence")})
                continue
            values.setdefault(value, f"vault:{slot.parent.parent.name}/{slot.name}")

    # 3. the OpenRouter destinations
    for label, path in DESTINATIONS.items():
        text = _read(path)
        if text is None:
            continue
        homes.append({"path": str(path)})
        for raw in text.splitlines():
            raw = raw.strip()
            if "=" in raw and not raw.startswith("#"):
                raw = raw.split("=", 1)[1].strip().strip('"').strip("'")
            if raw.startswith("sk-") and len(raw) >= MIN_LEN:
                values.setdefault(raw, f"openrouter/{label}")
    return values, homes, skipped


def targets(days: int) -> tuple[list[pathlib.Path], list[dict]]:
    ""                                                                         
    out: list[pathlib.Path] = []
    notes: list[dict] = []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    if SESSIONS.is_dir():
        old = 0
        for p in SESSIONS.rglob("*.jsonl"):
            try:
                if p.stat().st_mtime < cutoff:
                    old += 1
                    continue
            except OSError:
                continue
            out.append(p)
        if old:
            notes.append({"what": f"{old} session transcript(s)",
                          "why": f"older than {days} days; `--days N` widens the "
                                 f"window and `--full` re-reads from the start"})
    logs = paths.STATE / "logs"
    if logs.is_dir():
        out.extend(sorted(logs.glob("*.jsonl")))
    if paths.DASHBOARD_HTML.is_file():
        out.append(paths.DASHBOARD_HTML)
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True, timeout=60)
        for rel in tracked.stdout.splitlines():
            p = ROOT / rel
            if p.is_file():
                out.append(p)
    except (OSError, subprocess.SubprocessError) as exc:
        notes.append({"what": "the tracked tree",
                      "why": f"git ls-files failed: {type(exc).__name__}"})
    return out, notes


def scan_sqlite(db: pathlib.Path, pattern: list[bytes], by_value: dict[bytes, str]
                ) -> tuple[dict[tuple[str, str], int], str | None]:
    ""                                                                      
                                                                              

                                                                              
                                                                               
                                                                                
                                                                            
                                                                            
       
    hits: dict[tuple[str, str], int] = {}
    if not db.is_file():
        return hits, None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return hits, f"{type(exc).__name__}: {exc}"
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        # FTS mirrors are the same text again: `observations_fts` and its
        # `_fts_*` shadow tables doubled every count on the first run.
        tables = [t for t in tables if not re.search(r"_fts(_|$)", t)]
        for table in tables:
            try:
                cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')
                        if str(r[2] or "").upper() in ("TEXT", "", "BLOB", "CLOB", "VARCHAR", "JSON")]
            except sqlite3.Error:
                continue
            if not cols:
                continue
            sel = ", ".join(f'"{c}"' for c in cols)
            try:
                cur = conn.execute(f'SELECT {sel} FROM "{table}"')
            except sqlite3.Error:
                continue
            while True:
                rows = cur.fetchmany(500)
                if not rows:
                    break
                for row in rows:
                    for col, cell in zip(cols, row):
                        if cell is None:
                            continue
                        blob = cell if isinstance(cell, bytes) else str(cell).encode("utf-8", "surrogateescape")
                        for needle in pattern:
                            n = blob.count(needle)
                            if n:
                                key = (by_value[needle], f"{table}.{col}")
                                hits[key] = hits.get(key, 0) + n
    except sqlite3.Error as exc:
        return hits, f"{type(exc).__name__}: {exc}"
    finally:
        conn.close()
    return hits, None


def scan_file(path: pathlib.Path, pattern: list[bytes], by_value: dict[bytes, str],
              start: int, longest: int) -> tuple[dict[str, int], int]:
    ""                                                       
    hits: dict[str, int] = {}
    try:
        size = path.stat().st_size
    except OSError:
        return hits, start
    if size < start:
        # TRUNCATED OR REPLACED. A log that rotated is a new file under an old
        # name, and resuming at the old offset would skip its whole beginning.
        start = 0
    try:
        with path.open("rb") as fh:
            fh.seek(start)
            carry = b""
            pos = start
            while True:
                chunk = fh.read(CHUNK)
                if not chunk:
                    break
                buf = carry + chunk
                for needle in pattern:
                    at = buf.find(needle)
                    while at >= 0:
                        name = by_value[needle]
                        hits[name] = hits.get(name, 0) + 1
                        at = buf.find(needle, at + 1)
                keep = min(longest, len(buf))
                carry = buf[len(buf) - keep:]
                pos += len(chunk)
    except OSError:
        return hits, start
    return hits, size


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true",
                    help="forget remembered offsets and read every target whole")
    ap.add_argument("--days", type=int, default=14,
                    help="how far back a session transcript counts (default 14)")
    a = ap.parse_args(argv[1:])

    values, homes, skipped = known_values()
    home_paths = {h["path"] for h in homes}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not values:
        atomic.write_json(OUT, {
            "scanned_at": now, "hits": [], "known": 0, "skipped": skipped,
            "degraded": [{"why": "nothing to look for: no env scan, no vault and "
                                 "no installed key on this machine",
                          "effect": "a clean report here means UNMEASURED, not clean"}]})
        print("leaks: nothing to look for — no env scan, no vault, no installed key")
        return 0

    by_value = {v.encode("utf-8", "surrogateescape"): n for v, n in values.items()}
    longest = max(len(b) for b in by_value)
    # `bytes.find` PER PATTERN, not one compiled alternation. The alternation was
    # the obvious thing and it read 956 MB in 2m58s: `re` walks the buffer in its
    # own VM, while `find` is `memmem` in C and 199 passes of that over the same
    # buffer still win by an order of magnitude. Measured, not assumed.
    pattern = sorted(by_value, key=len, reverse=True)

    state = {}
    if STATE.is_file() and not a.full:
        try:
            state = json.loads(STATE.read_text(encoding="utf-8")).get("offsets", {})
        except ValueError:
            state = {}

    files, notes = targets(a.days)
    hits: dict[tuple[str, str], int] = {}
    read_bytes = 0
    for p in files:
        key = str(p)
        if key in home_paths:
            continue
        start = int(state.get(key, 0))
        found, reached = scan_file(p, pattern, by_value, start, longest)
        read_bytes += max(0, reached - start)
        state[key] = reached
        for name, n in found.items():
            hits[(name, key)] = hits.get((name, key), 0) + n

                                                                           
                                                                                
                                                                                
    mem = paths.COMPANION_DB
    mem_hits, mem_problem = scan_sqlite(mem, pattern, by_value)
    for (name, where_in), n in mem_hits.items():
        hits[(name, f"{mem}#{where_in}")] = hits.get((name, f"{mem}#{where_in}"), 0) + n
    if mem_problem:
        notes.append({"what": str(mem), "why": f"a SQLite store that would not open: {mem_problem}"})
    companion = {"path": str(mem), "read": mem.is_file() and not mem_problem}

    atomic.write_json(STATE, {"updated_at": now, "offsets": state})
    rows = [{"secret": name, "where": where, "occurrences": n}
            for (name, where), n in sorted(hits.items(), key=lambda kv: -kv[1])]
    atomic.write_json(OUT, {
        "scanned_at": now,
        "known": len(values),
        "targets": len(files),
        "read_bytes": read_bytes,
        "incremental": not a.full,
        "hits": rows,
        "skipped": skipped,
        "not_scanned": notes,
        "companion_store": companion,
        "degraded": [],
    })
    print(f"leaks: {len(values)} known value(s) against {len(files)} target(s), "
          f"{read_bytes/1e6:.1f} MB read, {len(rows)} sighting(s)")
    for r in rows[:8]:
        # THE NAME AND THE FILE, never the line. A report that quotes the leak is
        # a second copy of it, in a file that is easier to read than the first.
        print(f"  {r['secret']} seen in {r['where']} ×{r['occurrences']}")
    for n in notes:
        print(f"  not scanned: {n['what']} — {n['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
