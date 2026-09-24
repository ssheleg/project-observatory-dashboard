#!/usr/bin/env python3
"""Look for the estate's own secrets where they do not belong.

    scan_leaks.py                 incremental: only bytes nobody has read yet
    scan_leaks.py --full          forget the offsets and read everything again
    scan_leaks.py --days N        how far back a transcript counts (default 14)

WHY. `tools/check_secrets.py` asks "does this tracked file contain something
SHAPED like a credential" — a good question with a known weakness: it cannot tell
this estate's live key from a plausible-looking string, so it is tuned not to cry
wolf and it only reads the tracked tree. This asks the other question, the one
that actually goes wrong in practice: **is a value we hold sitting somewhere
it should not be.** The typical leak is a value echoed into an agent session
transcript by a database client error or an HTTP library traceback — and
nothing else on the machine would notice it.

WHAT IT KNOWS. Every value the estate holds, gathered at the start of the run and
dropped at the end of it:

  env secrets   the `secret`-class variables `store/raw/env.json` lists, read
                back out of their files
  vault slots   `<vault dir>/<project>/<env>/<NAME>` (`OBSERVATORY_VAULT_DIR`)
  destinations  the files an OpenRouter key is installed into (`DESTINATIONS`)

READING THE VAULT DIRECTLY IS THE ONE EXCEPTION TO `handling-secrets`, and it is
deliberate: that rule addresses AGENTS, whose transcripts are the hazard. This is
a tool — it holds the values in memory for one pass, matches, and reports a NAME
and a FILE. It never prints a value, never writes one, and never quotes the
surrounding line, because a leak report that quotes the leak is a second copy of
it. You cannot detect the leak of a value you have no copy of; the alternative to
this exception is not a safer scanner, it is no scanner.

WHAT IT READS. Agent session transcripts — gigabytes over a few weeks on a busy
machine, which is why this is incremental: a JSONL transcript is append-only, so
a remembered offset makes the steady-state cost the size of what was said since
the last tick. Plus this project's own logs, its built page, its tracked tree,
and the session companion's SQLite store.

WHAT IT DOES NOT DO. It does not write `leaks.jsonl`. That register is the
operator's debt ledger and a false entry there is expensive to withdraw — so a
hit leaves as a `secret.seen_outside_its_home` finding carrying the exact
`tools/vault.py leak` command, and a person or an agent confirms it. The scanner
is allowed to be noisy; the ledger is not.
"""
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
sys.path.insert(0, str(ROOT / "tools"))
import atomic              
import paths              
import sqlite_scan  # noqa: E402  — when a store may be read from its last mark (PB-131)

STATE = paths.SCRATCH / "leak-scan-state.json"
OUT = paths.SCRATCH / "leak-scan.json"
VAULT = pathlib.Path(os.environ.get(
    "OBSERVATORY_VAULT_DIR",
    paths.source_path("secret_store", paths.SECRETS) / 'projects'))
SESSIONS = pathlib.Path(os.environ.get(
    "OBSERVATORY_SESSIONS", paths.SESSIONS))

#: Below this a value is not searched for. A twelve-character password produces
#: matches on prose; the rule this protects is that a report nobody can trust is
#: a report nobody reads. Short values are COUNTED and named in `skipped`, never
#: dropped in silence.
MIN_LEN = 12


def searchable(value: str) -> bool:
    """Is a match on this value EVIDENCE, or just a coincidence?

    `scan_env.classify` calls a variable a secret when its NAME says so and the
    value is not obviously a word — which is right for an inventory and wrong
    here. A session-name variable can pass that test while its value is a short
    identifier that appears in ordinary text, and a scan built on it would
    report thousands of "leaks" in one transcript.

    So the leak hunt uses the stricter, NAME-BLIND test: a known issuer prefix, a
    URL carrying credentials, or real randomness. A value that fails it is named
    in `skipped` rather than dropped quietly — it is still a secret, it is just
    not one a text match can prove anything about.
    """
    import scan_env
    return len(value) >= MIN_LEN and scan_env.looks_secret(value)

#: How much of one file to read at a time, with an overlap so a value split
#: across two reads is still found.
CHUNK = 1 << 20

