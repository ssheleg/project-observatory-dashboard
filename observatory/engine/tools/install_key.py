#!/usr/bin/env python3
""                                                                                 

                                                                                
                                                    
                                                                                    

                                                                                
                                         

                                                                                 
                                                                                 
                                                                                 
                                                                                   
                                                                                  
                                                                                  
                                                                                 

                                                                              
                                                                               
                                                                              
                                                                             
                                                                               
                                                        

                                                                                
                                                              

                                                                             
                                                                               
                      
   
from __future__ import annotations
import argparse
import json
import os
import pathlib
import stat
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import private_io
import paths                                                                    

#: consumer -> (file, what reads it). Enumerated, because a fourth consumer must
#: be a deliberate line here rather than a guess at install time.
DESTINATIONS: dict[str, tuple[pathlib.Path, str]] = {
    "observatory": (paths.STORE / ".openrouter-key",
                    "the tick's agent and indexer (`./observatory.py key` shows "
                    "what the SCHEDULED run resolves)"),
    "claude-mem": (paths.source_path("companion_home", paths.HOME / "disabled/companion") / ".env",
                   "the memory observer's worker, which reads this file and "
                   "nothing else"),
}
PROVISIONING = paths.source_path("secret_store", paths.SECRETS) / 'openrouter-provisioning'
API = "https://openrouter.ai"


def die(msg: str) -> None:
    sys.exit(f"install_key: {msg}")


def ask(path: str, key: str) -> tuple[int, dict]:
    req = urllib.request.Request(API + path, method="GET",
                                 headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
    except OSError as e:
        die("provider unreachable")
    return 0, {}


def kind_of(key: str) -> tuple[str, dict]:
    ""                                                                    

                                                                             
                                                                           
                                                                             
                  
       
    status, _ = ask("/api/v1/keys", key)
    if status == 200:
        return "provisioning", {}
    status, body = ask("/api/v1/key", key)
    if status == 200:
        return "inference", (body.get("data") or {})
    die(f"the provider does not recognise this key (HTTP {status}) — check that "
        f"it was copied whole")
    return "", {}


def write(dest: pathlib.Path, key: str, consumer: str) -> None:
    if dest == PROVISIONING:
        dest = private_io.legacy_path(dest)
    private_io.check(dest)
    with private_io.lock(dest.with_name("." + dest.name + ".install.lock")):
        if dest.name == ".env":
            old = private_io.read(dest) if dest.exists() else ""
            lines, replaced = [], False
            for line in old.splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    lines.append(f"OPENROUTER_API_KEY={key}")
                    replaced = True
                else:
                    lines.append(line)
            if not replaced:
                lines.append(f"OPENROUTER_API_KEY={key}")
            payload = "\n".join(lines) + "\n"
        else:
            payload = key
        private_io.write(dest, payload)
        if private_io.read(dest) != payload:
            raise RuntimeError("Credential delivery verification failed")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or 'Install a locally supplied provider key.').splitlines()[0])
    ap.add_argument("--for", dest="consumer", choices=sorted(DESTINATIONS),
                    help="which consumer reads this key (inference keys only)")
    a = ap.parse_args(argv[1:])

    if sys.stdin.isatty():
        die("the key must arrive on stdin, never in an argument — an argument "
            "lands in the shell history and in the process list.\n"
            "    run install_key with --for claude-mem and redirect a protected file to stdin")
    key = sys.stdin.read().strip()
    if not key:
        die("stdin was empty")
    if not key.startswith("sk-or-"):
        die("that does not look like an OpenRouter key (it should start `sk-or-`)")

    kind, info = kind_of(key)
    if kind == "provisioning":
        if a.consumer:
            print(f"note: --for {a.consumer} ignored — a provisioning key has one "
                  f"home and mints the others")
        write(PROVISIONING, key, "provisioning")
        print(f"provisioning key installed: {PROVISIONING} (600), "
              f"length {len(key)}; value hidden")
        print("  keys can now be minted, capped and revoked from this machine — "
              "`tools/revoke_key.py --list` reads it")
        return 0

    if not a.consumer:
        die("this is an INFERENCE key, so it needs a consumer:\n"
            + "\n".join(f"    --for {c:<12} {why}" for c, (_, why) in
                        sorted(DESTINATIONS.items())))
    dest, why = DESTINATIONS[a.consumer]
    write(dest, key, a.consumer)
    print(f"inference key installed for {a.consumer}: {dest} (600), "
          f"length {len(key)}; value hidden")
    print(f"  read by {why}")
    limit, rem = info.get("limit"), info.get("limit_remaining")
    reset = info.get("limit_reset")
    if limit is None:
        print("  the provider reports NO limit on this key — it can spend the "
              "whole account balance")
    else:
        reset_label = reset or ('NEVER — a lifetime cap, which drifts from a monthly '
                                'budget until the key dies for no visible reason')
        print(f"  limit {limit}, remaining {rem}, reset {reset_label}")
    if a.consumer == "claude-mem":
        print("  restart the worker so it picks this up:")
        print("    use the restart command for your configured companion installation")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (OSError, ValueError, RuntimeError):
        die("private credential operation refused; value hidden")
