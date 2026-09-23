#!/usr/bin/env python3
"""Fingerprint the registry, then say what moved since the previous fingerprint.

Deterministic. No model participates — this is the INPUT the agent reads, and it
is computed before any token is spent so that a quiet machine costs nothing.

Why fingerprints rather than a git diff of registry/*.json: git sees only what
was committed, and the interesting moment is often before that. A fingerprint is
taken on every scan, committed or not.

Why one row per scan rather than one per project: 159 projects (measured 2026-09-08; 157 when this was written) times every scan
is a table that grows for no reason. The whole map is small — a few fields per
project — and diffing two maps is what produces the per-project rows that matter.

Run `snapshot` after an emit, then `diff` to fill the `deltas` table:

    python3 collectors/compute_deltas.py snapshot
    python3 collectors/compute_deltas.py diff
"""
from __future__ import annotations
import argparse, json, sys, pathlib, uuid
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths
from collectors import registry_read
from store import db as store_db

#: One rule, two collectors — see `collectors/registry_read.py` for why an
#: unreadable registry may not degrade to an empty one.
RegistryUnreadable = registry_read.RegistryUnreadable

KIND = store_db.FINGERPRINT_KIND   # the store owns its own vocabulary
COLLECTOR_VERSION = "compute_deltas/1"

#: What a change in each field means, in words the agent will read. A delta kind
#: with no meaning attached is a diff nobody can act on.
FIELD_MEANING = {
    "repos": "the set of repositories implementing it changed",
    "last_activity_on": "work happened",
    "lifecycle": "it was archived or revived",
    "ownership": "who owns it changed",
    "sites": "a public surface appeared or disappeared",
    "stack": "the technology it is built on changed",
    "vault_notes": "the wiki gained or lost notes about it",
    "dirty": "uncommitted work appeared or was resolved",
    "commits": "commits were recorded",
    "name": "it was renamed",
}

#: The two kinds that are not a field changing, and which need the explanation
#: most: they were the ones arriving at the agent as a bare word.
LIFECYCLE_MEANING = {
    "project-appeared": "the estate gained a project the previous scan did not hold",
    "project-disappeared": "a project the previous scan held is gone — deleted, "
                           "renamed, or its anchor withdrawn",
}


def meaning_of(kind: str) -> str:
    """The sentence FIELD_MEANING was written for.

    Its docstring said the table held "what a change in each field means, in
    words the agent will read" — and only its KEYS were ever used, to enumerate
    which fields moved. `agent/observe.py` sent `kind: before -> after` and the
    prose went nowhere: written for a reader that did not exist. This is the
    accessor that gives it one."""
    if kind in LIFECYCLE_MEANING:
        return LIFECYCLE_MEANING[kind]
    return FIELD_MEANING.get(kind[:-len("-changed")] if kind.endswith("-changed") else kind, "")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprints(conn) -> dict[str, dict]:
    projects = registry_read.read("projects.json", "projects")
    repos = {r["id"]: r for r in registry_read.read("repositories.json", "repositories")}
    members: dict[str, list[str]] = {}
    for rel in registry_read.read("relations.json", "relations"):
        if rel["type"] == "implemented_by":
            members.setdefault(rel["from"], []).append(rel["to"])
    commits = {r["project_id"]: r["n"] for r in conn.execute(
        "SELECT project_id, count(*) AS n FROM events WHERE kind='commit'"
        " AND project_id IS NOT NULL GROUP BY project_id")}
    out = {}
    for p in projects:
        ids = sorted(members.get(p["id"], []))
        dirty = sum((repos[i].get("local") or {}).get("uncommitted_files", 0)
                    for i in ids if i in repos)
        out[p["id"]] = {
            "name": p["name"],
            "repos": [i.split(":", 1)[1] for i in ids],
            "last_activity_on": p.get("last_activity_on", ""),
            "lifecycle": p.get("lifecycle", ""),
            "ownership": p.get("ownership", ""),
            "sites": sorted(s["host"] for s in p.get("sites", [])),
            "stack": sorted(p.get("stack", [])),
            "vault_notes": p.get("vault_notes", 0),
            "dirty": dirty,
            "commits": commits.get(p["id"], 0),
        }
    return out


#: The cursor's name. One string, one place — `store/schema.sql` documents the
#: table and this is the only key written into it by this collector.
CURSOR = "deltas.diffed_through"


def diffed_through(conn) -> str | None:
    row = conn.execute("SELECT value FROM cursors WHERE name = ?", (CURSOR,)).fetchone()
    return row[0] if row else None


def remember(conn, scan_id: str) -> None:
    conn.execute("INSERT INTO cursors (name, value, updated_at) VALUES (?,?,?)"
                 " ON CONFLICT(name) DO UPDATE SET value = excluded.value,"
                 " updated_at = excluded.updated_at", (CURSOR, scan_id, now()))


