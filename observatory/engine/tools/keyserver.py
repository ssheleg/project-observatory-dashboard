#!/usr/bin/env python3
""                                                        

                                                                            
                                                  
                                                                         

                                                                       
                                                                           
                                                                           
                                                                                
                                                                          

                                                                             

                                                                                
                                                                               
                                                              
                                           
                                                                              
                                           
                                                    

                                                                              
                                                                            
                                                                                
                                                                         
                                                                               
                                                                                
                                                                                 
                                                                            
                                                                                
                                                                                
                          

                                                                        
                                                                                
                                                                        
                                                                            
                                                                              
                                 

                   

                                                                            
                                                                           
                                                                               
                                                                   
                                                                  
                                                                             
                                                                               
                                          

                                                                         
                                                                          
                                             
   
from __future__ import annotations
import argparse
import contextvars
import hmac
import html as html_module
import math
import socket
import http.server
import json
import os
import pathlib
import re
import socketserver
import sys
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "collectors"))
import paths              

import stat
from runtime_identity import IdentityError, load as load_identity

TOKEN_FILE = paths.STATE / ".keyserver-token"
                                                                                  
                                                                                
                                                                               
                                                                             
AUDIT = paths.STATE / "logs" / "keyserver.jsonl"
HEADER = "X-Observatory-Token"
                                                                             
                                                                                
                                                                             
                                                                         
                                                                                
                                                                              
                                                             
CALLER_HEADER = "X-Observatory-Caller"
_CALLER: contextvars.ContextVar[str] = contextvars.ContextVar("caller", default="unnamed")


def caller_name(raw: str | None) -> str:
    ""                                                                           
                                                                        
    if not raw:
        return "unnamed"
    s = re.sub(r"[^A-Za-z0-9._:@/+-]", "", raw.strip())[:80]
    return s or "unnamed"

                                                                               
                                                                            
                                                       
DESTINATIONS = {"observatory", "claude-mem"}

                                                                           
                                                                         
                                                                              
                                                                            
                                                                           
                                                                                
                                                                               
                                                                        
VAULT_DEST = re.compile(r"^vault:(?P<project>[a-z0-9][a-z0-9._-]{0,63})"
                        r"/(?P<env>[a-z][a-z0-9-]{0,15})"
                        r"/(?P<name>[A-Z][A-Z0-9_]{0,63})$")


def known_projects() -> set[str]:
    ""                                                                         
                                                                             
                                      
    names: set[str] = set()
    doc = paths.REGISTRY / "projects.json"
    try:
        for row in json.loads(doc.read_text(encoding="utf-8")).get("projects", []):
            if row.get("name"):
                names.add(str(row["name"]).lower())
    except (OSError, ValueError):
        pass
    store = pathlib.Path(os.environ.get(
        "OBSERVATORY_VAULT_DIR", paths.source_path("secret_store", paths.SECRETS) / "projects"))
    try:
        names |= {d.name for d in store.iterdir() if d.is_dir()}
    except OSError:
        pass
    return names


def check_destination(dest: str) -> str:
    ""                                                                       
    if dest in DESTINATIONS:
        return dest
    m = VAULT_DEST.match(dest or "")
    if not m:
        raise ValueError(
            f"destination must be one of {sorted(DESTINATIONS)} or a vault slot "
            f"`vault:<project>/<env>/<NAME>` — project and env lowercase, the "
            f"variable UPPER_SNAKE; got {dest!r}")
    known = known_projects()
    if known and m.group("project") not in known:
        raise ValueError(
            f"no project named {m.group('project')!r} on this machine — a slot "
            f"under a misspelt project is one nothing will ever read. Known "
            f"names are in registry/projects.json")
    return dest


def token() -> str:
    ""                                                                                 
    return load_identity(TOKEN_FILE, 'keyserver-token')


