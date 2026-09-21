#!/usr/bin/env python3
""                                                                          

                                                                               
                                                                             
                                                                           
                                                                               
                                                                               

                                                                            
                                                                            
                                                                                
                                                                              
   
from __future__ import annotations
import importlib.util
import json
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tmp                                                            
import source_reader                                                               

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup, PROJECT_ID as SYNTHETIC_PROJECT
portable_setup()

sys.path.insert(0, str(ROOT / "plugins"))
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "plugins" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TABLE = {"catalog.example": "project:catalog",
         "chat.example": "project:chat.example",
         "notes.example": "project:notes"}


def test_hostmap_resolves_most_specific_first() -> None:
    hm = load("hostmap")
    check("an exact host resolves",
          hm.resolve("catalog.example", TABLE) == "project:catalog")
    check("www falls back to the apex",
          hm.resolve("www.chat.example", TABLE) == "project:chat.example")
    check("a deeper subdomain falls back to a claimed apex",
          hm.resolve("api.eu.catalog.example", TABLE) == "project:catalog")
    check("an unclaimed host is None, never a guess",
          hm.resolve("stranger.example", TABLE) is None)
    check("case and trailing dots do not matter",
          hm.resolve("CaTaLoG.ExAmPlE.", TABLE) == "project:catalog")
    check("and the live map builds from the registry",
          hm.build().get("example.test") == SYNTHETIC_PROJECT, "the synthetic site maps to its declared project")


def test_cloudflare_rows_attribute_and_report_unmapped() -> None:
    cf = load("cloudflare_analytics")
    zones = [{"id": "z1", "name": "catalog.example"},
             {"id": "z2", "name": "unclaimed.example"},
             {"id": "z3", "name": "www.chat.example"}]
    per_zone = {"z1": {"requests": 1200, "pageviews": 300, "uniques": 80},
                "z2": {"requests": 5, "pageviews": 5, "uniques": 1},
                "z3": {"requests": 40, "pageviews": 10, "uniques": 9}}
    rows, unmapped = cf.rows_from(zones, per_zone, "2026-09-11", TABLE)
    check("two mapped zones give four rows", len(rows) == 4, str(rows)[:200])
    check("each row lands on the OWNING project",
          {r["project_id"] for r in rows} ==
          {"project:catalog", "project:chat.example"}, str(rows)[:200])
    check("the timestamp is the closed day at midnight UTC",
          all(r["at"] == "2026-09-11T00:00:00Z" for r in rows))
    check("the zone travels in the payload for audit",
          any(r["payload"]["zone"] == "catalog.example" for r in rows))
    check("an unclaimed zone is REPORTED, not dropped — with its size, so the "
          "list can be worked from the top",
          unmapped == [{"zone": "unclaimed.example", "requests": 5}], str(unmapped))
    check("a zone the fetch did not answer for produces nothing",
          not any(r["payload"].get("zone") == "missing" for r in rows))


def test_cloudflare_asks_for_at_most_ten_zones_per_query() -> None:
    ""                                                                       
                                                                                
    cf = load("cloudflare_analytics")
    asked = []

    def fake(q, token, graphql=False):
        ids = q["variables"]["zones"]
        asked.append(len(ids))
        return {"data": {"viewer": {"zones": [
            {"zoneTag": z, "httpRequests1dGroups": [
                {"sum": {"requests": 1, "pageViews": 1}, "uniq": {"uniques": 1}}]}
            for z in ids]}}}
    cf._call = fake
    got = cf.fetch_day("t", [f"z{i}" for i in range(23)], "2026-09-12")
    check("23 zones travel in three queries", asked == [10, 10, 3], str(asked))
    check("and every zone comes back", len(got) == 23, str(len(got)))


def test_gsc_rows_speak_both_property_shapes() -> None:
    gsc = load("search_console")
    check("sc-domain properties reduce to the host",
          gsc.host_of("sc-domain:chat.example") == "chat.example")
    check("url-prefix properties reduce to the host too",
          gsc.host_of("https://catalog.example/") == "catalog.example")
    per_site = {"sc-domain:chat.example": {"clicks": 12, "impressions": 480},
                "https://nowhere.example/": {"clicks": 1, "impressions": 3}}
    rows, unmapped = gsc.rows_from(per_site, "2026-09-08", TABLE)
    check("a mapped property gives clicks and impressions rows", len(rows) == 2
          and {r["metric"] for r in rows} == {"search.clicks_1d", "search.impressions_1d"},
          str(rows)[:200])
    check("an unmapped property is reported",
          unmapped == ["https://nowhere.example/"], str(unmapped))
    check("the lagged day is used verbatim",
          all(r["at"].startswith("2026-09-08") for r in rows))
    check("and the lag exists in the fetch half",
          gsc.day_lagged(__import__("datetime").date(2026, 9, 12)) == "2026-09-09",
          "GSC revises its last ~48h; an unlagged number gets silently rewritten")


