""                                                      

                                                                               
                                                                                
                             

                                                                       
                                                                                
                                                                               
                                                                            
                                                                                 
                                                                               
                                                                     
                                                                               
                                                                                
                          

                                                                        
                                                                                
                                                                              
                                                                                
                                                                      
                                                                         
                                                                

                                           
   
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import atomic
import paths
import json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
DATA = paths.DATA

                                                                                 
                                                                               
                                                                             
                                                                             
FILE_COUNT_CAP = 20000


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


                                                                             
                                                                                 
           
  
                                                           
                                                                                                          
  
                                                                                   
                                                                                   
                                                                             
                                                                        
                                                                                 
                                                                                 
                                                                   
  
                                                                         
                                                                               
                                                                        
                               
GIT_ENV = {"LC_ALL": "C", "LANGUAGE": ""}


def sh(args, cwd=None):
    ""                                                                       

                                                                          
                                                                               
                                                                                
                             

                                                                               
                                                       
       
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=25,
                           env={**os.environ, **GIT_ENV})
    except subprocess.TimeoutExpired:
        return "", f"`{' '.join(args[:3])}` did not finish in 25s"
    except OSError as exc:
        return "", f"`{args[0]}` could not run: {type(exc).__name__}: {exc}"
    if r.returncode != 0:
        return "", (f"`{' '.join(args[:3])}` exited {r.returncode}: "
                    f"{(r.stderr or '').strip()[:100]}")
    return r.stdout.strip(), ""


MARKERS = [
    ("package.json","node"), ("pyproject.toml","python"), ("requirements.txt","python"),
    ("go.mod","go"), ("Cargo.toml","rust"), ("composer.json","php"), ("Gemfile","ruby"),
    ("build.gradle","android"), ("build.gradle.kts","android"), ("Package.swift","swift"),
    ("pubspec.yaml","flutter"), ("Dockerfile","docker"), ("docker-compose.yml","docker"),
    ("SKILL.md","agent-skill"), (".claude-plugin","claude-plugin"),
    ("next.config.js","nextjs"), ("next.config.ts","nextjs"), ("next.config.mjs","nextjs"),
    ("astro.config.mjs","astro"), ("vercel.json","vercel"), ("wrangler.toml","cloudflare-worker"),
    ("wrangler.jsonc","cloudflare-worker"), ("netlify.toml","netlify"),
]
DOMAIN_RX = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:com|org|net|io|dev|app|ai|me|pro|bot|chat|xyz|club|cards|care|social|spot|trading|business|codes|estate|fm|forex|vip|online|ru\.com))\b")


def exclusions() -> tuple[tuple[str, ...], dict[str, str]]:
    ""                                                            

                                                                               
                                                                         
                                                                            
                                                                     
       
    f = paths.config_file('folder_exclusions.json')
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return (), {}
    return (tuple(x["prefix"] for x in doc.get("prefixes") or []),
            {x["name"]: x.get("why", "") for x in doc.get("names") or []})


def first_para(p: Path):
    for name in ("README.md","readme.md","README.MD"):
        f = p/name
        if not f.exists(): continue
        try: txt = f.read_text(encoding="utf-8", errors="replace")
        except Exception: return ""
        out=[]
        for line in txt.splitlines():
            s=line.strip()
            if not s or s.startswith(("#","!","[!","<!--","---","```","|","> [!")):
                if out: break
                continue
            out.append(s)
            if len(" ".join(out))>240: break
        return re.sub(r"\s+"," "," ".join(out))[:300]
    return ""
def detect(p: Path):
    kinds=[]
    for marker, kind in MARKERS:
        if (p/marker).exists() and kind not in kinds: kinds.append(kind)
    if list(p.glob("*.xcodeproj")) or list(p.glob("*.xcworkspace")): kinds.append("ios")
    if (p/"skills").is_dir() and (p/".claude-plugin").exists(): kinds.append("claude-plugin")
    return kinds
