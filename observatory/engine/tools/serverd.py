#!/usr/bin/env python3
""                                                                               

                                                                       
                                                                           
                                                                         
                                                                  
                                                                               

                                                                              
                                                                                
                                                                             

                                                                                
                                                                                 
                                                                                  
                                                                                  
                                                                                   

                                                                            
                                                                            
                                                                                 
                                                                           
                                          

                                                                             
                                                                                  
                                                                                 
                                                                             
                                                                             
                                                                                 
                                                                               
                                                                       

                                                                                
                                                                           
                                                                             
                                                                              
                                                                           

                                                                             
                                                                           
                                     
   
from __future__ import annotations
import argparse
import datetime
import http.server
import json
import os
import pathlib
import plistlib
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic                                                                   
import paths                                                                    

PORT = int(os.environ.get("OBSERVATORY_SERVER_PORT", "47311"))
RECEIPT = paths.SCRATCH / "serverd.json"
import configuration
try:
    from tools import install_launchd
except ImportError:
    import install_launchd
LABEL = install_launchd.instance_label("server")
PLIST = pathlib.Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
                                                                           
                                                                          
                                                              
AT_RISK = ("ahead", "local-only-branch", "unpushed-and-remote-moved", "diverged")
REFRESH_SECONDS = 20
STARTED = time.time()
VERSION = "0.1.0"


def now_z() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(p: pathlib.Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def refresh_remote() -> dict:
    ""                                                                    

                                                                            
                                                
       
    doc = _read_json(paths.REGISTRY / "repositories.json")
    if not doc:
        return {"readable": False, "measured_from": None, "states": {},
                "at_risk": [], "note": "registry unreadable — no claim about remotes"}
    states: dict[str, int] = {}
    risky: list[dict] = []
    for r in doc.get("repositories", []):
        lo = r.get("local") or {}
        checkouts = [lo] + list(lo.get("extra_checkouts") or [])
        for c in checkouts:
            s = c.get("sync")
            if not s:
                continue
            states[s] = states.get(s, 0) + 1
            if s in AT_RISK:
                risky.append({"repo": r.get("name_with_owner"),
                              "folder": c.get("folder") or lo.get("path"),
                              "branch": c.get("branch"), "sync": s})
    try:
        mtime = (paths.REGISTRY / "repositories.json").stat().st_mtime
        measured = datetime.datetime.fromtimestamp(
            mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        measured = None
    return {"readable": True, "measured_from": measured, "states": states,
            "at_risk_total": len(risky),
            "at_risk": sorted(risky, key=lambda x: (x["sync"], x["repo"] or ""))[:100]}


def refresh_leaks() -> dict:
    reg = pathlib.Path(os.environ.get(
        "OBSERVATORY_VAULT_DIR",
        paths.source_path("secret_store", paths.SECRETS) / "projects")) / "leaks.jsonl"
    if not reg.is_file():
        return {"register": False, "open": 0, "total": 0}
    rows, settled = [], set()
    try:
        for line in reg.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("event") == "settled":
                settled.add(r.get("of"))
            elif r.get("event") == "leaked":
                rows.append(r)
    except (OSError, ValueError):
        return {"register": True, "readable": False}
    open_rows = [r for r in rows if r.get("id") not in settled]
    return {"register": True, "readable": True, "total": len(rows),
            "open": len(open_rows),
                                                                           
                                                                             
                                                
            "open_secrets": [{"secret": r.get("secret"), "where": r.get("where"),
                              "at": r.get("at")} for r in open_rows]}


def refresh_skills() -> dict:
    ""                                                                    
    shipped: dict[str, str] = {}
    for sk in (ROOT / "skill/plugins/observatory-log/skills").glob("*/SKILL.md"):
        body = sk.read_text(encoding="utf-8")
        v = None
        for line in body.splitlines():
            if line.strip().startswith("version:"):
                v = line.split(":", 1)[1].strip()
                break
        shipped[sk.parent.name] = v or "unversioned"
    sessions = _read_json(paths.SCRATCH / "skill-sessions.json") or {}
    return {"shipped": shipped, "sessions": sessions.get("sessions", {})}


def heartbeat() -> dict:
    lease = _read_json(paths.SCRATCH / "tick-lease.json") or {}
    tick = _read_json(paths.SCRATCH / "tick.json") or {}
    doc = {
        "at": now_z(), "pid": os.getpid(), "port": PORT, "version": VERSION,
        "uptime_s": int(time.time() - STARTED),
        "remote": refresh_remote(),
        "leaks": refresh_leaks(),
        "skills": refresh_skills(),
        "tick": {"last_finished": tick.get("finished_at"),
                 "lease_holder": lease.get("holder")},
    }
    atomic.write_json(RECEIPT, doc)
    return doc


def local_request(host: str, origin: str | None, fetch_site: str | None, port: int) -> bool:
    ""                                                                             
    if host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
        return False
    if fetch_site == "cross-site":
        return False
    if origin:
        try:
            parsed = urlsplit(origin)
            if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
                    or parsed.port != port or parsed.username is not None
                    or parsed.password is not None or parsed.path not in {"", "/"}
                    or parsed.query or parsed.fragment):
                return False
        except ValueError:
            return False
    return True


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = f"observatory-serverd/{VERSION}"

    def log_message(self, fmt, *args):                                      
        pass                                                                    

    def _json(self, doc, code=200):
        body = json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def do_GET(self):                                                 
        if not local_request(self.headers.get("Host", ""), self.headers.get("Origin"),
                             self.headers.get("Sec-Fetch-Site"), self.server.server_address[1]):
            self._json({"error": "only local browser origins are accepted"}, 403)
            return
        route = self.path.split("?", 1)[0].rstrip("/") or "/"
                                                                             
                                                                               
                                                                      
        if route.startswith("/dashboard/"):
            name = route[len("/dashboard/"):]
            sys.path.insert(0, str(ROOT / "dashboard"))
            import shell
            kind = {shell.ASSET_CSS: "text/css", shell.ASSET_JS: "text/javascript"}.get(name)
            if kind or (name.endswith(".html") and name[:-5] in shell.NAMES):
                page = paths.DASHBOARD_DIR / name
                if page.is_file():
                    body = page.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", f"{kind or 'text/html'}; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self._json({"error": "the pages are not built yet",
                            "build_with": "./observatory.py dashboard"}, 404)
                return
            self._json({"error": "no such page", "pages": list(shell.NAMES)}, 404)
            return
        if route in ("/", "/dashboard"):
            # The split pages load app.css/app.js as relative siblings, so the
            # index must be addressed under /dashboard/; served at / its assets
            # would resolve to /app.css and 404, leaving an unstyled, dead page.
            if (paths.DASHBOARD_DIR / "index.html").is_file():
                self.send_response(302)
                self.send_header("Location", "/dashboard/index.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            page = paths.DASHBOARD_HTML
            if not page.is_file():
                self._json({"error": "the dashboard is not built yet",
                            "build_with": "./observatory.py dashboard"}, 404)
                return
            body = page.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif route == "/health":
            self._json(heartbeat())
        elif route == "/remote":
            self._json(refresh_remote())
        elif route == "/leaks":
            self._json(refresh_leaks())
        elif route == "/skills":
            self._json(refresh_skills())
        else:
            self._json({"error": "no such route",
                        "routes": ["/", "/dashboard/<page>.html", "/health", "/remote",
                                   "/leaks", "/skills"]}, 404)

    def do_POST(self):                                                
        self._json({"error": "GET only — this server changes nothing"}, 405)


def serve(port: int) -> int:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)

    def beat():
        while True:
            try:
                heartbeat()
            except Exception as exc:                                             
                print(f"heartbeat: {type(exc).__name__}: {exc}",                 
                      file=sys.stderr)                                  
            time.sleep(REFRESH_SECONDS)

    threading.Thread(target=beat, daemon=True).start()
    print(f"observatory serverd {VERSION} on http://127.0.0.1:{port} "
          f"(pid {os.getpid()})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def build_plist() -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": [sys.executable,
                             str(ROOT / "tools/serverd.py"), "--run", "--port", str(PORT)],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardErrorPath": str(paths.STATE / "logs/serverd.err"),
        "StandardOutPath": str(paths.STATE / "logs/serverd.out"),
        "EnvironmentVariables": install_launchd.environment(),
        "Umask": 0o077,
        "LowPriorityIO": True,
        "Nice": 5,
    }


def install() -> int:
    if not install_launchd.scheduler_allowed():
        print("Scheduler disabled: enable features.scheduler before installing background jobs", file=sys.stderr)
        return 1
    if sys.platform != "darwin":
        print("launchd is supported on macOS only", file=sys.stderr)
        return 1
    install_launchd.prepare_logs(("serverd.err", "serverd.out"), paths.STATE / "logs")
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(PLIST, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(plistlib.dumps(build_plist()))
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST)],
                   capture_output=True, timeout=60)                               
    p = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)],
                       capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        print(f"launchctl bootstrap failed: {p.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"installed and started: {LABEL} (RunAtLoad + KeepAlive) — "
          f"http://127.0.0.1:{PORT}/")
    print(f"  off is `tools/serverd.py --uninstall`; off STAYS off until --install")
    return 0