def test_ga4_rows_honour_explicit_project_over_hostmap() -> None:
    ga = load("ga4_analytics")
    mapping = [{"property": "properties/1", "host": "catalog.example"},
               {"property": "properties/2", "project": "project:pinned-analytics"},
               {"property": "properties/3", "host": "stranger.example"}]
    per_prop = {"properties/1": {"sessions": 100.0, "users": 60.0},
                "properties/2": {"sessions": 5.0, "users": 4.0},
                "properties/3": {"sessions": 1.0, "users": 1.0}}
    rows, unmapped = ga.rows_from(mapping, per_prop, "2026-09-11", TABLE)
    check("a host-mapped and a pinned property both attribute", len(rows) == 4,
          str(rows)[:200])
    check("the explicit project wins without consulting the map",
          any(r["project_id"] == "project:pinned-analytics" for r in rows))
    check("a property with neither resolvable host nor project is reported",
          unmapped == ["properties/3"], str(unmapped))


def test_every_http_error_is_sanitised() -> None:
    ""                                                                            
    for name in ("cloudflare_analytics", "search_console", "ga4_analytics"):
        src = (ROOT / "plugins" / f"{name}.py").read_text(encoding="utf-8")
        check(f"{name} re-raises HTTP errors without headers",
              "from None" in src and "e.headers" not in src, name)
        check(f"{name} says why, beside the raise",
              "leak" in src or "header" in src.lower(),
              "the reason must travel with the rule")


def test_the_token_exchange_needs_no_third_party_transport() -> None:
    ""                                                                     

                                                                               
                                                                             
                                                                              
                                                                                
                         
       
    ga = load("google_auth")
    src = (ROOT / "plugins/google_auth.py").read_text(encoding="utf-8")
    code0 = source_reader.code_only(src)
    check("no transport from the requests family is imported",
          "transport.requests" not in code0 and "import requests" not in code0,
          "the documented transport pulls in `requests`, which this venv "
          "does not have and a launchd tick would report as a broken plugin")
                                                                           
                                                                            
                                                                      
                                           
    check("and the assertion never reaches an error message",
          "assertion" not in code0.split("except urllib.error.HTTPError")[1],
          "a signed assertion echoed into an exception is a credential in a log")
    missing = pathlib.Path(tmp.mkdtemp()) / "absent.json"
    try:
        ga.access_token(missing, "scope")
        check("an absent key file raises rather than returning ''", False, "no raise")
    except RuntimeError as exc:
        check("an absent key file says so", "unreadable" in str(exc), str(exc))
    half = pathlib.Path(tmp.mkdtemp()) / "half.json"
    half.write_text(json.dumps({"client_email": "a@b.c"}), encoding="utf-8")
    try:
        ga.access_token(half, "scope")
        check("a key file with no private_key raises", False, "no raise")
    except RuntimeError as exc:
        check("a key file with no private_key names the field",
              "private_key" in str(exc), str(exc))
                                                                               
                                                               
    ga._CACHE[("K", "S")] = ("cached-token", 1e12)
    check("a live cache entry is returned without any exchange",
          ga.access_token(pathlib.Path("K"), "S", now=0) == "cached-token")
    ga._CACHE[("K2", "S")] = ("stale", 10)
    try:
        ga.access_token(pathlib.Path("K2"), "S", now=1e11)
        check("an expired entry is not served", False, "returned the stale token")
    except RuntimeError:
        check("an expired entry is not served", True)


def test_cloudflare_reads_every_account_not_the_first() -> None:
    ""                                        

                                                                            
                                                                                 
                            
       
    cf = load("cloudflare_analytics")
    d = pathlib.Path(tmp.mkdtemp()) / "cloudflare-analytics.d"
    d.mkdir()
    (d / "acme").write_text("token-a\n", encoding="utf-8")
    (d / "other-co").write_text("token-b\n", encoding="utf-8")
    (d / ".DS_Store").write_text("junk", encoding="utf-8")
    (d / "empty").write_text("   \n", encoding="utf-8")
    cf.TOKEN_DIR = d
    got = cf.tokens()
    check("every account file becomes a token", [l for l, _ in got] == ["acme", "other-co"],
          str([l for l, _ in got]))
    check("the values are stripped", [v for _, v in got] == ["token-a", "token-b"], "")
    check("a dotfile is not an account", all(not l.startswith(".") for l, _ in got))
    (d / "acme.meta.json").write_text(json.dumps({"kind": "issued"}), encoding="utf-8")
    (d / "broken").write_text("line one\nline two\n", encoding="utf-8")
    got2 = cf.tokens()
    check("a token's meta RECORD is not read as a token — it was, on 2026-09-13",
          all(not l.endswith(".meta.json") for l, _ in got2), str([l for l, _ in got2]))
    check("and a multi-line file is not a token either",
          "broken" not in [l for l, _ in got2], str([l for l, _ in got2]))
    src2 = (ROOT / "plugins/cloudflare_analytics.py").read_text(encoding="utf-8")
    check("the header-echoing ValueError is caught before it can print a value",
          "except ValueError:" in src2 and "header-safe" in src2, "")
    src = (ROOT / "plugins/cloudflare_analytics.py").read_text(encoding="utf-8")
    check("one account's failure does not end the run",
          "except RuntimeError as exc:" in src and "continue" in src,
          "a revoked token on one login must not delete the others' traffic")