def fingerprints_kept(conn) -> list:
    """Every fingerprint still on record, oldest first. Retention keeps a few.

    **`rowid` is the tiebreak and it is load-bearing.** `observed_at` is
    second-resolution and this ordering once used `id` — `obs:<random hex>` — so
    two snapshots inside one second, which a launchd tick plus a manual run
    produces, were ordered AT RANDOM and a diff over them could come out
    inverted: every `before` and `after` swapped, every delta describing the
    opposite of what happened. `scans` got a unique-id fix for the collision
    half of this on 2026-09-04 (trap T12). `rowid` is monotonic in insertion
    order, which is exactly the question being asked — which was written later.

    Replaces `latest_two()`, whose contract was "the two most recent" and could
    therefore not express "since the last one I diffed"."""
    return list(conn.execute(
        "SELECT id, scan_id, payload_json, observed_at FROM observations"
        " WHERE kind = ? ORDER BY observed_at, rowid", (KIND,)))


def cmd_snapshot(conn) -> int:
    # A timestamp at second resolution is not unique: a launchd tick and a manual
    # run landing in the same second collided on the primary key. Verified
    # 2026-09-04, and the fix now lives in `store.db.scan_id` — it was applied
    # here and in `scan_events` and forgotten in `scan_sessions` (2026-09-08).
    scan_id = store_db.scan_id("fingerprint", now())
    fp = fingerprints(conn)
    with conn:
        conn.execute("INSERT INTO scans (id, started_at, finished_at, collector_version,"
                     " counts_json) VALUES (?,?,?,?,?)",
                     (scan_id, now(), now(), COLLECTOR_VERSION,
                      json.dumps({"projects": len(fp)})))
        conn.execute("INSERT INTO observations (id, scan_id, subject_id, kind, payload_json,"
                     " observed_at) VALUES (?,?,?,?,?,?)",
                     (f"obs:{uuid.uuid4().hex[:16]}", scan_id, "estate", KIND,
                      json.dumps(fp, ensure_ascii=False, sort_keys=True), now()))
    print(f"fingerprinted {len(fp)} projects as {scan_id}")
    return 0


def pair(conn) -> tuple[object, object, list[str], int]:
    """Which two fingerprints to compare, and what saying so costs.

    It used to be "the two most recent", full stop, and that could not tell what
    had already been compared. Two live consequences, measured 2026-09-07:

    * **A repeated `diff` wrote the same delta again.** Three such rows sat in
      the live store, all still pending, so the agent would have read one change
      twice and could have written two notes about it. In a fixture: 2 rows
      became 4. **Past tense on purpose, re-measured 2026-09-08: zero duplicate
      pending deltas, of 107 pending** — the cursor did what it was added for,
      and a sentence left in the present tense would go on reporting a defect
      that is fixed, which is the same lie as an undated figure.
    * **A skipped `diff` lost a generation.** Three snapshots and one diff
      produced deltas for the LAST pair only; the rename in the middle
      generation became nothing, under a printed "2 delta(s) written". A failed
      tick or a locked store is enough to cause it.

    So the FROM end is the last state actually reported — the cursor — rather
    than whichever fingerprint happens to be second-newest. Folding several
    generations into one comparison loses nothing: a delta answers "what moved
    since we last looked", and the answer is the same whether the estate passed
    through one intermediate state or four. It is REPORTED, because a fold and a
    quiet skip look identical in the output otherwise.

    Returns (from_row, to_row, notes, folded). `from_row` is None when there is
    nothing to compare against yet.
    """
    kept = fingerprints_kept(conn)
    notes: list[str] = []
    if not kept:
        return None, None, ["no fingerprint on record"], 0
    to_row = kept[-1]
    through = diffed_through(conn)
    if through == to_row["scan_id"]:
        return None, to_row, ["already diffed through this fingerprint"], 0
    if len(kept) == 1:
        return None, to_row, ["only one fingerprint on record"], 0
    by_scan = {r["scan_id"]: i for i, r in enumerate(kept)}
    if through is None:
        # NEVER DIFFED, so "since we last looked" has no answer — and the honest
        # substitute is the OLDEST state still on record, not the second-newest.
        # `kept[-2]` was the first version of this line and it loses every
        # generation before it: three snapshots on a fresh store produced deltas
        # for the last pair only, which is the same silent loss the cursor exists
        # to close, one case over. Same rule as the pruned branch below.
        from_row = kept[0]
    elif through in by_scan:
        from_row = kept[by_scan[through]]
    else:
        # The last diffed fingerprint has been pruned — retention keeps only a
        # few. The oldest one still on record is the closest available floor,
        # and whatever moved between the pruned state and it CANNOT be recovered.
        # Said out loud: this is the one case where a delta is genuinely lost,
        # and a collector that hid it would be claiming completeness it does not
        # have.
        from_row = kept[0]
        notes.append(f"the last diffed fingerprint ({through}) has been pruned; "
                     f"comparing from the oldest one still kept ({from_row['scan_id']}) — "
                     f"changes before it are not recoverable")
    folded = by_scan[to_row["scan_id"]] - by_scan[from_row["scan_id"]] - 1
    if folded > 0:
        notes.append(f"{folded} intermediate fingerprint(s) were never diffed; their "
                     f"changes are folded into this comparison rather than lost")
    return from_row, to_row, notes, folded