#: The four destinations `tools/install_key.py` owns, plus the observatory's own.
DESTINATIONS = {
    "observatory": paths.STATE / ".openrouter-key",
    # The legacy location, when the state is redirected (PB-091): a key left there
    # is still a key on this machine and must be seen.
    **({"observatory-legacy": paths.STORE / ".openrouter-key"} if paths.STATE != paths.STORE else {}),
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
    """value -> a name for it, plus the homes to exclude and what was skipped."""
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
    """Where a value must never appear, and what was left out of the window."""
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


def scan_sqlite(db: pathlib.Path, pattern: list[bytes], by_value: dict[bytes, str],
                since: dict[str, int] | None = None
                ) -> tuple[dict[tuple[str, str], int], str | None, dict[str, int], int]:
    """Occurrences by (secret name, `table.column`) across every text column
    of a SQLite store, read-only; the reason when it could not be read; the
    highest rowid read per table; and the number of rows read.

    A session companion's store holds session summaries, which is exactly the
    shape a leak takes, and a text scan of a SQLite file reads page headers and
    misses the rows — so the store is read as a database instead of being named
    as unread. Rows are read per table in pages of 500 so a store of hundreds of
    megabytes does not sit in memory.

    `since` maps a table to the highest rowid a previous pass read; only rows
    above it are read, the same way transcripts are read from their last
    offset, so a sighting is reported by the pass that first reads its row
    (tools/sqlite_scan.py decides when a pass must be complete). A page is
    tested against every value at once and examined cell by cell only when it
    holds one. A table that cannot be addressed by rowid is read whole on
    every pass and gets no mark.
    """
    since = since or {}
    hits: dict[tuple[str, str], int] = {}
    high: dict[str, int] = {}
    read = 0
    if not db.is_file():
        return hits, None, high, read
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return hits, f"{type(exc).__name__}: {exc}", high, read
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
            by_rowid = True
            try:
                floor = sqlite_scan.floor_for(conn, table, int(since.get(table, 0)))
                cur = conn.execute(f'SELECT rowid, {sel} FROM "{table}" WHERE rowid > ? ORDER BY rowid', (floor,))
            except sqlite3.Error:
                by_rowid, floor = False, 0
                try:
                    cur = conn.execute(f'SELECT NULL, {sel} FROM "{table}"')
                except sqlite3.Error:
                    continue
            top = floor
            while True:
                rows = cur.fetchmany(500)
                if not rows:
                    break
                read += len(rows)
                if by_rowid:
                    top = max(top, rows[-1][0])
                blobs = [[None if c is None else (c if isinstance(c, bytes) else str(c).encode("utf-8", "surrogateescape"))
                          for c in row[1:]] for row in rows]
                joined = b"\0".join(b for cells in blobs for b in cells if b)
                present = [n for n in pattern if n in joined]
                if not present:
                    continue
                for cells in blobs:
                    for col, blob in zip(cols, cells):
                        if not blob:
                            continue
                        for needle in present:
                            n = blob.count(needle)
                            if n:
                                key = (by_value[needle], f"{table}.{col}")
                                hits[key] = hits.get(key, 0) + n
            if by_rowid:
                high[table] = top
    except sqlite3.Error as exc:
        return hits, f"{type(exc).__name__}: {exc}", {}, read
    finally:
        conn.close()
    return hits, None, high, read


def scan_file(path: pathlib.Path, pattern: list[bytes], by_value: dict[bytes, str],
              start: int, longest: int) -> tuple[dict[str, int], int]:
    """Occurrences by secret name, and the offset reached."""
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

    state, sqlite_mark = {}, {}
    if STATE.is_file():
        try:
            saved = json.loads(STATE.read_text(encoding="utf-8"))
            sqlite_mark = saved.get("sqlite") or {}
            if not a.full:
                state = saved.get("offsets", {})
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

    # THE COMPANION'S STORE, read as a database rather than named as unread.
    # Whole every time — SQLite has no offset to resume from and the store is
    # rewritten in place — so it is not part of `read_bytes`.
    mem = paths.COMPANION_DB
    today = datetime.now(timezone.utc).date()
    digest = sqlite_scan.values_digest(values)
    full, why = sqlite_scan.plan(sqlite_mark, digest, a.full, today)
    since = {} if full else (sqlite_mark.get("stores") or {}).get(str(mem))
    mem_hits, mem_problem, mem_high, mem_rows = scan_sqlite(mem, pattern, by_value, since)
    new_mark = sqlite_scan.next_mark(sqlite_mark, digest, full, today,
                                     {} if mem_problem else {str(mem): mem_high}, not mem_problem)
    for (name, where_in), n in mem_hits.items():
        hits[(name, f"{mem}#{where_in}")] = hits.get((name, f"{mem}#{where_in}"), 0) + n
    if mem_problem:
        notes.append({"what": str(mem), "why": f"a SQLite store that would not open: {mem_problem}"})
    companion = {"path": str(mem), "read": mem.is_file() and not mem_problem,
                 "mode": "full" if full else "incremental", "why": why, "rows_read": mem_rows}

    atomic.write_json(STATE, {"updated_at": now, "offsets": state,
                              **({"sqlite": new_mark} if new_mark else {})})
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
          f"{read_bytes/1e6:.1f} MB read, {len(rows)} sighting(s); companion store "
          f"{companion['mode']} ({why}), {mem_rows} row(s) read")
    for r in rows[:8]:
        # THE NAME AND THE FILE, never the line. A report that quotes the leak is
        # a second copy of it, in a file that is easier to read than the first.
        print(f"  {r['secret']} seen in {r['where']} ×{r['occurrences']}")
    for n in notes:
        print(f"  not scanned: {n['what']} — {n['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