def uninstall() -> int:
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST)],
                   capture_output=True, timeout=60)
    existed = PLIST.exists()
    PLIST.unlink(missing_ok=True)
    print("stopped and removed the launchd agent" if existed else
          "nothing was installed")
    return 0


def status() -> int:
    doc = _read_json(RECEIPT)
    if not doc:
        print("no heartbeat receipt — the server has never run here")
        return 1
    age = time.time() - datetime.datetime.strptime(
        doc["at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc).timestamp()
    alive = age < REFRESH_SECONDS * 3
    print(f"{'UP' if alive else 'SILENT'} — last heartbeat {int(age)}s ago, "
          f"pid {doc.get('pid')}, port {doc.get('port')}, "
          f"uptime {doc.get('uptime_s')}s")
    r = doc.get("remote") or {}
    print(f"  remote watch: {r.get('at_risk_total', '?')} checkout(s) at risk "
          f"across states {r.get('states')}")
    l = doc.get("leaks") or {}
    print(f"  leaks: {l.get('open', '?')} open of {l.get('total', '?')} recorded")
    print(f"  installed: {'yes' if PLIST.exists() else 'no (not always-on)'}")
    return 0 if alive else 1


def main(argv: list[str]) -> int:                                            
    ap = argparse.ArgumentParser(description=(__doc__ or "Serve the private Project Observatory dashboard.").splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", action="store_true")
    g.add_argument("--once", action="store_true")
    g.add_argument("--install", action="store_true")
    g.add_argument("--uninstall", action="store_true")
    g.add_argument("--status", action="store_true")
    ap.add_argument("--port", type=int, default=PORT)
    a = ap.parse_args(argv[1:])
    globals()["PORT"] = a.port
    if a.once:
        doc = heartbeat()
        print(json.dumps({k: doc[k] for k in ("at", "pid", "port")},
                         ensure_ascii=False))
        return 0
    if a.run:
        return serve(a.port)
    if a.install:
        return install()
    if a.uninstall:
        return uninstall()
    return status()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
