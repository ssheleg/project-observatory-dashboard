"""When a known-value scan of a SQLite store may read only new rows.

Two tools read the memory companion's stores for known credential values:
`tools/scan_leaks.py` reports sightings, `tools/scrub_companion.py` rewrites
them. Both used to read every row on every tick. On a store of a few gigabytes
under a busy disk, that took most of the tick's half hour (PB-125, PB-131).

The rule both follow:

- The first pass is complete: every row of every table.
- Later passes read only rows whose rowid is above the highest rowid the last
  successful pass read, per table.
- A complete pass is forced when the set of known values changes, because a
  value learned today must be looked for in yesterday's rows too. It is also
  forced when the last complete pass is older than FULL_EVERY, which catches
  rows updated in place and rowids that were reused, and when asked for.
- A table whose highest rowid is now below its mark was emptied or recreated,
  so it is read from the start.

The value set is identified by an HMAC under this workspace's env-fingerprint
salt, so the state file holds nothing a value could be recovered from. Without
the salt no mark is kept, and every pass is complete.

The caller keeps the mark in its own state file and advances it only after a
pass that succeeded. A store that failed keeps its old marks, and a complete
pass that failed anywhere is not recorded as complete.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import sqlite3

FULL_EVERY = datetime.timedelta(days=7)


def values_digest(values: dict[str, str]) -> str | None:
    """HMAC of the known (value, name) set, or None when the salt is unavailable.

    Reads the salt only; never creates it (runtime_identity: reads never bootstrap).
    """
    try:
        import scan_env
        key = scan_env.salt().encode("ascii")
    except Exception:
        return None
    material = "\n".join(sorted(f"{n}\0{v}" for v, n in values.items())).encode("utf-8", "surrogateescape")
    return hmac.new(key, material, hashlib.sha256).hexdigest()


def plan(mark: dict | None, digest: str | None, force_full: bool,
         today: datetime.date) -> tuple[bool, str]:
    """(complete pass?, why) for a stored mark and the current value set."""
    mark = mark or {}
    if force_full:
        return True, "--full"
    if digest is None:
        return True, "no salt to identify the value set"
    if mark.get("values") != digest:
        return True, "the set of known values changed" if mark else "first pass"
    try:
        last = datetime.date.fromisoformat(mark.get("full_on") or "")
    except ValueError:
        return True, "no record of a complete pass"
    if today - last >= FULL_EVERY:
        return True, f"last complete pass {last.isoformat()}"
    return False, "incremental"


def floor_for(conn: sqlite3.Connection, table: str, mark: int) -> int:
    """The rowid to read above: the mark, or 0 when the table was emptied or recreated."""
    if not mark:
        return 0
    top = conn.execute(f'SELECT max(rowid) FROM "{table}"').fetchone()[0] or 0
    return 0 if top < mark else mark


def next_mark(mark: dict | None, digest: str | None, full: bool, today: datetime.date,
              stores: dict[str, dict[str, int]], all_ok: bool) -> dict | None:
    """The mark to store after a pass, or None when none may be kept (no salt).

    `stores` holds the new per-table high-water rowids of the stores that
    succeeded; a store missing from it keeps its old marks.
    """
    if digest is None:
        return None
    mark = mark or {}
    kept = {} if full else dict(mark.get("stores") or {})
    for store, tables in stores.items():
        kept[store] = {**(kept.get(store) or {}), **tables}
    if full and not all_ok:
        # A complete pass that failed somewhere is not a complete pass.
        return {"values": mark.get("values"), "full_on": mark.get("full_on"), "stores": kept}
    return {"values": digest, "full_on": today.isoformat() if full else mark.get("full_on"), "stores": kept}
