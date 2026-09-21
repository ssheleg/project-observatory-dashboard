""                                                                              
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import sqlite3
import tempfile
import time


def readonly_uri(target: Path) -> str:
    ""                                                                           

                                                                              
                                                                             
       
    wal = Path(str(target) + "-wal")
    immutable = not wal.exists() or wal.stat().st_size == 0
    return target.resolve().as_uri() + "?mode=ro" + ("&immutable=1" if immutable else "")


def preflight(target: Path) -> None:
    ""                                                                             
    if not target.exists():
        return
    from store import migrate
    conn = sqlite3.connect(readonly_uri(target), uri=True)
    try:
        migrate.validate(conn)
    finally:
        conn.close()


@contextmanager
def upgrade_lock(target: Path, timeout: float = 30):
    ""                                                                          
    lock_path = target.with_name(target.name + ".upgrade.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Another Observatory process is upgrading this database")
                time.sleep(0.05)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def verify_database(conn: sqlite3.Connection) -> None:
    ""                                                                               
    import re
    schemas = [row[0] or "" for row in conn.execute("SELECT sql FROM sqlite_master WHERE type='table'")]
    if any(re.search(r"\bUSING\s+vec0\b", sql, re.IGNORECASE) for sql in schemas):
        try:
            import sqlite_vec
        except ImportError:
            raise RuntimeError("This snapshot contains vector tables; install the locked sqlite-vec dependency") from None
        if not callable(getattr(conn, "enable_load_extension", None)):
            raise RuntimeError("Vector snapshots require Python SQLite loadable extension support; use an extension-enabled Python build")
        conn.enable_load_extension(True)
        try:
            sqlite_vec.load(conn)
        finally:
            conn.enable_load_extension(False)
    rows = conn.execute("PRAGMA integrity_check").fetchall()
    if len(rows) != 1 or rows[0][0] != "ok":
        raise RuntimeError("Database snapshot integrity verification failed")


def backup(conn: sqlite3.Connection, target: Path) -> Path:
    ""                                                                                
    directory = target.parent / "migration-backups"
    if directory.is_symlink():
        raise RuntimeError("Migration backup directory must not be a symbolic link")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    fd, name = tempfile.mkstemp(prefix=target.name + ".before-upgrade-", suffix=".db", dir=directory)
    os.close(fd)
    dest = Path(name)
    try:
        out = sqlite3.connect(dest)
        try:
            conn.backup(out)
            verify_database(out)
        finally:
            out.close()
        dest.chmod(0o600)
        return dest
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
