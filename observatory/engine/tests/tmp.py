#!/usr/bin/env python3
"""A temp directory that goes away, because 98 of them did not.

Every suite here builds its fixtures in `tempfile.mkdtemp()`, and `mkdtemp` is
the one that does NOT clean up — that is its whole difference from
`TemporaryDirectory`. Thirteen of the suites copy something substantial into it:
the live store is 22 MB and `test_erasure_bytes` copies it twice, the registry
and `store/raw` go in whole elsewhere.

**Measured 2026-09-07, and it is not theoretical.** One `./observatory.py check`
run took the data volume from 607 MiB free to 317 MiB — about 290 MB per run,
never returned. The volume reads 100% full, and the run before that one died with
`no space left on device` before the shell could write its own working file. A
gate that cannot run twice is not a gate.

`atexit` rather than a context manager, deliberately: the suites hold their
directories across several assertions inside one function and sometimes across
functions, so a `with` block would force every call site to be restructured, a
bigger change than the defect itself. `atexit` runs on a normal exit AND on
`SystemExit`, which is how every suite here ends, including the failing path. That
path matters most, because a failing suite is exactly the one somebody runs
again and again.

It does NOT run on SIGKILL, and that is stated rather than hidden: a killed run
leaves its directory, and `tools/check_paths.py` cannot help with that. The
remedy there is the operating system's periodic cleaner.
"""
from __future__ import annotations
import atexit
import shutil
import tempfile


def mkdtemp(prefix: str = "observatory-") -> str:
    """`tempfile.mkdtemp`, registered for removal when the process ends."""
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, ignore_errors=True)
    return path
