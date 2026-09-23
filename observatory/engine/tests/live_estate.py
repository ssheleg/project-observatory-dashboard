#!/usr/bin/env python3
"""Can the live estate answer this question at all — and if not, say so.

**Named `live_estate`, not `estate`.** The first version was `tests/estate.py`
and it SHADOWED the repository's own `estate.py` for every suite that puts
`tests/` on `sys.path` — which is most of them: `import estate` resolved here and
`test-events` died on `AttributeError: module 'estate' has no attribute
'records_events'`.

**The doctrine this repository applies everywhere else, applied to its own
suites for the first time.** `store/observatory.db` and `store/raw/` are
gitignored: a fresh clone has the registry and no store. Nine of the 114 test
steps read that state as a broken build — measured 2026-09-08 by running every
step with `OBSERVATORY_DB` pointed at a file that does not exist:

    test-plugins       "it produced a measurement per project with folders — 0"
    test-hook          "the deepest holds 0 revision(s)"
    test-project-surface  "there are events to look at" — against a payload
                       whose own `degraded` said "the event store is empty"
    test-queue-order   "no ledger conclusion is waiting for a decision"
    test-residue       the same
    test-labels        "some rows carry metrics — 0"
    test-work-tiles    required tiles that `work_tiles()` documents as ABSENT
                       without a store
    test-freshness     `FileNotFoundError: …/raw/model.json`
    test-receipt       a ledger revision that does not exist yet

Every one of them reads an ABSENCE as a FAILURE — the inversion
`dashboard/build_dashboard.py` refuses in its own docstring ("`0 commits` where
the truth is 'there is no store' is the inversion this repository refuses
everywhere else"). A contributor on a fresh clone cannot tell those nine from a
real defect, which is the whole cost.

**What this is not.** It is not permission to skip. A property that CAN be driven
without the estate must be driven — `tests/test_store_faults.py` now builds its
own store rather than hoping the live outbox is non-empty — and
`covered` exists to force the question: where IS this property asserted when the
estate cannot show it? A guard with nothing to name is a hole with a comment.
"""
from __future__ import annotations
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths                                                                      


def has_store() -> bool:
    """Is there a store FILE — which is rarely the question worth asking.

    A store that does not exist is CREATED by the first read-write connect:
    sqlite makes the file and `store/migrate.py` fills it with an empty schema.
    So on any machine that has run one step this answers True while every table
    is empty, and a guard built on it does not fire. **Guard on the rows the
    assertion needs**, not on the file.
    """
    try:
        return paths.DB.is_file() and paths.DB.stat().st_size > 0
    except OSError:
        return False


def has_receipt(name: str) -> bool:
    """Is a collector's receipt present under the scratch directory?"""
    try:
        return (paths.SCRATCH / name).is_file()
    except OSError:
        return False


def needs(what: str, present: bool, covered: str) -> bool:
    """True when the estate can answer; otherwise print a NOTE and return False.

    `covered` names where the property is asserted instead — a fixture, a
    planted case, another suite. It is required rather than optional because the
    NOTE is only honest if somebody can follow it.
    """
    if present:
        return True
    print(f"  NOTE  {what} is not on this machine, so the assertions below were "
          f"not made [covered: {covered}]")
    return False
