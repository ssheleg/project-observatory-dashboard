import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import atomic
import estate
import identity
import paths
import configuration
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import local_scan
import scan_remotes
import json, re, subprocess, sys
from pathlib import Path
SP=Path(sys.argv[1]) if len(sys.argv)>1 else paths.SCRATCH; V=paths.VAULT
ownership_file = paths.config_file("ownership.json")
ownership = json.loads(ownership_file.read_text()) if ownership_file.is_file() else {}
for field in ("organizations", "work_organizations"):
    value = ownership.get(field, [])
    if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
        raise ValueError("Ownership organizations must be lists of non-empty names")
OWNED_ORGS = set(ownership.get("organizations", []))
WORK_ORGS = set(ownership.get("work_organizations", []))
degraded: list[dict] = []
OWNED_DOMAINS={d["name"] for d in json.load(open(paths.REGISTRY/"domains.json"))["domains"]}
                                                                          
                                                                                
                                                                               
                                                                      
                                                                              
                                                                          
                                                                           
try:
    ZONE_NAMES={z["name"] for z in json.load(open(paths.SCRATCH/"cloudflare_zones.json"))["zones"]}
except (OSError, ValueError, KeyError):
    ZONE_NAMES=set()
                                                                                      
try:
    CLAIMS={h.lower():c for h,c in json.load(open(paths.config_file('domain_claims.json')))["claims"].items()}
except (OSError, ValueError, KeyError):
    CLAIMS={}
THIRD_PARTY={"github.com","replit.com","stackblitz.com","twitter.com","lobehub.com",
             "getoutline.com","postiz.com","desktop.telegram.org","officialskills.sh",
             "leomehlig.github.io","t.me","help.crypt.bot"}
gh={}
for f in sorted((SP/"gh").glob("*.json")):
    if f.name.startswith("_"): continue
    for r in json.load(open(f)): gh.setdefault(r["nameWithOwner"], r)
                                                                              
                                                                           
                                                  
local={l["folder"]: l for l in local_scan.folders(SP/"local.json")}
if (SP / "vault.json").is_file():
    vault={v["folder"]: v for v in json.loads((SP / "vault.json").read_text())}
else:
    vault={}
    degraded.append({"source":"wiki", "reason":"wiki scan unavailable; project notes were not measured"})
if not gh:
    degraded.append({"source":"github", "reason":"no repository listing available; remote account coverage was not measured"})

def _optional(name, key, default):
    ""                                                                    

                                                                            
                                                                            
                                         
    f = SP/name
    if not f.is_file():
        degraded.append({"source":name, "reason":"optional collector output unavailable; not measured"})
        return default
    return json.loads(f.read_text()).get(key, default)

                                                                                
                                                                                
                                                                              
                                                    
SESSIONS={}
for _s in _optional("sessions.json", "sessions", []):
    _d = _s.get("ended_on") or _s.get("started_on") or ""
    if _d and _d > SESSIONS.get(_s["project_id"], ""):
        SESSIONS[_s["project_id"]] = _d

                                                                               
                                                                               
                                      
SESSIONS_BY_SLUG={k.split(":",1)[1]: v for k, v in SESSIONS.items()}

