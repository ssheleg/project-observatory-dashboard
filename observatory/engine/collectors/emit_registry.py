import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import activity
import paths
import identity
import json, os, sys
from pathlib import Path
SP=Path(sys.argv[1]) if len(sys.argv)>1 else paths.SCRATCH; INV=paths.REGISTRY
M=json.load(open(SP/"model.json")); repos=M["repositories"]; projs=M["projects"]
ID_OVERRIDE=identity.ID_OVERRIDE                                        
OVERRIDES=json.load(open(paths.config_file('project_overrides.json')))["projects"]
REPO_STATUS=json.load(open(paths.config_file('repo_status.json')))["repositories"]
REPO_OVERRIDES=json.load(open(paths.config_file('repo_overrides.json')))["repositories"]
import atomic
import datetime as _dt


def _stamped(name, doc, stamps=("updated_on",)):
    ""                                                                        

                                                   

                                                                           
                                                                                
                                                                                 
                                                                           
                                                                              
                                                                                
                                              
                                                           

                                                                           
                                                      
       
    _, changed = atomic.write_json_carrying(
        INV / name, doc, stamps=stamps, now=OBS, indent=2)
    if changed:
        _CHANGED.append(name)
    return changed


_CHANGED: list[str] = []


def pid(key): return identity.project_id(key)
old_projects={p["id"]:p for p in json.load(open(INV/"projects.json"))["projects"]}
old_repos={r["id"]:r for r in json.load(open(INV/"repositories.json"))["repositories"]}
rel_doc=json.load(open(INV/"relations.json")); old_rel={r["id"]:r for r in rel_doc["relations"]}
src_doc=json.load(open(INV/"sources.json")); sources=src_doc["sources"]
have={s["id"] for s in sources}
                                                                         
                                                                          
                                                                     
                                                                                 
                                                                           
                                                                         
                                      
 
                                                                            
                                                                         
                                                         
OBS=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
                                                                          
                                                                               
                                                                          
                                                                              
                                                                     
                                                                                
                                                      
