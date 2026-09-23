#!/usr/bin/env python3
""                                                                       

                                                                               
                                                                             
                                                                           
                

                                                         

                                                                                     
                                                                     
               
                                                                           
                                       
                                                                                 
                                                                    

                                                                          
                                                                             
                                                          

                                                                                 
                                                                               
                                                                               
                                          
   
from __future__ import annotations
import json, os, sys, pathlib, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import atomic
import paths

CONFIG = paths.config_file('models.json')
CATALOGUE = paths.STATE / "openrouter-catalogue.json"
WALLET = paths.STATE / "wallet.json"
HEALTH = paths.STATE / "provider-health.json"
                                                                             
                                                                                 
                                                                              
                                                                             
KEY_USAGE = paths.STATE / "key-usage.json"
KEY_ENV = "OPENROUTER_API_KEY"
EMBED_KEY_ENV = "OPENAI_API_KEY"

                                                                                
                                                                                 
                                                                            
                              
  
                                                                         
                                                                                
                                                            
                                                                                 
                                                                             
                                                                            
                                                                              
                                                               
                                                                            
                                                                                 
                                                                              
                                                                               
                                                                           
                                                                                
                                                                            
                                                                            
                                                                          
                                                  
KEY_FILES = ((pathlib.Path(os.environ["OBSERVATORY_KEY_FILE"]),)
             if os.environ.get("OBSERVATORY_KEY_FILE") else
             (paths.STORE / ".openrouter-key",
              paths.source_path("secret_store", paths.SECRETS) / 'openrouter'))
UA = "project-observatory/0.1 (+https://github.com/ssheleg/project-observatory-dashboard)"


class ProviderError(Exception):
    ""                                                                                        


class Retryable(ProviderError):
    ""                                                                       


class Fatal(ProviderError):
    ""                                                                            
                                                                            


class CredentialError(Fatal):
    ""                                                                             
                                                                                    
                                                                       


class BudgetExceeded(ProviderError):
    ""                                                        


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


                                                                                                                                                                                                           

