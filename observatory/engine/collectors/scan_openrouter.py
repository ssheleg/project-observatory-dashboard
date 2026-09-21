#!/usr/bin/env python3
""                                                                           

                                                                              
                                                                               
                                                                               
                                                                                
                                                                               
                                             

                                        

                                                                 
                                                                      
                                                      

                                                                               
                                                                                
                                                                               
                                                                               
                                                                            
                           

                                                                           
                                                                                
                                                                            
                                                                             
                          

                                                
   
from __future__ import annotations
import json, pathlib, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic              
import paths              

API = "https://openrouter.ai/api/v1"
PAGE = 100
                                                                               
                                                                                  
                                                                               
                                                                            
         
MAX_PAGES = 12

                                                                        
                                                                         
                             
DESTINATIONS = {
    "observatory": paths.STORE / ".openrouter-key",
    "claude-mem": paths.source_path("companion_home", paths.HOME / "disabled/companion") / ".env",
    "gateway": paths.source_path("secret_store", paths.SECRETS) / 'openrouter',
    "provisioning": paths.source_path("secret_store", paths.SECRETS) / 'openrouter-provisioning',
}


                                                                     
                                                                              
                                                                              
                                                                                
  
                                                                               
                                                                             
                                                                 
                                                                                
                                                                           
                                                
TAIL = 3


def label_of(value: str) -> str:
    ""                                                                      
    value = (value or "").strip()
    if not value.startswith("sk-or-v1-") or len(value) < 16:
        return ""
    return "sk-or-v1-" + value[9:12] + "..." + value[-TAIL:]


def _label(text: str) -> str:
    ""                                                      
    text = (text or "").strip()
    if not text:
        return ""
    if "OPENROUTER_API_KEY" in text:                                              
        for line in text.splitlines():
            if line.strip().startswith("OPENROUTER_API_KEY"):
                text = line.split("=", 1)[-1].strip().strip('"').strip("'")
                break
    return label_of(text)


def destinations() -> tuple[dict[str, str], list[dict]]:
    ""                                                                            
    out, degraded = {}, []
    for name, path in DESTINATIONS.items():
        if not path.is_file():
            degraded.append({"source": f"openrouter:{name}",
                             "reason": f"no key at {path} — this consumer has none"})
            continue
        try:
            tail = _label(path.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            degraded.append({"source": f"openrouter:{name}",
                             "reason": f"unreadable: {type(exc).__name__}"})
            continue
        if not tail:
            degraded.append({"source": f"openrouter:{name}",
                             "reason": "the file holds no OpenRouter-shaped key"})
            continue
        out[name] = tail
    return out, degraded


def listing(prov: str) -> tuple[list[dict], str | None]:
    ""                                                                         
    rows, offset = [], 0
    for _ in range(MAX_PAGES):
        req = urllib.request.Request(f"{API}/keys?offset={offset}",
                                     headers={"Authorization": f"Bearer {prov}"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                page = json.loads(r.read().decode())["data"]
        except urllib.error.HTTPError as e:
            return rows, f"GET /keys failed: HTTP {e.code}"
        except Exception as e:                                                  
            return rows, f"GET /keys failed: {type(e).__name__}"
        rows.extend(page)
        if len(page) < PAGE:
            return rows, None
        offset += len(page)
        time.sleep(0.2)
    return rows, (f"stopped after {MAX_PAGES} pages ({len(rows)} keys); the account "
                  f"holds more and this list is partial")


def main(argv: list[str]) -> int:
    import configuration
    if not configuration.enabled("openrouter"):
        print("openrouter: not configured (integration disabled)")
        return 0
    out_path = pathlib.Path(argv[1]) if len(argv) > 1 else paths.SCRATCH / "openrouter.json"
    started = datetime.now(timezone.utc).isoformat()
    dests, degraded = destinations()

    prov_path = DESTINATIONS["provisioning"]
    if not prov_path.is_file():
                                                                                
                                                                                
                                                                         
        atomic.write_json(out_path, {
            "schema_version": 1, "scanned_at": started, "keys": [],
            "destinations": dests, "unlisted_destinations": sorted(dests),
            "degraded": degraded + [{"source": "openrouter:listing",
                                     "reason": "no provisioning key, so the account's "
                                               "keys cannot be listed at all"}],
        }, indent=1)
        print(f"openrouter.json: no provisioning key; {len(dests)} destination(s) read",
              file=sys.stderr)
        return 0

    prov = prov_path.read_text(encoding="utf-8").strip()
    rows, why = listing(prov)
    if why:
        degraded.append({"source": "openrouter:listing", "reason": why})

                                                                            
                                                                          
                       
    seen: dict[str, int] = {}
    for k in rows:
        lab = k.get("label") or ""
        seen[lab] = seen.get(lab, 0) + 1
    collisions = {lab for lab, n in seen.items() if n > 1}
    by_label = {lab: name for name, lab in dests.items() if lab not in collisions}
    for name, lab in dests.items():
        if lab in collisions:
            degraded.append({"source": f"openrouter:{name}",
                             "reason": (f"{seen[lab]} keys in this account share the label "
                                        f"{lab}, so which one this consumer holds cannot "
                                        f"be told from metadata alone")})
    keys = []
    for k in rows:
        label = k.get("label") or ""
        keys.append({
            "label": label,
            "tail": label[-TAIL:],
            "name": k.get("name"),
            "serves": by_label.get(label),
            "limit": k.get("limit"),
            "limit_reset": k.get("limit_reset"),
            "usage": round(k.get("usage") or 0, 6),
            "remaining": k.get("limit_remaining"),
            "disabled": bool(k.get("disabled")),
            "is_provisioning": bool(k.get("is_provisioning_key")),
            "created_at": (k.get("created_at") or "")[:19],
        })
    keys.sort(key=lambda x: (x["serves"] is None, x["serves"] or "", x["name"] or ""))

    listed = {k["label"] for k in keys}
    orphan_dests = sorted(n for n, t in dests.items() if t not in listed)
    for n in orphan_dests:
        degraded.append({"source": f"openrouter:{n}",
                         "reason": ("its key is not in this account's listing — either it "
                                    "belongs to another workspace or it no longer exists")})

    atomic.write_json(out_path, {
        "schema_version": 1,
        "scanned_at": started,
                                                                             
                                                                               
        "hashes": {(k.get("label") or ""): k.get("hash") for k in rows},
        "keys": keys,
        "destinations": dests,
                                                                              
                                                                                
        "destination_paths": {n: str(p) for n, p in DESTINATIONS.items() if p.is_file()},
        "unlisted_destinations": orphan_dests,
        "degraded": degraded,
    }, indent=1)
    served = sum(1 for k in keys if k["serves"])
    print(f"openrouter.json: {len(keys)} key(s), {served} serving a known consumer, "
          f"{len(orphan_dests)} destination(s) not in the listing, "
          f"{len(degraded)} degradation(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