NEW_SOURCES = [
    ("SRC-0007", "Filesystem scan of the configured project roots: folder list, git remotes, checked-out branch, commit counts, project-type markers, README opening paragraph, CNAME/wrangler/package.json homepage fields.", []),
    ("SRC-0008", "GitHub REST/GraphQL listing via `gh repo list` for the explicitly connected account and its accessible organizations: name, description, homepageUrl, visibility, archived, fork, language, default branch, pushedAt.", []),
    ("SRC-0009", "Obsidian vault project notes: folder inventory, overview summary, GitHub/Bitbucket references and DATA/ paths quoted inside the notes.", []),
    ("SRC-0010", "`git ls-remote --symref` against each checkout's own remote, over the SSH keys that already clone it — no API credential involved. Answers whether a local clone is current, behind, ahead or on a branch that exists nowhere else, and the remote's default branch where no API reports one.", ["local.sync", "local.remote_head", "local.remote_checked_on"]),
    ("SRC-0012", "claude-mem's own store at ~/.claude-mem/claude-mem.db, read read-only: one row per (session, project) from `session_summaries`, attributed to a project by local folder name, id slug, project name, or the first path segment of a nested name. Answers WHERE WORK WAS DONE, which the git sources cannot: every other activity date here is a commit or an mtime, so a project worked on without a commit read as silent and `activity_tier` called it cooling on that silence.", ["last_session_on"]),
    ("SRC-0014", "The machine's credential surfaces, read for METADATA only and never for values: OpenRouter's provisioning listing (name, the provider's own label, limit, usage, reset, disabled), tools/vault.py's slot paths and meta.json beside each value, and its leaks.jsonl register. Answers WHAT CREDENTIALS EXIST, WHICH PROJECTS MAY USE THEM and WHAT HAS LEAKED AND NOT BEEN ROTATED.", ["registry:credentials.json"]),
    ("SRC-0013", "Heroku Platform API v3 through the CLI's own session token (`heroku auth:token`, never stored): every application the account and its teams can see, with its formation, dynos, add-ons and release history, plus the Deploy tab\'s GitHub link from kolkrabbi. Answers WHERE A PROJECT IS RUNNING and what leaving it running costs — a fact no other source here holds.", ["registry:heroku-apps.json"]),
    ("SRC-0015", "Every `.env` under ~/DATA, read by collectors/scan_env.py for NAMES and never for values: the file, its project, its mode, its git state, and each variable\'s name and class. The value is read to decide the class and then dropped; the one derivation that survives it is a salted fingerprint kept in the gitignored scan, which is what lets `shared_with` be MEASURED rather than declared. Answers WHAT EACH PROJECT HOLDS LOCALLY, WHAT BREAKS IF A VALUE IS ROTATED and WHERE AN EMPTY SLOT COULD BE FILLED FROM.", ["registry:env-inventory.json"]),
    ("SRC-0016", "Cloudflare zone listings through the narrow tokens `tools/cloudflare.py` issues (Zone Read, one per account), joined at emit time to the domain registry, the projects' sites and the operator's boundary and claim files; and the operator's curated product groupings in collectors/products.json with the groupings suggested from shared registrable domains. Answers WHICH DOMAINS THE ESTATE HOLDS, whose surface each is, and what several projects are one product.", ["registry:cloudflare-zones.json", "registry:products.json"]),
    ("SRC-0017", "The MCP declarations in each agent's own config (~/.claude.json with its project scopes, ~/.cursor/mcp.json, ~/.config/opencode/opencode.json) plus what `claude mcp list` reports for plugins and claude.ai connectors — read for names, transports, targets without query strings and the PRESENCE of a key, never a value. Answers WHICH MCP SERVERS THE AGENTS ARE TOLD TO REACH and whether Claude reached them.", ["registry:mcp-servers.json"]),
    ("SRC-0018", "Heroku\'s config-vars endpoint through the same CLI session token, read by collectors/scan_remote_env.py: the endpoint answers with names AND values in one object and has no names-only form, so the values are TRANSIT — classified, fingerprinted with the machine-local salt collectors/scan_env.py uses, and dropped. The fingerprints stay in the gitignored scan beside the vault\'s own retired-value fingerprints; the document built from them carries only the verdict. Answers WHAT PRODUCTION IS CONFIGURED WITH, whether it matches this machine, and whether a value the vault has already rotated away is still deployed.", ["registry:remote-env.json"]),
    ("SRC-0019", "Google Analytics Admin and Data APIs, and Search Console, through the service accounts in the machine\'s secret store: every account and property the credential can see, each property\'s own declared web hosts and app bundle ids, thirty days of active users, sessions and views, and the Search Console sites. The credential signs a JWT and never leaves the collector; what is recorded is the account\'s public `client_email`. Answers WHICH PRODUCTS PEOPLE ACTUALLY USE, and joins each property to a project by what the property declares about itself rather than by a hand-written map.", ["registry:google-properties.json"]),
    ("SRC-0011", "Public DNS through `dig`, HTTP reachability through `curl`, and registrar records through RDAP at rdap.org. Answers whether a host resolves and answers, and what a registry says about a domain — measured, never transcribed.", ["registry:domain-liveness.json"]),
]
SOURCE_INPUTS = {"SRC-0007": SP / "local.json", "SRC-0008": SP / "gh",
    "SRC-0009": SP / "vault.json", "SRC-0010": SP / "remotes.json",
    "SRC-0011": SP / "domains_live.json", "SRC-0012": SP / "sessions.json",
    "SRC-0013": SP / "heroku.json", "SRC-0014": SP / "openrouter.json",
    "SRC-0015": SP / "env.json", "SRC-0016": SP / "cloudflare_zones.json",
    "SRC-0017": SP / "mcp.json", "SRC-0018": SP / "remote-env.json",
    "SRC-0019": SP / "google.json"}
def source_available(sid):
    path = SOURCE_INPUTS.get(sid)
    return bool(path and (path.is_file() or (path.is_dir() and any(p.is_file() and not p.name.startswith("_") for p in path.glob("*.json")))))
for sid, desc, evidence in NEW_SOURCES:
    if sid not in have:
        rec = {"id": sid, "kind": "agent-measurement", "observed_on": OBS if source_available(sid) else None, "description": desc, "availability": "measured-input" if source_available(sid) else "not-measured"}
        if evidence:
            rec["evidence_for"] = evidence
        sources.append(rec)
    elif evidence:
                                                                             
                                                                        
        for s in sources:
            if s["id"] == sid and s.get("evidence_for") != evidence:
                s["evidence_for"] = evidence
                                                                  
