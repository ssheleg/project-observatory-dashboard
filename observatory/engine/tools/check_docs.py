#!/usr/bin/env python3
""                                                                               

                                                                                
                                                                                
                                                                                
                                                                              
                                                                                
                                                                               
    

                                                                            
                                                                            
                                                                                
                            

                                                                              
                                                                              
                                                                               
                                                                              
                                                                              
                                                     

                                                                               
                                                                        
                                                                               
                                                                           
                                                                       

                                                                  
                                                                 
   
from __future__ import annotations
import argparse, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
                                                                              
                                                                               
                                                                         
                                
import paths              

                                                                 
RETIRED_CLAIMS = [
    ("README.md", "not built yet",
     "the agent has been scheduled and spending since 2026-09-04; "
     "`store/wallet.json` and 106 ledger rows are the evidence"),
    ("observatory.py", "The LLM layer is a separate entry point and is not built yet",
     "the `agent` step is in the table fifty lines below the sentence"),
    ("observatory.py", "No model participates in any of these",
     "`agent` and `index` both spend; the docstring contradicted its own table"),
                                                                        
                                                                           
                                                                            
                                                                       
                                                                                 
                                                                                
                                                                    
                                                                                
                                                                                  
                                                                                 
                                                                 
    ("docs/heroku-estate.md", "it has not been done",
     "the collector shipped on 2026-09-09 in a5a415a: collectors/scan_heroku.py, "
     "the `heroku` step, registry/heroku-apps.json and four finding rules"),
    ("docs/ARCHITECTURE.md", "claude-mem` collector is designed and NOT built",
     "`collectors/scan_sessions.py` reads that store read-only and records one "
     "`session` event per (session, project); 57 projects carry a "
     "`last_session_on` from it and six changed activity tier"),
    ("docs/ARCHITECTURE.md", "grep -rn claude-mem` over the Python returns nothing",
     "it returns `collectors/scan_sessions.py` and the SRC-0012 declaration in "
     "`collectors/emit_registry.py`"),
    ("docs/ARCHITECTURE.md", "the vault's `tools/validate_inventory.py`",
     "removed from the vault when the registry moved here"),
]

                                                                                
                                                                   
                                                                          
                                                                            
                                                                         
                                                                           
                                                                         
                                                                               
PATH_PREFIX_ALLOWLIST = {
    "store/raw/": "collector and tool output; the whole directory is gitignored and "
                  "written by a run, so a fresh clone has none of it",
    "store/logs/": "written by launchd",
}

PATH_ALLOWLIST = {
                                                                             
    "store/observatory.db": "the store is gitignored and rebuilt",
    "store/observatory.db.backup-2026-09-06T2150Z": "a dated backup, gitignored",
    "store/wallet.json": "written by the provider boundary",
    "store/provider-health.json": "written by the provider boundary",
    "store/key-usage.json": "the KEY's own account state, written by the provider "
                            "boundary whenever it answers; gitignored",
    "store/.openrouter-key": "a secret the reader is told to create",
    "store/logs/tick.log": "written by launchd", "store/logs/tick.err": "written by launchd",
    "store/budget.json": "named by an early design that a later one superseded",
    "docs/projects-dashboard.html": "generated, gitignored",
                                                  
    "tools/validate_inventory.py": "removed from the vault when the registry moved here",
    "tools/build_dashboard.py": "the vault's copy, removed for the same reason",
                                                
}

                                                                              
                                                  
TOP_LEVEL = {p.name for p in ROOT.iterdir()
             if p.is_dir() and not p.name.startswith((".", "_"))}
PATH_RX = re.compile(r"`([a-zA-Z0-9_./-]+\.(?:py|json|md|sql|sh|js|jsonl|yaml|css|html))`")


                                                                                
                                                                                 
                                                                               
                                                                                 
  
                                                                               
                                                                                   
                                                                              
                                               
SCALE_CLAIM_RX = re.compile(r"\*\*\d+ projects across \d+ repositories and \d+ owners\*\*")


