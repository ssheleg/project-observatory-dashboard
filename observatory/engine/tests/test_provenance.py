#!/usr/bin/env python3
"""A citation must name the thing that measured, not merely a thing that exists.

                                                                             
                                                                           
                                                                               
                                                 

A source now declares `evidence_for`, and the validator asserts the converse: a
record carrying one of those fields must cite that source. It is a NECESSARY
condition — nothing here can prove a citation true — but it closes the class
where a measured field appears with no witness.
"""
from __future__ import annotations
import json, os, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup, PROJECT_ID as SYNTHETIC_PROJECT
portable_setup()

sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir  # noqa: E402
import paths                                                        # noqa: E402

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def sandbox() -> pathlib.Path:
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-prov-"))
    shutil.copytree(paths.REGISTRY, d / "registry")
    return d / "registry"


def validate(reg: pathlib.Path) -> tuple[int, str]:
    p = subprocess.run([PY, "tools/validate_registry.py"], cwd=ROOT, capture_output=True,
                       text=True, timeout=300,
                       env={**os.environ, "OBSERVATORY_REGISTRY": str(reg)})
    return p.returncode, p.stdout + p.stderr


def test_a_source_declares_what_it_is_evidence_for() -> None:
    sources = json.loads((paths.REGISTRY / "sources.json").read_text(encoding="utf-8"))["sources"]
    by_id = {s["id"]: s for s in sources}
    check("the network probe has a source of its own", "SRC-0010" in by_id)
    check("and it declares the fields only it measures",
          set(by_id.get("SRC-0010", {}).get("evidence_for", [])) ==
          {"local.sync", "local.remote_head", "local.remote_checked_on"},
          str(by_id.get("SRC-0010", {}).get("evidence_for")))
    check("the domain probe has one too", "SRC-0011" in by_id)
    # The INVARIANT, not the next free number. This read `"SRC-0012" not in
    # by_id`, meaning "Bitbucket has no source because it measured nothing
    # here" — an assertion about which id happened to be unused, so it broke the
    # day SRC-0012 was taken by claude-mem, without anything having gone wrong.
    # The same currency-versus-invariant mistake this suite exists to catch.
    empty = [s["id"] for s in sources if "evidence_for" in s and not s["evidence_for"]]
    check("no source declares itself evidence for nothing",
          not empty, f"{empty} — a claim about a measurement that never happened")
    check("and no source exists for a collector that measured nothing here",
          not any("bitbucket" in (s.get("description") or "").lower()
                  and s.get("evidence_for") for s in sources),
          "Bitbucket's API listing is degraded on this machine, so a source "
          "declaring it as evidence would witness nothing")
    check("SRC-0012 is claude-mem's, and it declares the field it measures",
          by_id.get("SRC-0012", {}).get("evidence_for") == ["last_session_on"],
          str(by_id.get("SRC-0012", {}).get("evidence_for")))


def test_every_network_measured_record_now_cites_the_prober() -> None:
    repos = json.loads((paths.REGISTRY / "repositories.json")
                       .read_text(encoding="utf-8"))["repositories"]
    measured = [r for r in repos if any((r.get("local") or {}).get(f)
                                        for f in ("sync", "remote_head", "remote_checked_on"))]
    missing = [r["id"] for r in measured if "SRC-0010" not in r.get("source_refs", [])]
    check(f"all {len(measured)} network-probed repositories cite SRC-0010",
          not missing, str(missing[:3]))
    check("and there are enough of them for that to mean something", len(measured) == 8,
          str(len(measured)))


def test_the_liveness_file_carries_and_resolves_its_provenance() -> None:
    live = json.loads((paths.REGISTRY / "domain-liveness.json").read_text(encoding="utf-8"))
    check("domain-liveness.json cites a source", live.get("source_refs") == ["SRC-0011"],
          str(live.get("source_refs")))


def test_the_validator_CATCHES_a_false_citation() -> None:
    """The planted defect: the rule must fail the state it was written for."""
    reg = sandbox()
    code, out = validate(reg)
    check("the sandbox starts green", code == 0, out[-200:])

    doc = json.loads((reg / "repositories.json").read_text(encoding="utf-8"))
    stripped = 0
    for r in doc["repositories"]:
        if any((r.get("local") or {}).get(f)
               for f in ("sync", "remote_head", "remote_checked_on")):
            r["source_refs"] = [x for x in r["source_refs"] if x != "SRC-0010"]
            stripped += 1
            if stripped == 2:
                break
    (reg / "repositories.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                                           encoding="utf-8")
    code, out = validate(reg)
    check("removing the true citation fails validation", code != 0, out[-200:])
    check("and the message says which field has no witness",
          "which only SRC-0010 measures" in out, out[-300:])


def test_the_validator_CATCHES_liveness_without_provenance() -> None:
    reg = sandbox()
    live = json.loads((reg / "domain-liveness.json").read_text(encoding="utf-8"))
    live.pop("source_refs", None)
    (reg / "domain-liveness.json").write_text(json.dumps(live, indent=1, ensure_ascii=False),
                                              encoding="utf-8")
    code, out = validate(reg)
    check("a liveness file with no source_refs fails", code != 0, out[-200:])
    check("and it is named", "domain-liveness.json carries no source_refs" in out, out[-200:])


def test_a_curated_override_adds_a_witness_rather_than_replacing_them() -> None:
    """Found by the rule above the first time it ran, on this repository's own data."""
    src = (ROOT / "collectors/emit_registry.py").read_text(encoding="utf-8")
    check("source_refs from an override are unioned, not assigned",
          'ck=="source_refs" else cv' in src and 'k=="source_refs" else v' in src,
          "replacing them wiped the measured provenance off the curated records")
    repos = {r["name_with_owner"]: r for r in json.loads(
        (paths.REGISTRY / "repositories.json").read_text(encoding="utf-8"))["repositories"]}
    curated = json.loads((__import__("paths").config_file("repo_overrides.json"))
                         .read_text(encoding="utf-8"))["repositories"]
    for name in curated:
        refs = set(repos[name]["source_refs"])
        check(f"{name} keeps both its curated and its measured witnesses",
              {"SRC-0005", "SRC-0010"} <= refs, str(sorted(refs)))


if __name__ == "__main__":
    print("provenance — a citation that names the measurer\n")
    for fn in (test_a_source_declares_what_it_is_evidence_for,
               test_every_network_measured_record_now_cites_the_prober,
               test_the_liveness_file_carries_and_resolves_its_provenance,
               test_the_validator_CATCHES_a_false_citation,
               test_the_validator_CATCHES_liveness_without_provenance,
               test_a_curated_override_adds_a_witness_rather_than_replacing_them):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mevery measured field names the thing that measured it\033[0m")
