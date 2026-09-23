#!/usr/bin/env python3
"""List every repository the authenticated GitHub account can read.

Uses the `gh` CLI so the token stays in the keyring rather than in this process.
Owners are discovered from `user/orgs` plus the authenticated login; nothing is
hardcoded, because an org added tomorrow must appear without editing this file.

Writes one JSON file per owner into the output directory, and reports the owners
it could NOT read rather than dropping them silently.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import listing_guard  # noqa: E402

FIELDS =("name,nameWithOwner,description,homepageUrl,url,visibility,isArchived,"
          "isFork,primaryLanguage,pushedAt,createdAt,repositoryTopics,diskUsage,"
          "defaultBranchRef")


def gh(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def owners() -> list[str]:
    code, out, err = gh(["api", "user", "--jq", ".login"])
    if code != 0:
        raise SystemExit(f"gh is not authenticated: {err.strip()}")
    found = [out.strip()]
    code, out, _ = gh(["api", "user/orgs", "--jq", ".[].login"])
    if code == 0:
        found += [line for line in out.splitlines() if line.strip()]
    return list(dict.fromkeys(found))


def main() -> int:
    import configuration
    if not configuration.enabled("github"):
        print("github: not configured (integration disabled)")
        return 0
                                                                              
                                                                                  
                                                                                 
                                                                                   
                                                                     
                                                                                
                                                                     
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else paths.SCRATCH / "gh"
    out_dir.mkdir(parents=True, exist_ok=True)
    degraded, total, kept = [], 0, 0
    for owner in owners():
        code, out, err = gh(["repo", "list", owner, "--limit", "500", "--json", FIELDS])
        if code != 0:
            degraded.append({"source": f"github:{owner}", "reason": err.strip()[:200]})
            print(f"{owner:<20} DEGRADED {err.strip()[:60]}", file=sys.stderr)
            continue
        repos = json.loads(out)
        # An empty listing that SUCCEEDED is not a measurement — the rule and its
        # sentence live in `listing_guard`, which Bitbucket applies too.
        prev = out_dir / f"{owner}.json"
        had = 0
        if prev.is_file():
            try:
                had = len(json.loads(prev.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                had = 0
        reason = listing_guard.empty_would_lose(
            f"github:{owner}", had, len(repos),
            f"Delete {prev.name} by hand if the owner really is empty.")
        if reason:
            degraded.append({"source": f"github:{owner}", "reason": reason})
            print(f"{owner:<20} REFUSED empty listing (kept {had})", file=sys.stderr)
            kept += had
            continue
        prev.write_text(json.dumps(repos, indent=1, ensure_ascii=False),
                        encoding="utf-8")
        total += len(repos)
        print(f"{owner:<20} {len(repos):>4} repositories")
    (out_dir / "_degraded.json").write_text(json.dumps(degraded, indent=1), encoding="utf-8")
    # Two numbers, because one would be a claim about the estate made out of what
    # this run happened to write. `kept` is what an earlier run measured and this
    # one declined to destroy; folding it into `total` would hide the refusal
    # behind a plausible number.
    print(f"total {total} repositories written; {kept} kept from a refused empty "
          f"listing; degraded sources: {len(degraded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
