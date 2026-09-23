#!/usr/bin/env python3
"""Weekly aggregates that outlive the rows they were computed from.

Every statistic in this system was a `sum(1 for …)` over the CURRENT registry,
so the only real time series was the raw commit stream — bounded by
`store/retention.json` — and once a week aged out, "was this project active in
Q1" stopped having an answer at all. An aggregate is orders of magnitude
smaller than what it summarises: one row per project per week is a few
thousand rows a year for a large estate, so it is kept for ever while the rows
beneath it are still pruned on the same horizon as before.

**The freeze rule is the whole design.** A week is recomputed only while its
WHOLE span lies inside the event window. Once retention's cutoff passes that
week's start, the row is frozen and never rewritten — because recomputing it
would read the pruned events, find none, and replace a measurement with a zero.
That is the same shape as a collector and a pruner undoing each other every
tick until they are made to read one horizon, except that here it destroys the
only copy rather than merely churning it.

A week only PARTLY covered by the window is not written at all. A partial count
understates without saying so, and no row is better than a wrong one.

    rollup.py refresh    recompute every fully-covered week; freeze the rest
    rollup.py status     what is stored, what is frozen, what the window covers
"""
from __future__ import annotations
import argparse, collections, json, pathlib, sqlite3, sys
from datetime import date, datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import identity                                                                 
import paths                                                                    
from store import db as store_db                                                

RETENTION = paths.config_file("retention.json")


def _registry_projects() -> list[dict]:
    """The registry's projects, or [] with the reason on stderr.

    Optional by the same rule every collector input follows: a registry that
    will not open must not stop the rollup, it must stop the FOLDING — and then
    a former id simply keeps its own row, which is the state before folding
    existed rather than a wrong number.
    """
    f = paths.REGISTRY / "projects.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))["projects"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"  rollup: {f} unreadable ({type(exc).__name__}); former project "
              f"ids are NOT folded this run", file=sys.stderr)
        return []


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def window_days() -> int:
    """The SAME horizon the collector asks git for and the pruner deletes by.
    Three readers, one file — the arrangement trap T25 exists to enforce."""
    try:
        return int(json.loads(RETENTION.read_text(encoding="utf-8"))["events_days"])
    except Exception:
        return 365


def week_of(stamp: str) -> tuple[str, str]:
    """(ISO year-week, that week's Monday) in UTC.

    Computed in Python, not with SQLite's `%W`, because `%W` counts weeks from
    the first Monday of the calendar year and puts early-January days in week 00
    — a different answer from ISO 8601 at exactly the boundary where a yearly
    report is read. Every timestamp here is UTC `Z`, so the week a commit falls
    in is unambiguous."""
    d = date.fromisoformat(stamp[:10])
    iso = d.isocalendar()
    monday = d - timedelta(days=iso.weekday - 1)
    return f"{iso.year}-W{iso.week:02d}", monday.isoformat()


