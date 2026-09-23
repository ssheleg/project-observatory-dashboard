#!/usr/bin/env python3
"""What a collector said about its own coverage, read the same way everywhere.

AGENTS.md rule 7: a source that could not be read appears in `degraded` with its
reason, and never as an empty result in place of a partial one. Every collector
writes that list; this is the one function that reads it.

It lives here rather than in `survey.py` because it now has two callers, and the
last time a rule about collector output existed in two places the two disagreed:
`survey` expected an object with a `degraded` key while `scan_github` wrote a
bare list, so the largest source in the estate could fail on every owner and no
survey, dashboard or finding would mention it. Both shapes are accepted below,
in one place, so a third caller cannot pick the wrong half.

Absent and empty are deliberately DIFFERENT claims. A missing file means "this
collector has not run", and a caller that reports it as "measured and fine" has
turned silence into a clean bill of health — the exact substitution the whole
degradation channel exists to prevent.
"""
from __future__ import annotations
import json

import paths


def collector(name: str) -> list[dict]:
    """The `degraded` rows a collector wrote, or [] if it never ran.

    `name` is relative to the scratch directory — `"bitbucket.json"`,
    `"gh/_degraded.json"`, `"model.json"`. Resolved through `paths.SCRATCH` so a
    fixture can redirect it; a hardcoded `store/raw` was the third instance of
    that class in one sitting and `tools/check_paths.py` now refuses it.
    """
    f = paths.SCRATCH / name
    if not f.is_file():
        return []
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # An unreadable file is a measurement in its own right, and the loudest
        # kind: it means a collector wrote something nothing can parse.
        return [{"source": name, "reason": "collector output is unreadable"}]
    if isinstance(doc, list):
        return list(doc)
    return list(doc.get("degraded") or [])

                                                                              
                                                                            
                                                                               
                                                                             
                                                                             
         
OWN_READER = {
    "model.json": "tools/build_findings.py builds `model.degraded` with the "
                  "remedy for a `gh` failure and its own deduplication",
}


def every_collector() -> dict[str, list[dict]]:
    """Every receipt in the scratch that carries a `degraded` list, DERIVED.

                                                                              
                                                                               
                                                                              
                                                                            
                                                                            
                                                                         
                                                                            
                                                           

    Derived from the directory rather than listed, so a collector added tomorrow
    is surfaced by default and skipping one takes a sentence in `OWN_READER`.
    """
    out: dict[str, list[dict]] = {}
    if not paths.SCRATCH.is_dir():
        return out
    for f in sorted(paths.SCRATCH.glob("*.json")):
        if f.name in OWN_READER:
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            out[f.name] = [{"source": f.name,
                            "reason": "collector output is unreadable"}]
            continue
        # A `degraded` KEY is the contract. A receipt without one is not a
        # collector report — `tick.json`, `integrity.json` and the rest — and
        # inventing an empty list for them would put every receipt in a rule
        # about collectors.
        if isinstance(doc, dict) and isinstance(doc.get("degraded"), list) and doc["degraded"]:
            out[f.name] = list(doc["degraded"])
    return out
