#!/usr/bin/env python3
""                                                     

                                                                               
                                                                                
                                    
   
from __future__ import annotations
import asyncio, json, os, pathlib, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup, PROJECT_ID as SYNTHETIC_PROJECT
portable_setup()

sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir              

from mcp import ClientSession, StdioServerParameters                              
from mcp.client.stdio import stdio_client                                         
import mcp.types as mtypes                                                        

REQUIRED = ["observatory_status", "observatory_project", "observatory_timeline",
            "observatory_recall", "observatory_record", "observatory_propose"]
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def payload(result) -> dict:
    if getattr(result, "structured_content", None):
        return result.structured_content
    for block in result.content:
        if isinstance(block, mtypes.TextContent):
            return json.loads(block.text)
    raise AssertionError("no JSON payload in tool result")


async def run() -> None:
                                                                             
                                   
    tmp = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-wire-")) / "test.db"
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / "mcp/server.py")], cwd=str(ROOT),
                                   env={**os.environ, "OBSERVATORY_DB": str(tmp)})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
                                                                                  
                                                                                   
                                                                             
                                                                              
            disc = await session.discover()
            check("server/discover offers 2026-07-28",
                  "2026-07-28" in disc.supported_versions, f"got {disc.supported_versions}")
            check("session adopts 2026-07-28",
                  session.protocol_version == "2026-07-28", f"got {session.protocol_version}")
            check("server instructions describe the degraded contract",
                  "degraded" in (disc.instructions or ""), (disc.instructions or "")[:60])

            listed = await session.list_tools()
            names = sorted(t.name for t in listed.tools)
            missing = [t for t in REQUIRED if t not in names]
            check("all three declared tools are served", not missing, f"missing {missing}")

            res = await session.call_tool("observatory_status",
                                          {"kind": "project",
                                           "value": SYNTHETIC_PROJECT})
            data = payload(res)
            check("status: counts.projects == 1", data["counts"]["projects"] == 1,
                  str(data["counts"]))
            check("status: degraded is present", "degraded" in data)
            check("status: evidence is non-empty", bool(data["evidence"]))
            rules = data["projects"][0]["membershipRules"]
            repos = data["projects"][0]["repositories"]
            check("status: every repository is named in a rule",
                  all(r["nameWithOwner"] in " \n".join(rules) for r in repos),
                  f"{len(repos)} repos, {len(rules)} rules")

            res = await session.call_tool("observatory_project",
                                          {"project_id": SYNTHETIC_PROJECT,
                                           "timeline_limit": 3})
            data = payload(res)
            check("project: returns the project", data.get("project", {}).get("id")
                  == SYNTHETIC_PROJECT, str(data)[:120])
            check("project: names the empty event store in degraded",
                  any("empty" in d["reason"] for d in data["degraded"]), str(data["degraded"])[:120])

            res = await session.call_tool("observatory_project", {"project_id": "project:does-not-exist"})
            data = payload(res)
            check("project: an unknown id is a typed answer, not a crash",
                  data.get("error") == "unknown project", str(data)[:120])

                                                                                       
                                                                                     
            res = await session.call_tool("observatory_timeline",
                                          {"project_id": SYNTHETIC_PROJECT, "limit": 5})
            data = payload(res)
            check("timeline: an empty store degrades honestly rather than returning silence",
                  data["events"] == [] and
                  any("empty" in d["reason"] for d in data["degraded"]), str(data)[:160])

            res = await session.call_tool("observatory_status", {"kind": "owner"})
            data = payload(res)
            check("a scope missing its value is a typed answer, not a crash",
                  data.get("error") == "missing value" and not res.is_error, str(data)[:120])

                                                                             
            res = await session.call_tool("observatory_record", {
                "statement": "wire test wrote this", "owner": "agent:wire-test",
                "project_id": "project:observatory-wire-test", "why": "to prove the path exists"})
            wrote = payload(res)
            check("record: an agent's note lands as proposed",
                  wrote.get("state") == "proposed", str(wrote)[:140])
            check("record: an agent's note carries confidence below 1",
                  (wrote.get("owner") == "agent:wire-test"), str(wrote)[:140])
            mid, rev = wrote.get("memoryId"), wrote.get("revision")

            res = await session.call_tool("observatory_record",
                                          {"statement": "no owner given"})
            check("record: a missing owner is refused by the schema, before the ledger",
                  bool(res.is_error), "expected a validation error")

            res = await session.call_tool("observatory_record", {
                "statement": "stale writer", "owner": "agent:wire-test",
                "memory_id": mid, "expected_revision": 99})
            conflict = payload(res)
            check("record: a stale revision returns a conflict with the current number",
                  conflict.get("error") == "RevisionConflict" and conflict.get("currentRevision") == rev,
                  str(conflict)[:160])

            res = await session.call_tool("observatory_record", {
                "statement": "another agent's rewrite", "owner": "agent:someone-else",
                "memory_id": mid, "expected_revision": rev})
            refused = payload(res)
            check("record: another agent cannot correct this record",
                  refused.get("error") == "OwnerRefused", str(refused)[:160])

            res = await session.call_tool("observatory_recall",
                                          {"project_id": "project:observatory-wire-test"})
            recalled = payload(res)
            check("recall: the note reads back",
                  any(r["memory_id"] == mid for r in recalled["records"]), str(recalled)[:140])
            check("recall: the answer says absence is not proof of absence",
                  "absence" in recalled.get("note", ""), recalled.get("note", "")[:60])

            before = (__import__("paths").REGISTRY / "projects.json").stat().st_mtime_ns
            res = await session.call_tool("observatory_propose", {
                "owner": "agent:wire-test", "target_id": "project:observatory-wire-test",
                "patch": {"description": "proposed, not applied"},
                "evidence": [{"uri": "test:wire"}]})
            prop = payload(res)
            check("propose: lands as proposed", prop.get("status") == "proposed", str(prop)[:140])
            check("propose: registry/projects.json is untouched",
                  (__import__("paths").REGISTRY / "projects.json").stat().st_mtime_ns == before)

            res = await session.call_tool("observatory_status", {"kind": "owner", "value": "example"})
            data = payload(res)
            check("owner scope selects only that owner",
                  data["counts"]["projects"] > 0 and
                  all(any(r["nameWithOwner"].startswith("example/") for r in p["repositories"])
                      for p in data["projects"] if p["repositories"]),
                  f"{data['counts']}")


if __name__ == "__main__":
    print("MCP wire — mcp/server.py over stdio\n")
    asyncio.run(run())
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mwire ok\033[0m")