def refresh(conn: sqlite3.Connection, *, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=window_days())
    # BOTH KINDS. With `commit` alone as the whole series, a (project, week)
    # pair with agent sessions but no commit produced NO ROW AT ALL — in the
    # one table designed to outlive its source. And with a deadline attached:
    # once a week passes the retention cutoff the freeze rule forbids
    # rewriting it, so every such week would become a permanent zero.
    #
    # `commits`, `active_days` and `authors` keep their EXACT previous meaning —
    # commits, commit-days, commit-actors. Widening a column in place is how a
    # measurement stops being comparable with the one beside it.
    rows = conn.execute(
        "SELECT project_id, occurred_at, actor, kind FROM events"
        " WHERE kind IN ('commit','session') AND project_id IS NOT NULL").fetchall()

    # A PROJECT'S FORMER IDS FOLD INTO ITS CURRENT ONE, before bucketing.
    # A project's id is derived from its publication state, so giving it a
    # remote renames it — and its earlier events keep the old name. Without
    # folding, one week can exist under BOTH ids of the same project, and any
    # reader that took both counts that week twice. Folding here rather than
    # summing at read time is what keeps `active_days`, `authors` and
    # `worked_days` correct: they are SET SIZES computed from the events, and
    # two rows cannot be added.
    former = identity.former_index(_registry_projects())

    buckets: dict[tuple[str, str], dict] = {}
    for r in rows:
        pid, stamp, actor, kind = (r["project_id"], r["occurred_at"], r["actor"],
                                   r["kind"]) if hasattr(r, "keys") else r
        pid = former.get(pid, pid)
        week, monday = week_of(stamp)
        b = buckets.setdefault((pid, week), {
            "week_start": monday, "commits": 0, "days": set(), "authors": set(),
            "sessions": 0, "session_days": set(), "first": stamp, "last": stamp})
        if kind == "commit":
            b["commits"] += 1
            b["days"].add(stamp[:10])
            b["authors"].add(actor or "")
        else:
            b["sessions"] += 1
            b["session_days"].add(stamp[:10])
        # `first_at`/`last_at` span ANY activity: they answer "when in this week
        # was this project touched", and a session is a touch.
        b["first"] = min(b["first"], stamp)
        b["last"] = max(b["last"], stamp)

    frozen = {(r[0], r[1]) for r in conn.execute(
        "SELECT project_id, week FROM project_week WHERE frozen_at IS NOT NULL")}
    written = skipped_partial = skipped_frozen = 0
    with conn:
        for (pid, week), b in sorted(buckets.items()):
            monday = date.fromisoformat(b["week_start"])
            if monday < cutoff:
                # The window starts inside this week, so the count would be a
                # fraction of the truth with nothing saying so.
                skipped_partial += 1
                continue
            if (pid, week) in frozen:
                skipped_frozen += 1
                continue
            conn.execute(
                "INSERT INTO project_week (project_id, week, week_start, commits,"
                " active_days, authors, sessions, session_days, worked_days,"
                " first_at, last_at, computed_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(project_id, week) DO UPDATE SET"
                "   commits=excluded.commits, active_days=excluded.active_days,"
                "   authors=excluded.authors, sessions=excluded.sessions,"
                "   session_days=excluded.session_days,"
                "   worked_days=excluded.worked_days, first_at=excluded.first_at,"
                "   last_at=excluded.last_at, computed_at=excluded.computed_at"
                " WHERE project_week.frozen_at IS NULL",
                (pid, week, b["week_start"], b["commits"], len(b["days"]),
                 len(b["authors"]), b["sessions"], len(b["session_days"]),
                 # A SET UNION, not a sum. Two commits and one session on the
                 # same Tuesday is one day worked, and `active_days +
                 # session_days` would say two — which is why the union is
                 # stored rather than left to a reader who cannot compute it.
                 len(b["days"] | b["session_days"]),
                 b["first"], b["last"], now_iso()))
            written += 1

        # THE ROWS THE FOLD SUPERSEDED, and only those. A week now counted
        # under the project's current id must not also sit under its former one,
        # or every aggregate reader counts it twice.
        #
        # GUARDED BY THE COUNTERPART'S EXISTENCE. Deleting a row whose week has
        # NOT been recomputed under the new id would lose it — a frozen row
        # whose events retention has since pruned holds numbers nothing can
        # reproduce. Those are kept and counted, so the gap is a number rather
        # than a silent loss.
        superseded = kept_unfolded = 0
        for old, new in sorted(former.items()):
            for (week,) in conn.execute(
                    "SELECT week FROM project_week WHERE project_id = ?", (old,)).fetchall():
                if conn.execute("SELECT 1 FROM project_week WHERE project_id = ?"
                                " AND week = ?", (new, week)).fetchone():
                    conn.execute("DELETE FROM project_week WHERE project_id = ?"
                                 " AND week = ?", (old, week))
                    superseded += 1
                else:
                    kept_unfolded += 1

        # Freeze what the window has left behind. This is what makes the table
        # outlive its source: after this, no recompute can zero these rows.
        froze = conn.execute(
            "UPDATE project_week SET frozen_at = ?"
            " WHERE frozen_at IS NULL AND week_start < ?",
            (now_iso(), cutoff.isoformat())).rowcount
    # A FROZEN ROW WITH NO SESSION FIGURE can never be completed: the freeze rule
    # forbids rewriting it and the events under it are gone. Counted here so the
    # gap is a number a reader can see rather than a silent NULL. Zero on this
    # machine when the columns shipped, which is the only reason none was lost.
    unfillable = conn.execute(
        "SELECT count(*) FROM project_week"
        " WHERE frozen_at IS NOT NULL AND sessions IS NULL").fetchone()[0]
    return {"weeks_written": written, "weeks_frozen_now": froze,
            "already_frozen": skipped_frozen, "partial_weeks_skipped": skipped_partial,
            "frozen_without_sessions": unfillable,
            # NAMED, not folded into `weeks_written`. A rename that moves rows is
            # a fact about the estate, and a row KEPT because its week could not
            # be recomputed is the one number a reader would want and never get.
            "weeks_superseded_by_rename": superseded,
            "weeks_kept_unfolded": kept_unfolded,
            "window_days": window_days(), "cutoff": cutoff.isoformat()}


