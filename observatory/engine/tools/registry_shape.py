#!/usr/bin/env python3
""                                                                           

                                                                               
                                                                              
                                                                          
                                                                                 
                                                                                
                                                                   

                                                                              
                                                                           
                                                                              
                                                                                        
                                                                               
                                                                        

                                                                              
                                                                               
                                                                               
                                                                                  
                                              

                                                                                
                                                                                  
                                                                                
                                                      
                                                                                  
                                  

                                                                                 
                                                                             
                                                                                 
                            

                                                
                                                           
                                                                  
   
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic
import paths                                                                      

                                                                  
                                                                        
                                                                                
                                                                  
                                                                          
                                                                            
                                                                    
WRITE_CMD = "`.venv/bin/python tools/registry_shape.py --write`"

DOC = ROOT / "docs/REGISTRY_SHAPE.md"

                                                                                 
                                                                 
NESTED = ("local",)

                                                                                
                                           
EXAMPLES = 1


def _type_of(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        inner = {_type_of(v) for v in value[:8]}
        return f"list[{'|'.join(sorted(inner)) or 'empty'}]"
    if isinstance(value, dict):
        return "dict"
    return "null"


def _fields(records: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for key, value in rec.items():
            slot = out.setdefault(key, {"type": set(), "present": 0, "example": None})
            slot["present"] += 1
            slot["type"].add(_type_of(value))
            if slot["example"] is None and value not in (None, "", [], {}):
                slot["example"] = value
    for slot in out.values():
        kinds = sorted(k for k in slot["type"] if k != "null") or ["null"]
        slot["type"] = "|".join(kinds)
        ex = slot.pop("example")
        slot["example"] = (json.dumps(ex, ensure_ascii=False)[:60]
                           if ex is not None else "")
    return dict(sorted(out.items()))


def shapes() -> dict:
    ""                                                                         
    out: dict[str, dict] = {}
    for path in sorted(paths.REGISTRY.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
                                                                                
                                                                             
                                            
            out[path.name] = {"unreadable": f"{type(exc).__name__}: {exc}"}
            continue
        if not isinstance(doc, dict):
            out[path.name] = {"records": 0, "fields": {}, "nested": {},
                              "note": f"top level is {_type_of(doc)}, not an object"}
            continue
                                                                              
                                                                                  
                                                                            
                                                                                
                                                      
        lists = [(k, v) for k, v in doc.items() if isinstance(v, list)]
        key = max(lists, key=lambda kv: len(kv[1]))[0] if lists else None
        if key is None:
            out[path.name] = {"records": 1, "collection": "",
                              "fields": _fields([doc]), "nested": {}}
            continue
        records = [r for r in doc[key] if isinstance(r, dict)]
        nested: dict[str, dict] = {}
        for block in NESTED:
            inner = [r[block] for r in records
                     if isinstance(r.get(block), dict) and r[block]]
            if inner:
                nested[block] = _fields(inner)
        out[path.name] = {"records": len(records), "collection": key,
                          "fields": _fields(records), "nested": nested}
    return out


def stamp(data: dict) -> str:
    ""                                              

                                                                          
                                                                                  
                                                              
       
    skeleton = {
        name: {"records_present": bool(d.get("records")),
               "fields": {k: v["type"] for k, v in (d.get("fields") or {}).items()},
               "nested": {b: {k: v["type"] for k, v in f.items()}
                          for b, f in (d.get("nested") or {}).items()}}
        for name, d in data.items()}
    blob = json.dumps(skeleton, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def render(data: dict) -> str:
    lines = [f"<!-- generated by tools/registry_shape.py — data={stamp(data)} -->",
             "# The registry's shape",
             "",
             "**Generated. Do not edit** — " + WRITE_CMD + " rewrites it,",
             "and `tools/check_docs.py` fails when it is stale.",
             "",
             "`AGENTS.md` calls these documents typed facts, and nothing published the",
             "types until this file existed. Every field below carries how many records",
             "hold it, because an optional field listed beside a mandatory one teaches a",
             "reader it is always there.",
             ""]
    for name in sorted(data):
        d = data[name]
        lines.append(f"## `{name}`")
        lines.append("")
        if d.get("unreadable"):
            lines += [f"Does not parse: {d['unreadable']}", ""]
            continue
        head = f"{d['records']} record(s)"
        if d.get("collection"):
            head += f" under `{d['collection']}`"
        if d.get("note"):
            head += f" — {d['note']}"
        lines += [head, "", "| field | type | present | example |",
                  "|---|---|---|---|"]
        for key, slot in d["fields"].items():
            ex = slot["example"].replace("|", "\\|")
            lines.append(f"| `{key}` | `{slot['type']}` | {slot['present']}"
                         f" of {d['records']} | {ex} |")
        lines.append("")
        for block, fields in (d.get("nested") or {}).items():
            lines += [f"### `{block}`", "",
                      "| field | type | present | example |", "|---|---|---|---|"]
            total = max((s["present"] for s in fields.values()), default=0)
            for key, slot in fields.items():
                ex = slot["example"].replace("|", "\\|")
                lines.append(f"| `{key}` | `{slot['type']}` | {slot['present']}"
                             f" of {total} | {ex} |")
            lines.append("")
    lines.append(f"<!-- {datetime.now(timezone.utc).strftime('%Y-%m-%d')} -->")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--write", action="store_true",
                    help="regenerate docs/REGISTRY_SHAPE.md")
    args = ap.parse_args(argv)
    data = shapes()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return 0
    if args.write:
        DOC.parent.mkdir(parents=True, exist_ok=True)
        atomic.write_text(DOC, render(data))
        print(f"wrote {DOC.relative_to(ROOT)} — data={stamp(data)}")
        return 0
    for name in sorted(data):
        d = data[name]
        if d.get("unreadable"):
            print(f"{name}: {d['unreadable']}")
            continue
        print(f"{name}: {d['records']} record(s)"
              + (f" under `{d['collection']}`" if d.get("collection") else ""))
        for key, slot in d["fields"].items():
            print(f"    {key:26} {slot['type']:14} {slot['present']:>4}/{d['records']}"
                  f"  {slot['example'][:40]}")
        for block, fields in (d.get("nested") or {}).items():
            total = max((s["present"] for s in fields.values()), default=0)
            print(f"  {name} · {block}:")
            for key, slot in fields.items():
                print(f"    {key:26} {slot['type']:14} {slot['present']:>4}/{total}"
                      f"  {slot['example'][:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
