#!/usr/bin/env python3
""                                                                   

                                                                              
                                                                               
                                                                            

                                                                         
                                                                              
                                                                           
                                                                             
                                                                    

                                             

                                                                          
                                                                                
                                                                           
                            

                                                                         
                                                                        
                                                                           
                                                                           
                                                                              
   
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
import hostmap                                                                  

#: THREE ACCOUNTS, not one. The operator holds zones under several Cloudflare
#: logins and issued a token per account; a single-token plugin would measure
#: whichever account happened to be first and report the rest as absent — which
#: looks exactly like zero traffic. Every file in this directory is a token, and
#: `tools/add_cloudflare_token.py` is what puts one there, named by the account
#: Cloudflare itself reports.
TOKEN_DIR = paths.source_path("secret_store", paths.SECRETS) / 'cloudflare-analytics.d'
API = "https://api.cloudflare.com/client/v4"


def tokens() -> list[tuple[str, str]]:
    ""                                                              
    out = []
    if TOKEN_DIR.is_dir():
        for p in sorted(TOKEN_DIR.iterdir()):
            # A `.meta.json` is the RECORD of a token, not a token. On
            # 2026-09-13 the first issued token's record was read here and sent
            # as a bearer value; it held no secret, and the header-echoing
            # ValueError that followed is exactly the shape of the 09-12 leak.
            if (p.is_file() and not p.name.startswith(".")
                    and not p.name.endswith(".meta.json")):
                v = p.read_text(encoding="utf-8").strip()
                if v and "\n" not in v:
                    out.append((p.name, v))
    return out


