#!/usr/bin/env python3
""                                                                   

                                                                          
                                                                  
                                                                                

                                                                           
                                                                                 
                                                                             
                                                                                 
                                                                              
                                                      

                                                                                
                                                                               
                                

                                                                         

                                                                           
                                                                             
                                                                                
                                                                             
                                                                              
                                                                              
                                                                                
                                                   

                                                         

                                                                          
                                                                          
                                                                

                                                                             
                                                                      
                                                          
   
from __future__ import annotations
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths              
sys.path.insert(0, str(ROOT / "tools"))
import vault as private_files

VAULT = pathlib.Path(os.environ.get(
    "OBSERVATORY_VAULT_DIR",
    paths.source_path("secret_store", paths.SECRETS) / 'projects'))
AUDIT = paths.STATE / "logs" / "secret-use.jsonl"

                                                                             
                                                                               
                                                                              
ENVS = ("local", "stage", "prod")

                                                                               
                                                                              
                                  
CHUNK = 65536


def audit(action: str, subject: str, detail: dict) -> None:
    row = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "action": action, "subject": subject, **detail}
    private_files._append_private(AUDIT, json.dumps(row, ensure_ascii=False) + "\n")


def scan() -> dict:
    src = paths.SCRATCH / "env.json"
    if not src.is_file():
        return {"files": []}
    return json.loads(src.read_text(encoding="utf-8"))


def env_candidates(project: str, name: str) -> list[pathlib.Path]:
    ""                                                                  

                                                                               
                                                                               
                                                                             
       
    rows = []
    for f in scan().get("files", []):
        if f.get("project") != project:
            continue
        if name not in {v.get("name") for v in f.get("variables", [])}:
            continue
        rows.append(f)
    rows.sort(key=lambda f: (f.get("kind") != "env",
                             f.get("path", "").count("."),
                             f.get("path", "")))
    selected = []
    root = paths.DATA.absolute()
    private_files._no_symlinks(root)
    for row in rows:
        relative = pathlib.Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Inventory path must remain inside the configured projects root")
        target = root / relative
        private_files._no_symlinks(target)
        selected.append(target)
    return selected


def read_env_value(path: pathlib.Path, name: str) -> str | None:
    sys.path.insert(0, str(ROOT / "collectors"))
    import scan_env
    try:
        pairs, _ = scan_env.parse(private_files._read_private(path, private=False))
    except OSError:
        return None
    for n, v in pairs:
        if n == name:
            return v
    return None


def vault_slot(project: str, name: str, env: str | None) -> tuple[pathlib.Path | None, str | None]:
    private_files.validate_names(project, env, name)
    for e in ([env] if env else ENVS):
        slot = VAULT / project / e / name
        private_files._no_symlinks(slot)
        if slot.is_file():
            return slot, e
    return None, None


def resolve(project: str, name: str, env: str | None = None) -> tuple[str, str]:
    ""                                                                       
    slot, got_env = vault_slot(project, name, env)
    files = env_candidates(project, name)
    if slot is not None:
        if files:
            print(f"note: {name} is in the vault ({project}/{got_env}) and in "
                  f"{files[0].relative_to(paths.DATA)}; taking the vault. Two copies "
                  f"of one credential drift.", file=sys.stderr)
        return private_files._read_private(slot).strip(), f"vault:{project}/{got_env}/{name}"
    for f in files:
        value = read_env_value(f, name)
        if value:
            return value, f"env:{f.relative_to(paths.DATA)}"
    raise LookupError(
        f"{name} is not in the vault under projects/{project}/"
        f"{{{','.join(ENVS)}}} and not in any env file the inventory lists for "
        f"{project}. `use_secret.py names {project}` shows what is there; "
        f"`pbpaste | tools/vault.py put {project} local {name}` adds it.")


def _redaction(values: dict[str, str]):
    replacements = {value.encode("utf-8", "surrogateescape"): f"«{name}»".encode("utf-8")
                    for name, value in values.items() if value}
    pattern = re.compile(b"|".join(re.escape(value) for value in sorted(replacements, key=len, reverse=True))) if replacements else None
    return pattern, replacements


