#!/usr/bin/env python3
""                                                                                

                                                                       
                                                                             
                                                                              
                                                                            
                                                
                                                                             
                                                                                
                                                                               
                                                                                

                                                                            
                                                                            
                                                                              
                                                                              
                                                    

                                                                             
                                                                         
                                                                               
                                                                
                                                                               
                                                    

                                                                         
                                                                            

                                                                
   
from __future__ import annotations
import concurrent.futures as cf
import json, os, pathlib, subprocess, sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths              
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import local_scan              

WORKERS = 8
NET_TIMEOUT = 25
ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",                                               
    "GIT_ASKPASS": "/usr/bin/true",
    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=10 "
                       "-o StrictHostKeyChecking=accept-new",
}


def git(args: list[str], cwd: pathlib.Path | None = None, timeout: int = 10):
    try:
        r = subprocess.run(["git", *args], cwd=cwd, env=ENV, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"


                                                                        
                                                                                   
                                                                              
                                                                                
                                                                           
                                                                               
                                             
STATES = frozenset({
    "current", "ahead", "behind", "behind-or-diverged", "diverged",
    "local-only-branch", "stale", "unpushed-and-remote-moved",
    "unreachable", "unknown",
})


def tracking_state(path: pathlib.Path, local_sha: str, branch: str) -> str | None:
    ""                                                                        

                                                                                 
                                                                           
                                                                           
                                                                           

                                                                              
                                                                               
                                                     

                                                                                
                                                                                
                                                                      
       
    if not branch or branch == "HEAD":
        return None
    ref = f"refs/remotes/origin/{branch}"
    if git(["rev-parse", "--verify", "--quiet", ref], cwd=path)[0] != 0:
        return None
    if git(["merge-base", "--is-ancestor", local_sha, ref], cwd=path)[0] == 0:
        return "stale"
    return "unpushed-and-remote-moved"


def sync_state(path: pathlib.Path, local_sha: str, remote_sha: str,
               branch: str = "") -> str:
    ""                                                
    if not remote_sha:
        return "local-only-branch"
    if local_sha == remote_sha:
        return "current"
    if git(["cat-file", "-e", remote_sha + "^{commit}"], cwd=path)[0] != 0:
        # The remote commit is not in this clone, and getting it would mean
        # writing to the operator's repository. But the half that MATTERS here —
        # is there work on this disk and nowhere else — is answerable from the
        # tracking ref without either. Ask that; refuse only what is left.
        return tracking_state(path, local_sha, branch) or "behind-or-diverged"
    if git(["merge-base", "--is-ancestor", remote_sha, local_sha], cwd=path)[0] == 0:
        return "ahead"
    if git(["merge-base", "--is-ancestor", local_sha, remote_sha], cwd=path)[0] == 0:
        return "behind"
    return "diverged"



#: The states where work exists on this disk and possibly nowhere else. Only
#: these are counted: `behind` and `current` have nothing at stake, and asking
#: git about them would be a walk for an answer nobody reads.
AT_RISK_STATES = ("ahead", "unpushed-and-remote-moved", "local-only-branch",
                  "diverged")


def at_stake(path, state: str, local_sha: str, remote_sha: str,
             branch: str = "") -> dict:
    ""                                                            

                                                                          
                                                                                
                                                                        
                           

                        

                                                   
                                                         
                                                                               
                                                                               

                                                                                
                                                                                   
                                                                               
                                                                                
                               
       
    if state not in AT_RISK_STATES:
        return {}
    if state == "local-only-branch":
        args = ["rev-list", "--count", "HEAD", "--not", "--remotes"]
        log = ["log", "-1", "--format=%cs", "HEAD"]
    elif state == "unpushed-and-remote-moved":
        ref = f"refs/remotes/origin/{branch}" if branch else "refs/remotes/origin/HEAD"
        args = ["rev-list", "--count", f"{ref}..HEAD"]
        log = ["log", "-1", "--format=%cs", f"{ref}..HEAD"]
    else:
        if not remote_sha:
            return {}
        args = ["rev-list", "--count", f"{remote_sha}..HEAD"]
        log = ["log", "-1", "--format=%cs", f"{remote_sha}..HEAD"]
    code, out, _ = git(args, cwd=path)
    if code != 0 or not out.strip().isdigit():
        return {}
    n = int(out.strip())
    if n <= 0:
                                                                               
                                                                               
                                                                               
                                                                                 
                                                                                
                     
        return {"nothing_exclusive": True}
    got: dict = {"unpushed": n}
    code, when, _ = git(log, cwd=path)
    if code == 0 and len(when.strip()) == 10:
        got["newest_on"] = when.strip()
    return got


def probe(rec: dict) -> tuple[str, dict]:
    folder, path = rec["folder"], pathlib.Path(rec["path"])
    url, branch = rec.get("remote", ""), rec.get("branch", "")
    out: dict = {"remote": url, "checked_at": datetime.now(timezone.utc)
                 .strftime("%Y-%m-%dT%H:%M:%SZ")}
    if not url:
        out.update(reachable=False, reason="no origin remote")
        return folder, out

    refs = ["HEAD"] + ([f"refs/heads/{branch}"] if branch and branch != "HEAD" else [])
    code, stdout, stderr = git(["ls-remote", "--symref", url, *refs], timeout=NET_TIMEOUT)
    if code != 0:
        # A permission failure and a deleted repository are different facts and
        # the operator needs to tell them apart; git says which, so pass it on.
        out.update(reachable=False, reason=(stderr.splitlines() or ["unknown"])[-1][:200])
        return folder, out

    default_branch, remote_head, branch_sha = "", "", ""
    for line in stdout.splitlines():
        if line.startswith("ref: ") and line.endswith("HEAD"):
            default_branch = line.split()[1].removeprefix("refs/heads/")
        elif "\t" in line:
            sha, ref = line.split("\t", 1)
            if ref == "HEAD":
                remote_head = sha
            elif ref == f"refs/heads/{branch}":
                branch_sha = sha

    local_sha = git(["rev-parse", "HEAD"], cwd=path)[1]
    state = sync_state(path, local_sha, branch_sha, branch) if local_sha else "unknown"
    out.update(reachable=True, default_branch=default_branch, remote_head=remote_head,
               branch=branch, branch_remote_sha=branch_sha, sync=state)
                                                                             
                                                                              
                                                                
    out.update(at_stake(path, state, local_sha, branch_sha, branch))
    return folder, out


def main(argv: list[str]) -> int:
    import configuration
    if not configuration.enabled("git_remotes"):
        print("SKIP remote Git probes: integration git_remotes is disabled")
        return 0
    if len(argv) < 2:
        sys.exit(__doc__)
    dest = pathlib.Path(argv[1])
    only = set(argv[argv.index("--only") + 1:]) if "--only" in argv else None

    # `paths.SCRATCH`: see scan_bitbucket for the class this belongs to.
    src = paths.SCRATCH / "local.json"
    if not src.is_file():
        sys.exit(f"scan_remotes: no {src} — run scan_filesystem.py first")
    rows = [r for r in local_scan.folders(src)
            if r.get("is_git") and (only is None or r["folder"] in only)]
    if not rows:
        print("scan_remotes: no git checkout to probe")

    result: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for folder, info in pool.map(probe, rows):
            result[folder] = info

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repositories": result,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    tally: dict[str, int] = {}
    for info in result.values():
        key = info.get("sync") if info.get("reachable") else "unreachable"
        tally[key or "unknown"] = tally.get(key or "unknown", 0) + 1
    print(f"probed {len(result)} remote(s) -> {dest}")
    for k in sorted(tally, key=lambda k: -tally[k]):
        print(f"  {k:20s} {tally[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