def _nwo_of(url: str) -> str:
    ""                                                                     
    m = re.search(r"(?:github\.com|bitbucket\.org)[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def homepage(p: Path):
    hits=[]
    pj=p/"package.json"
    if pj.exists():
        try:
            j=json.loads(pj.read_text(encoding="utf-8", errors="replace"))
            h=j.get("homepage")
            if isinstance(h,str) and h.startswith("http"): hits.append(("package.json:homepage",h))
        except Exception: pass
    for cname in list(p.glob("CNAME"))+list(p.glob("*/CNAME"))+list(p.glob("public/CNAME")):
        try: hits.append((f"{cname.relative_to(p)}", cname.read_text(encoding='utf-8',errors='replace').strip()))
        except Exception: pass
    for wr in ("wrangler.toml","wrangler.jsonc","wrangler.json"):
        f=p/wr
        if f.exists():
            try:
                t=f.read_text(encoding="utf-8", errors="replace")
                for m in set(DOMAIN_RX.findall(t.lower()))-{"example.com"}:
                    hits.append((wr,m))
            except Exception: pass
                                                                             
                                                                                
                                                                                  
                                                                           
                                                                
    for envf in sorted(p.glob(".env*")):
        if not envf.is_file() or envf.name.endswith((".bak", ".swp")):
            continue
        try:
            for line in envf.read_text(encoding="utf-8", errors="replace").splitlines():
                                                                                        
                                                                                
                                                                              
                                                                              
                                                                              
                                                                               
                              
                m = re.match(r"\s*(?:export\s+)?((?:NEXT_PUBLIC_|VITE_|REACT_APP_|NUXT_PUBLIC_)?"
                             r"(?:APP|SITE|PUBLIC|BASE|WEB|FRONTEND|CANONICAL|PRODUCTION|NEXTAUTH)?_?"
                             r"(?:URL|DOMAIN|HOST|ORIGIN))\s*=\s*[\"']?(https?://[^\s\"'#]+)", line)
                if not m or "@" in m.group(2):
                    continue
                host = re.sub(r"^https?://", "", m.group(2)).split("/")[0].split(":")[0].lower()
                if host and not host.startswith(("localhost", "127.", "0.0.0.0", "example.")) and "." in host:
                    hits.append((f"env:{envf.name}:{m.group(1)}", "https://" + host))
        except OSError:
            pass
                                                                                   
    for conf in list(p.glob("*.conf")) + list(p.glob("nginx/*.conf")) + list(p.glob("deploy/*.conf")) + list(p.glob("docker/*.conf")):
        try:
            for m in re.finditer(r"server_name\s+([^;]+);", conf.read_text(encoding="utf-8", errors="replace")):
                for host in m.group(1).split():
                    host = host.strip().lower()
                    if "." in host and not host.startswith(("_", "*", "localhost")) and "$" not in host:
                        hits.append((f"nginx:{conf.relative_to(p)}", "https://" + host))
        except OSError:
            pass
    return hits


def count_files(p: Path) -> tuple[int, bool]:
    ""                                                                  
    n = 0
    try:
        for f in p.rglob("*"):
            if f.is_file():
                n += 1
                if n >= FILE_COUNT_CAP:
                    return n, True
    except OSError:
                                                                               
                                                                      
        return n, False
    return n, False


rows=[]
degraded=[]
skipped=[]
EXCLUDED_PREFIXES, EXCLUDED_NAMES = exclusions()

                                                                              
                                                                                
                                                                            
                                  
 
                                                                              
                                                                              
 
                                                                               
                                                                                 
                                                                           
                                                                               
                                                                          
                                                                      
 
                                                                              
                                     
_probe, _why = sh(["git", "--version"])
if _why:
    _git_folders = [e for e in os.listdir(DATA)
                    if not e.startswith(".") and (DATA/e/".git").exists()]
    if _git_folders:
        sys.exit(f"scan_filesystem: {_why}\n"
                 f"  {len(_git_folders)} folder(s) under {DATA} are git checkouts and "
                 f"none of them can be read.\n"
                 f"  Writing this scan would turn every one into a folder-anchored "
                 f"project — measured: 156 projects become 206 and 172 repositories "
                 f"become 149.\n"
                 f"  {sys.argv[1] if len(sys.argv) > 1 else 'the previous scan'} is "
                 f"left untouched.")
for entry in sorted(os.listdir(DATA)):
    p = DATA/entry
    if entry.startswith(".") or not p.is_dir(): continue
                                                                           
                                                                                
                             
    if entry.startswith(EXCLUDED_PREFIXES) or entry in EXCLUDED_NAMES:
        skipped.append({"folder": entry,
                        "why": EXCLUDED_NAMES.get(entry)
                        or f"excluded by prefix {[x for x in EXCLUDED_PREFIXES if entry.startswith(x)]}"})
        continue
    is_link = p.is_symlink()
    real = str(p.resolve())
    dotgit = p/".git"
    git = dotgit.exists()
                                                                  
                                                                              
                                                                              
                                                                                    
                                                                               
                                                          
    worktree_of = ""
    if git and dotgit.is_file():
        try:
            head = dotgit.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            head = ""
        if head.startswith("gitdir:") and "/worktrees/" in head.replace("\\", "/"):
            target = head.split("gitdir:", 1)[1].strip().replace("\\", "/")
            worktree_of = target.split("/.git/")[0].rstrip("/").split("/")[-1]
    rec = {"folder": entry, "path": str(p), "real_path": real, "symlink": is_link, "is_git": git,
           "worktree_of": worktree_of,
           "kinds": detect(p), "readme": first_para(p), "homepage_hits": homepage(p)}
                                                                          
                                                                              
                                                                               
                                                                               
                                                                                  
                                                                               
                 
    gm = p / ".gitmodules"
    if git and gm.is_file():
        subs, cur = [], {}
        try:
            for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s.startswith("[submodule"):
                    cur = {}
                    subs.append(cur)
                elif "=" in s:
                    k, _, v = s.partition("=")
                    cur[k.strip()] = v.strip()
        except OSError:
            subs = []
        rec["submodules"] = [
            {"path": m.get("path", ""), "url": m.get("url", ""),
             "nwo": _nwo_of(m.get("url", ""))}
            for m in subs if m.get("path")]
                                                                              
                                                                              
    gj = p / "graphify-out" / "graph.json"
    if gj.is_file():
        try:
            rec["graph_built_on"] = datetime.fromtimestamp(
                gj.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")
        except OSError:
            pass
    if git:
        unread = {}
                                                                            
                                                                        
        for field, argv in (
                ("remote", ["git", "remote", "get-url", "origin"]),
                ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
                ("last_commit", ["git", "log", "-1", "--format=%cs"]),
                ("commits", ["git", "rev-list", "--count", "HEAD"])):
            out, why = sh(argv, cwd=p)
            rec[field] = out
            if not why:
                continue
                                                                            
                                                                              
                                                                                  
                                                                                  
                                                                        
                                                                        
                                                                             
                                                       
                                                                          
                                                                                
                                                                           
            if field == "remote" and "No such remote" in why:
                rec["no_origin"] = True
                continue
            if field in ("branch", "last_commit", "commits") and (
                    "unknown revision" in why or "does not have any commits" in why
                    or "ambiguous argument 'HEAD'" in why):
                rec["no_commits"] = True
                continue
            unread[field] = why
        out, why = sh(["git", "remote", "-v"], cwd=p)
        rec["remotes_all"] = out.splitlines()[:6]
        if why:
            unread["remotes_all"] = why
        out, why = sh(["git", "status", "--porcelain"], cwd=p)
        rec["dirty"] = len(out.splitlines())
        if why:
            unread["dirty"] = why
        if unread:
                                                                            
                                                                                 
                                                                           
                                                                      
            rec["unread"] = unread
            degraded.append({"source": f"folder:{entry}",
                             "reason": "; ".join(f"{k}: {v}" for k, v in unread.items())})
    else:
                                                                              
                                                                            
                                                    
        try:
            rec["mtime"] = datetime.fromtimestamp(
                p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")
        except OSError as exc:
            rec["mtime"] = ""
            degraded.append({"source": f"folder:{entry}",
                             "reason": f"mtime unreadable: {type(exc).__name__}"})
        n, capped = count_files(p)
        rec["file_count"] = n
        if capped:
                                                                                 
                                                                               
                                          
            rec["file_count_capped"] = True
    rows.append(rec)

atomic.write_json(sys.argv[1], {"scanned_at": now(), "folders": rows,
                                "skipped": skipped, "degraded": degraded})
print(f"scanned {len(rows)} folders -> {sys.argv[1]}")
if skipped:
    print(f"  skipped {len(skipped)}: {', '.join(s['folder'] for s in skipped)}")
for d in degraded:
    print(f"  degraded {d['source']}: {d['reason'][:110]}")