def scrub(data: bytes, values: dict[str, str]) -> bytes:
    pattern, replacements = _redaction(values)
    return pattern.sub(lambda match: replacements[match.group()], data) if pattern else data


def pump(src, dst, values: dict[str, str], longest: int) -> None:
    ""                                                                      

                                                                          
                                                                        
                     
       
    pattern, replacements = _redaction(values)
    longest = max((len(value) for value in replacements), default=1)
    carry = b""
    while True:
        chunk = src.read(CHUNK)
        final = not chunk
        buffer = carry + chunk
        safe_end = len(buffer) if final else max(0, len(buffer) - longest + 1)
        cursor = 0
        output = []
        while cursor < safe_end:
            match = pattern.search(buffer, cursor) if pattern else None
            if match is None or match.start() >= safe_end:
                output.append(buffer[cursor:safe_end])
                cursor = safe_end
            else:
                output.extend((buffer[cursor:match.start()], replacements[match.group()]))
                cursor = match.end()
        carry = buffer[cursor:]
        if output:
            dst.write(b"".join(output))
            dst.flush()
        if final:
            break


def cmd_names(args) -> int:
    private_files.validate_names(args.project)
    private_files._no_symlinks(VAULT / args.project)
    doc_path = paths.REGISTRY / "env-inventory.json"
    rows: list[tuple[str, str, str]] = []
    if doc_path.is_file():
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        for f in doc.get("files", []):
            if f.get("project") != args.project:
                continue
            for v in f.get("variables", []):
                rows.append((v["name"], v["class"], f["path"]))
    vdir = VAULT / args.project
    if vdir.is_dir():
        for directory in sorted(vdir.iterdir()):
            private_files._no_symlinks(directory)
            if not directory.is_dir() or directory.name not in private_files.ENVS:
                continue
            for slot in sorted(directory.iterdir()):
                private_files._no_symlinks(slot)
                if slot.is_file() and re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", slot.name):
                    rows.append((slot.name, "vault", f"vault:{args.project}/{directory.name}"))
    if not rows:
        print(f"{args.project}: nothing in the vault and nothing in the env "
              f"inventory. `./observatory.py env` refreshes the second.")
        return 0
    width = max(len(r[0]) for r in rows)
    seen = set()
    for name, cls, where in sorted(rows, key=lambda r: (r[1] != "vault", r[0])):
        key = (name, where)
        if key in seen:
            continue
        seen.add(key)
        print(f"  {name.ljust(width)}  {cls:11}  {where}")
    print(f"\n{len(seen)} name(s). Values are never printed — to USE one:\n"
          f"  tools/use_secret.py run {args.project} <NAME> -- <command>")
    return 0


def cmd_where(args) -> int:
    try:
        _, where = resolve(args.project, args.name, args.env)
    except LookupError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(where)
    return 0


