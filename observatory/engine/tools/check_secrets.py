#!/usr/bin/env python3
""                                                                             

                                                                             
                                                                             
                                                                             
                                                                              
                                                                         
               

                                                                                  
                                                                       
                                                                               
              

                                                                   
                                                                    
                             
                             
                                                                             

                                                                            
                                                                  
                                               

                                                                                 
                                                                                 
                                                                               
                                                                         

                                                                          
                                                                          
                                                                         
                                                                               
                                                                                
                                                                          
                                                                      

                                                                                  
                                                                             
                                                                          
                                                                               
                                                                               
                                                         

                                                                              
                                                                        
   
from __future__ import annotations
import argparse, collections, json, math, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

                                                                             
                                                                                
                                                                          
                                                                               
                                                                             
  
                                                           
  
                                                                       
                                                                        
                                                                      
                                      
  
                                                                         
                                                                 
NORMALISED_FLOOR = 0.78

                                                                                
                                                                              
                                                                            
                                                                            
                                                                         
                                                                               
MIN_BODY = 24

#: Shapes a vendor defines precisely enough that the prefix alone is the answer.
#: A false positive here costs one allowlist line with a reason; a false negative
#: is a leaked credential.
EXACT_SHAPES = {"aws access key", "google api key"}

#: (name, pattern). Each is a vendor prefix that means "this is a credential"
#: rather than a guess about shape. The generic assignment rule at the end is
#: what catches an unbranded token.
PATTERNS = [
    ("openai/openrouter", re.compile(r"\bsk-(?:or-v1-|proj-|ant-api03-)?[A-Za-z0-9_\-]{16,}")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}")),
    ("github fine-grained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("linear api key", re.compile(r"\blin_api_[A-Za-z0-9]{16,}")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}")),
    ("google api key", re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY")),
    # An unbranded token assigned to a name that says what it is. The name is
    # what makes it worth measuring; the entropy is what decides.
    ("named secret", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|passwd|password)\b\s*[:=]\s*"
        r"['\"]([A-Za-z0-9_\-+/=]{20,})['\"]")),
]

                                                                              
                                                                        
                                                                            
                                                                          
                                                                     
                                                                                
                                                                               
                                                                               
                                                                           
                                                                               
                                                                             
            
  
                                                                               
                                      
ALLOWLIST: dict[str, str] = {
    "tools/check_secrets.py":
        "this file IS the scanner; the literals here are its detection patterns, "
        "and a pattern that matches a private-key header is not one",
    "tests/test_secrets.py":
        "the fixtures that drive the scanner, including a truncated private-key "
        "header with no key material — planted so the detector can be watched "
        "detecting",
                                                                         
                                                                           
                                                                            
                                                                             
                                                                              
                                                                          
    "tests/test_project_secrets.py":
        "a planted service-account file whose private-key header was written out "
        "once (b78147b) over a body that is plainly not key material; the tree "
        "composes the header now, so this covers the history hit only",
}

#: Paths never scanned, with the reason. This file quotes every pattern it hunts
#: for, and the decisions log quotes the audit's findings verbatim.
SKIP = {
    "tools/check_secrets.py": "it contains the patterns themselves",
    "docs/DECISIONS.md": "it quotes the audit's findings, including the fixture",
    "tests/test_secrets.py": "it plants credentials to prove the check refuses them",
}


def entropy(s: str) -> float:
    if not s:
        return 0.0
    f = collections.Counter(s)
    return -sum((c / len(s)) * math.log2(c / len(s)) for c in f.values())


def normalised(s: str) -> float:
    ""                                                                

                                                                              
                                                                                  
                
       
    if len(s) < 2:
        return 0.0
    return entropy(s) / math.log2(len(s))


