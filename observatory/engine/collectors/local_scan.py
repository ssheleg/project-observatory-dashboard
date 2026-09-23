#!/usr/bin/env python3
"""Read and write `local.json`, in one place, accepting both of its shapes.

The filesystem scan is the base collector: `merge.py`, `scan_remotes.py` and
`scan_bitbucket.py` all start from its output, so it is the one file whose shape
cannot be changed carelessly. It was a bare LIST of folders, which left the
collector nowhere to say what it could not read — and `sh()` returned `""`
identically for a git command that failed, one that timed out, and one that
raised, so a repository whose remote could not be read was indistinguishable
from one that has none. That is the third instance of the class after the domain
probe and the transfer check, in the collector everything
else is built on.

So the file is now an object with `folders` and `degraded`. This module reads
BOTH shapes, because a store on disk from before the change is a legitimate
input — the same reason `degradations.collector` accepts a list and an object.
A reader that crashed on the old shape would turn a shape change into an outage
half an hour long.
"""
from __future__ import annotations
import json
from pathlib import Path


def folders(path: str | Path) -> list[dict]:
    """The folder rows, whichever shape the file is in."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return doc
    return list(doc.get("folders") or [])


def degraded(path: str | Path) -> list[dict]:
    """What the scan could not read. Empty for the old shape — which is a
    truthful answer about a file that had no way to record it, not a claim that
    nothing went wrong."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return []
    return list(doc.get("degraded") or [])
