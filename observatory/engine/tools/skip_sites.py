#!/usr/bin/env python3
""                                                                        

                                                                                                                                                                                                    
                                                                                
                              

                                                                                 
                                                                             
                                                                                  
                                                    

                                                                                
                                                                               
                                                                                
                                                                             
                                                           

                                                                               
                                                                             
                                                                            
                                              

                                                                      
                                                                                  
                                                                             
                                                                                
                                                                                 
                                                   

                                                     
                                                       
   
from __future__ import annotations
import argparse, ast, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

                                                                            
                                                                            
CALL_RX = re.compile(r'print\(f?"  (SKIP|NOTE)')

                                                                               
              
  
                                         
                                                        
  
                                                                      
                                                                               
                                                                               
                                                                                 
                                                                         
                                                                 
  
                                                                            
                                                                            
                                                                              
  
                                                                       
                                             
                                                                               
                                                          
                                                                               
                                                                     
                                                                                  
                                                                              
                                                                         
  
                                                                                   
                                                                
                                                                            
                                                                                
                                                                              
                                                                                
                                                                              
                                                                               
                                        




                                                                                 
                                                                                 
                                                           
  
                                                                               
                                                                                 
                                                                               
                                                                                
                                                                                 
          
CAPABILITY_REASONS: dict[str, str] = {
    "store": "no store|no live store|no store or registry",
    "node": r"\bnode\b",
    "jsonschema": "jsonschema",
    "sqlite-vec": "sqlite-vec",
    "embedding-key": "no embedding key",
    "launchd-job": "launchd",
    "agent-sync": "agent-sync",
    "sqlite-drop-column": "cannot DROP COLUMN",
    "claude-cli": "claude CLI",
    "estate": "estate is not on this machine",
}

CAPABILITY_RX = re.compile("|".join(CAPABILITY_REASONS.values()), re.I)


def cover_kind(message: str) -> str:
    ""                                                        

                                                                                
                                                                            
                                                                    

                                                                            
                                                                              
                                                                              
                                                                                
                                                                            
                                                                         
                                                                            
                                                                              
                                                                            
                                                                               
                                           
       
    if "[covered:" in message:
        return "named"
    if "[uncoverable:" in message:
        return "uncoverable"
    if "[gap:" in message:
        return "gap"
    if re.search(r"tests/test_[a-z_]+\.py", message):
        return "named"
    if CAPABILITY_RX.search(message):
        return "capability"
    return "none"


def _marker_of(node) -> tuple[str, str] | None:
    ""                                                                   
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return None
    fn = node.value.func
    if not (isinstance(fn, ast.Name) and fn.id == "print") or not node.value.args:
        return None
    parts: list[str] = []
    for arg in node.value.args:
        for piece in ast.walk(arg):
            if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                parts.append(piece.value)
    text = " ".join(parts).strip()
    m = re.match(r"(SKIP|NOTE)\s+(.*)", text, re.S)
    if not m:
        return None
    return m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()


def site_kinds(src: str) -> list[dict]:
    ""                                                                    

                                                                             
                                                                                
                                                                        

                                                          
                                                                                
                                                                                
                                                                              
                                                                       
                                     

                                                                             
                                                                                      
       
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out: list[dict] = []
    for parent in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(parent, field, None)
            if not isinstance(block, list):
                continue
            for i, node in enumerate(block):
                got = _marker_of(node)
                if got is None:
                    continue
                kind, message = got
                after = block[i + 1:]
                abandons = any(
                    isinstance(later, (ast.Return, ast.Continue, ast.Break))
                    for later in after)
                out.append({
                    "line": node.lineno,
                    "kind": kind,
                    "message": message,
                    "kind_of_site": "skip" if abandons else "annotation",
                    "cover_kind": cover_kind(message),
                })
    return sorted(out, key=lambda r: r["line"])


def _call_text(src: str, start: int) -> str:
    ""                                                                       
    i = src.index("(", start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    return src[i:]


def survey(where: pathlib.Path | None = None) -> list[dict]:
    ""                                                                        

                                                                                  
                                                                           
                                                                              
                                                  
       
    where = where or (ROOT / "tests")
    out: list[dict] = []
    for f in sorted(where.glob("test_*.py")):
        try:
            src = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for row in site_kinds(src):
            out.append({"file": str(f.relative_to(ROOT)), **row})
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    args = ap.parse_args(argv)
    sites = survey()
    named = [s for s in sites if s["cover_kind"] != "none"]
    if args.json:
        print(json.dumps({"sites": sites, "total": len(sites),
                          "explained": len(named)}, ensure_ascii=False, indent=1))
        return 0
    skips = [s for s in sites if s["kind_of_site"] == "skip"]
    notes = [s for s in sites if s["kind_of_site"] != "skip"]
    named = [s for s in skips if s["cover_kind"] != "none"]
    caps = [s for s in skips if s["cover_kind"] == "capability"]
    print(f"{len(skips)} site(s) where a block of assertions is SKIPPED — the print "
          f"is followed by a return or continue — in "
          f"{len({s['file'] for s in skips})} suite(s).")
    print(f"{len(named)} are explained: named cover, uncoverable, or waiting on a "
          f"machine capability ({len(caps)} of them).")
    if notes:
        print(f"{len(notes)} further marker(s) annotate a run whose assertions do "
              f"run; they are listed but not counted as skips.")
    print()
    for s in sites:
        if s["kind_of_site"] != "skip":
            mark = " note "
        else:
            mark = {"named": "cover", "uncoverable": "uncov",
                    "capability": " cap ", "none": "  -  "}[s["cover_kind"]]
        print(f"  {mark}  {s['file']}:{s['line']:<4} {s['kind']}  {s['message'][:70]}")
    if len(named) < len(skips):
        print(f"\n{len(skips) - len(named)} skip site(s) say nothing about who carries the "
              f"property. That is a judgement per site, not something this file can "
              f"decide — `gate.skips_uncovered` keeps the number visible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
