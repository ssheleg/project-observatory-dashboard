#!/usr/bin/env python3
""                                                

                                                                             
                                                                                
                                                                       
                                                                                  
                                                                     

                                                                          
                                                                              
                                                                                
                                                                      
                                                  

                                                                              
   
from __future__ import annotations

#: Named by name up to this many, as everywhere else on this board.
LISTED = 6
#: A scan older than this is stale enough that the page should say so. Analytics
#: settle daily and the scan is gated to twice a day, so three days means the
#: tick has not run, not that Google was quiet.
STALE_DAYS = 3


def _listed(items: list[str]) -> str:
    shown = items[:LISTED]
    rest = len(items) - len(shown)
    return ", ".join(shown) + (f" and {rest} more" if rest > 0 else "")


def findings(doc: dict | None, today: str = "") -> list[dict]:
    if not doc:
        return []
    props = doc.get("properties") or []
    if not props:
        return []
    out: list[dict] = []

    # ── properties nothing here claims ──────────────────────────────────────
    unclaimed = [p for p in props if p.get("standing") == "unclaimed"]
    if unclaimed:
        unclaimed.sort(key=lambda p: -(p.get("users_30d") or 0))
        users = sum(p.get("users_30d") or 0 for p in unclaimed)
        named = _listed([f"{p['name']} ({(p.get('users_30d') or 0):,})" for p in unclaimed])
        out.append({
            "type": "analytics.property_unclaimed",
            "subject": "estate:analytics",
            "severity": "info",
            "title": (f"{len(unclaimed)} analytics propert{'y' if len(unclaimed) == 1 else 'ies'} "
                      f"carrying {users:,} user(s) in 30 days belong to no project here"),
            "detail": (f"Worst first: {named}. A property is joined to a project by what "
                       f"it declares about itself — a web stream's host through the "
                       f"registry, an app stream's bundle id, its own name — and these "
                       f"matched none. By the operator's estate rule that means somebody "
                       f"else runs them or they are not being worked on; the point of the "
                       f"row is that the biggest number in this estate should not be the "
                       f"one nothing claims."),
            "action": ("name the project in plugins/config/ga4_properties.json, or say "
                       "the host is somebody else's in collectors/host_boundary.json — "
                       "either answer silences this row"),
        })

    # ── a property that would not report ────────────────────────────────────
    broken = [p["name"] for p in props if p.get("error")]
    if broken:
        out.append({
            "type": "analytics.property_unreadable",
            "subject": "estate:analytics",
            "severity": "warning",
            "title": f"{len(broken)} analytics propert{'y' if len(broken) == 1 else 'ies'} would not report",
            "detail": (f"{_listed(sorted(broken))}. Their traffic is unknown here, which "
                       f"is not the same as zero — nothing on this board should be read "
                       f"as saying they are quiet."),
            "action": "check the service account's access to them in the Analytics admin",
        })

    # ── a credential that cannot reach a surface at all ─────────────────────
    for d in doc.get("degraded") or []:
        if "accessNotConfigured" in str(d.get("reason", "")) or "has not been used in project" in str(d.get("reason", "")):
            out.append({
                "type": "analytics.api_disabled",
                "subject": f"credential:{d.get('source', 'google')}",
                "severity": "info",
                "title": f"a Google API is switched off for {d.get('source', 'a credential')}",
                "detail": (f"{str(d.get('reason'))[:240]} — the credential has the rights "
                           f"and the API is not enabled in its Cloud project, which reads "
                           f"as a permission problem and is not one."),
                "action": d.get("remedy") or "enable the API in that Cloud project",
            })

    # ── the numbers are old ─────────────────────────────────────────────────
    scanned = (doc.get("scanned_on") or "")[:10]
    if today and scanned:
        import datetime
        try:
            age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(scanned)).days
        except ValueError:
            age = 0
        if age > STALE_DAYS:
            out.append({
                "type": "analytics.stale",
                "subject": "estate:analytics",
                "severity": "warning",
                "title": f"the analytics numbers are {age} day(s) old",
                "detail": (f"Measured {scanned}; the scan is gated to twice a day, so this "
                           f"means the tick has not run rather than that Google was quiet. "
                           f"Every traffic figure on the page is that old."),
                "action": "`./observatory.py google --force`, or the refresh button on the traffic page",
            })
    return out