for record in sources:
    if record.get("id") in SOURCE_INPUTS:
        available = source_available(record["id"])
        record["availability"] = "measured-input" if available else "not-measured"
        if available and not record.get("observed_on"):
            record["observed_on"] = OBS
                                                                               
                                                                               
                                                                                 
                                                      
SRC=[sid for sid in ("SRC-0007","SRC-0008","SRC-0009") if source_available(sid)]
                        
out_repos=[]; cleared_repos: list[str] = []
for k in sorted(repos):
    r=repos[k]; rid="repository:"+k; prev=old_repos.get(rid,{})
    e={"id":rid,"host":r["host"],"name_with_owner":k,
       "url":r["url"],"visibility":r["visibility"],
                                                                              
                                                                              
                                                                                
                                                                               
                                                                                 
                                                    
       "default_branch":r.get("default_branch") or prev.get("default_branch",""),
                                                                             
                                                                       
                                                                           
                                                                                 
                                                                      
                                                                               
                                         
       "description":r["description"] or "",
       "archived":r["archived"],"fork":r["fork"],"language":r["language"],
       "topics":r["topics"],"last_pushed_on":r["pushed_at"],"created_on":r["created_at"],
       "discovered_by":r["source"],
       "source_refs":sorted({"SRC-0008" if r["source"]=="github-api" else "SRC-0007"})}
    st = REPO_STATUS.get(k)
    if st:
        e["status"] = st["status"]
        e["status_evidence"] = st["evidence"]
        e["status_measured_on"] = st.get("measured_on")
                                                                                   
                                                                             
                                                                                 
                                                                           
        for field in ("superseded_by", "moved_to"):
            if st.get(field):
                e[field] = st[field]
    if r["local"]:
        e["local"]={"path":r["local"]["path"],"folder":r["local"]["folder"],
                    "symlink":r["local"]["symlink"],"checked_out_branch":r["local"]["branch"],
                    "commits":r["local"]["commits"],"last_commit_on":r["local"]["last_commit"],
                    "uncommitted_files":r["local"]["dirty"],"stack":r["local"]["kinds"]}
                                                                                
                                                                                
                                    
                                                                                 
                                                                                   
                                                                                 
                                                         
        for k_, v_ in (("sync", r["local"].get("sync")),
                       ("remote_head", r["local"].get("remote_head")),
                       ("remote_checked_on", r["local"].get("remote_checked_on")),
                       ("unpushed", r["local"].get("unpushed")),
                       ("unpushed_newest_on", r["local"].get("unpushed_newest_on")),
                       ("nothing_exclusive", r["local"].get("nothing_exclusive")),
                                                                           
                                                                           
                                                                             
                                                                               
                                    
                       ("unpushed_recounted", r["local"].get("unpushed_recounted"))):
            if v_: e["local"][k_]=v_
                                                                               
                                                                                
                                                                               
                                                                                 
                                                                                  
                                                                                 
                                                              
        if r.get("extra_checkouts"):
            xs=r["extra_checkouts"]
            e["local"]["extra_clones"]=[x["folder"] for x in xs]
            e["local"]["extra_checkouts"]=[{kk:vv for kk,vv in x.items()
                                            if vv not in (None,"")} for x in xs]
        e["source_refs"]=sorted(set(e["source_refs"])|{"SRC-0007"})
                                                                   
                                                                                
                                                                                
                                       
        if any(e["local"].get(f) for f in ("sync", "remote_head", "remote_checked_on")):
            e["source_refs"]=sorted(set(e["source_refs"])|{"SRC-0010"})
                                                                                
                                                              
    if e.get("default_branch") and r["host"]=="bitbucket.org":
        e["source_refs"]=sorted(set(e["source_refs"])|{"SRC-0010"})
    rov=REPO_OVERRIDES.get(k)
    if rov:
        for ck,cv in rov.items():
            if ck=="why": continue
                                                                                
                                                                             
                                                                                 
                                                                              
                                                                              
                                                         
            e[ck]=sorted(set(e.get(ck) or [])|set(cv)) if ck=="source_refs" else cv
        e["curated_fields"]=sorted(ck for ck in rov if ck!="why")
    for field in ("description","default_branch"):
        if prev.get(field) and not e.get(field):
            cleared_repos.append(f"{rid}.{field} was {str(prev[field])[:40]!r}, measurement says nothing")
    out_repos.append(e)
                    
                                                                            
                                                                             
                                                                            
                                                                                
                                                   
