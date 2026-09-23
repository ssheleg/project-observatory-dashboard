#!/usr/bin/env python3
""                                                                           

                                                                               
                                                                                 
                                                                              
                                                                            
                                                                            
                      

                                                                               
                                                                                    
                                                                                
                                                                          

                                                                                
                                                                                
                                                                           
                         

                                                               
                                                                             
                                                                          
                                             
   
from __future__ import annotations
import json, pathlib, re, sys, tomllib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths                                                                    

#: Depth 2 from a project folder: a monorepo keeps `packages/*/package.json`, and
#: a deeper walk starts counting vendored copies and example apps.
MAX_DEPTH = 2
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "vendor", "Pods", "target",
             "build", "dist", ".next", "__pycache__", "examples", "example",
             "fixtures", "testdata"}


def npm(text: str) -> set[str]:
    ""                                                                         

                                                                           
                                                                            
                                
       
    doc = json.loads(text)
    out: set[str] = set()
    for key in ("dependencies", "peerDependencies"):
        block = doc.get(key)
        if isinstance(block, dict):
            out |= set(block)
    return out


def pyproject(text: str) -> set[str]:
    doc = tomllib.loads(text)
    out: set[str] = set()
    proj = doc.get("project")
    if isinstance(proj, dict):
        for spec in proj.get("dependencies") or []:
            name = re.split(r"[<>=!~\[; ]", str(spec), 1)[0].strip()
            if name:
                out.add(name.lower())
    poetry = (((doc.get("tool") or {}).get("poetry") or {}).get("dependencies") or {})
    if isinstance(poetry, dict):
        out |= {k.lower() for k in poetry if k.lower() != "python"}
    return out


def requirements(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        # `-r other.txt`, `-e .`, `--index-url …`: directives, not dependencies.
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[; ]", line, 1)[0].strip()
        if name and not name.startswith(("http", "git+", ".", "/")):
            out.add(name.lower())
    return out


def cargo(text: str) -> set[str]:
    doc = tomllib.loads(text)
    deps = doc.get("dependencies")
    return set(deps) if isinstance(deps, dict) else set()


def composer(text: str) -> set[str]:
    doc = json.loads(text)
    req = doc.get("require")
    return {k for k in req if k != "php"} if isinstance(req, dict) else set()


def gradle(text: str) -> set[str]:
    ""                                                                        
                                                                       
                                                                          
                               
    out: set[str] = set()
    for m in re.finditer(r"""^\s*(?:api|implementation|compile)\s*[\('"]+([^'")\s]+)""",
                         text, re.M):
        spec = m.group(1)
        if ":" in spec:
            out.add(":".join(spec.split(":")[:2]))
    return out


#: filename -> parser. A format is added by adding a line here, and by nothing
#: else — the same property the plugin seam itself claims one level up.
PARSERS = {
    "package.json": npm,
    "pyproject.toml": pyproject,
    "requirements.txt": requirements,
    "Cargo.toml": cargo,
    "composer.json": composer,
    "build.gradle": gradle,
    "build.gradle.kts": gradle,
}


def manifests(root: pathlib.Path) -> list[pathlib.Path]:
    found: list[pathlib.Path] = []
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if depth < MAX_DEPTH and e.name not in SKIP_DIRS:
                    stack.append((e, depth + 1))
            elif e.name in PARSERS:
                found.append(e)
    return found


def count(folder: pathlib.Path) -> tuple[set[str], list[str]]:
    ""                                                                         
                                                                             
                
    names: set[str] = set()
    problems: list[str] = []
    for f in manifests(folder):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            got = PARSERS[f.name](text)
        except Exception as exc:                                                  
                                                                           
                                                                               
                                              
            problems.append(f"{f.name}: {type(exc).__name__}: {str(exc)[:60]}")
            continue
        eco = f.name.split(".")[0]
        names |= {f"{eco}:{n}" for n in got}
    return names, problems


def main() -> int:
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    projects = json.loads((paths.REGISTRY / "projects.json")
                          .read_text(encoding="utf-8"))["projects"]
    for p in projects:
        names: set[str] = set()
        problems: list[str] = []
        seen: set[str] = set()
        for folder in p.get("local_folders") or []:
            path = paths.DATA / folder
            if not path.is_dir():
                continue
            real = str(path.resolve())
            if real in seen:
                continue                                                          
            seen.add(real)
            got, bad = count(path)
            names |= got
            problems += bad
        if problems:
            print(f"{p['id']}: {'; '.join(problems[:3])}", file=sys.stderr)
        # A project with no manifest at all emits NO ROW rather than a zero: it
        # has no dependency surface to measure, which is different from having
        # measured one and found it empty.
        if names:
            print(json.dumps({"project_id": p["id"], "metric": "deps.direct",
                              "at": at, "value": float(len(names))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
