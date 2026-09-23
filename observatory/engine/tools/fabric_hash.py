#!/usr/bin/env python3
"""Compute and stamp provider.contentHash in fabric-agent.json.

                                                            
                                                                        
                       

                                                                                 
                                                                      
                                                                                
                                                                                   
                                                                        
                                                        

Canonical form: UTF-8 JSON, keys sorted, no insignificant whitespace.
"""
from __future__ import annotations
import copy, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
                                                                            
                                                                            
                                                                                
                                                                               
                                                                              
                                                                              
import atomic                                                                    

MANIFEST = ROOT / "fabric-agent.json"


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute(manifest: dict) -> str:
    stripped = copy.deepcopy(manifest)
    stripped.get("provider", {}).pop("contentHash", None)
    return "sha256:" + hashlib.sha256(canonical(stripped)).hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    digest = compute(manifest)
    check = "--check" in sys.argv
    current = manifest.get("provider", {}).get("contentHash")
    if check:
        if current == digest:
            print(f"contentHash OK {digest}")
            return 0
        print(f"contentHash MISMATCH\n  stored:   {current}\n  computed: {digest}", file=sys.stderr)
        return 1
    manifest["provider"]["contentHash"] = digest
    atomic.write_text(MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"stamped {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
