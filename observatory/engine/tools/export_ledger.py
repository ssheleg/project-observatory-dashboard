#!/usr/bin/env python3
""                                                                     

                                                                              
                                                                               
                                                                             
                                                                                  
                                                                           
             

                                                                            
                                                                                
                                                                               
                                                                               
                                                                          

                                                                              
                                                                            
                                                                              
                                                 

                                                           
                                                                                 
                                                                            

                                                          

                                                                              
                                                                               
                                                                                   
                                                                               
                                                                           
                                                                             
                

                                                                               

                                                                         
                                                                             
                                  
                                                                                
                                                                             
                                                                              
                                      
                                                                            
                                                                                  
                                                                   
   
from __future__ import annotations
import json, pathlib, sqlite3, sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic
import paths                                                                      
from store import db as store_db                                                  

OUT = paths.REGISTRY / "ledger.jsonl"
HEADER = {
    "_export": "ledger",
    "_note": ("Every revision of the append-only ledger, and every tombstone, as "
              "JSON Lines so a diff shows one record per line. Written by "
              "tools/export_ledger.py on every tick. This is the ONLY copy of the "
              "ledger outside store/observatory.db, which is gitignored — the "
              "store was found corrupt on 2026-09-06 and recovered by luck."),
    "_tombstoned_text_is_here": (
        "A TOMBSTONED REVISION'S TEXT IS IN THIS FILE, and this file is committed. "
        "A tombstone hides a revision from every READ — `ledger.live()`, the "
        "lexical index and the vector index, measured 2026-09-07 — and keeps it in "
        "canon, because retention never deletes a ledger row: an erasure with no "
        "audit trail is indistinguishable from a bug. The export mirrors canon, so "
        "it keeps it too, and git history keeps the export. If text must be "
        "unrecoverable rather than unreadable, a tombstone is not the mechanism "
        "and this project does not have one — revisions are immutable by design, "
        "so nothing here can rewrite one."),
}


def rows(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM ledger ORDER BY memory_id, revision"):
        out.append({"_kind": "revision", **{k: r[k] for k in r.keys()}})
    try:
        for r in conn.execute("SELECT * FROM tombstones ORDER BY memory_id, revision"):
            out.append({"_kind": "tombstone", **{k: r[k] for k in r.keys()}})
    except sqlite3.Error:
        pass
    return out


def render(data: list[dict]) -> str:
    lines = [json.dumps(HEADER, ensure_ascii=False, sort_keys=True)]
    lines += [json.dumps(d, ensure_ascii=False, sort_keys=True) for d in data]
    return "\n".join(lines) + "\n"


#: Two tick intervals. The tick exports on every run, so a row still unexported
#: after two of them means the exporter is not running — while a row written in
#: the last few minutes means only that the export is younger than it.
GRACE_SECONDS = 3600


def key(row: dict) -> tuple:
    return (row.get("_kind"), row.get("memory_id"), row.get("revision"))


def read_export() -> dict[tuple, dict]:
    if not OUT.is_file():
        return {}
    out = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("_kind"):
            out[key(row)] = row
    return out


def age_seconds(created_at: str | None) -> float:
    ""                                                                          
                                                                              
    if not created_at:
        return float("inf")
    try:
        made = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return float("inf")
    return (datetime.now(timezone.utc) - made).total_seconds()


def audit(stored: list[dict]) -> tuple[int, list[str]]:
    ""                                                                           
    have, want = read_export(), {key(r): r for r in stored}
    missing = [want[k] for k in want.keys() - have.keys()]
    extra = [have[k] for k in have.keys() - want.keys()]
    differing = [k for k in want.keys() & have.keys() if want[k] != have[k]]

    stale = [r for r in missing if age_seconds(r.get("created_at")) > GRACE_SECONDS]
    fresh = len(missing) - len(stale)
    out, code = [], 0

    if differing:
        code = 1
        out.append(f"DIVERGED: {len(differing)} record(s) differ between the store and the "
                   f"export — {differing[:2]}. That is not staleness; one of the two was "
                   f"rewritten or damaged.")
    if stale:
        oldest = max(age_seconds(r.get("created_at")) for r in stale)
        code = 1
        out.append(f"NOT EXPORTED: {len(stale)} record(s) older than {GRACE_SECONDS // 60} "
                   f"minutes are missing from the export, the oldest by "
                   f"{oldest / 3600:.1f} hours. Nothing is exporting. "
                   f"Run tools/export_ledger.py.")
    if extra:
        out.append(f"note: the export holds {len(extra)} record(s) the store does not. That is "
                   f"the export doing its job after a store loss, not a fault.")
    if fresh:
        out.append(f"{fresh} record(s) written since the last export, all within the "
                   f"{GRACE_SECONDS // 60}-minute grace — the next tick exports them.")
    if not out:
        out.append(f"ledger export current: {len(want)} record(s)")
    return code, out


def main(argv: list[str]) -> int:
    if "--check" in argv:
                                                                                
                                                                                  
                                                    
        conn = sqlite3.connect(f"file:{paths.DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        code, lines = audit(rows(conn))
        conn.close()
        for line in lines:
            print(line, file=sys.stderr if code else sys.stdout)
        return code

    conn = store_db.connect()
    text = render(rows(conn))
    n = text.count("\n") - 1
    conn.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(OUT, text)
    # The registry lives in the private workspace, not under the program: name it
    # relative to the source only in a checkout that keeps data beside the code.
    shown = OUT.relative_to(ROOT) if OUT.is_relative_to(ROOT) else OUT
    print(f"ledger -> {shown} ({n} record(s), "
          f"{OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
