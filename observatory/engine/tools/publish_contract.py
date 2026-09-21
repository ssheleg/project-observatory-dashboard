#!/usr/bin/env python3
""                                                                           

                                                                              
                                                                             
                                                                            
                                                                               
                                                                              
   
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configuration
import workspace
from fabric_hash import compute

MANIFEST = ROOT / "fabric-agent.json"
PUBLIC_NWO = "ssheleg/project-observatory-open-source"
RAW = "https://raw.githubusercontent.com/" + PUBLIC_NWO
SCHEMA_RELEASE = json.loads((ROOT / "fabric-contract.lock.json").read_text())["schemaRelease"]
if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", SCHEMA_RELEASE):
    raise ValueError("Invalid pinned schema release")
PREFIX = f"{RAW}/{SCHEMA_RELEASE}/observatory/engine/fabric/"
PUBLISHABLE = (("fabric/schemas", "schemas", "*.json"),
               ("fabric/fixtures", "fixtures", "*.json"))


def revision() -> int:
    return int(json.loads(MANIFEST.read_text())["provider"]["revision"])


def staged(rev: int | None = None) -> dict[str, str]:
    ""                                                                     
    return {f"{dest}/{path.name}": path.read_text(encoding="utf-8")
            for source, dest, pattern in PUBLISHABLE
            for path in sorted((ROOT / source).glob(pattern))}


def manifest_uris() -> list[str]:
    return sorted(set(re.findall(r'"(https://raw\.githubusercontent\.com/[^"]+)"',
                                 MANIFEST.read_text(encoding="utf-8"))))


def local_failures() -> list[str]:
    doc = json.loads(MANIFEST.read_text())
    files = staged()
    failures = []
    if not files or not manifest_uris():
        failures.append("schema/fixture publication set is empty")
    if doc.get("provider", {}).get("contentHash") != compute(doc):
        failures.append("manifest content hash differs")
    for uri in manifest_uris():
        if not uri.startswith(PREFIX) or uri[len(PREFIX):] not in files:
            failures.append("manifest URI does not name a bundled release schema or fixture")
    for name, text in files.items():
        value = json.loads(text)
        if name.startswith("schemas/") and value.get("$id") != PREFIX + name:
            failures.append(f"schema identity differs: {name}")
    for cap in doc.get("capabilities", []):
        if cap.get("profile", {}).get("connection", {}).get("executableRef") != "observatory-install:mcp-server":
            failures.append("source manifest must remain a portable installation template")
    return failures


def fetch(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "observatory-schema-check"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except OSError:
        return 0, ""


def cmd_check() -> int:
    failures = local_failures()
    for name, wanted in staged().items():
        status, actual = fetch(PREFIX + name)
        if status != 200 or actual != wanted:
            failures.append(f"published file differs or is unavailable: {name}; HTTP {status}")
    for failure in failures:
        print(failure, file=sys.stderr)
    print(json.dumps({"publication_identical": not failures, "external_host_admission": "unverified"}))
    return 1 if failures else 0


def local_manifest(destination: Path) -> None:
    base = configuration.home().absolute()
    destination = destination.expanduser().absolute()
    configuration.validate_workspace(base, required=True)
    workspace.reject_symlinks(destination)
    if base not in destination.parents:
        raise configuration.ConfigurationError("Local manifest must remain beneath OBSERVATORY_HOME")
    if destination.exists():
        raise configuration.ConfigurationError("Local manifest destination already exists")
    doc = copy.deepcopy(json.loads(MANIFEST.read_text()))
    for cap in doc["capabilities"]:
        cap["profile"]["connection"] = {
            "mode": "stdio", "executableRef": Path(sys.executable).resolve().as_uri(),
            "args": [str(ROOT / "mcp/server.py"), "--stdio"]}
    doc["provider"]["contentHash"] = compute(doc)
    workspace.write_json(destination, doc)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--local-manifest", type=Path)
    group.add_argument("--stage", action="store_true")
    group.add_argument("--publish", action="store_true")
    args = parser.parse_args(argv)
    if args.stage or args.publish:
        parser.error("Schemas ship with the package release; use --local to validate, --check after publication")
    if args.local_manifest:
        try:
            local_manifest(args.local_manifest)
        except (configuration.ConfigurationError, OSError):
            print("Local manifest refused; check initialized private home and unused destination", file=sys.stderr)
            return 2
        print("Private installation manifest written; do not publish it")
        return 0
    if args.check:
        return cmd_check()
    failures = local_failures()
    for failure in failures:
        print(failure, file=sys.stderr)
    print(json.dumps({"bundled_schema_references_valid": not failures, "external_host_admission": "unverified"}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