def test_the_cf_door_probes_with_the_plugins_own_query() -> None:
    ""                                                                  

                                                                             
                                                                                
                                                                       
                                                                
       
    import importlib.util
    spec = importlib.util.spec_from_file_location("cf_door", ROOT / "tools/cloudflare.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    cf2 = load("cloudflare_analytics")

    def refuse_graphql(q, token, graphql=False):
        if graphql:
            raise RuntimeError("cloudflare graphql: zones [z-1] are not authorized")
        return {"result": [{"id": "z-1", "name": "example.org"}],
                "result_info": {"total_pages": 1}}
    cf2._call = refuse_graphql
    sys.modules["cloudflare_analytics"] = cf2
    why = m.can_read_analytics("whatever", ["z-1"])
    check("a Zone:Read-only token is caught by the plugin's OWN query",
          "not authorized" in why, why)
    cf2._call = lambda q, token, graphql=False: (
        {"data": {"viewer": {"zones": [{"zoneTag": "z-1",
                                        "httpRequests1dGroups": [
                                            {"sum": {"requests": 1, "pageViews": 1},
                                             "uniq": {"uniques": 1}}]}]}}}
        if graphql else {"result": [], "result_info": {"total_pages": 1}})
    check("and a token that can read analytics passes the probe",
          m.can_read_analytics("whatever", ["z-1"]) == "", "")

                                                                              
                                      
    m._request = lambda path, token, payload=None, method=None: {
        "result": [{"id": "z-9", "name": "example.com",
                    "account": {"name": "Example Account"}}],
        "result_info": {"total_pages": 1}}
    zs = m.zones_of("whatever")
    label = m.slug(next(z["account"] for z in zs if z["account"]))
    check("the label is the account Cloudflare names, slugged",
          label == "example-account", label)


def test_the_manifests_declare_what_the_scripts_emit() -> None:
    declared = {}
    for mf in ("cloudflare-analytics", "search-console", "ga4-analytics"):
        doc = json.loads((ROOT / "plugins" / f"{mf}.json").read_text(encoding="utf-8"))
        declared[mf] = {m["name"] for m in doc["metrics"]}
        check(f"{mf} requires its credential path",
              any(r.startswith("secret:") for r in doc["requires"]), str(doc["requires"]))
        check(f"{mf} runs daily", doc["every_hours"] == 24, str(doc["every_hours"]))
        check(f"{mf} labels every metric for the dashboard",
              all(m.get("label") for m in doc["metrics"]))
    emitted = {
        "cloudflare-analytics": {"web.requests_1d", "web.visitors_1d"},
        "search-console": {"search.clicks_1d", "search.impressions_1d"},
        "ga4-analytics": {"ga.sessions_1d", "ga.users_1d"}}
    for mf, names in emitted.items():
        check(f"{mf}'s script emits exactly what it declares",
              declared[mf] == names, f"{declared[mf]} vs {names}")
    check("the visitors metric carries the traffic role for core surfaces",
          any(m.get("role") == "traffic.visitors" for m in json.loads(
              (ROOT / "plugins/cloudflare-analytics.json").read_text())["metrics"]))


if __name__ == "__main__":
    print("analytics plugins — attribution, lag, sanitised errors, no network\n")
    for fn in (test_hostmap_resolves_most_specific_first,
               test_cloudflare_rows_attribute_and_report_unmapped,
               test_cloudflare_asks_for_at_most_ten_zones_per_query,
               test_gsc_rows_speak_both_property_shapes,
               test_ga4_rows_honour_explicit_project_over_hostmap,
               test_every_http_error_is_sanitised,
               test_the_manifests_declare_what_the_scripts_emit,
               test_the_token_exchange_needs_no_third_party_transport,
               test_cloudflare_reads_every_account_not_the_first,
               test_the_cf_door_probes_with_the_plugins_own_query):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mtraffic follows ownership, and nothing leaks on the way\033[0m")
