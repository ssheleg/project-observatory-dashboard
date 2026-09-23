#!/usr/bin/env python3
"""Keep more than one copy of the half of this system git cannot hold.

                                                                              
                                                                               
                                                                         
                                                                           
                                                                        
                                                                             
                                                                            
         

                                                                              
                                                                            
                                                                             
                                                

WHAT IT REFUSES TO DO. It never deletes the newest copy, and it never deletes
anything when the new backup failed — a rotation that prunes before it proves
the replacement exists is how a backup set becomes empty.

    backup_store.py            take one, prune to KEEP
    backup_store.py --list     what exists, newest first
"""
from __future__ import annotations
import pathlib, sqlite3, sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths  # noqa: E402

#: Three days of daily copies. Enough to survive a corruption noticed the next
#: morning; not so many that a 24 MB file becomes a gigabyte nobody notices.
KEEP = 3
PREFIX = "observatory.db.backup-"


#: SQLite writes these beside a database, and they are not backups. The first
#: version of this file globbed `PREFIX + "*"` and counted them: one real copy
#: read as three, so the rotation believed it was over the limit and deleted the
#: only other backup on the machine. Caught by running it once.
COMPANIONS = ("-wal", "-shm", "-journal")


def existing(store: pathlib.Path) -> list[pathlib.Path]:
    """Newest first, and BACKUPS only — never the files SQLite writes beside one."""
    return sorted((p for p in store.glob(PREFIX + "*")
                   if not p.name.endswith(COMPANIONS)), reverse=True)


def take(db: pathlib.Path, stamp: str) -> pathlib.Path:
    dest = db.parent / f"{PREFIX}{stamp}"
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    return dest


def main(argv: list[str]) -> int:
    db = paths.DB
    store = db.parent
    if "--list" in argv:
        rows = existing(store)
        if not rows:
            print("no backup exists — the store's history lives on one disk in one file")
            return 0
        for p in rows:
            print(f"  {p.name}  {p.stat().st_size / 1e6:.1f} MB")
        return 0
    if not db.is_file():
        # Nothing to copy is not a failure: a fresh clone has no store, and a
        # backup step that fails there would make the tick red on a machine
        # where nothing is wrong.
        print("no store to back up", file=sys.stderr)
        return 0
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    # SAME STAMP, SAME DAY: a second run inside one minute would otherwise take
    # a second copy and push a good one out of the window.
    if (store / f"{PREFIX}{stamp}").exists():
        print(f"backup {stamp} already exists")
        return 0
    dest = take(db, stamp)
    size = dest.stat().st_size
    if size == 0:
        dest.unlink()
        print("the backup came out empty and was removed; nothing was pruned",
              file=sys.stderr)
        return 1
    # PRUNE ONLY AFTER THE NEW ONE IS PROVEN. Its size is read above, so the
    # replacement exists before anything is removed.
    dropped = []
    for old in existing(store)[KEEP:]:
        # `-wal` and `-shm` beside an old copy are its own, and leaving them
        # behind is how a directory fills with orphans.
        for suffix in ("",) + COMPANIONS:
            companion = old.with_name(old.name + suffix)
            if companion.exists():
                companion.unlink()
        dropped.append(old.name)
    print(f"backup {dest.name}: {size / 1e6:.1f} MB, "
          f"{len(existing(store))} kept" + (f", pruned {len(dropped)}" if dropped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
