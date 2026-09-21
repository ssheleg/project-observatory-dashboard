#!/usr/bin/env python3
""                                                                                 

                                  

                                                                         
                                                                            
                                                               
                                                                               
                                                                              
                                                                             
                                                                         
             

                                                                           
                                                                            
                                                                                 
                                                                       

                                                                               
                                                                               
                                                                           
                  
   
from __future__ import annotations
import json
import pathlib
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths                                            
import atomic                                                                   

HOME = paths.source_path("mcp_config_root", paths.HOME / "disabled/mcp")
SOURCES = {
    "claude": HOME / ".claude.json",
    "cursor": HOME / ".cursor/mcp.json",
    "opencode": HOME / ".config/opencode/opencode.json",
}
                                                                             
                                                 
OWN_SERVER = "observatory"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_url(url: str) -> tuple[str, bool]:
    ""                                                         
    try:
        s = urlsplit(url)
    except ValueError:
        return url.split("?")[0], "?" in url
    return urlunsplit((s.scheme, s.netloc, s.path, "", "")), bool(s.query)


def classify(name: str, cfg: dict) -> dict:
    ""                                                                
    url = cfg.get("url") or ""
    cmd = cfg.get("command") or ""
                                                                                 
                                                                              
    extra_args: list = []
    if isinstance(cmd, list):
        extra_args = [str(a) for a in cmd[1:]]
        cmd = str(cmd[0]) if cmd else ""
    transport = (cfg.get("type") or ("http" if url else "stdio")).lower()
    if transport in ("remote", "sse", "streamable-http"):
        transport = "http"
    target, key_in_url = (safe_url(url) if url else (pathlib.Path(cmd).name if cmd else "", False))
    headers = cfg.get("headers") or {}
    keyed_header = any(k.lower() in ("authorization", "x-api-key", "x-observatory-token")
                       or "key" in k.lower() or "token" in k.lower() for k in headers)
    env = cfg.get("env") or {}
    keyed_env = any(re.search(r"(KEY|TOKEN|SECRET|PASS)", k, re.I) for k in env)
    args = extra_args + [str(a) for a in (cfg.get("args") or [])]
    return {
        "name": name, "transport": transport, "target": target,
        "command": pathlib.Path(cmd).name if cmd else None,
        "args_count": len(args),
        "key_in_url": key_in_url,
        "key_in_header": keyed_header, "key_in_env": keyed_env,
        "command_present": (bool(shutil.which(cmd) or pathlib.Path(cmd).is_file())
                            if cmd else None),
    }


def read_declarations() -> list[dict]:
    rows: list[dict] = []
    for agent, path in SOURCES.items():
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            rows.append({"agent": agent, "name": None, "error": f"{type(exc).__name__}"})
            continue
        table = doc.get("mcpServers") if agent != "opencode" else doc.get("mcp")
        for name, cfg in (table or {}).items():
            if isinstance(cfg, dict):
                rows.append({**classify(name, cfg), "agent": agent, "scope": "user",
                             "declared_in": str(path).replace(str(HOME), "~")})
        if agent == "claude":
            for proj, pcfg in (doc.get("projects") or {}).items():
                for name, cfg in (pcfg.get("mcpServers") or {}).items():
                    if isinstance(cfg, dict):
                        rows.append({**classify(name, cfg), "agent": agent,
                                     "scope": f"project:{proj.replace(str(HOME), '~')}",
                                     "declared_in": "~/.claude.json#projects"})
    return rows


                                                                                     
                                                                              
                                                                
LINE = re.compile(r"^(?P<name>.+?): (?P<target>.*?) - (?P<mark>✔|✘|!) (?P<status>.+)$")


def claude_probe() -> tuple[dict[str, dict], str | None]:
    ""                                                                          
    if not shutil.which("claude"):
        return {}, "claude CLI not on PATH"
    try:
        p = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True,
                           timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, f"claude mcp list: {type(exc).__name__}"
    out: dict[str, dict] = {}
    for raw in (p.stdout + p.stderr).splitlines():
        m = LINE.match(raw.strip())
        if not m:
            continue
        name = m.group("name").strip()
        mark = m.group("mark")
        status = {"✔": "connected", "✘": "failed", "!": "needs-auth"}[mark]
        plugin = None
        if name.startswith("plugin:"):
            _, plugin, name = name.split(":", 2)
        elif name.startswith("claude.ai "):
            plugin, name = "claude.ai", name[len("claude.ai "):]
        out[name] = {"status": status, "plugin": plugin,
                     "detail": m.group("status").strip()[:60]}
    if not out:
        return {}, "claude mcp list answered with nothing this scan could parse"
    return out, None


def main(argv: list[str]) -> int:
    import configuration
    if not configuration.enabled("mcp"):
        print("mcp: not configured (integration disabled)")
        return 0
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    rows = read_declarations()
    probe, why = claude_probe()
    degraded = [{"source": "claude mcp list", "reason": why}] if why else []
    for r in rows:
        if r.get("name") is None:
            continue
        if r["agent"] == "claude" and r["name"] in probe:
            r["liveness"] = probe[r["name"]]["status"]
            r["liveness_detail"] = probe[r["name"]]["detail"]
        elif r["agent"] == "claude" and probe and r["scope"].startswith("project:"):
                                                                             
                                                                        
            r["liveness"] = "not-probed"
        elif r["agent"] == "claude" and probe:
            r["liveness"] = "not-listed"
        else:
            r["liveness"] = "not-probed"
                                                                             
                                                                              
                                                     
    declared = {r["name"] for r in rows if r.get("name")}
    for name, pr in probe.items():
        if name not in declared and pr["plugin"]:
            rows.append({"name": name, "agent": "claude",
                         "scope": f"plugin:{pr['plugin']}" if pr["plugin"] != "claude.ai" else "claude.ai",
                         "declared_in": "plugin" if pr["plugin"] != "claude.ai" else "claude.ai connector",
                         "transport": None, "target": None, "command": None, "args_count": 0,
                         "key_in_url": False, "key_in_header": False, "key_in_env": False,
                         "command_present": None,
                         "liveness": pr["status"], "liveness_detail": pr["detail"]})
    rows.sort(key=lambda r: (r.get("agent") or "", r.get("name") or ""))
    atomic.write_json(argv[1], {"scanned_at": now(), "servers": rows,
                                "own_server": OWN_SERVER,
                                "own_declared": any(r.get("name") == OWN_SERVER for r in rows),
                                "degraded": degraded})
    by = {}
    for r in rows:
        by[r.get("liveness", "?")] = by.get(r.get("liveness", "?"), 0) + 1
    print(f"mcp: {len(rows)} declaration(s) across "
          f"{len({r.get('agent') for r in rows})} agent(s) — "
          + ", ".join(f"{k} {v}" for k, v in sorted(by.items())))
    for d in degraded:
        print(f"  degraded {d['source']}: {d['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