def cmd_diff(conn) -> int:
    old, new, notes, folded = pair(conn)
    if new is None:
        print("no fingerprint yet — run `snapshot` first", file=sys.stderr)
        return 1
    if old is None:
        print(notes[0] if notes else "nothing to compare against yet")
        pending = conn.execute('SELECT count(*) FROM deltas WHERE consumed_at IS NULL').fetchone()[0]
        print(f"{pending} unconsumed delta(s) waiting for the agent")
        return 0
    for note in notes:
        print(f"  NOTE: {note}")
    a = json.loads(old["payload_json"])
    b = json.loads(new["payload_json"])

    written = 0
    with conn:
        for pid in sorted(set(a) | set(b)):
            before, after = a.get(pid), b.get(pid)
            if before == after:
                continue
            if before is None:
                kinds = [("project-appeared", None, after)]
            elif after is None:
                kinds = [("project-disappeared", before, None)]
            else:
                # Over the UNION OF KEYS PRESENT, not over FIELD_MEANING. The
                # loop used to iterate the meaning table, so a field the
                # fingerprint records and the table does not know was
                # undiffable: `name` was exactly that, and a renamed project
                # produced ZERO deltas while this command printed "nothing
                # moved — the agent will not be called". A reassurance in place
                # of an event. Measured 2026-09-07 by driving a rename through
                # `cmd_diff` on a fixture: 0 rows written.
                #
                # Iterating the data instead means the next field added to
                # `fingerprints()` is diffable the day it is added; the meaning
                # is what a test then demands, and a missing one is a red gate
                # rather than silence.
                kinds = [(f"{f}-changed", before.get(f), after.get(f))
                         for f in sorted(set(before) | set(after))
                         if before.get(f) != after.get(f)]
            for kind, was, is_ in kinds:
                conn.execute(
                    "INSERT INTO deltas (id, from_scan, to_scan, subject_id, kind,"
                    " before_json, after_json) VALUES (?,?,?,?,?,?,?)",
                    (f"delta:{uuid.uuid4().hex[:16]}", old["scan_id"], new["scan_id"], pid,
                     kind, json.dumps(was, ensure_ascii=False),
                     json.dumps(is_, ensure_ascii=False)))
                written += 1
        # INSIDE the transaction that wrote the deltas. Advancing the cursor
        # afterwards would leave a window where the rows exist and the record of
        # having written them does not — and the next run would write them
        # again, which is the defect this cursor exists to close.
        remember(conn, new["scan_id"])
    pending = conn.execute(
        "SELECT count(*) FROM deltas WHERE consumed_at IS NULL").fetchone()[0]
    print(f"{written} delta(s) written between {old['scan_id']} and {new['scan_id']}"
          + (f", folding {folded} intermediate generation(s)" if folded > 0 else ""))
    print(f"{pending} unconsumed delta(s) waiting for the agent")
    if written == 0:
        print("nothing moved — the agent will not be called, and that costs nothing")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["snapshot", "diff", "pending"])
    args = ap.parse_args()
    conn = store_db.connect()
    try:
        if args.command == "snapshot":
            # A REFUSAL, not a fingerprint of nothing. An unreadable registry
            # recorded as `{}` would make every project look disappeared, and the
            # next diff would hand the agent one `project-disappeared` per
            # project — its most expensive input, entirely fictional.
            try:
                return cmd_snapshot(conn)
            except RegistryUnreadable as exc:
                print(f"NOT fingerprinted — {exc}", file=sys.stderr)
                print("The registry is the subject of this measurement; a snapshot "
                      "taken without it would read as an estate that lost every "
                      "project.", file=sys.stderr)
                return 1
        if args.command == "diff":
            return cmd_diff(conn)
                                                                           
                                                                               
                                                                                
                                                                      
        CAP = 60
        total = conn.execute(
            "SELECT count(*) FROM deltas WHERE consumed_at IS NULL").fetchone()[0]
        rows = list(conn.execute(
            "SELECT subject_id, kind, before_json, after_json FROM deltas"
            " WHERE consumed_at IS NULL ORDER BY subject_id LIMIT ?", (CAP,)))
        for r in rows:
            print(f"  {r['subject_id']:<48} {r['kind']:<26} "
                  f"{r['before_json'][:40]} -> {r['after_json'][:40]}")
        print(f"{len(rows)} shown of {total} unconsumed"
              + (f" — {total - len(rows)} not listed, capped at {CAP}"
                 if total > len(rows) else ""))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
