#!/usr/bin/env python3
""                                                                           

                                                                            
                                                                                  
                                                                                
                                                                             
                                                                          
                    

                                                                            
                                                                                
                                                                             
                                                                               
                        

                                                                                
                                                                               
                                                                            
                                                                     

                                                                                

                                                                   
   
from __future__ import annotations
import concurrent.futures as cf
import shutil
import json, pathlib, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths              

WORKERS = 6
RDAP = "https://rdap.org/domain/"
RDAP_RETRIES = 4
RDAP_BACKOFF = 2.0
                                                                            
                                                                         
                             
RDAP_WORKERS = 1
                                                                                 
                                                                         
TWO_LABEL_SUFFIXES = {"co.uk", "com.br", "com.au", "co.jp", "com.ua", "co.il"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def registrable(host: str) -> str:
    ""                                                                                   
    parts = host.strip(".").lower().split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in TWO_LABEL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def dig(host: str, rtype: str) -> tuple[list[str], str | None]:
    ""                                                                        

                                                                           
                                                                              
                                                                               
                                                                           
                                                                              
                                                                               
                             

                                                                           
                                                                       
                                                                        
                                                                          
                                                                             
       
    try:
        r = subprocess.run(["dig", "+short", "+time=5", "+tries=2", rtype, host],
                           capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        return [], "dig is not installed here"
    except subprocess.TimeoutExpired:
        return [], "dig timed out after 15s"
    except OSError as exc:
        return [], f"dig could not run: {exc}"
    if r.returncode != 0:
        return [], f"dig exited {r.returncode}: {(r.stderr or '').strip()[:80]}"
    return [ln.strip().rstrip(".") for ln in r.stdout.splitlines() if ln.strip()], None


def http_status(host: str) -> tuple[int, str | None]:
    ""                                          

                                                                               
                                                                              
                                                                              
                                                                         
       
    try:
        r = subprocess.run(["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}",
                            "--max-time", "12", f"https://{host}"],
                           capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        return 0, "curl is not installed here"
    except subprocess.TimeoutExpired:
        return 0, "curl timed out after 20s"
    except OSError as exc:
        return 0, f"curl could not run: {exc}"
    try:
        return int(r.stdout.strip() or 0), None
    except ValueError:
        return 0, f"curl returned {r.stdout.strip()[:40]!r} instead of a status"


def rdap(name: str, attempt: int = 0) -> tuple[dict, str]:
    ""                                                                        

                                                                        
                                                                          
                                                                                    
                                                                         
                                                                            
                                  
       
    req = urllib.request.Request(RDAP + name, headers={
        "Accept": "application/rdap+json", "User-Agent": "project-observatory"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code == 429 and attempt < RDAP_RETRIES:
            wait = float(e.headers.get("Retry-After") or 0) or RDAP_BACKOFF * (2 ** attempt)
            time.sleep(min(wait, 30))
            return rdap(name, attempt + 1)
        if e.code == 429:
            return {}, (f"RDAP rate-limited {name} (429) after {RDAP_RETRIES} retries — "
                        f"this says nothing about the domain, only about the query rate")
        if e.code == 404:
            return {}, (f"RDAP has no record for {name} (404). For a TLD outside the "
                        f"RDAP bootstrap — .me and .co answer this way while resolving "
                        f"normally — it means no RDAP service, NOT an unregistered domain")
        return {}, f"RDAP returned HTTP {e.code} for {name}"
    except OSError as e:
        return {}, f"RDAP unreachable for {name}: {e}"

                                                                                
                                                                               
                                                                                
                                                                              
                                                                   
    out: dict = {"about": (d.get("ldhName") or name).lower(), "statuses": d.get("status") or []}
    for ev in d.get("events") or []:
        act = (ev.get("eventAction") or "").replace(" ", "_")
        if act in ("registration", "expiration", "last_changed"):
            out[act] = str(ev.get("eventDate") or "")[:10]
    for ent in d.get("entities") or []:
        if "registrar" in (ent.get("roles") or []):
            for row in (ent.get("vcardArray") or [None, []])[1]:
                if row and row[0] == "fn":
                    out["registrar"] = row[3]
                                                                    
     
                                                                             
                                                                                
                                                                         
                                                                            
                                                                                
                                                                             
                                                                            
               
     
                                                                                
                                                                                
                                                                                
                                                                           
                                                            
    unread = [k for k, present in (("status", bool(d.get("status"))),
                                   ("expiration", bool(out.get("expiration"))),
                                   ("registrar", bool(out.get("registrar"))))
              if not present]
    if unread:
        out["unread"] = unread
    return out, ""


def probe(host: str) -> tuple[str, dict]:
    ""                                                                       

                                                                           
                                                                 
                                                                              
                                                                     
       
    (ns, ns_err) = dig(host, "NS")
    (a, a_err) = dig(host, "A")
    (cname, cn_err) = dig(host, "CNAME")
    info: dict = {"checked_at": now(), "nameservers": ns, "a": a, "cname": cname,
                  "registrable": registrable(host)}

                                                                                
                                                                                
                            
    probe_err = a_err or cn_err
    if probe_err:
        info["resolves"] = None
        info["unmeasured"] = probe_err
        info["http"] = None
        return host, info

    resolves = bool(a or cname)
    info["resolves"] = resolves
    if resolves:
        status, http_err = http_status(host)
        info["http"] = None if http_err else status
        if http_err:
            info["http_unmeasured"] = http_err
    else:
        info["http"] = 0
                                                                               
                                                      
        info["dark"] = True
    return host, info


def main(argv: list[str]) -> int:
    import configuration
    if not configuration.enabled("domains"):
        print("domains: not configured (integration disabled)")
        return 0
    if len(argv) < 2:
        sys.exit(__doc__)
    dest = pathlib.Path(argv[1])
    only = set(argv[argv.index("--only") + 1:]) if "--only" in argv else None

    domains = [d["name"] for d in
               json.loads((paths.REGISTRY / "domains.json").read_text())["domains"]]
    sites = [s["host"] for p in
             json.loads((paths.REGISTRY / "projects.json").read_text())["projects"]
             for s in p.get("sites", [])]
    hosts = sorted({h for h in domains + sites if h and (only is None or h in only)})
    if not hosts:
        sys.exit("scan_domains: nothing to probe")

                                                                                
                                                                               
                                                                              
                                                                                
    missing = [tool for tool in ("dig", "curl") if shutil.which(tool) is None]
    if missing:
        print(f"scan_domains: {', '.join(missing)} not on PATH — REFUSING to scan. "
              f"Every host would come back unmeasured, and overwriting "
              f"{dest.name} with that would turn a tooling gap into 58 claims "
              f"about the estate. The previous file is left untouched.",
              file=sys.stderr)
        return 1

    live: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for host, info in pool.map(probe, hosts):
            live[host] = info

    names = sorted({info["registrable"] for info in live.values()})
    whois: dict[str, dict] = {}
    degraded: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=RDAP_WORKERS) as pool:
        for name, (data, err) in zip(names, pool.map(rdap, names)):
            if err:
                degraded.append({"source": f"rdap:{name}", "reason": err})
            else:
                whois[name] = data

                                                                             
                                                                               
                                                                                 
                                                                            
                                                                          
    by_key: dict[str, list[str]] = {}
    for name, rec in whois.items():
        for key in rec.get("unread") or []:
            by_key.setdefault(key, []).append(name)
    for key, names_ in sorted(by_key.items()):
        degraded.append({
            "source": f"rdap:{key}",
            "reason": (f"RDAP answered for {len(names_)} domain(s) without a "
                       f"`{key}`: {', '.join(sorted(names_)[:6])}"
                       + (f" and {len(names_) - 6} more" if len(names_) > 6 else "")
                       + f". Whatever reads `{key}` has nothing to read for them, "
                       f"and an empty answer there is not the same as a negative "
                       f"one")})

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"scanned_at": now(), "hosts": live, "rdap": whois,
                                "degraded": degraded}, ensure_ascii=False, indent=1),
                    encoding="utf-8")

    dark = [h for h, i in live.items() if i.get("dark")]
    held = [n for n, w in whois.items()
            if any("hold" in s for s in w.get("statuses", []))]
    soon = [(n, w["expiration"]) for n, w in whois.items()
            if w.get("expiration") and w["expiration"] <= "2026-12-05"]
    print(f"probed {len(live)} host(s), {len(whois)} RDAP record(s) -> {dest}")
    print(f"  dark (no A and no CNAME): {len(dark)}" + (f" — {dark[:6]}" if dark else ""))
    print(f"  registrar hold:           {len(held)}" + (f" — {held[:6]}" if held else ""))
    print(f"  expiring within 90 days:  {len(soon)}" + (f" — {soon[:6]}" if soon else ""))
    for d in degraded[:6]:
        print(f"  degraded {d['source']}: {d['reason'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
