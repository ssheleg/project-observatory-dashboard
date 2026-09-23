#!/usr/bin/env python3
"""Google Search Console: clicks and impressions per property, per project.

Auth is a SERVICE ACCOUNT, not OAuth: OAuth needs a browser and a human every
ninety days, a service account is a JSON key that signs its own JWTs — the only
Google auth shape that survives a launchd tick. Setup, once:

                                                                 
                                                        
                                                                                            
                                                                            
                                                                            

Until step 2 the manifest keeps this plugin `waiting`. Properties the account
can see but the registry cannot attribute are reported on stderr, unmapped —
the same contract as the Cloudflare plugin.

The window is the last complete UTC day, lagged by three: GSC data firms up
about 48h behind, and a number that will be revised is worse than a number a
day late (the same reasoning the tick applies to frozen weeks).
"""
from __future__ import annotations
import datetime
import json
import pathlib
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths                                            
import google_auth                                                              
import hostmap                                                                  

                                                                              
                                                                                
                                                                              
                                                                             
                                                             
KEY_FILE = paths.source_path("secret_store", paths.SECRETS) / 'google-gsc-service-account.json'
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def token() -> str:
    """A bearer token for this plugin's scope.

    Through `plugins/google_auth.py`, which does the JWT exchange over the
    standard library: the documented `google.auth.transport.requests.Request`
    needs `requests`, and a launchd tick would have reported that as a broken
    plugin (measured 2026-09-12).
    """
    return google_auth.access_token(KEY_FILE, SCOPE)


def _call(url: str, tok: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        url, method="POST" if payload else "GET",
        data=json.dumps(payload).encode("utf-8") if payload else None,
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        # Status and url only — a header in an error message is how this
        # repository leaked a credential on 2026-09-12.
        raise RuntimeError(f"gsc answered {e.code} for {url.split('?')[0]}") from None
    except OSError as e:
        raise RuntimeError(f"gsc unreachable: {type(e).__name__}") from None


def properties(tok: str) -> list[str]:
    d = _call("https://www.googleapis.com/webmasters/v3/sites", tok)
    return [s["siteUrl"] for s in d.get("siteEntry", [])
            if s.get("permissionLevel") not in ("siteUnverifiedUser",)]


def host_of(site_url: str) -> str:
    """`sc-domain:example.com` and `https://example.com/` both -> example.com."""
    if site_url.startswith("sc-domain:"):
        return site_url[len("sc-domain:"):]
    return site_url.split("//", 1)[-1].strip("/")


def day_lagged(today: datetime.date | None = None, lag: int = 3) -> str:
    t = today or datetime.datetime.now(datetime.timezone.utc).date()
    return (t - datetime.timedelta(days=lag)).isoformat()


def fetch_day(tok: str, site_url: str, day: str) -> dict:
    from urllib.parse import quote
    d = _call("https://www.googleapis.com/webmasters/v3/sites/"
              f"{quote(site_url, safe='')}/searchAnalytics/query", tok,
              {"startDate": day, "endDate": day})
    row = (d.get("rows") or [{}])[0]
    return {"clicks": row.get("clicks", 0), "impressions": row.get("impressions", 0)}


def rows_from(per_site: dict[str, dict], day: str,
              table: dict[str, str]) -> tuple[list[dict], list[str]]:
    """(metric rows, unmapped site urls) — pure, testable without Google."""
    rows, unmapped = [], []
    at = f"{day}T00:00:00Z"
    for site_url, stats in sorted(per_site.items()):
        pid = hostmap.resolve(host_of(site_url), table)
        if pid is None:
            unmapped.append(site_url)
            continue
        rows.append({"project_id": pid, "metric": "search.clicks_1d", "at": at,
                     "value": stats["clicks"], "unit": "clicks",
                     "payload": {"property": site_url}})
        rows.append({"project_id": pid, "metric": "search.impressions_1d", "at": at,
                     "value": stats["impressions"], "unit": "impressions",
                     "payload": {"property": site_url}})
    return rows, unmapped


def main() -> int:
    import configuration
    if not configuration.enabled("search_console"):
        print("integration search_console disabled", file=sys.stderr)
        return 0
    tok = token()
    sites = properties(tok)
    if not sites:
        print("the service account sees no Search Console properties — add its "
              "client_email as a user on each property", file=sys.stderr)
        return 0
    day = day_lagged()
    per_site = {s: fetch_day(tok, s, day) for s in sites}
    rows, unmapped = rows_from(per_site, day, hostmap.build())
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    if unmapped:
        print(f"unmapped properties ({len(unmapped)}): {', '.join(unmapped)} — "
              f"outside the estate's projects; adopt only when work begins here",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
