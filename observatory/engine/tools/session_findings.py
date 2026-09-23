#!/usr/bin/env python3
""                                                               

                                                                          
                                                                           
                                                                         
                                                                           
                                                                            
                                                                          
                                                   
                                                                           
                                                                          
                                              

                                                                           
                                                                            
                                                                           
                                                       
   
from __future__ import annotations
import collections
import datetime
import json
import pathlib

DAYS = 14
LISTED = 6


def rows_of(path: pathlib.Path, now: datetime.datetime | None = None) -> list[dict]:
    if not path.is_file():
        return []
    now = now or datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if (r.get("at") or "") >= since and r.get("cwd"):
                out.append(r)
    except OSError:
        return []
    return out


def findings(path: pathlib.Path, known_folders: set[str], data_root: pathlib.Path,
             now: datetime.datetime | None = None) -> list[dict]:
    """`known_folders` are the estate folders the registry already joins; a
    sighting inside the estate whose folder is now known has been picked up by
    a tick since, and is not reported."""
    seen = rows_of(path, now)
    if not seen:
        return []
    by_cwd: dict[str, list[dict]] = collections.defaultdict(list)
    for r in seen:
        by_cwd[r["cwd"]].append(r)
    still: list[tuple[str, int, str | None]] = []
    for cwd, rs in by_cwd.items():
        p = pathlib.Path(cwd)
        try:
            folder = p.resolve().relative_to(data_root.resolve()).parts[0]
            if folder in known_folders:
                continue                                                    
        except (ValueError, IndexError, OSError):
            pass
        remote = next((r.get("remote") for r in rs if r.get("remote")), None)
        still.append((cwd, len({r.get("session_id") for r in rs}), remote))
    if not still:
        return []
    still.sort(key=lambda t: (-t[1], t[0]))
    total_sessions = sum(n for _c, n, _r in still)
    named = ", ".join(f"{pathlib.Path(c).name} ({n} сесс.{', ' + r if r else ''})" for c, n, r in still[:LISTED])
    more = len(still) - min(len(still), LISTED)
    return [{
        "type": "project.seen_unobserved",
        "subject": "estate:sessions-seen",
        "severity": "info",
        "title": (f"{len(still)} folder(s) agents worked in over {DAYS} days are not in the registry"),
        "detail": (f"{named}{f' and {more} more' if more > 0 else ''} — {total_sessions} session(s) in all. "
                   f"Each was where an agent was told to work and the board could show nothing "
                   f"about it: no keys by name, no findings, no history. A folder under the configured project directory "
                   f"joins on the next tick; one elsewhere joins only if it moves."),
        "action": ("move the folder under the configured project directory, or update "
                   "sources.projects; otherwise this row records a project outside the scan scope"),
    }]