REMOTES=_optional("remotes.json", "repositories", {})
BB={r["full_name"]: r for r in _optional("bitbucket.json", "repositories", [])}
def nwo(remote):
    if not remote: return None
    m=re.search(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", remote)
    if m: return ("github", f"{m.group(1)}/{m.group(2)}")
    m=re.search(r"bitbucket\.org[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", remote)
    if m: return ("bitbucket", f"{m.group(1)}/{m.group(2)}")
    return None
                                    
repos={}
for k,r in gh.items():
    repos[k]={"key":k,"host":"github","owner":k.split("/")[0],"name":k.split("/")[1],
        "url":r["url"],"description":(r.get("description") or "").strip(),
        "homepage":(r.get("homepageUrl") or "").strip(),"visibility":r["visibility"].lower(),
        "archived":r["isArchived"],"fork":r["isFork"],
        "language":(r.get("primaryLanguage") or {}).get("name") or "",
        "pushed_at":(r.get("pushedAt") or "")[:10],"created_at":(r.get("createdAt") or "")[:10],
        "topics":[t["name"] for t in (r.get("repositoryTopics") or [])],
        "default_branch":(r.get("defaultBranchRef") or {}).get("name") or "",
        "local":None,"source":"github-api"}
                                                                            
                                                                                  
                                                                              
                                                             
                                                     

                                                                           
                                                                           
                                                                              
                                                                
                                                                                     
                                                                        
                                                                             
                                                    
  
                                                                               
                                                                             
                                                     
def _previous_transfers() -> dict:
    f = SP / "model.json"
    if not f.is_file():
        return {}
    try:
        return json.load(open(f)).get("transfers_followed") or {}
    except (ValueError, OSError):
        return {}

PREVIOUS_TRANSFERS = _previous_transfers()


def canonical(host: str, k: str) -> tuple[str, str | None, str]:
    ""                                                                          

                                                                               
                                                                            
                                                                                
                                                                        
                                                                          
                                                                                
                                                                                 
                                                    

                                                                              
                                                                            
                                                                                 
                                                                              
            
       
    if host != "github":
        return k, None, ""
    if not configuration.enabled("github"):
        return k, None, "GitHub integration disabled; repository transfer not checked"
    try:
        out = subprocess.run(["gh", "api", f"repos/{k}", "--jq", ".full_name"],
                             capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return k, None, "`gh` is not installed, so no transfer could be followed"
    except Exception as exc:
        return k, None, f"{type(exc).__name__}: {exc}"
    real = out.stdout.strip()
    if out.returncode != 0:
                                                                                 
                                                                                  
        err = (out.stderr or "").strip()[:120]
        if "Not Found" in err or "404" in err:
            return k, None, ""
        return k, None, f"`gh api repos/{k}` exited {out.returncode}: {err}"
    if not real or real == k:
        return k, None, ""
    return real, k, ""


moved: dict[str, str] = {}
unchecked: dict[str, str] = {}
for folder,l in local.items():
    if not l["is_git"]: continue
    hk=nwo(l.get("remote"))
    if not hk: continue
    host,k=hk
    if k not in repos:
        asked = k                                                                 
        real, was, why = canonical(host, k)
        if why:
                                                                           
                                                                                
                                                                               
                                                                              
            carried = PREVIOUS_TRANSFERS.get(asked)
            if carried:
                moved[asked] = carried
                k = carried
                degraded.append({"source": f"transfer:{asked}", "reason":
                    f"could not re-check whether {asked} has moved ({why}); using "
                    f"the previous run's answer, {asked} -> {carried}"})
            else:
                unchecked[asked] = why
                degraded.append({"source": f"transfer:{asked}", "reason":
                    f"could not check whether {asked} has moved ({why}), and no "
                    f"earlier run had answered. It is recorded as it stands: if "
                    f"the clone's remote is stale, this is a repository that does "
                    f"not exist"})
        elif was:
            moved[was] = real
            k = real
    if k not in repos:
        repos[k]={"key":k,"host":host,"owner":k.split("/")[0],"name":k.split("/")[1],
            "url":(f"https://github.com/{k}" if host=="github" else f"https://bitbucket.org/{k}"),
            "description":"","homepage":"","visibility":"unknown","archived":False,"fork":False,
            "language":"","pushed_at":"","created_at":"","topics":[],"default_branch":"","local":None,
            "source":"local-remote-only"}
    b=BB.get(k)
    if b and repos[k].get("source")=="local-remote-only":
                                                                             
                                                                
        repos[k].update(description=b.get("description") or "",
                        visibility="private" if b.get("is_private") else "public",
                        language=b.get("language") or "",
                        pushed_at=(b.get("updated_on") or "")[:10],
                        created_at=(b.get("created_on") or "")[:10],
                        default_branch=b.get("default_branch") or "",
                        source="bitbucket-api")
    rm=REMOTES.get(folder) or {}
    if rm.get("reachable") and not repos[k].get("default_branch"):
                                                                                
                                                                             
                                                                             
        repos[k]["default_branch"]=rm.get("default_branch") or ""
    lr={"folder":folder,"path":l["path"],"symlink":l["symlink"],"kinds":l["kinds"],
        "sync":rm.get("sync") if rm.get("reachable") else ("unreachable" if rm else ""),
                                                                                   
                                                                                    
                                                                                 
                                                                            
                                                                 
                                                                             
                                                              
        "remote_head":rm.get("remote_head",""),
        "remote_checked_on":(rm.get("checked_at") or "")[:10],
        "branch":l.get("branch",""),"last_commit":l.get("last_commit",""),
        "commits":int(l.get("commits") or 0),"dirty":l.get("dirty",0),
        "readme":l["readme"],"homepage_hits":l["homepage_hits"]}
                                                                              
                                                                             
                                                                                
                                                                        
                 
    for key, out_key in (("unpushed", "unpushed"), ("newest_on", "unpushed_newest_on"),
                         ("nothing_exclusive", "nothing_exclusive")):
        if rm.get(key) is not None:
            lr[out_key] = rm[key]
                                                                                 
                                                                               
                                                                             
                                                                             
                                         
     
                                                                               
                                                                               
                                                                                 
                                                                             
                                                           
     
                                                                             
                                                                            
                                                                                 
                                  
                                                                              
                                                                      
                                                                              
                                                                                
                                                                       
                                                                      
                                                                                
                                                                              
                                                                     
    if lr["sync"] in scan_remotes.AT_RISK_STATES and l.get("path"):
        fresh = scan_remotes.at_stake(pathlib.Path(l["path"]), lr["sync"], "",
                                      rm.get("branch_remote_sha") or
                                      lr.get("remote_head", ""),
                                      lr.get("branch", ""))
        if fresh:
                                                                               
                                                                               
                                                                             
                                                                  
                                                                         
                      
            for key, out_key in (("unpushed", "unpushed"),
                                 ("newest_on", "unpushed_newest_on"),
                                 ("nothing_exclusive", "nothing_exclusive")):
                lr.pop(out_key, None)
                if fresh.get(key) is not None:
                    lr[out_key] = fresh[key]
            lr["unpushed_recounted"] = True
    lr["worktree_of"]=l.get("worktree_of","")
                                                                      
                                                                             
                                                                                 
                                                                            
                                                                          
                                                                              
                                                                                 
                                                                            
                                                                             
                                                                             
                                                                                
    def demoted(rec):
        return {kk: rec.get(kk) for kk in
                ("folder","path","worktree_of","branch","sync","commits","dirty",
                 "last_commit")}
    if repos[k]["local"] is None:
        repos[k]["local"]=lr
    elif repos[k]["local"].get("worktree_of") and not lr.get("worktree_of"):
                                                                               
        repos[k].setdefault("extra_checkouts",[]).append(demoted(repos[k]["local"]))
        repos[k]["local"]=lr
    else:
        repos[k].setdefault("extra_checkouts",[]).append(demoted(lr))
                                                          
ORG_BY_LOWER={o.lower():o for o in OWNED_ORGS}
projects={}
                                                                              
                                                                               
                                                                             
             
slug = identity.slug
for folder,v in vault.items():
    projects[folder]={"key":slug(folder),"name":folder,"anchor":"vault-folder",
        "vault":{"folder":folder,"overview":v["overview"],"notes":v["note_count"],
                 "summary":v["summary"],"domains":v["domains"]},
        "repos":[],"rules":[],"sites":[]}
                                                                                
own_folder_of={}
for folder in vault:
    for k in repos:
        if repos[k]["name"]==folder or (repos[k]["local"] and repos[k]["local"]["folder"]==folder):
            own_folder_of[k]=folder
                                                                               
                                                                                 
                                                                             
                                                                              
                                                                              
                                                                              
                                                                          
SUBMODULES = {f: {s["nwo"]: s["path"] for s in (l.get("submodules") or []) if s.get("nwo")}
              for f, l in local.items()}

for folder,v in vault.items():
    p=projects[folder]
    for k in repos:
        if own_folder_of.get(k) not in (None, folder): continue
        why=None
        sub = SUBMODULES.get(folder, {})
        if k in sub: why=f"git submodule at {sub[k]}"
        elif k in v["github"] or k in v["bitbucket"]: why="named in vault notes"
        elif repos[k]["local"] and repos[k]["local"]["folder"]==folder: why="local folder name"
        elif repos[k]["name"]==folder: why="repository name"
        elif ORG_BY_LOWER.get(folder.lower())==repos[k]["owner"]: why="organisation"
        elif repos[k]["local"] and repos[k]["local"]["folder"] in v.get("datapaths",[]): why="DATA/ path in vault notes"
        if why: p["repos"].append(k); p["rules"].append(f"{k}: {why}")
DENIED={(d["project"], d["repo"]) for d in
        json.load(open(paths.config_file('denied_links.json')))["denied"]}
for folder,p in projects.items():
    dropped=[k for k in p["repos"] if (folder, k) in DENIED]
    for k in dropped:
        p["repos"].remove(k)
        p["rules"]=[r for r in p["rules"] if not r.startswith(f"{k}:")]
        print(f"  denied by the operator: {folder} does not hold {k}")
                                                                                    
                                                                                    
                                                                                   
                                                                                     
                                                                                     
      
INACTIVE = {k for k, v in json.load(
    open(paths.config_file('repo_status.json')))["repositories"].items()
    if v.get("status") == "inactive"}

VER=json.load(open(paths.config_file('verified_links.json')))["links"]

def apply_verified_links():
    ""                                                                       

                                                                        
                                                                               
                                                                              
                                                                            
                                                                         
                                                                            
                                                              
       
    for L in VER:
        p=projects.get(L["project"])
        if not p or L["repo"] not in repos or L["repo"] in p["repos"]: continue
        p["repos"].append(L["repo"]); p["rules"].append(f'{L["repo"]}: verified — {L["evidence"]}')
                                                                        
                                                                              
                                              
        victim=projects.get(L["repo"])
        if victim is not None and victim is not p and victim["repos"]==[L["repo"]]:
            del projects[L["repo"]]

apply_verified_links()
assigned={k for p in projects.values() for k in p["repos"]}
                                 
orgs_with_project={repos[k]["owner"] for p in projects.values() for k in p["repos"]}
from collections import defaultdict
left=defaultdict(list)
for k,r in repos.items():
    if k in assigned: continue
    left[r["owner"]].append(k)
for owner,ks in sorted(left.items()):
                                                                                
                                                                                
                                                                               
                                                                            
                                                                           
                                                                             
                                                                              
                                                   
    ks = [k for k in ks if k not in INACTIVE]
    if owner not in orgs_with_project and owner in OWNED_ORGS and len(ks)>1:
        projects[owner]={"key":slug(owner),"name":owner,"anchor":"organisation",
            "vault":None,"repos":sorted(ks),"rules":[f"{k}: organisation with no vault note" for k in ks],"sites":[]}
    else:
                                                                                  
                                                                            
        for k in ks:
            projects[k]={"key":slug(k.replace("/","-")),"name":repos[k]["name"],"anchor":"repository",
                "vault":None,"repos":[k],"rules":[f"{k}: standalone repository"],"sites":[]}
apply_verified_links()                                                      
                                                           
                                                                             
                                                                            
                                                                           
                                                                               
                                                                             
                                                                      
                                                                              
                                                                               
                                                  
                                             
_EXCL=json.load(open(paths.config_file('folder_exclusions.json')))
EXCLUDED_PREFIXES=tuple(x["prefix"] for x in _EXCL["prefixes"])
EXCLUDED_NAMES={x["name"] for x in _EXCL["names"]}
for folder,l in local.items():
    if folder.startswith(EXCLUDED_PREFIXES) or folder in EXCLUDED_NAMES: continue
    if l["is_git"] and nwo(l.get("remote")): continue                                
    rule = (f"{folder}: git repository with no remote, local only"
            if l["is_git"] else f"{folder}: local folder, not a git repository")
    projects["local:"+folder]={"key":identity.local_key(folder),"name":folder,"anchor":"local-folder",
        "vault":None,"repos":[],"rules":[rule],"sites":[],
                                                                              
                                                                              
                                                                              
                                                                      
                                                                           
                                                                                 
                                                                      
        "local_only":{"folder":folder,"path":l["path"],"kinds":l["kinds"],"unpublished":l["is_git"],
                      "commits":int(l.get("commits") or 0),"branch":l.get("branch","") or "",
                      "last_commit":l.get("last_commit","") or "","dirty":int(l.get("dirty") or 0),
                      "readme":l["readme"],"files":l.get("file_count",0),"mtime":l.get("mtime","")}}
                                               
def host_of(u):
    u=(u or "").strip().lower(); u=re.sub(r"^https?://","",u); u=re.sub(r"^www\.","",u)
    return u.split("/")[0].rstrip(".").rstrip("/")
def registrable(h):
    parts=h.split(".")
    for i in range(len(parts)-1):
        cand=".".join(parts[i:])
        if cand in OWNED_DOMAINS: return cand
    return None
for key,p in projects.items():
    cand={}
    my_id=identity.project_id(key)
    for k in p["repos"]:
        r=repos[k]
        if r["homepage"] and not r["fork"]:
            h=host_of(r["homepage"])
            if h and h not in THIRD_PARTY: cand.setdefault(h,[]).append(f"github:{k}:homepageUrl")
        if r["local"]:
            for src,val in r["local"]["homepage_hits"]:
                h=host_of(val)
                if not h or h in THIRD_PARTY: continue
                                                                               
                                                                                
                if src.startswith(("env:","nginx:")) and not (registrable(h) or ".".join(h.split(".")[-2:]) in ZONE_NAMES):
                    continue
                cand.setdefault(h,[]).append(f"repo-config:{r['local']['folder']}/{src}")
    if p["vault"] and p["vault"]["overview"]:
        try: ov=(V/p["vault"]["overview"]).read_text(encoding="utf-8",errors="replace")
        except Exception: ov=""
        for d in p["vault"]["domains"]:
            if re.search(r"(?<![\w.-])"+re.escape(d)+r"(?![\w-])", ov):
                cand.setdefault(d,[]).append(f"vault-overview:{p['vault']['overview']}")
                                                                               
                                                                           
                                                                          
                                                                             
    for h,claim in CLAIMS.items():
        if claim.get("project")==my_id:
            cand.setdefault(h,[]).append(f"operator-claim:{claim.get('why','')[:80]}")
    for h,ev in sorted(cand.items()):
        reg=registrable(h)
        p["sites"].append({"host":h,"owned_domain":reg,
            "confidence":"registry-confirmed" if reg else "declared-not-in-registry",
            "evidence":sorted(set(ev))})
                                                   
for p in projects.values():
    desc=""; src=""
    if p["vault"] and p["vault"]["summary"]:
        desc, src = p["vault"]["summary"], "vault-overview"
    if not desc and p["anchor"]!="organisation":
        for k in p["repos"]:
            if repos[k]["description"]: desc, src = repos[k]["description"], f"github:{k}"; break
    if not desc and p["anchor"]!="organisation":
        for k in p["repos"]:
            if repos[k]["local"] and repos[k]["local"]["readme"]:
                desc, src = repos[k]["local"]["readme"], f"readme:{repos[k]['local']['folder']}"; break
    if not desc and p.get("local_only") and p["local_only"]["readme"]:
        desc, src = p["local_only"]["readme"], f"readme:{p['local_only']['folder']}"
    p["description"]=desc.strip(); p["description_source"]=src
    dates=[repos[k]["pushed_at"] for k in p["repos"] if repos[k]["pushed_at"]]
    dates+= [repos[k]["local"]["last_commit"] for k in p["repos"] if repos[k]["local"] and repos[k]["local"]["last_commit"]]
    if p.get("local_only") and p["local_only"]["mtime"]: dates.append(p["local_only"]["mtime"])
                                                                      
                                                                                   
                                                                              
                                                                           
                                                                               
    if p.get("local_only") and p["local_only"].get("last_commit"):
        dates.append(p["local_only"]["last_commit"])
                                                                               
                                                                                  
                                                                                
                                                                         
                                                                          
                                                
                                                                              
                                                                           
                                                                            
                                                                               
                                                                               
    _sess = SESSIONS.get(f"project:{p['key']}") or SESSIONS_BY_SLUG.get(p["key"], "")
    if _sess: dates.append(_sess)
    p["last_activity"]=max(dates) if dates else ""
    p["last_session_on"]=_sess or ""
    p["folders"]=sorted({repos[k]["local"]["folder"] for k in p["repos"] if repos[k]["local"]}
                        | ({p["local_only"]["folder"]} if p.get("local_only") else set()))
    kinds=set()
    for k in p["repos"]:
        if repos[k]["local"]: kinds|=set(repos[k]["local"]["kinds"])
    if p.get("local_only"): kinds|=set(p["local_only"]["kinds"])
    p["kinds"]=sorted(kinds)
    owners={repos[k]["owner"] for k in p["repos"]}
    p["owner"]=sorted(owners)[0] if len(owners)==1 else ("multi" if owners else "—")
    p["owners"]=sorted(owners)
    p["ownership"]=("owned" if owners and owners<=OWNED_ORGS else
                    "work-bitbucket" if owners and owners <= WORK_ORGS else
                    "external" if owners else "local-only")
    p["archived"]=bool(p["repos"]) and all(repos[k]["archived"] for k in p["repos"])
    p["dirty"]=sum(repos[k]["local"]["dirty"] for k in p["repos"] if repos[k]["local"])
    p["has_note"]=bool(p["vault"])
dups={}
for k,r in repos.items(): dups.setdefault(r["name"].lower(),[]).append(k)
duplicates=sorted([v for v in dups.values() if len(v)>1], key=lambda v:v[0])
                                                                              
                                                                                   
                                                                            
                                                                                 
                                                                               
                                                                               
                                                                         
                                                                                
 
                                                                                
                                                                       
_discovered={r["owner"] for r in repos.values() if r["host"]=="github"}
_undeclared=sorted(o for o in _discovered if o not in OWNED_ORGS
                   and any(k in gh for k in repos if repos[k]["owner"]==o))
if _undeclared:
                                                                               
                                                                              
                                                                                
                                                              
    _und_repos = [k for k, r in repos.items() if r["owner"] in _undeclared]
    _und_cloned = sum(1 for k in _und_repos if repos[k]["local"])
    degraded.append({"source": "ownership",
                     "reason": estate.undeclared_owner_reason(
                         _undeclared, len(_und_repos), _und_cloned)})
    print(f"  UNDECLARED owner(s): {', '.join(_undeclared)} — reported as external"
          f" ({_und_cloned} of {len(_und_repos)} cloned here)")

out={"repositories":repos,"projects":{p["key"]:p for p in projects.values()},
     "duplicate_repo_names":duplicates,"degraded":degraded}
if moved:
    print(f"followed {len(moved)} transfer(s) — a clone still pointed at the old address:")
    for was, real in sorted(moved.items()):
        print(f"  {was} -> {real}")
out["transfers_followed"] = moved
                                                                             
                                                                             
                                                                                
                                                                          
                                                                            
                                                                          
                                       
out["stale_remotes"] = [
    {"was": was, "now": real,
     "folder": (repos.get(real, {}).get("local") or {}).get("folder", ""),
     "path": (repos.get(real, {}).get("local") or {}).get("path", "")}
    for was, real in sorted(moved.items())]
out["transfers_unchecked"] = unchecked
atomic.write_json(SP / "model.json", out)
if degraded:
    print(f"degraded: {len(degraded)} source(s)")
    for d in degraded:
        print(f"  {d['source']}: {d['reason'][:120]}")
P=out["projects"]
print(f"projects={len(P)}  repositories={len(repos)}")
from collections import Counter
print("anchor:",dict(Counter(p["anchor"] for p in P.values())))
print("ownership:",dict(Counter(p["ownership"] for p in P.values())))
print("with site:",sum(1 for p in P.values() if p["sites"]),
      "| registry-confirmed:",sum(1 for p in P.values() if any(s["confidence"]=="registry-confirmed" for s in p["sites"])))
print("with vault note:",sum(1 for p in P.values() if p["has_note"]),
      "| with local folder:",sum(1 for p in P.values() if p["folders"]))
print("duplicate repo names:",duplicates)
print("\nmulti-repo projects:")
for p in sorted(P.values(),key=lambda x:-len(x["repos"])):
    if len(p["repos"])>1: print(f'  {p["name"]:<34} {len(p["repos"]):>2} repos  {", ".join(p["repos"][:6])}{" …" if len(p["repos"])>6 else ""}')