def scale_claim_failures(text: str, rel: str) -> list[str]:
    ""                                                                       

                                                                              
                                                                          
                                                                           
                                                                             
                                                                         
                                                                            
                                                                       

                                                                         
                                                                             
                              
       
    if not SCALE_CLAIM_RX.search(text):
        return []
                                                                            
                                                                               
                                                                               
                                                                              
                                                                               
                                                                    
    if re.search(r"[Mm]easured(?: on)? \d{4}-\d{2}-\d{2}", text):
        return []
    return [f"{rel} states a scale claim with no measurement date — an undated "
            f"figure reads as current for ever, and this one was five days stale "
            f"the day it was noticed"]


LEDGERS = (("docs/DECISIONS.md", "DEC"), ("docs/OPEN_QUESTIONS.md", "OQ"))

                                                                                     
                                                                              
                                                                            
                                                                           
                                                                              
                                                                                
                                                                        
VACANT_RX = re.compile(r"\*\*Vacant ids:\*\*(.*)")


def ledger_failures(path: pathlib.Path, prefix: str, rel: str) -> list[str]:
    ""                                              

                                                                                
                                                                                
                                                      
       
    out: list[str] = []
    text = path.read_text(encoding="utf-8")
    minted = [int(m) for m in re.findall(rf"^#+ {prefix}-(\d+)\b", text, re.M)]
    ids = sorted(set(minted))
                                                                              
                                                                            
                                                                                
                                                                                
    for dup in sorted({i for i in minted if minted.count(i) > 1}):
        out.append(f"{rel} mints {prefix}-{dup:04d} {minted.count(dup)} times — one id, "
                   f"one entry; renumber the later one to the next free id and say so "
                   f"in its first line")
    if not ids:
        return out
    top = max(ids)

    ptr = re.search(rf"\*\*Next free ID:\*\* `{prefix}-(\d+)`", text)
    if not ptr:
        out.append(f"{rel} carries no `Next free ID` pointer, so nothing tells the "
                   f"next writer which id is free — last one present is {prefix}-{top:04d}")
    elif int(ptr.group(1)) != top + 1:
        out.append(f"{rel} says `Next free ID: {prefix}-{ptr.group(1)}` while "
                   f"{prefix}-{top:04d} already exists — it should be "
                   f"{prefix}-{top + 1:04d}. This counter was once fixed by hand "
                   f"and it drifted again; bump it in the same edit that appends.")

                                                                                 
                                                                                             
                                                                              
                                                                        
                                                                                 
                                       
    if prefix == "OQ":
        for sec in re.split(r"(?m)^## ", text)[1:]:
            head = sec.split("\n", 1)[0].strip()
            if not re.match(rf"{prefix}-\d+", head):
                continue
            if not re.search(r"(?m)^- Status: ", sec):
                out.append(f"{rel} entry {head[:24]!r} carries no `- Status:` line, "
                           f"so nothing can count what is open without reading prose")

    declared = set()
    m = VACANT_RX.search(text)
    if m:
        declared = {int(x) for x in re.findall(rf"{prefix}-(\d+)", m.group(1))}
    gaps = {i for i in range(1, top + 1) if i not in set(ids)}
    for i in sorted(gaps - declared):
        out.append(f"{rel} has no {prefix}-{i:04d} and does not declare it vacant — "
                   f"a reader hunting for it cannot tell a lost entry from a skipped id")
    for i in sorted(declared - gaps):
        out.append(f"{rel} declares {prefix}-{i:04d} vacant, but it is present — "
                   f"the declaration is stale")
    return out



