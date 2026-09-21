#!/usr/bin/env python3
"""Inspect the public tree/entire Git blob history without printing matches.

Optional --private-denylist reads a LOCAL JSON array of private identifiers.
It must never be committed. This scanner prints categories/counts, not values.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_TOP = {".github", "observatory", "tests", "tools", "docs", "site"}
ALLOWED_ROOT = {".gitignore", "LICENSE", "README.md", "SECURITY.md", "CONTRIBUTING.md", "pyproject.toml", "AGENTS.md"}
SKIP = {".git", ".venv", "__pycache__", "node_modules", "build", "dist"}
EXTENSIONS = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".html", ".css", ".js", ".svg", ".txt", ".xml"}
# Compose token-shape patterns so the detector's own source is not a fixture hit.
PATTERNS = {
    "provider-token-shape": re.compile(r"\b(?:" + "gh[pousr]_" + r"[A-Za-z0-9]{30,}|" + "github_pat_" + r"[A-Za-z0-9_]{40,}|" + "sk-" + r"(?:proj-|or-v1-|ant-api03-)?[A-Za-z0-9_-]{30,}|" + "AKIA" + r"[A-Z0-9]{16}|" + "AIza" + r"[A-Za-z0-9_-]{30,})"),
    "private-key-block": re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "personal-machine-path": re.compile(r"/(?:" + "Users" + r"|home)/[A-Za-z0-9_.-]+/"),
    "credential-url": re.compile(r"https?://[^\s/@:]+:[^\s/@]+@"),
}


def scan_text(text: str, deny: list[str]) -> dict[str, int]:
    hits = {kind: len(rx.findall(text)) for kind, rx in PATTERNS.items()}
    hits["private-identifier"] = sum(len(re.findall(r"(?<![A-Za-z0-9_.-])" + re.escape(value) + r"(?:\.git)?(?![A-Za-z0-9_.-])", text)) for value in deny if value)
    return {kind: n for kind, n in hits.items() if n}


def allowed_path(rel: Path) -> bool:
    if any(x in SKIP or x.endswith(".egg-info") for x in rel.parts):
        return False
    allowed = (len(rel.parts) == 1 and str(rel) in ALLOWED_ROOT) or (len(rel.parts) > 1 and rel.parts[0] in ALLOWED_TOP)
    return bool(allowed and not any(x.startswith(".env") or x in {"registry", "secrets", "store"} for x in rel.parts)
                and (rel.suffix in EXTENSIONS or str(rel) in ALLOWED_ROOT or rel.name in {"_headers", "_redirects", "robots.txt"}))


def audit(root: Path, deny: list[str], history: bool) -> dict:
    findings = []
    files = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(x in SKIP or x.endswith(".egg-info") for x in rel.parts):
            continue
        if p.is_symlink():
            findings.append({"file_index": len(files), "kind": "symlink", "count": 1})
            continue
        if not p.is_file():
            continue
        index = len(files)
        files.append(str(rel))
        if not allowed_path(rel):
            findings.append({"file_index": index, "kind": "outside-public-allowlist", "count": 1})
        if p.stat().st_size > 2 * 1024 * 1024:
            findings.append({"file_index": index, "kind": "oversized-public-file", "count": 1})
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            findings.append({"file_index": index, "kind": "unreadable-or-binary", "count": 1})
            continue
        for kind, n in scan_text(content, deny).items():
            findings.append({"file_index": index, "kind": kind, "count": n})
    blobs = 0
    if (root / ".git").exists():
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True)
        if tracked.returncode:
            findings.append({"kind": "tracked-inventory-unavailable", "count": 1})
        else:
            for rel in tracked.stdout.split("\0"):
                if rel and not allowed_path(Path(rel)):
                    findings.append({"kind": "tracked-outside-public-allowlist", "count": 1})
    if history:
        paths = subprocess.run(["git", "-C", str(root), "log", "--all", "--name-only", "--format=", "-z"], capture_output=True, text=True)
        if paths.returncode:
            findings.append({"kind": "historical-paths-unavailable", "count": 1})
        else:
            for rel in set(x.strip("\n") for x in paths.stdout.split("\0") if x.strip("\n")):
                if not allowed_path(Path(rel)):
                    findings.append({"kind": "history:forbidden-path", "count": 1})
                for category, n in scan_text(rel, deny).items():
                    findings.append({"kind": "history-path:" + category, "count": n})
        run = subprocess.run(["git", "-C", str(root), "rev-list", "--objects", "--all"], capture_output=True, text=True)
        if run.returncode:
            findings.append({"kind": "git-history-unavailable", "count": 1})
        else:
            seen = set()
            for line in run.stdout.splitlines():
                oid, _, rel = line.partition(" ")
                if oid in seen:
                    continue
                seen.add(oid)
                kind = subprocess.run(["git", "-C", str(root), "cat-file", "-t", oid], capture_output=True, text=True)
                if kind.stdout.strip() != "blob":
                    continue
                if not rel or not allowed_path(Path(rel)):
                    findings.append({"kind": "history:outside-public-allowlist", "count": 1})
                size = subprocess.run(["git", "-C", str(root), "cat-file", "-s", oid], capture_output=True, text=True)
                if size.returncode or int(size.stdout.strip()) > 2 * 1024 * 1024:
                    findings.append({"kind": "history:oversized-or-unreadable", "count": 1})
                    continue
                blob = subprocess.run(["git", "-C", str(root), "cat-file", "blob", oid], capture_output=True)
                if blob.returncode:
                    findings.append({"kind": "history:unreadable-blob", "count": 1})
                    continue
                blobs += 1
                try:
                    text = blob.stdout.decode("utf-8")
                except UnicodeError:
                    findings.append({"kind": "binary-git-blob", "count": 1})
                    continue
                for category, n in scan_text(text, deny).items():
                    findings.append({"kind": "history:" + category, "count": n})
            messages = subprocess.run(["git", "-C", str(root), "log", "--all", "--format=%B"], capture_output=True, text=True)
            if messages.returncode:
                findings.append({"kind": "commit-messages-unavailable", "count": 1})
            for category, n in scan_text(messages.stdout, deny).items():
                findings.append({"kind": "commit-message:" + category, "count": n})
    return {"gate": "public-release-privacy", "passed": not findings, "files_checked": len(files),
            "history_blobs_checked": blobs, "private_denylist_entries": len(deny),
            "findings": findings,
            "limits": "Pattern/identifier checks cannot prove absence of every secret or private fact. Review source, metadata and release scope independently. Match values and paths are never printed."}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--private-denylist", type=Path)
    p.add_argument("--history", action="store_true")
    a = p.parse_args()
    deny = []
    if a.private_denylist:
        try:
            deny = json.loads(a.private_denylist.read_text())
            if not isinstance(deny, list) or any(not isinstance(x, str) for x in deny):
                raise ValueError()
        except (ValueError, OSError):
            print(json.dumps({"passed": False, "error": "Private denylist must be a readable local JSON string array."}))
            return 2
    report = audit(a.root, deny, a.history)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
