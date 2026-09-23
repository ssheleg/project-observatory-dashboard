#!/usr/bin/env python3
"""Sweep the test fixtures this project leaves when a process is killed.

**Measured 2026-09-07, and it stopped the work.** The volume holding this
repository reached 0 bytes free mid-run — `no space left on device` out of the
gate. The cause was **13,833 `observatory-*` directories in `$TMPDIR` holding
22.3 GiB**, 11,550 of them created that day. `tests/tmp.py` registers
`shutil.rmtree` with `atexit` and it works: a suite run by hand leaks nothing,
and the whole `check` group leaks nothing. What leaks is a process that never
reaches its `atexit` handlers — killed by a harness timeout, by an out-of-space
crash, by a session ending. That is not a defect any one file carries, which is
exactly why remembering to clean up by hand was never going to hold.

**And it lied about whose fault it was.** `host.disk_low` names the largest
holders under the projects root — measured by the `disk-usage` plugin — so a
volume filled by this project's own litter in `$TMPDIR` reads as the operator's
projects being too big. That misattribution is easy to act on before anyone
counts the directories, so the sweep reports its own volume through
`fixtures.leaked` rather than letting the disk finding carry the blame.

WHAT IT WILL NOT TOUCH. Only directories matching `observatory-*` directly
inside the temp root, and only those untouched for `--older-than` hours (six by
default). A live gate run's fixtures are minutes old, so the floor is what keeps
this from deleting the working set of a concurrent run — the one way a sweeper
becomes worse than the leak it fixes.

    sweep_fixtures.py                  sweep, and write the receipt
    sweep_fixtures.py --dry-run        measure and report, remove nothing
    sweep_fixtures.py --older-than 24  raise the floor
"""
from __future__ import annotations
import argparse, os, pathlib, shutil, sys, tempfile, time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic                                                                   
import paths                                                                    

#: What the suites prefix their fixtures with (`tests/tmp.py`). A narrower glob
#: than "everything old in $TMPDIR" on purpose: this tool cleans up after THIS
#: project and must never develop an opinion about anybody else's litter.
PREFIX = "observatory-"
DEFAULT_AGE_HOURS = 6.0


def now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def subtree_bytes(d: pathlib.Path) -> tuple[int, int]:
    """(bytes, files) under `d`, counting what is readable and skipping what is
    not — a fixture whose permissions were part of a test must not stop the
    measurement of everything beside it."""
    total = files = 0
    for root, _, names in os.walk(d, onerror=lambda e: None):
        for n in names:
            files += 1
            try:
                total += os.lstat(os.path.join(root, n)).st_size
            except OSError:
                pass
    return total, files


def survey(root: pathlib.Path, older_than_h: float, now: float | None = None
           ) -> tuple[list[dict], list[dict]]:
    """(stale, fresh) — every fixture directory, split by the age floor."""
    now = time.time() if now is None else now
    stale: list[dict] = []
    fresh: list[dict] = []
    for d in sorted(root.glob(PREFIX + "*")):
        if not d.is_dir():
            continue
        try:
            age_h = (now - d.stat().st_mtime) / 3600.0
        except OSError:
            continue
        b, f = subtree_bytes(d)
        row = {"path": str(d), "age_hours": round(age_h, 2), "bytes": b, "files": f}
        (stale if age_h >= older_than_h else fresh).append(row)
    return stale, fresh


def sweep(root: pathlib.Path, older_than_h: float = DEFAULT_AGE_HOURS,
          dry_run: bool = False) -> dict:
    stale, fresh = survey(root, older_than_h)
    removed = 0
    freed = 0
    refused: list[dict] = []
    for row in stale:
        if dry_run:
            continue
        try:
            shutil.rmtree(row["path"])
        except OSError as exc:
            # NAMED, and the sweep continues. One undeletable fixture must not
            # leave the other thousands in place, and a swallowed failure here
            # would be a sweeper that reports success while the disk fills.
            refused.append({"path": row["path"],
                            "reason": f"{type(exc).__name__}: {exc}"})
            continue
        removed += 1
        freed += row["bytes"]
    return {
        "ran_at": now_z(), "root": str(root), "older_than_hours": older_than_h,
        "dry_run": dry_run,
        "stale": len(stale), "fresh_kept": len(fresh),
        "removed": removed, "freed_bytes": freed,
        "stale_bytes": sum(r["bytes"] for r in stale),
        "fresh_bytes": sum(r["bytes"] for r in fresh),
        "refused": refused,
        # The largest few, so a receipt read later says which suites litter
        # without carrying thousands of rows into a committed document.
        "largest": sorted(stale, key=lambda r: -r["bytes"])[:5],
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and report, remove nothing")
    ap.add_argument("--older-than", type=float, default=DEFAULT_AGE_HOURS,
                    metavar="HOURS", help=f"age floor (default {DEFAULT_AGE_HOURS})")
    ap.add_argument("--root", default=None,
                    help="temp root to sweep (default: the system temp dir)")
    args = ap.parse_args(argv[1:])

    root = pathlib.Path(args.root) if args.root else pathlib.Path(tempfile.gettempdir())
    if not root.is_dir():
        print(f"sweep_fixtures: {root} is not a directory", file=sys.stderr)
        return 1

    rep = sweep(root, args.older_than, args.dry_run)
    try:
        atomic.write_json(paths.SCRATCH / "fixtures.json", rep)
    except Exception as exc:                                                      
        print(f"the receipt could not be written: {type(exc).__name__}: {exc}",
              file=sys.stderr)

    gib = rep["freed_bytes"] / 1024 ** 3
    stale_gib = rep["stale_bytes"] / 1024 ** 3
    if args.dry_run:
        print(f"{rep['stale']} stale fixture dir(s), {stale_gib:.2f} GiB — "
              f"would remove; {rep['fresh_kept']} newer than "
              f"{args.older_than}h kept")
    else:
        print(f"removed {rep['removed']} of {rep['stale']} stale fixture dir(s), "
              f"freed {gib:.2f} GiB; {rep['fresh_kept']} newer than "
              f"{args.older_than}h kept")
    for r in rep["refused"]:
        print(f"  refused {r['path']}: {r['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    import configuration
    if ("--apply" in sys.argv) and not configuration.enabled("fixture_cleanup", "features"):
        print("Not configured: enable features.fixture_cleanup explicitly")
        raise SystemExit(0)

    raise SystemExit(main(sys.argv))