def status(conn: sqlite3.Connection) -> str:
    total, frozen = conn.execute(
        "SELECT COUNT(*), COUNT(frozen_at) FROM project_week").fetchone()
    # `COUNT(sessions)` counts non-NULL, so this is "rows that carry the
    # measure" — and the difference from `total` is rows that predate it. Two
    # numbers rather than a sum, because a NULL and a zero mean different things
    # and one line reporting "0 sessions" over both would erase that.
    measured = conn.execute("SELECT COUNT(sessions) FROM project_week").fetchone()[0]
    worked_only = conn.execute(
        "SELECT COUNT(*) FROM project_week WHERE commits = 0 AND sessions > 0").fetchone()[0]
    span = conn.execute(
        "SELECT MIN(week_start), MAX(week_start) FROM project_week").fetchone()
    projects = conn.execute("SELECT COUNT(DISTINCT project_id) FROM project_week").fetchone()[0]
    top = conn.execute(
        "SELECT project_id, SUM(commits) c FROM project_week GROUP BY project_id"
        " ORDER BY c DESC LIMIT 5").fetchall()
    out = [f"{total} weekly row(s) across {projects} project(s); {frozen} frozen",
           f"span {span[0]} .. {span[1]}",
           f"{measured} row(s) carry a session figure"
           + (f", {total - measured} predate it" if total - measured else "")
           + f"; {worked_only} week(s) held work with no commit"]
    out += [f"  {r[1]:6}  {r[0]}" for r in top]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", nargs="?", default="refresh", choices=["refresh", "status"])
    a = ap.parse_args()
    conn = store_db.connect()
    if a.action == "status":
        print(status(conn))
        return 0
    r = refresh(conn)
    # THE NUMBERS OUTLIVE THE RUN. `partial_weeks_skipped` counts weeks whose
    # data will never be captured, and it lived on stdout only — piped by the
    # tick into a log nothing reads on a schedule. A month of zero writes, or a
    # rising skip count, looked exactly like a healthy rollup.
    try:
        paths.SCRATCH.mkdir(parents=True, exist_ok=True)
        (paths.SCRATCH / "rollup.json").write_text(
            json.dumps({"ran_at": now_iso(), **r}, indent=1), encoding="utf-8")
    except OSError as exc:
        print(f"could not write the rollup receipt: {exc}", file=sys.stderr)
    print(f"rollup: {r['weeks_written']} week(s) written, {r['weeks_frozen_now']} newly frozen, "
          f"{r['already_frozen']} already frozen, {r['partial_weeks_skipped']} partial week(s) "
          f"skipped (window {r['window_days']}d, cutoff {r['cutoff']})")
    if r.get("weeks_superseded_by_rename") or r.get("weeks_kept_unfolded"):
        print(f"  {r['weeks_superseded_by_rename']} week(s) moved to a project's "
              f"current id after a rename; {r['weeks_kept_unfolded']} kept under "
              f"the former id because that week could not be recomputed")
    if r["frozen_without_sessions"]:
        print(f"  {r['frozen_without_sessions']} frozen week(s) carry no session "
              f"figure and never can — their events are gone", file=sys.stderr)
    print(status(conn))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