def shape_doc_failures() -> list[str]:
    ""                                                            

                                                                           
                                                                              
                                                                        

                                                                                
                                                                              
                                                                            
          
       
    doc = ROOT / "docs/REGISTRY_SHAPE.md"
    if not doc.is_file():
        return [f"docs/REGISTRY_SHAPE.md is missing — the registry calls itself "
                f"typed facts and nothing publishes the types; "
                f"`.venv/bin/python tools/registry_shape.py --write` writes it"]
    text = doc.read_text(encoding="utf-8")
    m = re.search(r"data=(\w+)", text)
    if not m:
        return ["docs/REGISTRY_SHAPE.md carries no data= stamp, so nothing can "
                "tell whether it describes the current registry"]
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import registry_shape
        live = registry_shape.stamp(registry_shape.shapes())
    except Exception as exc:                                                        
        return [f"the registry shape could not be computed: "
                f"{type(exc).__name__}: {exc}"]
    if m.group(1) != live:
        return [f"docs/REGISTRY_SHAPE.md describes shape {m.group(1)}, the live "
                f"registry is {live} — a field was added or removed; "
                f"`.venv/bin/python tools/registry_shape.py --write` regenerates it"]
    return []


def conformance_doc_failures() -> list[str]:
    ""                                                                  

                                                                                  
                                                                                
                                                                               
                                                                                 
                                                                             
               

                                                                             
                                                                                 
                                                                     
       
    doc = ROOT / "fabric/FABRIC-CONFORMANCE.md"
    manifest = ROOT / "fabric-agent.json"
    if not doc.is_file() or not manifest.is_file():
        return []
    text = doc.read_text(encoding="utf-8")
    try:
        m = json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"fabric-agent.json will not parse: {exc}"]
    out: list[str] = []
    for cap in m.get("capabilities") or []:
        if cap["name"] not in text:
            out.append(f"fabric/FABRIC-CONFORMANCE.md never names `{cap['name']}`, "
                       f"which fabric-agent.json declares — a host reads this "
                       f"document to learn the surface")
    rev = (m.get("provider") or {}).get("revision")
    if rev is not None and f"revision {rev}" not in text:
        out.append(f"fabric/FABRIC-CONFORMANCE.md does not name revision {rev}, "
                   f"which the manifest declares — the document describes a "
                   f"provider that no longer exists")
    return out