def audit(action: str, subject: str, detail: dict) -> None:
    ""                                                                           
    AUDIT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    row = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "action": action, "subject": subject,
           "caller": _CALLER.get(), "by": os.environ.get("USER", "unknown"), **detail}
                                                                             
                                                                            
    value_shape = re.compile(r"sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9_+/=-]{40,}")
    encoded = value_shape.sub("[redacted]", json.dumps(row, ensure_ascii=False))
    fd = os.open(AUDIT, os.O_WRONLY | os.O_APPEND | os.O_CREAT |
                 getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            raise ValueError("audit destination must be a regular file")
        os.fchmod(fh.fileno(), 0o600)
        fh.write(encoded + "\n")


def _door():
    ""                                                              

                                                                              
                                                                             
                                                                                    
                                                                             
                                                                             
                                                                             
                                                                        
       
    sys.path.insert(0, str(ROOT / "tools"))
    import openrouter
    return openrouter


def act_mint(body: dict) -> dict:
    ""                                                                   
                                                                      
    dest = check_destination(body.get("destination"))
    name = (body.get("name") or f"observatory-{dest}").strip()
    limit = float(body.get("limit") or 0)
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("a mint without a limit is a key with no ceiling; give one")
    audit("mint", name, {"destination": dest, "limit": limit})
    try:
        r = _door().issue_key(name, limit, body.get("account"), dest, body.get("project"))
    except (ValueError, RuntimeError) as exc:
        raise LookupError(str(exc)) from None
    return {"ok": True, **r, "destination": dest}


def act_limit(body: dict) -> dict:
    label = body.get("label") or body.get("name") or ""
    limit = float(body.get("limit") or 0)
    reset = body.get("limit_reset") or "monthly"
    if not label or not math.isfinite(limit) or limit <= 0:
        raise ValueError("a label and a positive limit are both required")
    audit("limit", label, {"limit": limit, "limit_reset": reset})
    try:
        r = _door().set_limit(label, limit, reset)
    except (ValueError, LookupError, RuntimeError) as exc:
        raise LookupError(str(exc)) from None
    return {"ok": True, **r}


def act_revoke(body: dict) -> dict:
    label = body.get("label") or body.get("name") or ""
    if not label:
        raise ValueError("a label is required")
                                                                               
                                                                        
                                                       
    scan = paths.SCRATCH / "openrouter.json"
    if scan.is_file():
        for kk in json.loads(scan.read_text(encoding="utf-8")).get("keys", []):
            if kk.get("label") == label and kk.get("serves"):
                raise ValueError(f"{label} is what {kk['serves']} is reading right now; "
                                 f"mint its replacement first, then revoke this one")
    audit("revoke", label, {})
    try:
        r = _door().revoke_key(label)
    except (ValueError, LookupError, RuntimeError) as exc:
        raise LookupError(str(exc)) from None
    return {"ok": True, **r}


def act_leak(body: dict) -> dict:
    ""                                                                          
    for field in ("project", "env", "name", "where"):
        if not (body.get(field) or "").strip():
            raise ValueError(f"{field} is required; a leak with no `where` is a note "
                             f"nobody can act on")
    import subprocess
    args = [sys.executable, str(ROOT / "tools/vault.py"), "leak",
            body["project"], body["env"], body["name"], "--where", body["where"]]
    audit("leak", f"{body['project']}/{body['env']}/{body['name']}",
          {"location_supplied": True})
    p = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise LookupError(p.stderr.strip()[-200:] or "vault refused the mark")
    return {"ok": True, "marked": f"{body['project']}/{body['env']}/{body['name']}"}


def act_annotate(body: dict) -> dict:
    ""                                                                

                                                                              
                                                                              
                                                                                
                                                                             
                                                                            
       
    cred = (body.get("id") or "").strip()
    if not cred:
        raise ValueError("id is required — the credential as the registry spells it")
    sys.path.insert(0, str(ROOT / "tools"))
    import sign_credential
    audit("annotate", cred, {"fields": sorted(k for k in
          ("purpose", "owner", "evidence", "rotation_days", "tags") if k in body)})
    try:
        row = sign_credential.write(cred, {
            "purpose": body.get("purpose"), "evidence": body.get("evidence"),
            "owner": body.get("owner"), "rotation_days": body.get("rotation_days"),
            "tags": body.get("tags") or []})
    except ValueError as exc:
        raise ValueError(str(exc)) from None
    return {"ok": True, "id": cred, "signed_on": row["signed_on"]}


def act_reveal(body: dict) -> dict:
    ""                                                                    

                                                                             
                                       

                                                                             
                                                                             
                                                                       
                                                                                
                                               

                                                                            
                                                                           

                                                                                  
                                                                         
                                             

                                                                          

                                                                              
                                                                        
                                                                           
                                                                              
                                                                              
                            
       
    path = str(body.get("path") or "").strip()
    name = str(body.get("name") or "").strip()
    if not path or not name:
        raise ValueError("path and name are both required")
    scan = paths.SCRATCH / "env.json"
    if not scan.is_file():
        raise ValueError("no env scan on this machine — run `./observatory.py env` "
                         "first; this reads the inventory, not the disk")
    doc = json.loads(scan.read_text(encoding="utf-8"))
    rec = next((f for f in doc.get("files", []) if f.get("path") == path), None)
    if rec is None:
        raise ValueError(f"{path} is not in the env inventory, so it is not "
                         f"readable from here")
    if name not in {v.get("name") for v in rec.get("variables", [])}:
        raise ValueError(f"{path} holds no variable {name!r} in the current scan")
    root = paths.DATA.resolve()
    target = (root / path).resolve()
    if root not in target.parents:
                                                                                
                                                                             
        raise ValueError(f"{path} resolves outside {root}")
    audit("reveal", f"{path}:{name}", {"class": next(
        (v.get("class") for v in rec["variables"] if v.get("name") == name), None)})
    sys.path.insert(0, str(ROOT / "collectors"))
    import scan_env
    pairs, _ = scan_env.parse(target.read_text(encoding="utf-8", errors="replace"))
    for n, v in pairs:
        if n == name:
            return {"path": path, "name": name, "value": v}
    raise LookupError(f"{name} was in the scan and is not in the file now — "
                      f"rescan with `./observatory.py env`")


def _toggle(body: dict, disabled: bool) -> dict:
    ""                                                                                            
                                                                               
    name = body.get("name") or body.get("label") or ""
    if not name:
        raise ValueError("a key name is required")
    audit("disable" if disabled else "enable", name, {})
    try:
        return {"ok": True, **_door().toggle_key(name, disabled)}
    except LookupError as exc:
        raise LookupError(str(exc)) from None
    except RuntimeError as exc:
        raise LookupError(f"the provider refused: {exc}") from None


def act_disable(body: dict) -> dict:
    return _toggle(body, True)


def act_enable(body: dict) -> dict:
    return _toggle(body, False)


def act_rotate_key(body: dict) -> dict:
    ""                                                                                   
                                                                      
                                                                             
                                                                          
    name = body.get("name") or body.get("label") or ""
    if not name:
        raise ValueError("a key name is required")
    audit("rotate-key", name, {})
    try:
        return {"ok": True, **_door().rotate_one(name)}
    except LookupError as exc:
        raise LookupError(str(exc)) from None
    except RuntimeError as exc:
        raise LookupError(f"the provider refused: {exc}") from None


ACTIONS = {"mint": act_mint, "limit": act_limit, "revoke": act_revoke,
           "leak": act_leak, "reveal": act_reveal, "annotate": act_annotate,
           "disable": act_disable, "enable": act_enable, "rotate-key": act_rotate_key}

                                                                          
REFUSED = {
    "put": "a value travels on stdin and nowhere else — run `tools/vault.py put` yourself",
    "rotate": "a value travels on stdin and nowhere else — run `tools/vault.py rotate` yourself",
}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "observatory-keyserver"

    def log_message(self, fmt, *args):                                   
        pass                                                                              

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _local_request(self) -> bool:
        ""                                                                       

                                                                               
                                                                             
                                                                               
           
        hosts = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        port = self.server.server_address[1]
        expected = {f"{host}:{port}" for host in ("127.0.0.1", "localhost", "[::1]")}
        if port == 80:
            expected.update(("127.0.0.1", "localhost", "[::1]"))
        if len(hosts) != 1 or hosts[0].lower() not in expected:
            self._send(403, {"error": "Host must name this loopback server and port"})
            return False
        if len(origins) > 1:
            self._send(403, {"error": "one same-origin Origin is required"})
            return False
        if origins:
            origin = origins[0]
            try:
                parsed = urllib.parse.urlsplit(origin)
                valid = (parsed.scheme == "http" and not parsed.username and not parsed.password
                         and not parsed.path and not parsed.query and not parsed.fragment
                         and parsed.netloc.lower() == hosts[0].lower()
                         and (parsed.port or 80) == port
                         and origin.lower() == f"http://{hosts[0].lower()}")
            except ValueError:
                valid = False
            if not valid:
                self._send(403, {"error": "Origin must match this loopback server and port"})
                return False
        return True

    def _authorised(self) -> bool:
                                                                             
                                                                        
        given = self.headers.get(HEADER) or ""
        if (len(self.headers.get_all(HEADER, [])) != 1
                or not hmac.compare_digest(given.encode(), str(self.server.token).encode())):
            self._send(401, {"error": "bad or missing token"})
            return False
        _CALLER.set(caller_name(self.headers.get(CALLER_HEADER)))
        return True

    def _page_for(self, route: str):
        ""                                                   

                                                                      
                                                                          
                                                                              
                                                                          
                                                                             
                                                                              
                  
           
        sys.path.insert(0, str(ROOT / "dashboard"))
        import shell
        if route in ("/", "/index.html"):
            page = paths.DASHBOARD_DIR / "index.html"
            return (page if page.is_file() else paths.DASHBOARD_HTML), "text/html"
        if route.startswith("/dashboard/"):
            name = route[len("/dashboard/"):]
            kind = {shell.ASSET_CSS: "text/css", shell.ASSET_JS: "text/javascript"}.get(name)
            if kind or (name.endswith(".html") and name[:-5] in shell.NAMES):
                return paths.DASHBOARD_DIR / name, kind or "text/html"
        return None, None

    def do_GET(self) -> None:                                            
        if not self._local_request():
            return
        route = self.path.split("?", 1)[0].split("#", 1)[0]
        page, ctype = self._page_for(route)
        if page is not None and ctype != "text/html":
            if not page.is_file():
                self._send(404, {"error": "the pages have not been built — ./observatory.py dashboard"})
                return
            body = page.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if page is not None:
            if not page.is_file():
                self._send(404, {"error": "the dashboard has not been built — "
                                          "./observatory.py dashboard"})
                return
            html = page.read_text(encoding="utf-8")
                                                                                
                                                                               
                                                                            
                                    
            html = html.replace("</head>",
                                f'<meta name="observatory-token" content="{html_module.escape(str(self.server.token), quote=True)}">'
                                f"</head>", 1)
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/state":
            if not self._authorised():
                return
            doc = paths.REGISTRY / "credentials.json"
            self._send(200, json.loads(doc.read_text(encoding="utf-8"))
                       if doc.is_file() else {"credentials": [], "totals": {}})
            return
        self._send(404, {"error": "no such path"})

    def do_POST(self) -> None:                                           
        if not self._local_request():
            return
        if not self.path.startswith("/api/"):
            self._send(404, {"error": "no such path"})
            return
        if not self._authorised():
            return
        what = self.path[len("/api/"):]
        if what in REFUSED:
            self._send(403, {"error": REFUSED[what]})
            return
        fn = ACTIONS.get(what)
        if not fn:
            self._send(404, {"error": f"no action {what!r}"})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
            self._send(400, {"error": "one Content-Length and no Transfer-Encoding are required"})
            return
        try:
            if not re.fullmatch(r"[0-9]+", lengths[0]):
                raise ValueError
            length = int(lengths[0])
            if length > 65536:
                self._send(413, {"error": "request body is too large"})
                return
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError
            body = json.loads(raw or b"{}", parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
            if not isinstance(body, dict):
                raise ValueError
        except (ValueError, UnicodeError):
            self._send(400, {"error": "body must be a bounded JSON object with finite numbers"})
            return
        try:
            self._send(200, fn(body))
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except LookupError as exc:
                                                                             
                                                                                 
                                                                           
            self._send(404, {"error": str(exc)})
        except urllib.error.HTTPError as exc:
            self._send(502, {"error": f"the provider refused: HTTP {exc.code}"})
        except Exception as exc:                                           
            self._send(500, {"error": "action failed; inspect the local service configuration"})


class Server(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, addr, handler, tok):
        if addr[0] not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("keyserver binds only to a loopback address")
        if not tok:
            raise ValueError("keyserver requires a nonempty token")
        if addr[0] == "::1":
            self.address_family = socket.AF_INET6
                                                                             
        super().__init__(addr, handler)
        self.token = tok

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(10)
        return sock, address


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=7717)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--once", action="store_true",
                    help="answer one request and exit")
    a = ap.parse_args(argv[1:])
    if a.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"refusing to bind {a.host}: this holds a provisioning key and answers "
              f"only to this machine", file=sys.stderr)
        return 2
    try:
        tok = token()
    except IdentityError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    with Server((a.host, a.port), Handler, tok) as srv:
        shown_host = f"[{a.host}]" if a.host == "::1" else a.host
        print(f"keyserver on http://{shown_host}:{srv.server_address[1]} — open it; the page carries "
              f"its own token")
        print(f"  audit: {AUDIT}")
        print(f"  refused by design: vault put and rotate — a value travels on stdin")
        if a.once:
            srv.handle_request()
        else:
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