def body_of(match: str) -> str:
    ""                                                 

                                                                            
                                                                               
                                                                           
       
    for pre in ("sk-or-v1-", "sk-proj-", "sk-ant-api03-", "sk-", "github_pat_",
                "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "lin_api_", "AKIA", "AIza"):
        if match.startswith(pre):
            return match[len(pre):]
    return match


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit(f"check_secrets: `git ls-files` failed: {out.stderr[:200]}")
    return [l for l in out.stdout.splitlines() if l]


def scan_text(text: str, where: str) -> list[dict]:
    hits = []
    for label, rx in PATTERNS:
        for m in rx.finditer(text):
            raw = m.group(1) if m.groups() else m.group(0)
            if label == "private key block":
                hits.append({"where": where, "kind": label, "entropy": None,
                             "why": "a private key block is a credential whatever "
                                    "its contents"})
                continue
            body = body_of(raw)
            line = text[:m.start()].count("\n") + 1
            if label in EXACT_SHAPES:
                hits.append({"where": f"{where}:{line}", "kind": label,
                             "entropy": round(entropy(body), 2),
                             "normalised": round(normalised(body), 2),
                             "credential": True, "length": len(raw),
                             "why": "the vendor defines this shape exactly, and "
                                    "entropy cannot separate a 16-character "
                                    "credential from a placeholder"})
                continue
            if len(body) < MIN_BODY:
                # Too short to measure and not an exact shape: reported, never
                # silently dropped, because "below the measurable length" is a
                # different answer from "measured and harmless".
                hits.append({"where": f"{where}:{line}", "kind": label,
                             "entropy": round(entropy(body), 2),
                             "normalised": round(normalised(body), 2),
                             "credential": False, "length": len(raw),
                             "why": f"body is {len(body)} chars, under the {MIN_BODY} "
                                    f"entropy needs to mean anything"})
                continue
            n = normalised(body)
            hits.append({"where": f"{where}:{line}", "kind": label,
                         "entropy": round(entropy(body), 2),
                         "normalised": round(n, 2),
                         "credential": n >= NORMALISED_FLOOR,
                         "length": len(raw)})
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history", type=int, default=0, metavar="N",
                    help="also scan the added lines of the last N commits")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    credentials, fixtures, allowed = [], [], []
    for rel in tracked():
        if rel in SKIP:
            continue
        f = ROOT / rel
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue                                                                   
        for hit in scan_text(text, rel):
            if rel in ALLOWLIST:
                allowed.append({**hit, "allowed_because": ALLOWLIST[rel]})
            elif hit.get("credential") or hit["entropy"] is None:
                credentials.append(hit)
            else:
                fixtures.append(hit)

    if a.history:
        out = subprocess.run(
            ["git", "log", f"-{a.history}", "-p", "--no-color", "--unified=0"],
            cwd=ROOT, capture_output=True, text=True, timeout=600)
                                                                            
                                                                         
                                                                                
                                                                                
                                                                             
                                                                       
         
                                                                             
                                                                               
                  
        per_file: dict[str, list[str]] = {}
        current = "history(unattributed)"
        for line in out.stdout.splitlines():
            if line.startswith("+++ b/"):
                current = line[6:].strip()
                continue
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                per_file.setdefault(current, []).append(line[1:])
        hits = []
        for rel_hist, lines in per_file.items():
            for hit in scan_text("\n".join(lines), f"history:{rel_hist}"):
                hit["file"] = rel_hist
                hits.append(hit)
        for hit in hits:
            if hit.get("file") in ALLOWLIST:
                allowed.append({**hit, "allowed_because": ALLOWLIST[hit["file"]]})
                continue
            if hit.get("credential") or hit["entropy"] is None:
                # ROTATION, not a rewrite. A rewrite breaks every clone and the
                # credential is compromised either way — the audit's own remedy
                # text says the same.
                hit["remedy"] = "rotate the credential at its issuer; a history "
                credentials.append(hit)
            else:
                fixtures.append(hit)

    if a.json:
        print(json.dumps({"credentials": credentials, "fixtures": fixtures,
                          "allowed": allowed, "normalised_floor": NORMALISED_FLOOR,
                          "min_body": MIN_BODY},
                         indent=1))
    else:
        for h in credentials:
            print(f"  CREDENTIAL  {h['where']}  {h['kind']}"
                  + (f"  entropy {h['entropy']}" if h.get("entropy") else ""))
        for h in fixtures:
            print(f"  fixture     {h['where']}  {h['kind']}  normalised "
                  f"{h.get('normalised')} < {NORMALISED_FLOOR}")
        for h in allowed:
            print(f"  allowed     {h['where']}  {h['allowed_because'][:60]}")
        print(f"{len(tracked())} tracked file(s); {len(credentials)} credential(s), "
              f"{len(fixtures)} fixture(s), {len(allowed)} allowed")
    if credentials:
        print("\nA credential in the tracked tree is rotated at its issuer FIRST, "
              "then removed. Rewriting history is not the fix: it breaks every "
              "clone and the credential is compromised either way.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