DERIVED_TYPES = {"implemented_by", "public_domain_of", "deployed_to", "credential_used_by", "part_of"}
authored = [r for r in rel_doc["relations"] if r["type"] not in DERIVED_TYPES]
stale = len(rel_doc["relations"]) - len(authored)
if stale:
    print(f"rebuilding {stale} derived relation(s) from the model; "
          f"keeping {len(authored)} authored one(s)")
out_projs=[]; relations=list(authored); seen_rel={r["id"] for r in relations}
seen_edge={(r["type"],r["from"],r["to"]) for r in relations}
def add_rel(rid,typ,frm,to,refs):
    if rid in seen_rel or (typ,frm,to) in seen_edge: return
    relations.append({"id":rid,"type":typ,"from":frm,"to":to,"source_refs":refs})
    seen_rel.add(rid); seen_edge.add((typ,frm,to))
cleared: list[str] = []
for key in sorted(projs):
    p=projs[key]; i=pid(key); prev=old_projects.get(i,{})
                                                                                 
                                                                        
                                                                                   
                                                                             
                                                                                 
                                                                                
                                                                                   
                                                                               
                                   
     
                                                                         
                                                                          
                                                                                 
                                                                                  
                                                                           
                                
    e={"id":i,"name":p["name"],"anchor":p["anchor"],"ownership":p["ownership"],
       "owners":p["owners"],"lifecycle":"archived" if p["archived"] else "active",
       "description":p["description"] or "",
       "stack":p["kinds"],"local_folders":p["folders"],"last_activity_on":p["last_activity"],
                                                                                 
                                                                                 
                                                                  
       "activity_tier":activity.tier_of(p["last_activity"]),
       "has_vault_note":p["has_note"],"description_source":p.get("description_source",""),
       "membership_rules":p["rules"],
       "source_refs":sorted(SRC)}
                                                                                
                                                                          
                                                                                
    if p.get("last_session_on"):
        e["last_session_on"]=p["last_session_on"]
        e["source_refs"]=sorted(set(e["source_refs"])|{"SRC-0012"})
    cp=("vault:"+p["vault"]["overview"]) if p["vault"] else None
    if cp and cp.startswith("../"): cp="vault:"+cp[3:]                                             
    if cp and (paths.VAULT/cp.split(":",1)[1]).exists(): e["canonical_page"]=cp
    if p["vault"]: e["vault_notes"]=p["vault"]["notes"]
    ov=OVERRIDES.get(i)
    if ov:
        for k,v in ov.items():
            if k=="why": continue
            e[k]=sorted(set(e.get(k) or [])|set(v)) if k=="source_refs" else v
        e["curated_fields"]=sorted(k for k in ov if k!="why")
    if p["sites"]: e["sites"]=p["sites"]
    if p.get("local_only"): e["local_only"]=p["local_only"]
                                                                              
                                                                                
                                                                             
                                                                                 
                                  
    for field in ("lifecycle","description","canonical_page"):
        had, has = prev.get(field), e.get(field)
        if had and not has:
            cleared.append(f"{i}.{field} was {str(had)[:40]!r}, measurement says nothing")
    out_projs.append(e)
    for k in p["repos"]:
        add_rel(f"relation:{key}:implemented-by:{k}".replace("/","-"),"implemented_by",i,"repository:"+k,SRC)
    for s in p["sites"]:
        if s["confidence"]=="registry-confirmed":
            add_rel(f"relation:{s['owned_domain']}:public-domain-of:{key}","public_domain_of",
                    "domain:"+s["owned_domain"],i,SRC)
                                                                           
                                                                                
                                                                               
                                                                                  
                                                                                
                                                                                
            
 
                                                                                
                                                                                    
                                                                                  
                
 
                                                                                 
                                                                                
                       
