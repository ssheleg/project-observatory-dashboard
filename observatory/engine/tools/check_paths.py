#!/usr/bin/env python3
""                                                                      

                                                                          
                                                                          
                                                                            
                                                                           
                                                                            
     

                                                                           
                                                                       

                                                                               
                                                                                
                                  
                                                                               
                                                                                 
                                                                          
                                                                                
                                                                              
                                                                             
             
                                                                          
                                      
                                                                          

                                                                      
                                                                              
                                                                                
                                                                             
                                                                            

                                                               

                                                                         

                                                                 
   
from __future__ import annotations
import ast, io, pathlib, re, sys, tokenize

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALLOW = "paths-check: allow"

                                                                              
                                                        
RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r'/\s*"store"\s*/\s*"raw"'), "paths.SCRATCH",
     "the collector output directory; six sites resolved it from ROOT"),
    (re.compile(r'(?:Path|open)\(\s*f?"store/raw'), "paths.SCRATCH",
     "same directory, built as a relative string"),
    (re.compile(r'else\s+f?"store/raw'), "paths.SCRATCH",
     "a relative default output path — scan_github.py wrote ten owner listings "
     "into store/raw/github, which nothing reads"),
    (re.compile(r'(?:STORE|ROOT)\s*/\s*"observatory\.db"'), "paths.DB",
     "the ledger; notify_findings.py wrote fixture rows into the live store"),
    (re.compile(r'/\s*"store"\s*/\s*"observatory\.db"'), "paths.DB",
     "the same, spelled out"),
    (re.compile(r'ROOT\s*/\s*"registry"'), "paths.REGISTRY",
     "the canonical fact base; a sandboxed registry must be redirectable"),
                                                                                
                                                                                
                                                                              
                                                                              
                                              
    (re.compile(r'(?:Path|open)\(\s*f?"registry/'), "paths.REGISTRY",
     "the registry as a relative string; a sandboxed registry must be "
     "redirectable however the path is spelled"),
                                                                              
                                                                               
                                                                                
                                        
    (re.compile(r'home\(\)\s*/\s*"DATA"'), "paths.DATA",
     "the estate root; a machine that keeps its projects elsewhere is the case "
     "the resolver exists for"),
                                                                                   
                                                                                 
                                                                                
                                                                                 
                                                                        
                 
    (re.compile(r'/\s*"registry"\s*/\s*"_raw"'), "paths.RAW",
     "the registrar exports the validator compares against"),
                                                                               
                                                                                
                                                                                  
                                                                                 
                                                                              
                                                                               
    (re.compile(r'tempfile\.mkdtemp\('), "tests/tmp.mkdtemp (imported as `tmpdir`)",
     "mkdtemp leaves its directory behind; a gate that cannot run twice is not "
     "a gate"),
]

                                                                                
                                                                              
                                                                               
                                 
EXEMPT_FILES = {
    "paths.py": "it is where the overridable variables are DEFINED",
    "tools/check_paths.py": "it quotes every pattern it hunts for",
    "tests/tmp.py": "it WRAPS `tempfile.mkdtemp` — being the one place that "
                    "calls it is the point of the file",
}


def prose_removed(src: str) -> str:
    ""                                                          

                                                                               
                                                                               
                                                                                  
                                             

                                                                             
                                                                     
                                                           
                                                                                
                                                                          
                                                                          
                         

                                                                  
       
    grid = [list(l) for l in src.splitlines(keepends=True)]

    def blank(r1: int, c1: int, r2: int, c2: int) -> None:
        for row in range(r1 - 1, min(r2, len(grid))):
            line = grid[row]
            start = c1 if row == r1 - 1 else 0
            end = c2 if row == r2 - 1 else len(line)
            for col in range(start, min(end, len(line))):
                if line[col] != "\n":
                    line[col] = " "

    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            blank(tok.start[0], tok.start[1], tok.end[0], tok.end[1])
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            d = body[0].value
            blank(d.lineno, d.col_offset, d.end_lineno, d.end_col_offset)
    return "".join("".join(l) for l in grid)


def sources() -> list[pathlib.Path]:
    out = []
    for f in sorted(ROOT.rglob("*.py")):
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith((".venv/", "node_modules/", "store/raw/")):
            continue
        if rel in EXEMPT_FILES:
            continue
        out.append(f)
    return out


def main() -> int:
    bad: list[str] = []
    allowed = 0
    for f in sources():
        rel = f.relative_to(ROOT).as_posix()
        raw = f.read_text(encoding="utf-8")
        try:
            code = prose_removed(raw)
        except (SyntaxError, tokenize.TokenError, IndentationError) as exc:
                                                                               
                                                                                
            bad.append(f"{rel}: cannot be read as Python: {type(exc).__name__}: {exc}")
            continue
                                                                                
                                                                             
                                                                            
                                                                              
                                         
        for n, (line, shown) in enumerate(zip(code.splitlines(),
                                              raw.splitlines()), 1):
            for pat, use, why in RULES:
                if not pat.search(line):
                    continue
                if ALLOW in shown:
                    allowed += 1
                    continue
                bad.append(f"{rel}:{n}: resolve this through {use} — {why}\n"
                           f"    {shown.strip()[:110]}")
                break
    for b in bad:
        print(b)
    print(f"checked {len(sources())} python files; {len(bad)} violation(s); "
          f"{allowed} allowed by marker")
    if bad:
        print("\nEach of these is an input a test cannot redirect. Six were found by "
              "hand in one sitting; this check exists so the seventh is found here.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
