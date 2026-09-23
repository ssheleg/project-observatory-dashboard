#!/usr/bin/env python3
""                                                                             

                                                                               
                                                                                
                                                                                 
                                                                                 
                                                                           
                                                              

                                                                                
     

                                                                               
                                                                    
                                                                  

                                                                             
                                                                            
                                                                        

                                                                            
                                                                               
                                                                                
                                                                        
                                                                           
                                                                                 
                                                                          
                         

                                                              
                                                       
                                                                        

                                                                                   
                                                                              
                                                                            
                                                                               
          
   
from __future__ import annotations
import argparse
import importlib.util
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import paths                                                                    
import tmp as tmpdir                                                            

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable

                                                                              
                                                                            
                                                                            
  
                                                         
                                                                               
                                                                             
                                                                                               
def _forget(work: pathlib.Path, name: str) -> None:
    ""                                                                         
    import json as _json
    proj = work / "projects.json"
    doc = _json.loads(proj.read_text(encoding="utf-8"))
    doc["projects"] = [p for p in doc["projects"] if p["id"] != f"project:{name}"]
    proj.write_text(_json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    repos = work / "repositories.json"
    doc = _json.loads(repos.read_text(encoding="utf-8"))
    doc["repositories"] = [r for r in doc["repositories"]
                           if not r["name_with_owner"].endswith(f"/{name}")]
    repos.write_text(_json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    rel = work / "relations.json"
    doc = _json.loads(rel.read_text(encoding="utf-8"))
    doc["relations"] = [r for r in doc["relations"] if name not in r["id"]]
    rel.write_text(_json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


MUTATIONS: list[dict] = [
    # ── the registry's own claims ──────────────────────────────────────────
    {"trap": "T1", "subject": "registry", "file": "relations.json",
     "find": '"id": "relation:example-app:implemented-by:example-org-example-app",',
     "replace": ('"id": "relation:example-app:implemented-by:planted",\n'
                 '      "type": "implemented_by",\n'
                 '      "from": "project:example-app",\n'
                 '      "to": "repository:example-org/unlinked-repository",\n'
                 '      "source_refs": []\n    },\n    {\n'
                 '      "id": "relation:example-app:implemented-by:example-org-example-app",'),
     "why": "one more repository attached to a project whose rules never name it "
            "— the adoption that took 36"},
                                                                        
                                                                              
                                                                               
                                                                             
                                                            
    {"trap": "T33", "subject": "source", "file": "collectors/repo_status.json",
     "find": '"status": "inactive"', "replace": '"status": "active"',
     "why": "a retirement that only recolours the row leaves the row"},
    {"trap": "T35", "subject": "registry", "file": "ledger.jsonl",
     "find": "\n", "replace": "\n", "sql": None, "truncate": True,
     "why": "an export that carries only its header is not a backup"},

    # ── the code that must refuse ─────────────────────────────────────────
    {"trap": "T7", "subject": "source", "file": "store/ledger.py",
     "find": 'raise OwnerRequired("a write must declare its owner; there is no default")',
     "replace": 'owner = owner or "operator"',
     "why": "the default argument that made anonymous writes operator-owned (BL-455)"},
    {"trap": "T15", "subject": "source", "file": "agent/observe.py",
     "find": "import argparse, json, os, sys, pathlib, sqlite3",
     "replace": 'import argparse, json, os, sys, pathlib, sqlite3\nVENDOR = "claude-opus-4"',
     "why": "a vendor id outside the provider boundary is wrong the day the "
            "provider renames it"},
    {"trap": "T13", "subject": "source", "file": "agent/providers.py",
     "find": "#: OBSERVATORY_KEY_FILE overrides the search entirely",
     "replace": ('BUDGET_FIELD = {"budget_tokens": 4096}\n'
                 '#: OBSERVATORY_KEY_FILE overrides the search entirely'),
     "why": "a ceiling that travels in the request is one the provider may ignore"},

    # ── the store's shape ─────────────────────────────────────────────────
    # `vec_notes_vector_chunks%` is what the guard measures, and the first
    # attempt planted `vec_probe_…` — invisible to it, reported as MISSED
    # against a guard that was fine. The name is the mutation.
    {"trap": "T34", "subject": "db",
     "sql": ["CREATE TABLE IF NOT EXISTS vec_notes_vector_chunks99 (contents BLOB)",
             "INSERT INTO vec_notes_vector_chunks99 VALUES (zeroblob(300000000))"],
     "why": "428 MB of empty pre-allocation is what a per-record partition key buys"},

    # ── the rest of the registry's claims ─────────────────────────────────
    {"trap": "T2", "subject": "registry", "file": "projects.json",
     "find": '"vault-overview:projects/example-app/example-app.md"', "replace": '',
     "why": "a site with no evidence is a domain that was merely mentioned somewhere"},
    # The repository must be one whose site evidence IS a `github:…:homepageUrl`,
    # or the fork branch is never reached and the guard reports nothing. The
    # first attempt marked a repository whose site came from a vault overview.
    {"trap": "T3", "subject": "registry", "file": "repositories.json",
     "patch": lambda d: [r.__setitem__("fork", True) for r in d["repositories"]
                         if r["name_with_owner"] == "example-org/example-app"],
     "file": "repositories.json",
     "guard": "tests/test_traps.py::test_t2_t3_sites",
     "why": "a fork inheriting its upstream's homepage credited two projects with "
            "sites they do not own"},
    {"trap": "T11", "subject": "registry", "file": "projects.json",
     "patch": lambda d: [p.pop("canonical_page", None) for p in d["projects"]
                         if p["id"] == "project:example-memory"],
     "why": "the curated value that vanished on the first rebuild from pure "
            "measurement, because it was read from the artefact being replaced"},
    {"trap": "T26", "subject": "registry", "file": "relations.json",
     "find": '"id": "relation:example-workbench:consumes:example-memory",',
     "replace": ('"id": "relation:planted:dangling",\n'
                 '      "type": "public_domain_of",\n'
                 '      "from": "domain:a-domain-that-is-gone.example",\n'
                 '      "to": "project:example-app",\n'
                 '      "source_refs": []\n    },\n    {\n'
                 '      "id": "relation:example-workbench:consumes:example-memory",'),
     "why": "removing a project left two edges pointing at nothing, and the "
            "validator was the wrong place to have to catch it"},
    {"trap": "T27", "subject": "registry", "file": "repositories.json",
     "find": '"name_with_owner": "previous-owner/example-skill",',
     "replace": '"name_with_owner": "example-org/example-skill",',
     "why": "a transferred repository whose old address still resolves was "
            "recorded as a second repository"},
    {"trap": "T29", "subject": "registry", "file": "relations.json",
     "find": '"id": "relation:example-app:implemented-by:example-org-example-app",',
     "replace": ('"id": "relation:example-sibling:implemented-by:example-sibling",\n'
                 '      "type": "implemented_by",\n'
                 '      "from": "project:example-sibling",\n'
                 '      "to": "repository:example-org/example-sibling",\n'
                 '      "source_refs": []\n    },\n    {\n'
                 '      "id": "relation:example-app:implemented-by:example-org-example-app",'),
     "why": "the third form of one mistake — a sibling absorbed because its "
            "folder was MENTIONED in a note"},
    {"trap": "T31", "subject": "registry", "file": "projects.json",
     "patch_dir": lambda w: _forget(w, "example-app"),
     "why": "a folder on disk that reaches the registry by no anchor at all"},

    # ── the rules that live in code ───────────────────────────────────────
    {"trap": "T5", "subject": "source", "file": "collectors/emit_registry.py",
     "find": 'authored = [r for r in rel_doc["relations"] if r["type"] not in DERIVED_TYPES]',
     "replace": ('authored = [dict(r, id=r["id"] + "-carried") for r in rel_doc["relations"]]'),
     "guard": "tests/test_traps.py::test_t4_t5_emit_is_idempotent",
     "why": "dedup keyed on the id rather than the edge is how relations doubled "
            "on every re-run"},
    {"trap": "T36", "subject": "source", "file": "tools/use_secret.py",
                                                                             
                                                                             
     "find": 'STDIN_PROGRAMS = {("python", "-"), ("python3", "-"), ("node", "-"), ("sh", "-s"),',
     "replace": 'STDIN_PROGRAMS = {("never", "-"),',
     "why": "a pipe into an interpreter that reads its program from stdin sends the "
            "secret into a parser that prints what it cannot parse"},
    {"trap": "T30", "subject": "source", "file": "collectors/emit_registry.py",
                                                                           
                                                                             
                                                                           
                      
                                                                                 
                                                                       
                                                                         
                                                                            
            
     "find": 'DERIVED_TYPES = {"implemented_by", "public_domain_of", "deployed_to", "credential_used_by", "part_of"}',
     "replace": 'DERIVED_TYPES = set()',
     "why": "an edge whose REASON vanished survives, because the emitter kept "
            "every relation it had ever written"},
                                                                                    
                                                                            
                                                                            
                                                                                 
                                                                              
                                                                          
                               
    {"trap": "R-heroku.app_down", "subject": "source", "file": "tools/heroku_findings.py",
     "find": 'if a["state"] not in ("down", "suspended") and not a.get("crashed"):',
     "replace": 'if True:',
     "guard": "tests/test_heroku.py::test_each_rule_fires_on_its_own_subject",
     "why": "a crashed dyno raises nothing, and an estate with nothing wrong "
            "looks exactly the same"},
    {"trap": "R-heroku.paying_for_nothing", "subject": "source", "file": "tools/heroku_findings.py",
     "find": 'if a["state"] != "resources-only":',
     "replace": 'if True:',
     "guard": "tests/test_heroku.py::test_each_rule_fires_on_its_own_subject",
     "why": "a database billing with no dyno to use it stops being reported"},
    {"trap": "R-heroku.orphan_app", "subject": "source", "file": "tools/heroku_findings.py",
     "find": "    return [row]",
     "replace": '    return [dict(row, subject=row["subject"] + ":" + o["name"]) for o in orphans]',
     "guard": "tests/test_heroku.py::test_each_rule_fires_on_its_own_subject",
     "why": "the aggregate grew a per-application field, which is how one row "
            "becomes nineteen — the clone.stale defect one subject over"},
    {"trap": "R-heroku.snapshot_stale", "subject": "source", "file": "tools/heroku_findings.py",
     "find": "if age is not None and age.days > STALE_AFTER_DAYS:",
     "replace": "if False:",
     "guard": "tests/test_heroku.py::test_a_stale_snapshot_withholds_every_estate_row",
     "why": "estate rows are built from a snapshot of any age, so a fixed "
            "application keeps raising a critical for ever"},
    {"trap": "T8", "subject": "source", "file": "skill/plugins/observatory-log/hooks/hooks.json",
     "find": '"hooks": {', "replace": '"hooks": {\n    "SessionStart": [],',
     "why": "854 tokens of doctrine at session start beat the family's routing "
            "block in live sessions"},
    {"trap": "T9", "subject": "source", "file": "store/schema.sql",
     "find": "SELECT 1, 'openai', 'text-embedding-3-small', 1536",
     "replace": "SELECT 1, 'openai', 'text-embedding-3-large', 1536",
     "why": "two writers into one vector column with different models degrades "
            "cosine silently"},
    {"trap": "T25", "subject": "source", "file": "collectors/scan_events.py",
     "find": 'args.insert(1, f"--since={horizon} days ago")',
     "replace": 'args.insert(1, "--since=3000 days ago")',
     "why": "the collector inserted what retention deleted, every thirty minutes, "
            "1161 events at a time"},
    # BOTH call sites. The guard greps the source AND drives a dead key through
    # the chain, so one site left intact keeps the grep green and the drive
    # honest — a partial mutation measures nothing.
    {"trap": "T14", "subject": "source", "file": "agent/providers.py",
     "edits": [('raise Retryable(f"HTTP {exc.code}: {detail}") from exc\n'
                '        if exc.code in (401, 403):',
                'raise Retryable(f"HTTP {exc.code}: {detail}") from exc\n'
                '        if exc.code in (499,):'),
               ('detail = exc.read().decode("utf-8", errors="replace")[:300]\n'
                '        if exc.code in (401, 403):',
                'detail = exc.read().decode("utf-8", errors="replace")[:300]\n'
                '        if exc.code in (499,):')],
     "why": "one dead key walked all three models and left all three unhealthy"},
    # BOTH spellings, because either alone leaves the redirect working and the
    # guard reports MISSED against a degradation that is still reachable.
    {"trap": "T18", "subject": "source", "file": "agent/providers.py",
     "edits": [('    search = ((pathlib.Path(os.environ["OBSERVATORY_KEY_FILE"]),)\n'
                '              if os.environ.get("OBSERVATORY_KEY_FILE") else KEY_FILES)',
                "    search = KEY_FILES"),
                                                                         
                                                                           
                                                                
               ('KEY_FILES = ((pathlib.Path(os.environ["OBSERVATORY_KEY_FILE"]),)\n'
                '             if os.environ.get("OBSERVATORY_KEY_FILE") else\n'
                '             (paths.STORE / ".openrouter-key",',
                'KEY_FILES = ((paths.STORE / ".openrouter-key",')],
     "why": "a machine-wide export made 'no credential' a state no test could "
            "reach, so a degradation nobody had watched work"},
    {"trap": "T28", "subject": "source", "file": "tools/audit_vault_links.py",
     "find": 'path = raw.split("#", 1)[0].strip()', "replace": "path = raw.strip()",
     "why": "an anchor read as part of the path is one of three false-positive "
            "classes that gave the wiki six broken links and it had none"},

    # ── the last six, so every trap carries an efficacy claim ─────────────
    {"trap": "T4", "subject": "source", "file": "collectors/emit_registry.py",
     "find": '"default_branch":r.get("default_branch") or prev.get("default_branch",""),',
     "replace": '"default_branch":(prev.get("default_branch","") + (r.get("default_branch") or "")),',
     "guard": "tests/test_traps.py::test_t4_t5_emit_is_idempotent",
     "why": "a field that carries the PREVIOUS OUTPUT forward is what made a "
            "wrong value impossible to clear — and it grows on every run"},
    {"trap": "T6", "subject": "source", "file": "store/retention.py",
     "find": "    for c in cands:\n        t = ledger.tombstone(",
     "replace": "    for c in []:\n        t = ledger.tombstone(",
     "guard": "tests/test_retention.py::test_an_old_proposed_row_is_tombstoned_not_deleted",
     "why": "a horizon that leaves no tombstone erases without an audit trail"},
    {"trap": "T10", "subject": "source", "file": "store/ledger.py",
     "find": '" LEFT JOIN tombstones t ON t.memory_id = l.memory_id"\n'
             '           " WHERE t.memory_id IS NULL")',
     "replace": '" LEFT JOIN tombstones t ON t.memory_id = l.memory_id"\n'
                '           " WHERE t.memory_id IS NULL AND l.state != \'contested\'")',
     "guard": "tests/test_ledger.py::test_conflicts_return_together",
     "why": "a retrieval that drops the contested side has quietly picked a winner"},
    {"trap": "T21", "subject": "db",
     "sql": ["INSERT INTO ledger (memory_id, revision, kind, owner, function, scope,"
             " statement, state, confidence, created_at, classification)"
             " VALUES ('planted-certainty', 1, 'note', 'agent:observer', 'semantic',"
             " 'project', 'a machine asserting certainty', 'proposed', 1.0,"
             " '2026-09-08T00:00:00Z', 'project-internal')"],
     "why": "the check that grepped for a min() call stayed green while a real "
            "run wrote confidence exactly 1.0"},
    {"trap": "T20", "subject": "source", "file": "tests/test_index.py",
     "find": '_CACHED = ("survey", "providers", "store.indexer", "store.ledger", "store.db", "store",',
     "replace": '_CACHED = ("survey", "providers", "store.indexer", "store.ledger", "store.db",',
     "step": "test-index",
     "why": "popping the submodule and not the package leaves `from store import "
            "db` reading the previous test's database — and it takes two tests "
            "in one process to show, which is why this one runs the whole suite"},
]

#: Traps whose guard plants its OWN defect and drives the real code against it,
#: so efficacy is established inside the suite rather than by this harness. The
#: value names the line that does the planting; the harness checks it is still
#: there. That is a weaker claim than a mutation and it is stated as one: it
#: proves the planting code exists, not that it still plants what it once did.
SELF_DRIVEN: dict[str, tuple[str, str]] = {
    "T12": ("tests/test_scan_ids.py", 'old = f"sessions-{FROZEN}"'),
    "T16": ("tests/test_skill.py", "plant"),
    "T17": ("tests/test_budget_subject.py", "KEY_SPENT"),
    "T19": ("tests/test_key_shape.py", "PLANTED"),
    "T22": ("tests/test_retention.py", '"snuck back in"'),
    "T23": ("tests/test_retention.py", "an erased record refuses a further revision"),
    "T32": ("tests/test_traps.py", '"why": "planted by T32"'),
    "T24": ("tests/test_retention.py", "R.indexer.load_vec"),
}


def guards() -> dict[str, list[tuple[str, str]]]:
    spec = importlib.util.spec_from_file_location("tm_eff", ROOT / "tools/trap_map.py")
    tm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tm)
    data, _ = tm.report()
    return {t: [(g["file"], g["function"]) for g in gs if g["function"]]
            for t, gs in data["by_trap"].items()}, data["declared"]


DRIVER = """
import importlib.util, pathlib, sys
ROOT = pathlib.Path({root!r})
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
spec = importlib.util.spec_from_file_location("suite_under_test", {suite!r})
m = importlib.util.module_from_spec(spec)
sys.modules["suite_under_test"] = m
spec.loader.exec_module(m)
getattr(m, {fn!r})()
print("SKIPPED" if not m.FAILURES and "SKIP" in "".join(m.FAILURES) else "")
sys.exit(1 if m.FAILURES else 0)
"""


def drive(suite: str, fn: str, env: dict) -> tuple[bool, str]:
    ""                                                                 

                                                                           
                                                                           
                                                                               
                    
       
    code = DRIVER.format(root=str(ROOT), suite=str(ROOT / suite), fn=fn)
    p = subprocess.run([PY, "-c", code], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=900)
    out = p.stdout + p.stderr
    return p.returncode == 0, out


def prepare(mut: dict) -> tuple[dict, pathlib.Path | None]:
    ""                                                                    
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    work = None
    if mut["subject"] == "registry":
        work = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-efficacy-")) / "registry"
        shutil.copytree(paths.REGISTRY, work)
        env["OBSERVATORY_REGISTRY"] = str(work)
    elif mut["subject"] == "db":
        work = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-efficacy-")) / "t.db"
        shutil.copy2(ROOT / "store/observatory.db", work)
        env["OBSERVATORY_DB"] = str(work)
    return env, work


def apply(mut: dict, work: pathlib.Path | None) -> None:
    if mut.get("patch_dir"):
                                                                             
                                                                                    
                                                                             
                                     
        mut["patch_dir"](work)
        return
    if mut["subject"] == "db":
        conn = sqlite3.connect(work)
        for stmt in mut["sql"]:
            conn.execute(stmt)
        conn.commit()
        conn.close()
        return
    target = (work / mut["file"]) if mut["subject"] == "registry" else (ROOT / mut["file"])
    text = target.read_text(encoding="utf-8")
    if mut.get("truncate"):
        target.write_text(text.splitlines(keepends=True)[0], encoding="utf-8")
        return
    if mut.get("patch"):
                                                                              
                                                                                
                                                                               
                                                                               
                                                                              
                                                                                 
        doc = json.loads(text)
        before = json.dumps(doc, sort_keys=True)
        mut["patch"](doc)
        if json.dumps(doc, sort_keys=True) == before:
            raise Stale(f"{mut['file']}: the patch changed nothing — its subject has moved")
        target.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        return
    for find, repl in mut.get("edits") or [(mut["find"], mut["replace"])]:
        n = text.count(find)
        if n != 1:
            raise Stale(f"{mut['file']}: the anchor occurs {n} times, expected exactly 1")
        text = text.replace(find, repl, 1)
    target.write_text(text, encoding="utf-8")


class Stale(Exception):
    ""                                                                     


def restore(mut: dict) -> None:
    if mut["subject"] != "source":
        return
    subprocess.run(["git", "checkout", "--", mut["file"]], cwd=ROOT,
                   capture_output=True, text=True, timeout=120)


def dirty(files: list[str]) -> list[str]:
    ""                                                                       

                                                                              
                                                                          
                                                                               
                                                                              
                                                                        
                                                           
       
    if not files:
        return []
    p = subprocess.run(["git", "status", "--porcelain", "--"] + files, cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    return [ln[3:] for ln in p.stdout.splitlines() if ln.strip()]


def run_step(step: str, env: dict) -> tuple[bool, str]:
    p = subprocess.run([PY, "observatory.py", step], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=1800)
    return p.returncode == 0, p.stdout + p.stderr


def run_one(mut: dict, guard: tuple[str, str]) -> tuple[str, str]:
    suite, fn = guard
    env, work = prepare(mut)
    run = ((lambda: run_step(mut["step"], env)) if mut.get("step")
           else (lambda: drive(suite, fn, env)))
    try:
        ok, control = run()
        if not ok:
            return "INCONCLUSIVE", f"the control run is already red: {control[-300:]}"
        apply(mut, work)
        ok, mutated = run()
        if ok:
            return "MISSED", "the guard passed with its own defect back in place"
        first = next((ln.strip() for ln in mutated.splitlines()
                      if ln.strip().startswith("FAIL")), mutated.strip()[-160:])
        return "CAUGHT", first[:160]
    except Stale as exc:
        return "INCONCLUSIVE", f"stale mutation — {exc}"
    finally:
        restore(mut)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or 'Run isolated diagnostic probes.').splitlines()[0])
    ap.add_argument("traps", nargs="*", help="only these traps (default: all declared)")
    ap.add_argument("--list", action="store_true", help="what is declared, without running")
    args = ap.parse_args(argv[1:])

    by_trap, declared = guards()
    want = args.traps or sorted({m["trap"] for m in MUTATIONS}, key=lambda t: int(t[1:]))
    plan = [m for m in MUTATIONS if m["trap"] in want]

    if args.list:
        for t in sorted(declared, key=lambda x: int(x[1:])):
            kind = ("mutation" if any(m["trap"] == t for m in MUTATIONS)
                    else "self-driven" if t in SELF_DRIVEN else "NOT DECLARED")
            print(f"  {t:5} {kind}")
        n = len({m['trap'] for m in MUTATIONS}) + len(SELF_DRIVEN)
        print(f"\n{n} of {len(declared)} trap(s) carry an efficacy claim; "
              f"{len(declared) - n} do not, and their guards are unmeasured.")
        return 0

    files = sorted({m["file"] for m in plan if m["subject"] == "source"})
    if files and (d := dirty(files)):
        print("REFUSING: these files carry uncommitted work and a restore would lose it:")
        for f in d:
            print("  -", f)
        return 2

    results: list[tuple[str, str, str]] = []
    for mut in plan:
        gs = by_trap.get(mut["trap"], [])
        if mut.get("step"):
            # The defect takes two tests in one process to show, so the subject
            # is the STEP. No guard function to resolve, and saying so beats
            # reporting "no guard declares this trap" about a trap whose guard
            # is the suite itself.
            gs = [(mut["step"], "")]
        elif mut.get("guard"):
            # An explicit guard, for a trap whose several guards do not all read
            # the mutation's subject. Named in the registry rather than guessed,
            # and checked: a stale name is reported, never silently skipped.
            rel, fn = mut["guard"].split("::")
                                                                               
                                                                                
                                                                                
                                                                               
                                                                              
                                                                     
            if mut["trap"] not in declared:
                path = ROOT / rel
                ok = path.is_file() and f"def {fn}(" in path.read_text(encoding="utf-8")
                gs = [(rel, fn)] if ok else []
                if not gs:
                    results.append((mut["trap"], "INCONCLUSIVE",
                                    f"the named guard {mut['guard']} does not exist"))
                    print(f"  INCONCLUSIVE  {mut['trap']} named guard {mut['guard']} "
                          f"does not exist")
                    continue
            else:
                gs = [(rel, fn)] if (rel, fn) in gs else []
            if not gs:
                results.append((mut["trap"], "INCONCLUSIVE",
                                f"the named guard {mut['guard']} does not declare this trap"))
                print(f"  INCONCLUSIVE  {mut['trap']:5} named guard {mut['guard']} is stale")
                continue
        if not gs:
            results.append((mut["trap"], "INCONCLUSIVE", "no guard declares this trap"))
            continue
        verdict, detail = run_one(mut, gs[0])
        results.append((mut["trap"], verdict, f"{gs[0][1]}: {detail}"))
        print(f"  {verdict:13} {mut['trap']:5} {detail[:110]}")

    for trap, (rel, marker) in sorted(SELF_DRIVEN.items(), key=lambda kv: int(kv[0][1:])):
        if trap not in want and args.traps:
            continue
        present = marker in (ROOT / rel).read_text(encoding="utf-8")
        results.append((trap, "SELF-DRIVEN" if present else "INCONCLUSIVE",
                        f"{rel} {'still plants' if present else 'NO LONGER contains'} {marker!r}"))
        if not present:
            print(f"  INCONCLUSIVE  {trap:5} {rel} no longer contains {marker!r}")

    if d := dirty([m["file"] for m in plan if m["subject"] == "source"]):
        print(f"\nTREE NOT RESTORED — {d}. Recover with: git checkout -- " + " ".join(d))
        return 2

    n = {v: sum(1 for _, x, _ in results if x == v)
         for v in ("CAUGHT", "MISSED", "SELF-DRIVEN", "INCONCLUSIVE")}
    unmeasured = len(declared) - len({t for t, _, _ in results})
    print(f"\n{n['CAUGHT']} caught, {n['MISSED']} MISSED, {n['SELF-DRIVEN']} self-driven, "
          f"{n['INCONCLUSIVE']} inconclusive; {unmeasured} of {len(declared)} trap(s) "
          f"carry no efficacy claim at all")
    (ROOT / "store/raw/trap-efficacy.json").write_text(json.dumps(
        {"results": [{"trap": t, "verdict": v, "detail": d} for t, v, d in results],
         "unmeasured": unmeasured, "declared": len(declared)},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if n["MISSED"] or n["INCONCLUSIVE"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