def _bulk_refusal() -> str:
    import os as _os
    if _os.environ.get("OBSERVATORY_ALLOW_BULK"):
        return ""
    limit = 0.25
    for name, key, new in (("projects.json", "projects", out_projs),
                           ("repositories.json", "repositories", out_repos)):
        f = INV / name
        if not f.is_file():
            continue
        try:
            was = len(json.loads(f.read_text(encoding="utf-8"))[key])
        except (ValueError, OSError, KeyError):
            continue
        if not was:
            continue
        change = (len(new) - was) / was
        if abs(change) > limit:
            return (f"{name} would go from {was} to {len(new)} "
                    f"({change:+.0%}, limit ±{limit:.0%}). A swing this size is a "
                    f"collector failure far more often than it is real work — a "
                    f"missing `git` alone accounts for +32% of projects. Nothing "
                    f"was written. If the change is genuine, re-run with "
                    f"OBSERVATORY_ALLOW_BULK=1.")
    return ""

_refusal = _bulk_refusal()
if _refusal:
    print(f"emit REFUSED: {_refusal}", file=sys.stderr)
    raise SystemExit(1)

_stamped("projects.json", {"schema_version":2,"updated_on":OBS,"projects":out_projs,"degraded":M.get("degraded",[])})
_stamped("repositories.json", {"schema_version":2,"updated_on":OBS,"repositories":out_repos,"degraded":M.get("degraded",[])})
                                                                              
                                                                               
                                                                                 
                                                    
                                                                              
                                                                          
                                                                       
                                                                            
                                                                           
                                                     
                                                                             
                                                                                
                                                                        
                                                                             
                                                                             
                  
HEROKU_SRC = paths.SCRATCH / "heroku.json"
heroku_apps: list = []
if HEROKU_SRC.is_file():
    import heroku_registry
    _scan = json.loads(HEROKU_SRC.read_text(encoding="utf-8"))
    heroku_apps, _edges = heroku_registry.records(_scan, out_projs, out_repos, relations)
    for e in _edges:
        add_rel(e["id"], e["type"], e["from"], e["to"], e["source_refs"])
    _doc = heroku_registry.document(_scan, heroku_apps, OBS)
    _stamped("heroku-apps.json", _doc)
    _t = _doc["totals"]
    print(f"heroku-apps.json: {_t['apps']} app(s), {_t['linked_to_a_project']} linked, "
          f"{_t['unlinked']} unlinked, ${_t['monthly_cost']}/month")
                                                                           
                                                                             
                                                                             
    import estate_surfaces as _es
    _owned_now = {d["name"] for d in json.load(open(INV/"domains.json"))["domains"]}
    _by_id = {p["id"]: p for p in out_projs}
    _added = 0
    for _pid, _hosts in _es.heroku_site_hints(_scan.get("apps") or [], heroku_apps).items():
        _proj = _by_id.get(_pid)
        if not _proj:
            continue
        for _h, _ev in _hosts.items():
            _hit = next((s for s in _proj.setdefault("sites", []) if s["host"] == _h), None)
            if _hit:
                if _ev not in _hit.get("evidence", []):
                    _hit.setdefault("evidence", []).append(_ev)
                continue
            _reg = _es.registrable(_h, _owned_now)
            _proj["sites"].append({"host": _h, "owned_domain": _reg,
                                   "confidence": "registry-confirmed" if _reg else "declared-not-in-registry",
                                   "evidence": [_ev]})
            if _reg:
                add_rel(f"relation:{_reg}:public-domain-of:{_pid.split(':',1)[1]}",
                        "public_domain_of", "domain:"+_reg, _pid, SRC)
            _added += 1
    if _added:
        print(f"  heroku domains: {_added} host(s) joined to projects through their apps")

                                                                             
                                                                                
                                                                            
                                                                            
import estate_surfaces
_domains_now = json.load(open(INV/"domains.json"))["domains"]
                                                                               
                              
MCP_SRC = paths.SCRATCH / "mcp.json"
if MCP_SRC.is_file():
    _mscan = json.loads(MCP_SRC.read_text(encoding="utf-8"))
    _mrows = estate_surfaces.mcp_rows(_mscan)
    _mdoc = estate_surfaces.mcp_document(_mscan, _mrows, OBS)
    _stamped("mcp-servers.json", _mdoc)
    _mt = _mdoc["totals"]
    print(f"mcp-servers.json: {_mt['declarations']} declaration(s), {_mt['distinct_servers']} "
          f"server(s), " + ", ".join(f"{k} {v}" for k, v in sorted(_mt['by_liveness'].items()))
          + (f", {_mt['key_in_url']} with a key in the URL" if _mt['key_in_url'] else ""))
