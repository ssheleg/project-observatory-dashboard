#!/usr/bin/env python3
"""Read a registry document, or say why not. One rule, every collector.

**An unreadable registry is a fact about the RUN; an empty one is a fact about
the estate.** Every collector here reads `projects.json`, `repositories.json` and
`relations.json` with a bare `json.loads(...read_text())["projects"]`, so a
truncated file, a permission error or a missing document was a TRACEBACK — and a
traceback out of a scheduled collector is a failure whose only record is a log
nobody reads on a schedule.

Degrading to `{}` would be worse than the traceback, and that is why this module
exists rather than a `try: … except: return []` at each call site:

* `compute_deltas` fingerprinting an unreadable registry as `{}` makes every
  project look DISAPPEARED, and the next diff hands the agent one
  `project-disappeared` delta per project — its most expensive input, and
  entirely fictional.
* `scan_events` reading no repositories records no commits, so the estate's
  activity dates freeze and every project drifts toward "inactive" — which is
  what the dashboard shows and what an archive proposal is built on.

So the rule is: raise a NAMED exception carrying the reason, and let each caller
decide whether its work can proceed without that document. What none of them may
do is proceed as though the answer were "nothing".
"""
from __future__ import annotations
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths


class RegistryUnreadable(Exception):
    """The document could not be read. Carries the reason, which the caller
    reports — never an empty result standing in for a partial one (AGENTS.md
    rule 7)."""


def read(name: str, key: str) -> list:
    """The `key` list out of `registry/<name>`, or raise with the reason."""
    f = paths.REGISTRY / name
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RegistryUnreadable(f"{name} does not exist at {f}")
    except (ValueError, OSError) as exc:
        raise RegistryUnreadable(f"{name} could not be read: {type(exc).__name__}: {exc}")
    if not isinstance(doc, dict) or not isinstance(doc.get(key), list):
        raise RegistryUnreadable(f"{name} has no `{key}` list")
    return doc[key]