def _fetch_catalogue(base_url: str) -> dict:
    req = urllib.request.Request(f"{base_url}/models", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def catalogue(refresh: bool = False) -> tuple[dict, str]:
    ""                                                                           
                                                
    cfg = config()
    ttl = timedelta(hours=cfg.get("catalogue_ttl_hours", 24))
    cached, age = None, None
    if CATALOGUE.exists():
        try:
            cached = json.loads(CATALOGUE.read_text(encoding="utf-8"))
            age = now() - datetime.strptime(cached["fetched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
        except Exception:
            cached = None
    if cached and not refresh and age is not None and age < ttl:
        return cached["models"], f"cached {int(age.total_seconds() // 60)}m ago"
    try:
        raw = _fetch_catalogue(cfg["base_url"])
    except (urllib.error.URLError, OSError, ValueError) as exc:
        if cached:
            return cached["models"], f"STALE ({exc.__class__.__name__}); cached {age}"
        raise Retryable(f"the catalogue is unreachable and nothing is cached: {exc}") from exc
    models = {}
    for m in raw.get("data", []):
        pricing = m.get("pricing") or {}
        def num(k: str) -> float:
            try:
                return float(pricing.get(k) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        models[m["id"]] = {
            "id": m["id"],
            "name": m.get("name", ""),
            "context_length": m.get("context_length") or 0,
            "price_in_per_1m": num("prompt") * 1e6,
            "price_out_per_1m": num("completion") * 1e6,
            "supported_parameters": m.get("supported_parameters") or [],
        }
                                                                            
                                                                                
                                                                              
                                                                            
                                                                                 
                                                                 
    atomic.write_json(CATALOGUE, {"fetched_at": iso(), "models": models})
    return models, "fetched now"


                                                                                                                                                                                                                         

def _health() -> dict:
    if HEALTH.exists():
        try:
            return json.loads(HEALTH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def mark_unhealthy(model_id: str, reason: str) -> None:
    h = _health()
    h[model_id] = {"since": iso(), "reason": reason[:200]}
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_json(HEALTH, h)


def mark_healthy(model_id: str) -> None:
    h = _health()
    if h.pop(model_id, None) is not None:
        atomic.write_json(HEALTH, h)


def unhealthy(model_id: str) -> str | None:
    ""                                                                      
                                                             
    entry = _health().get(model_id)
    if not entry:
        return None
    minutes = config().get("health", {}).get("probe_after_minutes", 60)
    try:
        since = datetime.strptime(entry["since"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None
    if now() - since > timedelta(minutes=minutes):
        return None                                                           
    return entry.get("reason", "unhealthy")


                                                                                                                                                                                                                   

def resolve_chain(requested: str | None = None) -> tuple[list[dict], str, str]:
    ""                                                        

                                                                             
                                                                               
       
    cfg = config()
    models, provenance = catalogue()
    if requested:
        entry = models.get(requested)
        if entry is None:
            raise Fatal(f"{requested} is not in the catalogue ({len(models)} models known). "
                        f"Check the id against {cfg['base_url']}/models")
        return [dict(entry, why="named by the caller")], "caller", provenance
    chain, retired = [], []
    for e in cfg.get("chain", []):
        entry = models.get(e["id"])
        if entry is None:
                                                                                   
                                                                          
                                                                            
                                                                              
                                                                              
                         
             
                                                                               
                                                                              
                                                                             
                                                                    
                                                                                
                                                                               
                                                                        
            retired.append(e["id"])
            continue
        chain.append(dict(entry, why=e.get("why", "")))
    if chain:
        if retired:
            chain[0] = dict(chain[0], chain_retired=retired)
        return chain, "config", provenance
    raise Fatal("no model in the configured chain exists in the catalogue; "
                "check agent/models.json against the provider")


def needs_structured(model: dict) -> bool:
    return "structured_outputs" in model.get("supported_parameters", [])


def estimate(model: dict, in_tokens: int, out_tokens: int) -> float:
    return (in_tokens * model["price_in_per_1m"] + out_tokens * model["price_out_per_1m"]) / 1e6


                                                                                                                                                                                                                         

_provider_usage_cache: dict | None = None


def provider_usage(force: bool = False) -> dict | None:
    ""                                                                  

                                                                            
                                                                               
                                                                           
                                                            

                                                                                
                                                            
       
    global _provider_usage_cache
    if _provider_usage_cache is not None and not force:
        return _provider_usage_cache
    key, _ = read_key()
    if not key:
        return None
    req = urllib.request.Request(f"{config()['base_url']}/key",
                                 headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8")).get("data") or {}
    except (urllib.error.URLError, OSError, ValueError):
        return None
    _provider_usage_cache = {
        "daily": float(d.get("usage_daily") or 0.0),
        "weekly": float(d.get("usage_weekly") or 0.0),
        "monthly": float(d.get("usage_monthly") or 0.0),
        "total": float(d.get("usage") or 0.0),
        "limit": d.get("limit"),
        "limit_remaining": d.get("limit_remaining"),
        "limit_reset": d.get("limit_reset"),
    }
    record_key_usage(_provider_usage_cache)
    return _provider_usage_cache


def retention_config() -> dict:
    ""                                                            

                                                                             
                                                                              
                                                                              
                                                                 
       
    try:
        return json.loads(paths.config_file("retention.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _wallet() -> dict:
    if WALLET.exists():
        try:
            return json.loads(WALLET.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"denomination": "credits", "events": [], "days": {}, "months": {}}


def _save_wallet(w: dict) -> None:
    WALLET.parent.mkdir(parents=True, exist_ok=True)
                                                                              
                                                                           
                                                                            
                             
    atomic.write_json(WALLET, w)


def record_key_usage(pu: dict) -> None:
    ""                                                                   

                                                                                 
                                                                               
                                                                                
                                                                         
                       

                                                                            
                                                  
       
    try:
        atomic.write_json(KEY_USAGE, {
            "checked_at": iso(),
            "daily": pu.get("daily"), "weekly": pu.get("weekly"),
            "monthly": pu.get("monthly"), "total": pu.get("total"),
            "limit": pu.get("limit"), "limit_remaining": pu.get("limit_remaining"),
            "limit_reset": pu.get("limit_reset"),
            "note": ("What the PROVIDER says this KEY has spent — the whole account, "
                     "shared with every other tool on this machine that uses it. "
                     "This project's own spend is in store/wallet.json and is what "
                     "its ceilings are measured against."),
        })
    except Exception:                                                             
        pass


def wallet_state() -> dict:
    w, cfg = _wallet(), config()["wallet"]
    day, month = now().strftime("%Y-%m-%d"), now().strftime("%Y-%m")
    window = timedelta(minutes=cfg["velocity_window_minutes"])
    recent = 0.0
    for e in w.get("events", []):
        try:
            t = datetime.strptime(e["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if now() - t <= window:
            recent += e.get("cost", 0.0)
    local_day = round(w.get("days", {}).get(day, 0.0), 6)
    local_month = round(w.get("months", {}).get(month, 0.0), 6)
    pu = provider_usage()
    state = {
        "denomination": w.get("denomination", "credits"),
                                                                          
                                                                             
                                                                           
                          
        "source": "provider" if pu else "local journal (the provider was unreachable)",
                                                                            
                                                                               
        "today": round(pu["daily"], 6) if pu else local_day,
        "key_today": round(pu["daily"], 6) if pu else None,
        "key_month": round(pu["monthly"], 6) if pu else None,
        "daily_ceiling": cfg["daily_ceiling"],
        "month": round(pu["monthly"], 6) if pu else local_month,
        "monthly_ceiling": cfg["monthly_ceiling"],
                                                                                
                                                                            
        "window_spend": round(recent, 6),
        "velocity_ceiling": cfg["velocity_ceiling"],
        "window_minutes": cfg["velocity_window_minutes"],
        "calls": len(w.get("events", [])),
        "local_today": local_day,
        "local_month": local_month,
    }
    if pu:
        state["key_limit"] = pu["limit"]
        state["key_remaining"] = round(pu["limit_remaining"] or 0.0, 6)
        state["key_limit_reset"] = pu["limit_reset"]
        state["key_total"] = round(pu["total"], 6)
    return state


def check_budget(provider: str = "openrouter") -> str | None:
    ""                                                                    

                                                                                   
                                                                                
                                 

                                                                                 
                                                                                 
                                                                        
                                                                               
                                                                                  
                                                                             
                                                                                
                                                                               
                                                                          
                                                                                
                                                                                
                

                                                                            
                                                                       
                                                                               
                                                                                
                                                                 
       
    s = wallet_state()
                                                                          
                                                                       
                                                                               
                                                                              
                              
     
                                               
                                           
                                                       
                                                                              
                                             
     
                                                                             
                                                                             
                                                                             
                                                                               
                                                                            
                                                                                
     
                                                                              
                                                                              
                                                                                 
                        
    today, month = s["local_today"], s["local_month"]
    source = "this project's journal"
    own_meter = provider == "openrouter"
                                                                               
                                                                             
                                                                                
                                                     
    if own_meter and s.get("key_remaining") is not None and s["key_remaining"] <= 0:
                                                                                 
                                                                               
                                                                              
                                                                            
                                                                               
                                                     
        others = max(float(s["key_total"]) - float(month), 0.0)
        return (f"the limit on this KEY is spent: {s['key_total']:.4f} of "
                f"{s['key_limit']} {s['denomination']}, resets "
                f"{s.get('key_limit_reset') or 'never'}. "
                f"this project's own journal holds {month:.4f} {s['denomination']} "
                f"for the month, so {others:.2f} was another consumer of the same key")
    if today >= s["daily_ceiling"]:
                                                                              
                                                                                
                                                                                
                                                                            
                                                                         
                                                                              
                                                                          
                                                                              
                                                                               
                                                                   
        extra = (f"; the key itself shows {s['key_today']:.4f} today, so "
                 f"{s['key_today'] - today:.4f} of that is another consumer"
                 if s.get("key_today") is not None else "")
        return (f"daily ceiling: {today:.4f} of {s['daily_ceiling']:.2f} "
                f"{s['denomination']} spent today by THIS project ({provider}, per "
                f"{source}){extra}")
    if month >= s["monthly_ceiling"]:
        extra = (f"; the key itself shows {s['key_month']:.4f} this month"
                 if s.get("key_month") is not None else "")
        return (f"monthly ceiling: {month:.4f} of {s['monthly_ceiling']:.2f} "
                f"{s['denomination']} spent this month by THIS project ({provider}, "
                f"per {source}){extra}")
    if s["window_spend"] >= s["velocity_ceiling"]:
        return (f"spend velocity: {s['window_spend']:.4f} {s['denomination']} in the last "
                f"{s['window_minutes']}min, ceiling {s['velocity_ceiling']:.2f} — "
                f"something is looping")
    return None


def charge(model_id: str, cost: float, tokens_in: int, tokens_out: int,
           upstream: float | None = None, provider: str = "openrouter",
           estimated: bool = False) -> str | None:
    ""                                                                             

                                                                 
       
    w = _wallet()
    day, month = now().strftime("%Y-%m-%d"), now().strftime("%Y-%m")
    w.setdefault("days", {})[day] = w.get("days", {}).get(day, 0.0) + cost
    w.setdefault("months", {})[month] = w.get("months", {}).get(month, 0.0) + cost
    w.setdefault("events", []).append({
        "at": iso(), "model": model_id, "provider": provider, "cost": round(cost, 8),
        "estimated": estimated,
        "upstream": round(upstream, 8) if upstream is not None else None,
        "in": tokens_in, "out": tokens_out})
                                                                              
                                                                             
                                                                              
                                                                            
                                                                        
                                                                           
    keep = retention_config()
    w["events"] = w["events"][-int(keep.get("wallet_events", 500)):]
    for d in sorted(w["days"])[:-int(keep.get("wallet_days", 60))]:
        del w["days"][d]
    for m in sorted(w["months"])[:-int(keep.get("wallet_months", 12))]:
        del w["months"][m]
    _save_wallet(w)
    global _provider_usage_cache
    _provider_usage_cache = None                                                
    return check_budget()


                                                                                                                                                                                                                     

def _post(base_url: str, key: str, body: dict, timeout: int = 120) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/chat/completions", data=data, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": UA,
                                                                                    
                 "HTTP-Referer": "https://github.com/ssheleg/project-observatory-dashboard",
                 "X-Title": "Project Observatory"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        if exc.code in (408, 409, 429) or exc.code >= 500:
            raise Retryable(f"HTTP {exc.code}: {detail}") from exc
        if exc.code in (401, 403):
            raise CredentialError(f"HTTP {exc.code}: {detail}") from exc
        raise Fatal(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise Retryable(f"{type(exc).__name__}: {exc}") from exc


EMBED_KEY_FILES = ((pathlib.Path(os.environ["OBSERVATORY_EMBED_KEY_FILE"]),)
                   if os.environ.get("OBSERVATORY_EMBED_KEY_FILE") else
                   (paths.source_path("secret_store", paths.SECRETS) / 'openai',
                    paths.STORE / ".openai-key"))


                                                                               
                                                                            
                                                                            
                                                                                
                                                                               
KEY_SHAPES = {
    "OPENROUTER_API_KEY": ("sk-or-v1-", "OpenRouter"),
    "OPENAI_API_KEY": ("sk-", "OpenAI"),
}
                                                                            
KEY_ANTI_SHAPES = {"OPENAI_API_KEY": ("sk-or-",)}


                                                                             
                                                                         
_SHAPE_WARNED: set[str] = set()


def _shape_ok(env_name: str, value: str) -> str | None:
    ""                                                                          
    want = KEY_SHAPES.get(env_name)
    if not want:
        return None
    prefix, who = want
    if not value.startswith(prefix):
        return (f"it does not start with {prefix!r}, so it is not a {who} key. "
                f"A key in the wrong variable is sent to the wrong host and "
                f"answered with a 401 that names nothing.")
    for bad in KEY_ANTI_SHAPES.get(env_name, ()):
        if value.startswith(bad):
            return (f"it starts with {bad!r} — that is an OpenRouter key sitting in "
                    f"{env_name}. Sent to {who}'s host it answers 401, and meanwhile it "
                    f"shadows the correct key in the secret store.")
    return None


                                                                           
                                                                          
                                                                               
                                                
def _shapes_file():
    return paths.STATE / "key-shapes.json"


def shape_report() -> list[dict]:
    ""                                                                    

                                                                                
                                                                               
                                                                                 
                                                                                
                                                                   

                                                                           
                                                                             
                                            
       
    rows: list[dict] = []
    for env_name, (prefix, who) in sorted(KEY_SHAPES.items()):
        value = os.environ.get(env_name)
        if not value:
            continue
        wrong = _shape_ok(env_name, value)
        row = {"env": env_name, "provider": who, "expected_prefix": prefix,
               "verdict": "wrong" if wrong else "ok"}
        if wrong:
            row["reason"] = wrong.split(". ")[0]
                                                                             
                                                                            
            row["looks_like"] = next(
                (bad for bad in KEY_ANTI_SHAPES.get(env_name, ())
                 if value.startswith(bad)), "")
        rows.append(row)
    return rows


def write_shape_report(rows: list[dict] | None = None) -> pathlib.Path:
    ""                                                                    

                                                                             
                                                                                
                                                                           
                                                                           
       
    rows = shape_report() if rows is None else rows
    f = _shapes_file()
    doc = {"observations": {}}
    if f.is_file():
        try:
            prior = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(prior.get("observations"), dict):
                doc["observations"] = prior["observations"]
        except (ValueError, OSError):
                                                                                
                                                                             
            pass
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in rows:
        doc["observations"][r["env"]] = {**r, "seen_at": stamp}
    doc["written_at"] = stamp
    f.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_json(f, doc)
    return f


def _read_from(env_name: str, files: tuple) -> tuple[str | None, str]:
    ""                                                                      
                                                                     

                                                                            
                                                                                 
                                                                    
    env = os.environ.get(env_name)
    if env and env.strip():
        wrong = _shape_ok(env_name, env.strip())
        if wrong:
                                                                            
                                                                              
                                                                                    
                                                                              
                                                                            
                                                                               
                                 
            if env_name not in _SHAPE_WARNED:
                _SHAPE_WARNED.add(env_name)
                print(f"  ignoring ${env_name}: {wrong}", file=sys.stderr)
        else:
            return env.strip(), f"${env_name}"
    for f in files:
        if not f.is_file():
            continue
        mode = f.stat().st_mode & 0o777
        if mode & 0o077:
            raise Fatal(f"{f} is mode {mode:o} — group or world readable. "
                        f"A key file must be 600.\n  chmod 600 {f}")
        value = f.read_text(encoding="utf-8").strip()
        if not value:
            continue
        wrong = _shape_ok(env_name, value)
        if wrong:
            raise Fatal(f"{f} holds something that is not a key for this provider: {wrong}")
        return value, str(f)
    return None, "nowhere"


def read_embed_key() -> tuple[str | None, str]:
    files = ((pathlib.Path(os.environ["OBSERVATORY_EMBED_KEY_FILE"]),)
             if os.environ.get("OBSERVATORY_EMBED_KEY_FILE") else EMBED_KEY_FILES)
    return _read_from(EMBED_KEY_ENV, files)


def embed(texts: list[str], log=print) -> dict:
    ""                                                                        

                                                                               
                                                                                   
                                                               

                                                                              
                                                                                
                                                                             
                                                                        
                                                                              
                                                                                
                                                                        
                                                       

                                                                            
                                                                               
                                                                               
                                                  
       
    import configuration
    if not configuration.enabled("embeddings", "features"):
        raise Fatal("Feature embeddings is not enabled for this workspace")
    cfg = config()["embedding"]
    if not texts:
        return {"vectors": [], "tokens": 0, "cost": 0.0, "model": cfg["model"]}
                                                                            
                                                               
    stop = check_budget(cfg["provider"])
    if stop:
        raise BudgetExceeded(stop)
    key, source = read_embed_key()
    if not key:
        raise Fatal(
            f"no embedding key. Looked in ${EMBED_KEY_ENV} and "
            + ", ".join(str(f) for f in EMBED_KEY_FILES)
            + f"\n  The estate already holds one; copy it in with:\n"
              f"    umask 077 && printf %s '<key>' > {EMBED_KEY_FILES[0]}")
    body = json.dumps({"model": cfg["model"], "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg['base_url']}/embeddings", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code in (401, 403):
            raise CredentialError(f"HTTP {exc.code}: {detail}") from exc
        if exc.code in (408, 409, 429) or exc.code >= 500:
            raise Retryable(f"HTTP {exc.code}: {detail}") from exc
        raise Fatal(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise Retryable(f"{type(exc).__name__}: {exc}") from exc

    vectors = [d["embedding"] for d in sorted(raw.get("data", []),
                                              key=lambda d: d.get("index", 0))]
    if len(vectors) != len(texts):
        raise Fatal(f"asked for {len(texts)} vectors, got {len(vectors)}")
    for v in vectors:
        if len(v) != cfg["dims"]:
            raise Fatal(
                f"the contract declares {cfg['dims']} dimensions and the provider returned "
                f"{len(v)}. Two writers into one vector column with different widths do not "
                f"fail — they degrade cosine search silently, so this refuses instead.")
    tokens = int((raw.get("usage") or {}).get("total_tokens") or 0)
                                                                              
                                                   
    cost = tokens * float(cfg["price_per_1m_tokens"]) / 1e6
    charge(f"{cfg['provider']}/{cfg['model']}", cost, tokens, 0, provider=cfg["provider"],
           estimated=True)
    return {"vectors": vectors, "tokens": tokens, "cost": cost, "model": cfg["model"],
            "key_source": source, "cost_is_estimate": True}


def read_key() -> tuple[str | None, str]:
    ""                                                            
    search = ((pathlib.Path(os.environ["OBSERVATORY_KEY_FILE"]),)
              if os.environ.get("OBSERVATORY_KEY_FILE") else KEY_FILES)
    return _read_from(KEY_ENV, search)


def have_key() -> bool:
    ""                                                       

                                                                         
                                                                              
                                                                            
                                                                               
                                                                            
                                                                               
           

                                                                             
                                                                                     
                                                                                  
                                                                                
                         
    try:
        key, _ = read_key()
    except Fatal:
        return False
    return bool(key)


def key_status() -> str:
    ""                                                                
    try:
        key, where = read_key()
    except Fatal as exc:
        return f"REFUSED — {exc}"
    if not key:
        places = "\n    ".join(f"${KEY_ENV}" if i == 0 else str(f)
                                for i, f in enumerate([None, *KEY_FILES]) if i or True)
        return (f"no key. Looked in:\n    ${KEY_ENV}\n    "
                + "\n    ".join(str(f) for f in KEY_FILES)
                + f"\n  Create one at https://openrouter.ai/keys, then:\n"
                  f"    umask 077 && printf %s '<key>' > {KEY_FILES[0]}")
    shape = f"{key[:9]}…{key[-4:]}" if len(key) > 16 else "…"
    return f"present ({shape}) from {where}"


def scheduled_key_status() -> str:
    ""                                                          

                                                                            
                                                                                  
                                                                             
                                                                             
                                                                                
                                                                              
                

                                                                               
                                                                                  
                                              
       
    import os as _os
    saved = {k: _os.environ.pop(k) for k in (KEY_ENV, "OPENAI_API_KEY")
             if k in _os.environ}
    try:
        return key_status()
    finally:
        _os.environ.update(saved)


def complete(messages: list[dict], *, schema_name: str, schema: dict,
             requested: str | None = None, log=print) -> dict:
    ""                                                                     

                                                                         
                                                                              
                                                    
       
    import configuration
    if not configuration.enabled("agent", "features"):
        raise Fatal("Feature agent is not enabled for this workspace")
    key, source = read_key()
    if not key:
        raise Fatal(f"no OpenRouter key. {key_status()}")
    log(f"  key from {source}")
    stop = check_budget()
    if stop:
        raise BudgetExceeded(stop)

    cfg = config()
    chain, level, provenance = resolve_chain(requested)
    log(f"  chain from {level} ({provenance}): "
        + ", ".join(f"{m['id']} ${m['price_in_per_1m']:.3f}/${m['price_out_per_1m']:.3f}"
                    for m in chain))

    budget_attempts = cfg.get("attempts", {}).get("total", 4)
    attempts, last_retryable = 0, None
    for model in chain:
        why_not = unhealthy(model["id"])
        if why_not:
            log(f"  skipping {model['id']}: marked unhealthy — {why_not}")
            continue
        if not needs_structured(model):
            log(f"  skipping {model['id']}: the catalogue says it has no structured_outputs")
            continue
        while attempts < budget_attempts:
            attempts += 1
            body = {
                "model": model["id"],
                "messages": messages,
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": schema_name, "strict": True,
                                                    "schema": schema}},
                                                                             
                                                                      
                "provider": {"require_parameters": True},
                "max_tokens": 2048,
            }
            try:
                raw = _post(cfg["base_url"], key, body)
            except Retryable as exc:
                last_retryable = exc
                log(f"  {model['id']} attempt {attempts}/{budget_attempts} retryable: {exc}")
                mark_unhealthy(model["id"], str(exc))
                break                                                                   
            except CredentialError:
                                                                              
                                                                             
                                               
                raise
            except Fatal as exc:
                mark_unhealthy(model["id"], str(exc))
                log(f"  {model['id']} fatal: {exc}")
                break

            usage = raw.get("usage") or {}
            cost = float(usage.get("cost") or 0.0)
            upstream = (usage.get("cost_details") or {}).get("upstream_inference_cost")
            tin = int(usage.get("prompt_tokens") or 0)
            tout = int(usage.get("completion_tokens") or 0)
            if cost == 0.0:
                                                                                 
                                                                              
                cost = estimate(model, tin, tout)
                log(f"  {model['id']}: no cost reported; estimated {cost:.6f} from the catalogue")
            stop = charge(model["id"], cost, tin, tout,
                          float(upstream) if upstream is not None else None)

            choices = raw.get("choices") or []
            if not choices:
                mark_unhealthy(model["id"], "no choices in the response")
                log(f"  {model['id']}: response carried no choices")
                break
            content = (choices[0].get("message") or {}).get("content") or ""
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                                                                            
                                                                      
                mark_unhealthy(model["id"], f"unparseable structured output: {exc}")
                log(f"  {model['id']}: structured output did not parse — {exc}")
                break
            mark_healthy(model["id"])
            return {"parsed": parsed, "model": model["id"], "cost": cost,
                    "tokens_in": tin, "tokens_out": tout, "attempts": attempts,
                    "finish_reason": choices[0].get("finish_reason"), "stop": stop,
                    "selection_level": level}
        if attempts >= budget_attempts:
            break
    if last_retryable:
        raise Retryable(f"every model in the chain failed; last: {last_retryable} "
                        f"({attempts} attempt(s) of {budget_attempts})")
    raise Fatal(f"no model in the chain could serve the request "
                f"({attempts} attempt(s) of {budget_attempts})")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Inspect the provider boundary.")
    ap.add_argument("what", choices=["chain", "wallet", "health", "refresh", "key"])
    a = ap.parse_args()
    if a.what == "refresh":
        models, prov = catalogue(refresh=True)
        print(f"catalogue {prov}: {len(models)} models")
    elif a.what == "chain":
        chain, level, prov = resolve_chain()
        print(f"selection level: {level} · catalogue {prov}\n")
                                                                              
                                                                              
                                                                          
        gone = (chain[0] if chain else {}).get("chain_retired") or []
        if gone:
            print(f"\033[33m{len(gone)} configured model(s) are NOT in the "
                  f"catalogue and were skipped: {', '.join(gone)}\033[0m")
            print("  The chain still works with what is left; check "
                  "agent/models.json against the provider.\n")
        for m in chain:
            flag = unhealthy(m["id"]) or ("ok" if needs_structured(m) else "NO structured_outputs")
            print(f"  {m['id']:<34} ${m['price_in_per_1m']:>7.3f}/${m['price_out_per_1m']:>7.3f} "
                  f"ctx {m['context_length']:>9,}  [{flag}]")
            if m.get("why"):
                print(f"      {m['why']}")
    elif a.what == "wallet":
        s = wallet_state()
        print(json.dumps(s, indent=1))
        print("guardrail:", check_budget() or "none — spending is permitted")
    elif a.what == "key":
        here = key_status()
        print(here)
                                                                              
                                                                                
                                                                                
                                                
        there = scheduled_key_status()
        if there != here:
            print(f"  the scheduled tick resolves a DIFFERENT key: {there}")
            print("  (launchd passes only HOME and PATH, so the shell's "
                  "variables are invisible to it — the tick is what spends)")
        else:
            print("  the scheduled tick resolves the same key")
                                                                            
                                                                                 
                                                                            
                                                                               
                                                                               
                                                                              
                                                         
        rows = shape_report()
        for r in rows:
            if r["verdict"] == "wrong":
                print(f"  ${r['env']}: WRONG SHAPE — {r.get('reason', '')}")
            else:
                article = "an" if r["provider"][0] in "AEIOU" else "a"
                print(f"  ${r['env']}: looks like {article} {r['provider']} key")
        if not rows:
            print("  no key variable is set in this environment — nothing to check")
        print(f"  recorded in {write_shape_report(rows)}")
    else:
        print(json.dumps(_health(), indent=1) or "no model marked unhealthy")