def failures() -> list[str]:
    from publish_contract import local_failures
    out: list[str] = list(local_failures())
    out += conformance_doc_failures()

                                                                    
    import observatory as obs
    doc = obs.__doc__ or ""
    named = set()
    for line in doc.splitlines():
        m = re.match(r"^\s{4}([a-z][a-z0-9-]+)\s{2,}\S", line)
        if m:
            named.add(m.group(1))
    unknown = sorted(named - set(obs.STEPS) - set(obs.GROUPS))
    if unknown:
        out.append(f"observatory.py's help names step(s) that do not exist: {unknown}")

                                                 
    for md in sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md", ROOT / "AGENTS.md"]:
        if not md.is_file():
            continue
        for path in sorted(set(PATH_RX.findall(md.read_text(encoding="utf-8")))):
                                                                              
                                                                       
                                                                               
                                                                              
                                                                                 
                                                                        
            first = path.split("/", 1)[0]
            if "/" not in path or first not in TOP_LEVEL:
                continue
            if (path in PATH_ALLOWLIST or path.startswith(("http", "~"))
                    or any(path.startswith(pre) for pre in PATH_PREFIX_ALLOWLIST)):
                continue
            if not (ROOT / path).exists():
                out.append(f"{md.relative_to(ROOT)} names {path}, which does not exist")

                                                                             
    manifest = json.loads((ROOT / "fabric-agent.json").read_text(encoding="utf-8"))
    revision = manifest["provider"]["revision"]
    conformance = ROOT / "fabric/FABRIC-CONFORMANCE.md"
    if conformance.is_file():
        text = conformance.read_text(encoding="utf-8")
        if f"revision {revision}" not in text and f"rev-{revision}" not in text:
            out.append(f"FABRIC-CONFORMANCE.md does not name revision {revision}, "
                       f"which is what fabric-agent.json declares")

                                                                                
                                                                               
                                                                               
                                                                                  
                                                                                
                                                                       
    declared = set()
    for cap in manifest.get("capabilities", []):
        for probe in (cap.get("profile") or {}).get("probes", []):
            declared.add(probe.get("name") or probe.get("id") or "")
    declared.discard("")
    if not declared:
        out.append("fabric-agent.json declares no probes at capabilities[].profile.probes "
                   "— either the manifest lost them or this rule is looking in the "
                   "wrong place, and both are defects")
    prose = ROOT / "fabric/probes/assertions.md"
    if prose.is_file() and declared:
        text = prose.read_text(encoding="utf-8")
        missing = sorted(p for p in declared if p not in text)
        if missing:
            out.append(f"fabric/probes/assertions.md — published to hosts — omits "
                       f"probe(s) the manifest declares: {missing}")
                                                                                
                                                                                 
                                                                                   
                                                                       
        for cap in manifest.get("capabilities", []):
            for probe in (cap.get("profile") or {}).get("probes", []):
                for a in probe.get("assertions", []):
                    if a not in text:
                        out.append(
                            f"assertions.md does not carry {probe.get('id')}'s assertion "
                            f"{a[:60]!r} — a host reads this instead of running the probe")

                                                                                 
                                                                               
                                                                            
    arch = ROOT / "docs/ARCHITECTURE.md"
    schema = ROOT / "store/schema.sql"
    if arch.is_file() and schema.is_file():
        tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)",
                                schema.read_text(encoding="utf-8")))
        text = arch.read_text(encoding="utf-8")
        missing = sorted(x for x in tables if x not in text)
        if missing:
            out.append(f"docs/ARCHITECTURE.md does not name table(s) the store has: {missing}")

                                                                                  
                                                                               
                                                                              
                                                                                
                                                                           
                                                                             
                                                                                
                                                                             
                                                                             
                                         
        for f in sorted(paths.REGISTRY.glob("*.json")):
            if f.name not in text:
                out.append(f"docs/ARCHITECTURE.md does not name registry document "
                           f"`{f.name}`, which exists")

                                                                                 
                                                                              
                                                                           
                                                                          
        exp = paths.REGISTRY / "ledger.jsonl"
        if exp.is_file():
            try:
                head = json.loads(exp.read_text(encoding="utf-8").splitlines()[0])
            except (ValueError, IndexError):
                head = {}
            if "TOMBSTONED REVISION" not in (head.get("_tombstoned_text_is_here") or ""):
                out.append("registry/ledger.jsonl's header does not say that it "
                           "carries tombstoned revisions' text, which it does")
            if "unreadable" not in (ROOT / "store/retention.py").read_text(
                    encoding="utf-8"):
                out.append("store/retention.py does not distinguish unreadable "
                           "from unrecoverable, which is what a tombstone does")

                                                                            
                                                                              
                                                                          
                                                       
        listed = ""
        for block in text.split("```"):
            if "project-observatory/" in block:
                listed = block
                break
        absent = sorted(d for d in TOP_LEVEL if f"{d}/" not in listed)
        if absent:
            out.append(f"docs/ARCHITECTURE.md's component tree omits: {absent}")

                                                                                 
                                                                               
                                                                               
                                               
        volatile = re.findall(r"\b\d[\d,]{2,}\s+(?:events|revisions|scans|deltas|ledger rows)\b",
                              text)
        if volatile:
            out.append(f"docs/ARCHITECTURE.md quotes a store-row count: {volatile[:3]} — "
                       f"name the command that measures it instead")

                                                                                 
                                                                          
                                                                             
                                                                               
                                                                               
                                                                                
                                                                               
                            
    snapshot = ROOT / "docs/AGENT_SYNC.md"
    cfg_file = ROOT / ".claude/agent-sync.json"
    if snapshot.is_file() and cfg_file.is_file():
        import hashlib
        head = snapshot.read_text(encoding="utf-8").split("\n", 1)[0]
        stamped = re.search(r"cfg=(\w+)", head)
        actual = hashlib.sha256(cfg_file.read_bytes()).hexdigest()[:12]
        if not stamped:
            out.append("docs/AGENT_SYNC.md carries no cfg= stamp, so nothing can tell "
                       "whether it describes the current configuration")
        elif stamped.group(1) != actual:
            out.append(f"docs/AGENT_SYNC.md describes configuration {stamped.group(1)}, "
                       f"the live one is {actual} — regenerate with `agent_sync.py setup`")

                                                                                 
    for rel, prefix in LEDGERS:
        f = ROOT / rel
        if f.is_file():
            out += ledger_failures(f, prefix, rel)

                                                                                 
     
                                                                             
                                                                               
                                                                               
                                                                                   
                                                                            
                                                                               
                                                                              
                                     
    obs_src = (ROOT / "observatory.py").read_text(encoding="utf-8")
    keys = re.findall(r'^    "([a-z0-9-]+)": \[', obs_src, re.M)
    for name in sorted({k for k in keys if keys.count(k) > 1}):
        out.append(f"observatory.py declares step {name!r} {keys.count(name)} times — "
                   f"Python keeps the last and drops the rest silently; rename one")
    groups_blk = re.search(r"^GROUPS = \{(.*?)^\}", obs_src, re.S | re.M)
    if groups_blk:
        for gname, gbody in re.findall(r'"([a-z0-9-]+)":\s*\[(.*?)\]',
                                       groups_blk.group(1), re.S):
            listed = re.findall(r'"([a-z0-9-]+)"', gbody)
            for name in sorted({x for x in listed if listed.count(x) > 1}):
                out.append(f"observatory.py group {gname!r} lists {name!r} "
                           f"{listed.count(name)} times — it would run that many times")

                                                                   
     
                                                             
                                                                              
                                                                            
                                                                                 
                                                                                
                                                                             
                                                                          
                                         
     
                                                                             
                                                                              
                                                                     
    grouped = set()
    if groups_blk:
        for _g, gbody in re.findall(r'"([a-z0-9-]+)":\s*\[(.*?)\]',
                                    groups_blk.group(1), re.S):
            grouped |= set(re.findall(r'"([a-z0-9-]+)"', gbody))
        for name in sorted(k for k in set(keys) if k.startswith("test-")):
            if name not in grouped:
                out.append(f"observatory.py declares step {name!r} and no group runs it "
                           f"— a suite outside every group is a suite that has stopped "
                           f"being run, and it goes red without anybody noticing")

                                                                   
                                                                          
    for rel in ("README.md", "AGENTS.md", "docs/ARCHITECTURE.md"):
        f = ROOT / rel
        if f.is_file():
            out += scale_claim_failures(f.read_text(encoding="utf-8"), rel)

                                                                      
    out += shape_doc_failures()

                                              
    for rel, phrase, why in RETIRED_CLAIMS:
        f = ROOT / rel
        if not f.is_file():
            continue
                                                                                
                                                                               
                                                                           
                                                                                
        text = "\n".join(
            re.sub(r'"[^"]*"', "", line) for line in f.read_text(encoding="utf-8").splitlines())
        if phrase in text:
            out.append(f"{rel} still says {phrase!r} — {why}")

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="what is checked")
    if ap.parse_args().list:
        print("1  every step the CLI's help names exists in its step table")
        print("2  every repository path a document names resolves")
        print("3  FABRIC-CONFORMANCE.md names the manifest's current revision")
        print("4  fabric/probes/assertions.md lists every declared probe")
        print(f"5  {len(RETIRED_CLAIMS)} retired claim(s) are absent")
        print("6  ARCHITECTURE.md names every table the store has")
        print("7  its component tree lists every top-level directory")
        print("8  and it quotes no store-row count")
        print("9  docs/AGENT_SYNC.md describes the LIVE agent-sync config")
        print("10 each ledger's `Next free ID` and vacant-id declaration "
              "agree with the ids it carries")
        print("11 no step name is declared twice, and no group lists one twice")
        print("12 every `test-*` step is reachable from at least one group")
        print("13 a scale claim carries the date it was measured on")
        print("14 docs/REGISTRY_SHAPE.md describes the LIVE registry's fields")
        return 0
    bad = failures()
    if not bad:
        print("documentation is current against every rule this file checks")
        return 0
    print(f"{len(bad)} documentation drift(s):", file=sys.stderr)
    for b in bad:
        print(f"  - {b}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