_pdoc, _pedges, _perrors = estate_surfaces.products_document(out_projs, _domains_now, OBS)
if _perrors:
                                                                          
                                                                               
    sys.exit("collectors/products.json refused:\n  " + "\n  ".join(_perrors))
for e in _pedges:
    add_rel(e["id"], e["type"], e["from"], e["to"], e["source_refs"])
    relations[-1]["role"] = e["role"]
_stamped("products.json", _pdoc)
products_doc = _pdoc
print(f"products.json: {_pdoc['totals']['curated']} curated, "
      f"{_pdoc['totals']['suggested']} suggested, "
      f"{_pdoc['totals']['projects_grouped']} project(s) grouped")
for _dg in _pdoc.get("degraded") or []:
    print(f"  degraded products.json: {_dg['reason'][:110]}")
ZONES_SRC = paths.SCRATCH / "cloudflare_zones.json"
zone_rows: list = []
if ZONES_SRC.is_file():
    _zscan = json.loads(ZONES_SRC.read_text(encoding="utf-8"))
    zone_rows = estate_surfaces.zone_rows(_zscan, _domains_now, out_projs, _pdoc["products"])
    _zdoc = estate_surfaces.zones_document(_zscan, zone_rows, OBS)
    _stamped("cloudflare-zones.json", _zdoc)
    _zt = _zdoc["totals"]
    print(f"cloudflare-zones.json: {_zt['zones']} zone(s), {_zt['linked']} linked to a "
          f"project, {_zt['in_domain_registry']} in the domain registry, "
          + ", ".join(f"{k} {v}" for k, v in sorted(_zt['by_standing'].items())))

                                                                            
                                                                           
                                                                              
                                                                           
                                                            
                                                                           
                                                                               
                                                                             
                                       
CRED_SRC = paths.SCRATCH / "openrouter.json"
credentials: list = []
if CRED_SRC.is_file():
    import credentials_registry
    _cscan = json.loads(CRED_SRC.read_text(encoding="utf-8"))
    _vault = pathlib.Path(os.environ.get(
        "OBSERVATORY_VAULT_DIR",
        paths.source_path("secret_store", paths.SECRETS) / 'projects'))
    credentials, _cedges = credentials_registry.records(_cscan, _vault, out_projs)
    for e in _cedges:
        add_rel(e["id"], e["type"], e["from"], e["to"], e["source_refs"])
    _cdoc = credentials_registry.document(credentials, _cscan, OBS)
    _stamped("credentials.json", _cdoc)
    _ct = _cdoc["totals"]
    print(f"credentials.json: {_ct['credentials']} credential(s), "
          f"{_ct['claimed_by_a_project']} claimed, {_ct['unclaimed']} unclaimed, "
          f"{_ct['leaked_unrotated']} leaked and unrotated")

                                                                            
                                                                               
                                                                              
                                                                             
                                                                                
                                                                              
                    
                                                                           
                                                  
ENV_SRC = paths.SCRATCH / "env.json"
if ENV_SRC.is_file():
    import env_registry
    _escan = json.loads(ENV_SRC.read_text(encoding="utf-8"))
    _edoc = env_registry.document(_escan, OBS)
    _stamped("env-inventory.json", _edoc)
    _et = _edoc["totals"]
    print(f"env-inventory.json: {_et['env_files']} env file(s) + {_et['templates']} "
          f"template(s), {_et['secrets']} secret-class variable(s), "
          f"{_et['shared_across_projects']} shared across projects, "
          f"{_et['tracked_in_git']} tracked in git")

                                                                            
                                                                              
GOOGLE_SRC = paths.SCRATCH / "google.json"
if GOOGLE_SRC.is_file():
    import google_registry
    _gscan = json.loads(GOOGLE_SRC.read_text(encoding="utf-8"))
    _grows = google_registry.rows(_gscan, out_projs,
                                  paths.config_file("ga4_properties.json"))
    _gdoc = google_registry.document(_gscan, _grows, OBS)
    _stamped("google-properties.json", _gdoc)
    _gt = _gdoc["totals"]
    print(f"google-properties.json: {_gt['properties']} property(ies) in "
          f"{_gt['accounts']} account(s), {_gt['linked_to_a_project']} linked, "
          f"{_gt['outside_the_estate']} outside, {_gt['unclaimed']} unclaimed "
          f"({_gt['users_30d_unclaimed']:,} users/30d), "
          f"{_gt['users_30d']:,} users/30d in all")

                                                                      
                                                                          
                                                                     
