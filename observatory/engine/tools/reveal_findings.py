#!/usr/bin/env python3
""                                                 

                                                                               
                                                                           
                                                                          
                                                                            
                                                                         
                                                                         
                                                                              
                                                                              
                                                                           
                                                                          

                                                      

                                                                                
                                                                        
                                                                           
                                                                            
                                                                          

                                                                             
                                                                         
                                                                  
   
from __future__ import annotations
import collections
import datetime
import json
import pathlib

                                                                            
                                                                           
                                                                     
BURST = 6
WINDOW_HOURS = 24
LISTED = 4


def read_journal(path: pathlib.Path) -> tuple[list[dict], str | None]:
    ""                                                                       
                                                                    
    if not path.is_file():
        return [], None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], f"{type(exc).__name__}: {exc}"
    rows = []
    bad = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            bad += 1
    return rows, (f"{bad} unparseable line(s)" if bad else None)


def _when(row: dict) -> datetime.datetime | None:
    try:
        return datetime.datetime.strptime(row.get("at", ""), "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def findings(journal: pathlib.Path, now: datetime.datetime | None = None) -> list[dict]:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    rows, problem = read_journal(journal)
    out: list[dict] = []
    if problem:
        out.append({
            "type": "secret.journal_unreadable",
            "subject": "estate:keyserver-journal",
            "severity": "warning",
            "title": "the keyserver's audit journal could not be read whole",
            "detail": (f"{journal.name}: {problem}. Every row in it is a reveal, mint, "
                       f"limit or revoke somebody made; a journal the board cannot read "
                       f"is a record nobody can answer from."),
            "action": "read the file by hand; a line that is not JSON was written by something other than keyserver.audit()",
        })
    since = now - datetime.timedelta(hours=WINDOW_HOURS)
    recent = [r for r in rows if r.get("action") == "reveal"
              and (w := _when(r)) is not None and w >= since]
    by_subject: dict[str, list[dict]] = collections.defaultdict(list)
    for r in recent:
        by_subject[str(r.get("subject") or "?")].append(r)
    for subject, hits in sorted(by_subject.items(), key=lambda kv: -len(kv[1])):
        if len(hits) < BURST:
            continue
        callers = collections.Counter(str(h.get("caller") or "unnamed") for h in hits)
        first, last = min(_when(h) for h in hits), max(_when(h) for h in hits)
        who = ", ".join(f"{c} ×{n}" for c, n in callers.most_common(LISTED))
        out.append({
            "type": "secret.reveal_burst",
            "subject": f"reveal:{subject}",
            "severity": "warning",
            "title": (f"{subject} was revealed {len(hits)} times in {WINDOW_HOURS} hours"),
            "detail": (f"Between {first:%Y-%m-%d %H:%M}Z and {last:%H:%M}Z, by {who}. A "
                       f"person opening a page reveals a variable once; a caller that "
                       f"re-reads one name this often is a loop that never kept the value "
                       f"by name (handling-secrets rule 2), or a caller nobody here "
                       f"started. The value itself is in none of this."),
            "action": ("find the caller — a named one is a session id or a page; an "
                       "`unnamed` one predates the caller header, so update its skill copy — "
                       "and make it keep the value by name after the first read"),
        })
    unnamed = [r for r in recent if str(r.get("caller") or "unnamed") == "unnamed"
               and "caller" in r]
    if unnamed:
        subjects = sorted({str(r.get("subject")) for r in unnamed})
        out.append({
            "type": "secret.reveal_unnamed",
            "subject": "estate:keyserver-callers",
            "severity": "info",
            "title": f"{len(unnamed)} reveal(s) in {WINDOW_HOURS} hours came from a caller that did not name itself",
            "detail": (f"Subjects: {', '.join(subjects[:LISTED])}"
                       f"{' and more' if len(subjects) > LISTED else ''}. The header "
                       f"`X-Observatory-Caller` exists since DEC-0242; a reveal without it "
                       f"is a skill copy or a script older than that, and the journal can "
                       f"say only that it was somebody on this machine."),
            "action": "update the installed `handling-secrets` copy; the dashboard names itself already",
        })
    return out
