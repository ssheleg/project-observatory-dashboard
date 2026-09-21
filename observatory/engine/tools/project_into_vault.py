#!/usr/bin/env python3
""                                                                 

                                                                            
                                                                              
                                                                          
                                                    
   
from __future__ import annotations
import json, sys, pathlib
from datetime import datetime, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import atomic
import paths

HEADER = {
    "_generated": True,
    "_generated_by": "project-observatory/tools/project_into_vault.py",
    "_canonical_source": paths.REGISTRY.as_uri(),
    "_do_not_edit": "Edits here are overwritten on the next projection. Change the registry instead.",
}
                                                                              
                                                                           
                                                                            
                                                               
                                                                         
                                                                             
                                                                             
                                
  
                                                                              
                                                                             
                                                                        
NOT_MIRRORED: dict[str, str] = {}


def main() -> int:
    dest = paths.VAULT_PROJECTION
    if not dest.parent.is_dir():
        print(f"vault not found at {paths.VAULT} — set OBSERVATORY_VAULT", file=sys.stderr)
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    written, skipped = 0, []
    for src in sorted(paths.REGISTRY.glob("*.json")):
        name = src.name
        if name in NOT_MIRRORED:
            skipped.append({"file": name, "why": NOT_MIRRORED[name]})
            continue
        try:
            doc = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
                                                                                 
                                                                           
            skipped.append({"file": name, "why": f"unreadable: {type(exc).__name__}"})
            print(f"skip (unreadable): {name}", file=sys.stderr)
            continue
        if not isinstance(doc, dict):
            skipped.append({"file": name, "why": "not a JSON object, so no header "
                                                 "could be merged into it"})
            print(f"skip (not an object): {name}", file=sys.stderr)
            continue
                                                                             
                                                                       
                                                                              
                                                      
        atomic.write_json(dest / name, {**HEADER, **doc})
        written += 1
    snap_src, snap_dest = paths.REGISTRY / "snapshots", dest / "snapshots"
    if snap_src.is_dir():
        snap_dest.mkdir(exist_ok=True)
        for f in sorted(snap_src.glob("*.json")):
            (snap_dest / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            written += 1
    print(f"projected {written} files into {dest}")
    for sk in skipped:
        print(f"  not mirrored: {sk['file']} — {sk['why']}")
                                                                           
                              
    try:
        paths.SCRATCH.mkdir(parents=True, exist_ok=True)
        atomic.write_json(paths.SCRATCH / "projection.json", {
            "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "written": written, "skipped": skipped,
            "registry_documents": len(list(paths.REGISTRY.glob("*.json"))),
            "destination": str(dest)})
    except OSError as exc:
        print(f"could not write the projection report: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    import configuration
    if (True) and not configuration.enabled("wiki_projection", "features"):
        print("Not configured: enable features.wiki_projection explicitly")
        raise SystemExit(0)

    raise SystemExit(main())