REMOTE_SRC = paths.SCRATCH / "remote-env.json"
if REMOTE_SRC.is_file() and ENV_SRC.is_file():
    import remote_registry
    _rscan = json.loads(REMOTE_SRC.read_text(encoding="utf-8"))
    _rdoc = remote_registry.document(_rscan, json.loads(ENV_SRC.read_text(encoding="utf-8")), OBS)
    _stamped("remote-env.json", _rdoc)
    _rt = _rdoc["totals"]
    print(f"remote-env.json: {_rt['apps']} app(s), {_rt['apps_with_a_checkout']} with a "
          f"checkout here, {_rt['same_as_local']} production value(s) equal to a local "
          f"one, {_rt['differs']} differing, {_rt['remote_only']} only in production, "
          f"{_rt['retired_still_deployed']} retired and still deployed")

endpoints = ({p["id"] for p in out_projs} | {r["id"] for r in out_repos}
             | {a["id"] for a in heroku_apps} | {c["id"] for c in credentials}
             | {pr["id"] for pr in products_doc["products"]}
             | {"domain:" + d["name"] for d in json.load(open(INV/"domains.json"))["domains"]})
kept, dropped = [], []
for r in relations:
    if r["from"] in endpoints and r["to"] in endpoints:
        kept.append(r)
    else:
        dropped.append(r)
if dropped:
    print(f"dropped {len(dropped)} relation(s) whose endpoint no longer exists:")
    for r in dropped[:8]:
        missing = [s for s in (r["from"], r["to"]) if s not in endpoints]
        print(f"  {r['id']} -> {', '.join(missing)}")
relations = kept
rel_doc.setdefault("relation_types", {})
rel_doc["relation_types"]["implemented_by"] = "A project is implemented by a repository."
rel_doc["relation_types"]["public_domain_of"] = "A domain is a public address of a project."
rel_doc["relation_types"]["credential_used_by"] = ("A project may use a credential. "
    "Many-to-many on purpose: one account serves several projects and one project uses "
    "several accounts, so the edge repeats rather than folding into a field.")
rel_doc["relation_types"]["part_of"] = ("A project is one part of a product — a site, its admin, "
    "its app, its wiki. Curated only: the edge carries the member's `role`, and a "
    "suggested grouping in registry/products.json never becomes an edge.")
rel_doc["relation_types"]["deployed_to"] = ("A project is deployed to a hosting application. "
    "The edge carries the rule that made it in registry/heroku-apps.json; a name was never enough.")