def cmd_run(args) -> int:
    names = [n.strip() for n in args.names.split(",") if n.strip()]
    if not names:
        print("no variable named", file=sys.stderr)
        return 2
    if not args.command:
        print("nothing to run — put the command after `--`", file=sys.stderr)
        return 2
    values: dict[str, str] = {}
    wheres: dict[str, str] = {}
    for n in names:
        try:
            values[n], wheres[n] = resolve(args.project, n, args.env)
        except LookupError as exc:
            print(str(exc), file=sys.stderr)
            return 2
                                                                         
                                                            
    audit("use", f"{args.project}:{','.join(names)}",
          {"from": wheres, "command": args.command[0],
           "argv_len": len(args.command)})
    child_env = dict(os.environ)
    child_env.update(values)
    if args.as_name and len(names) == 1:
        child_env[args.as_name] = values[names[0]]
    longest = max(len(v.encode("utf-8", "surrogateescape")) for v in values.values())
    proc = subprocess.Popen(args.command, env=child_env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    import threading
    threads = [
        threading.Thread(target=pump, args=(proc.stdout, sys.stdout.buffer, values, longest)),
        threading.Thread(target=pump, args=(proc.stderr, sys.stderr.buffer, values, longest)),
    ]
    for t in threads:
        t.start()
    rc = proc.wait()
    for t in threads:
        t.join()
    proc.stdout.close()
    proc.stderr.close()
    return rc


                                                                               
                                                                           
                                                                              
                                                                                  
                                                                             
STDIN_PROGRAMS = {("python", "-"), ("python3", "-"), ("node", "-"), ("sh", "-s"),
                  ("bash", "-s"), ("zsh", "-s"), ("ruby", "-"), ("perl", "-")}


def cmd_pipe(args) -> int:
    ""                                                                       
                                                                               
                                                                                
       
    if not args.command:
        print("nothing to run — put the command after `--`", file=sys.stderr)
        return 2
    head = tuple(pathlib.Path(args.command[0]).name.split("-")[0:1] + args.command[1:2])
    if head in STDIN_PROGRAMS or (len(args.command) > 1 and args.command[1] in ("-", "-s")
                                  and pathlib.Path(args.command[0]).name in {a for a, _ in STDIN_PROGRAMS}):
        print(f"refused: `{' '.join(args.command[:2])}` reads its PROGRAM from stdin, and "
              f"stdin is carrying the secret. The parser would print the line it cannot "
              f"parse — that is the leak of 2026-09-14. Put the script in a file: "
              f"`… | use_secret.py pipe {args.name} -- python3 probe.py`", file=sys.stderr)
        return 2
    if sys.stdin.isatty():
        print("the value must arrive on stdin, e.g. `heroku config:get NAME -a app | "
              "use_secret.py pipe NAME -- <command>`", file=sys.stderr)
        return 2
    value = sys.stdin.read().strip()
    if not value:
        print("stdin was empty — nothing to hand the command", file=sys.stderr)
        return 2
    values = {args.name: value}
    audit("pipe", args.name, {"command": args.command[0], "argv_len": len(args.command)})
    child_env = dict(os.environ)
    child_env[args.name] = value
    longest = len(value.encode("utf-8", "surrogateescape"))
    proc = subprocess.Popen(args.command, env=child_env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    import threading
    threads = [
        threading.Thread(target=pump, args=(proc.stdout, sys.stdout.buffer, values, longest)),
        threading.Thread(target=pump, args=(proc.stderr, sys.stderr.buffer, values, longest)),
    ]
    for th in threads:
        th.start()
    rc = proc.wait()
    for th in threads:
        th.join()
    proc.stdout.close()
    proc.stderr.close()
    return rc


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("names", help="what this project has, values never printed")
    p.add_argument("project")
    p.set_defaults(fn=cmd_names)

    p = sub.add_parser("where", help="which slot a name would resolve to")
    p.add_argument("project")
    p.add_argument("name")
    p.add_argument("--env", choices=ENVS)
    p.set_defaults(fn=cmd_where)

    p = sub.add_parser("run", help="run a command with the value in its environment")
    p.add_argument("project")
    p.add_argument("names", help="one NAME, or several separated by commas")
    p.add_argument("--env", choices=ENVS)
    p.add_argument("--as", dest="as_name",
                   help="also export it under this name (one variable only)")
    p.add_argument("command", nargs=argparse.REMAINDER,
                   help="after `--`, the command to run")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("pipe", help="value on stdin -> env NAME -> run, output scrubbed")
    p.add_argument("name", help="the environment variable the command will read")
    p.add_argument("command", nargs=argparse.REMAINDER, help="after `--`, the command")
    p.set_defaults(fn=cmd_pipe)

    a = ap.parse_args(argv[1:])
    if getattr(a, "command", None) and a.command and a.command[0] == "--":
        a.command = a.command[1:]
    try:
        if getattr(a, "as_name", None):
            private_files.validate_names("placeholder", name=a.as_name)
        if a.cmd == "pipe":
            private_files.validate_names("placeholder", name=a.name)
        return a.fn(a)
    except (OSError, ValueError):
        print("use_secret: private filesystem or input validation refused the operation", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