def _call(path_or_query, token: str, graphql: bool = False) -> dict:
    ""                                                                         
    if graphql:
        req = urllib.request.Request(
            f"{API}/graphql", method="POST",
            data=json.dumps(path_or_query).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"})
        url = f"{API}/graphql"
    else:
        url = f"{API}{path_or_query}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except ValueError:
        # http.client refuses a header with a newline by raising with the
        # HEADER VALUE in the message — the token. Never let that message out.
        raise RuntimeError("token value is not header-safe (contains a line "
                           "break) — the file is not a token") from None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = json.loads(e.read()).get("errors", [{}])[0].get("message", "")[:120]
        except Exception:                                                         
            pass
        raise RuntimeError(f"cloudflare answered {e.code} for {url}: {body}") from None
    except OSError as e:
        raise RuntimeError(f"cloudflare unreachable: {type(e).__name__}") from None


def zones(token: str) -> list[dict]:
    out, page = [], 1
    while True:
        d = _call(f"/zones?per_page=50&page={page}", token)
        out += [{"id": z["id"], "name": z["name"]} for z in d.get("result", [])]
        info = d.get("result_info") or {}
        if page >= (info.get("total_pages") or 1):
            return out
        page += 1


def day_bounds(today: datetime.date | None = None) -> tuple[str, str]:
    ""                                                                        
    t = today or datetime.datetime.now(datetime.timezone.utc).date()
    y = t - datetime.timedelta(days=1)
    return y.isoformat(), y.isoformat()


#: Cloudflare's GraphQL answers `too many zones requested` above ten in one
#: `zoneTag_in` — measured 2026-09-13 against the operator's 34- and 53-zone
#: accounts, which reported zero traffic for exactly that reason.
ZONES_PER_QUERY = 10


def fetch_day(token: str, zone_ids: list[str], day: str) -> dict[str, dict]:
    ""                                                                          
    out: dict[str, dict] = {}
    for i in range(0, len(zone_ids), ZONES_PER_QUERY):
        out.update(_fetch_batch(token, zone_ids[i:i + ZONES_PER_QUERY], day))
    return out


def _fetch_batch(token: str, zone_ids: list[str], day: str) -> dict[str, dict]:
    q = {"query": """
      query($zones: [String!], $day: Date!) {
        viewer { zones(filter: {zoneTag_in: $zones}) {
          zoneTag
          httpRequests1dGroups(limit: 1, filter: {date: $day}) {
            sum { requests pageViews }
            uniq { uniques }
          }
        } }
      }""", "variables": {"zones": zone_ids, "day": day}}
    d = _call(q, token, graphql=True)
    if d.get("errors"):
        raise RuntimeError("cloudflare graphql: "
                           + "; ".join(e.get("message", "?")[:100] for e in d["errors"]))
    out = {}
    for z in (d.get("data") or {}).get("viewer", {}).get("zones", []):
        g = (z.get("httpRequests1dGroups") or [{}])
        g = g[0] if g else {}
        out[z["zoneTag"]] = {
            "requests": (g.get("sum") or {}).get("requests", 0),
            "pageviews": (g.get("sum") or {}).get("pageViews", 0),
            "uniques": (g.get("uniq") or {}).get("uniques", 0)}
    return out


def rows_from(zone_list: list[dict], per_zone: dict[str, dict], day: str,
              table: dict[str, str]) -> tuple[list[dict], list[str]]:
    ""                                                                            
    rows, unmapped = [], []
    at = f"{day}T00:00:00Z"
    for z in zone_list:
        stats = per_zone.get(z["id"])
        if stats is None:
            continue
        pid = hostmap.resolve(z["name"], table)
        if pid is None:
            # The NAME and the SIZE: 79 unmapped zones is a list nobody works
            # through; 79 ranked by yesterday's requests is a list whose top
            # five are worth an afternoon (measured 2026-09-13).
            unmapped.append({"zone": z["name"], "requests": stats["requests"]})
            continue
        rows.append({"project_id": pid, "metric": "web.requests_1d", "at": at,
                     "value": stats["requests"], "unit": "requests",
                     "payload": {"zone": z["name"]}})
        rows.append({"project_id": pid, "metric": "web.visitors_1d", "at": at,
                     "value": stats["uniques"], "unit": "visitors",
                     "payload": {"zone": z["name"]}})
    return rows, unmapped


def main() -> int:
    import configuration
    if not configuration.enabled("cloudflare_analytics"):
        print("integration cloudflare_analytics disabled", file=sys.stderr)
        return 0
    accounts = tokens()
    if not accounts:
        print("no Cloudflare token installed — "
              "run add_cloudflare_token with a protected file redirected to stdin", file=sys.stderr)
        return 0
    rows: list[dict] = []
    unmapped: dict[str, int] = {}
    notes: list[str] = []
    table = hostmap.build()
    seen_zones: set[str] = set()
    day, _ = day_bounds()
    for label, token in accounts:
        # ONE ACCOUNT'S FAILURE IS NOT THE ESTATE'S. A revoked token, a rate
        # limit or a network blip on one login must not delete the other two
        # accounts' traffic from the store — it is reported and the run goes on.
        try:
            zs = [z for z in zones(token) if z["id"] not in seen_zones]
            seen_zones.update(z["id"] for z in zs)
            if not zs:
                notes.append(f"{label}: no zone of its own")
                continue
            per_zone = fetch_day(token, [z["id"] for z in zs], day)
        except RuntimeError as exc:
            notes.append(f"{label}: {exc}")
            continue
        r, u = rows_from(zs, per_zone, day, table)
        rows += r
        for x in u:
            unmapped[x["zone"]] = max(unmapped.get(x["zone"], 0), x["requests"])
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    if unmapped:
        # NOT dropped silently: traffic on a host no project claims is a fact
        # about the registry. run_plugins keeps stderr in its receipt.
        ranked = sorted(unmapped.items(), key=lambda kv: -kv[1])
        print(f"unmapped zones ({len(unmapped)}), by yesterday's requests: "
              + ", ".join(f"{z} ({n})" for z, n in ranked[:12])
              + (" …" if len(ranked) > 12 else "")
              + " — outside the estate's projects; adopt one onto a project only "
                "when work on it begins here",
              file=sys.stderr)
    if notes:
        print("accounts that could not be read: " + "; ".join(notes), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