rel_doc["schema_version"]=2; rel_doc["updated_on"]=OBS; rel_doc["relations"]=relations
_stamped("relations.json", rel_doc)
src_doc["sources"]=sources
_stamped("sources.json", src_doc, stamps=())                                      
_stamped("duplicate-repo-names.json", {"schema_version":1,"updated_on":OBS,"note":"Repository names that occur under more than one owner. Not defects by themselves; each pair needs a human decision.","source_refs":["SRC-0008"],"groups":M["duplicate_repo_names"]})
                                                                              
                                                                             
                                                                             
                                                                         
                                                                            
                                                                                
_stamped("stale-remotes.json", {"schema_version":1,"updated_on":OBS,"note":"Local checkouts whose `origin` names an address that has been transferred. GitHub keeps the old path working as a redirect, so nothing breaks and nothing says so; the merge follows the transfer to keep the phantom out of the registry. Remedy per row: git -C <path> remote set-url origin git@github.com:<now>.git","source_refs":["SRC-0008"],"clones":M.get("stale_remotes",[])})
print(f"projects={len(out_projs)} repositories={len(out_repos)} relations={len(relations)} sources={len(sources)}")
print("with canonical_page:",sum(1 for p in out_projs if "canonical_page" in p))

                                                                              
                                                                         
                                                                            
                                                                        
                                                                               
                                                                           
                                                                               
LIVE_SRC = paths.SCRATCH / "domains_live.json"
if LIVE_SRC.is_file():
    live = json.loads(LIVE_SRC.read_text(encoding="utf-8"))
    owned = {d["name"]: d for d in
             json.loads((paths.REGISTRY / "domains.json").read_text())["domains"]}
                                                                               
                                                                                 
                                                                           
                                                                         
                 
    was_dark: dict[str, str] = {}
    try:
        for r in json.loads((paths.REGISTRY / "domain-liveness.json")
                            .read_text(encoding="utf-8"))["hosts"]:
            if r.get("dark_first_seen"):
                was_dark[r["host"]] = r["dark_first_seen"]
    except (OSError, ValueError, KeyError, TypeError):
        was_dark = {}
    rows, agree, differ = [], 0, []
    for name, h in sorted(live["hosts"].items()):
        w = live["rdap"].get(h.get("registrable", name), {})
        row = {"host": name, "resolves": h.get("resolves", False),
               "http_status": h.get("http", 0),
               "nameservers": h.get("nameservers", []),
               "checked_on": (h.get("checked_at") or "")[:10]}
                                                                                  
                                                                                 
                                                                              
                                                                           
                                                                             
                                                                           
        _seen = h.get("resolves")
        if _seen is False:
            row["dark_first_seen"] = was_dark.get(name) or row["checked_on"]
        elif _seen is None and was_dark.get(name):
            row["dark_first_seen"] = was_dark[name]
        about = w.get("about") if w else None
                                                                                 
                                                                             
                                                                                 
        wrong_subject = bool(w) and name in owned and about != name
        if w and not wrong_subject:
            row["measured"] = {k: v for k, v in
                               (("about", about),
                                ("registrar", w.get("registrar")),
                                ("expires_on", w.get("expiration")),
                                ("registered_on", w.get("registration")),
                                ("statuses", w.get("statuses"))) if v}
        elif wrong_subject:
            row["unverifiable"] = (f"RDAP answered for {about}, a different name. "
                                   f"{name} sits under a multi-label public suffix and "
                                   f"has no RDAP record of its own; the suffix's "
                                   f"registrar and expiry are not this domain's.")
        d = owned.get(name)
        if d and w and not wrong_subject:
            said_r, said_e = d.get("registrar") or "", (d.get("namecheap") or {}).get("expires_on")
            got_r = (w.get("registrar") or "").lower()
            if (said_r and got_r and said_r not in got_r) or \
               (said_e and w.get("expiration") and said_e != w["expiration"]):
                differ.append({"domain": name, "registry_says": {"registrar": said_r,
                               "expires_on": said_e},
                               "rdap_says": {"registrar": w.get("registrar"),
                                             "expires_on": w.get("expiration")}})
            else:
                agree += 1
        rows.append(row)
    atomic.write_json(paths.REGISTRY / "domain-liveness.json", {
        "schema_version": 1,
        "note": ("Measured by collectors/scan_domains.py from public DNS and RDAP. "
                 "It NEVER overwrites registry/domains.json: that file records what "
                 "the operator transcribed, this one what the network says today, and "
                 "a disagreement is named rather than resolved."),
                                                                          
                                                                                
                              
        "source_refs": ["SRC-0011"],
                                                                                  
                                                                             
                                                                                 
                                                                               
                                                                              
        "scanned_on": (live.get("scanned_at") or "")[:10],
        "verification": {"agreed": agree, "disagreed": len(differ),
                         "unverifiable": len(live.get("degraded", [])),
                         "disagreements": differ},
        "hosts": rows,
        "degraded": live.get("degraded", []),
    }, indent=1)
    dark = sum(1 for r in rows if not r["resolves"])
    print(f"domain-liveness.json: {len(rows)} host(s), {dark} dark, "
          f"{agree} agree / {len(differ)} disagree with the transcription")


                                                                                 
                                                              
if cleared:
    print(f"CLEARED by measurement — {len(cleared)} field(s) that had a value now have none. "
          f"If one of these was curated, its home is collectors/project_overrides.json:")
    for line in cleared[:10]:
        print(f"  {line}")
if cleared_repos:
    print(f"CLEARED on repositories — {len(cleared_repos)} field(s); a curated one belongs in "
          f"collectors/repo_overrides.json:")
    for line in cleared_repos[:10]:
        print(f"  {line}")
