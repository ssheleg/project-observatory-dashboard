#!/usr/bin/env python3
""                                                                      
from __future__ import annotations
import os
from pathlib import Path
import configuration

ROOT = Path(__file__).resolve().parent
HOME = configuration.home()
configuration.validate_workspace(HOME)
CONFIG = HOME / "config"
SOURCE_DOCS = ROOT / "docs"
SECRETS = configuration.source_path("secrets", "secrets", "OBSERVATORY_SECRETS") if (os.environ.get("OBSERVATORY_SECRETS") or configuration.load().get("sources", {}).get("secrets")) else HOME / "secrets"

def setting_path(env: str, default: Path) -> Path:
    value = Path(os.environ.get(env, str(default))).expanduser()
    if not value.is_absolute():
        raise configuration.ConfigurationError(f"{env} must be an absolute path")
    return value

def source_path(name: str, default: Path) -> Path:
    value = configuration.load().get("sources", {}).get(name)
    return Path(value).expanduser() if value else default

def config_file(name: str) -> Path:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise configuration.ConfigurationError("Configuration name must be a filename")
    return CONFIG / name

REGISTRY = setting_path("OBSERVATORY_REGISTRY", HOME / "registry")
configuration.validate_registries(REGISTRY)
RAW = REGISTRY / "_raw"
STORE = HOME / "store"
SCRATCH = setting_path("OBSERVATORY_SCRATCH", STORE / "raw")
STATE = setting_path("OBSERVATORY_STATE", STORE)
DOCS = HOME / "docs"
DASHBOARD_HTML = setting_path("OBSERVATORY_DASHBOARD", DOCS / "projects-dashboard.html")
DASHBOARD_DIR = setting_path("OBSERVATORY_DASHBOARD_DIR", DASHBOARD_HTML.parent / "dashboard")
VAULT = configuration.source_path("wiki", "wiki", "OBSERVATORY_VAULT")
VAULT_PROJECTION = VAULT / "inventory"
DATA = configuration.source_path("projects", "projects", "OBSERVATORY_DATA")
NAMECHEAP_EXPORT = configuration.source_path("domain_export", "Domain_List.csv", "OBSERVATORY_DOMAIN_EXPORT")
FINDING_ACKS = setting_path("OBSERVATORY_ACKS", config_file("finding_acks.json"))
COMPANION_DB = configuration.source_path("companion_db", "claude-mem.db", "CLAUDE_MEM_DB")
SESSIONS = configuration.source_path("sessions", "sessions", "OBSERVATORY_SESSIONS")
DB = setting_path("OBSERVATORY_DB", STORE / "observatory.db")

def tighten() -> list[str]:
    ""                                                                

                                                                               
                                                                               
                                                                               
                                                                                
                                                                         
                                                                        

                                                                             
                                                                            
       
    changed: list[str] = []
    dirs = [STORE, STORE / "logs", SCRATCH, STATE, STATE / "logs"]
    files = [DB, *(STATE / "logs").glob("*.jsonl"), *SCRATCH.rglob("*.json"),
             *SCRATCH.rglob("*.jsonl")]
    for d in dirs:
        try:
            if not any(p.is_symlink() for p in (d, *d.parents)) and d.is_dir() and (d.stat().st_mode & 0o777) != 0o700:
                d.chmod(0o700)
                changed.append(str(d))
        except OSError:
            pass
    for f in files:
        try:
            if not any(p.is_symlink() for p in (f, *f.parents)) and f.is_file() and (f.stat().st_mode & 0o777) != 0o600:
                f.chmod(0o600)
                changed.append(str(f))
        except OSError:
            pass
    return changed
