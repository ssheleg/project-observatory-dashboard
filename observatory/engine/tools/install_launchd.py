#!/usr/bin/env python3
""                                                                       

                                                                           
                                                                               
                                                                       
                                                                             
   
from __future__ import annotations
import argparse, plistlib, subprocess, sys, os, pathlib, hashlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paths
import configuration


def instance_label(kind: str) -> str:
    digest = hashlib.sha256(str(paths.HOME.resolve()).encode()).hexdigest()[:16]
    return f"org.project-observatory.{digest}.{kind}"


LABEL = instance_label("tick")
PLIST = pathlib.Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = paths.STATE / "logs"


def scheduler_allowed() -> bool:
    return configuration.enabled("scheduler", "features")


def environment() -> dict[str, str]:
                                                                         
    return {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(pathlib.Path.home()), "OBSERVATORY_HOME": str(paths.HOME)}


def prepare_logs(names: tuple[str, ...], directory: pathlib.Path = LOG_DIR) -> None:
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise configuration.ConfigurationError("Log directory cannot be a symbolic link")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    for name in names:
        fd = os.open(directory / name, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)


def uid() -> int:
    return os.getuid()


def build(interval: int) -> dict:
    if interval < 60:
        raise ValueError("Tick interval must be at least 60 seconds")
    return {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(ROOT / "tools/tick.sh")],
        "StartInterval": interval,
        "RunAtLoad": False,                                                  
        "WorkingDirectory": str(ROOT),
        "StandardOutPath": str(LOG_DIR / "tick.log"),
        "StandardErrorPath": str(LOG_DIR / "tick.err"),
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 5,
                                                                             
                                                                                 
                                                                               
                                                                         
                                                                               
        "EnvironmentVariables": environment(),
        "Umask": 0o077,
    }


def run(*args: str) -> tuple[int, str]:
    p = subprocess.run(args, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["install", "uninstall", "status", "run-now"])
    ap.add_argument("--interval", type=int, default=1800)
    args = ap.parse_args()
    target = f"gui/{uid()}/{LABEL}"
    if args.action in {"install", "run-now"} and not scheduler_allowed():
        print("Scheduler disabled: enable features.scheduler in the workspace settings first", file=sys.stderr)
        return 1
    if sys.platform != "darwin":
        print("launchd is supported on macOS only", file=sys.stderr)
        return 1

    if args.action == "status":
        code, out = run("launchctl", "print", target)
        if code != 0:
            print(f"not loaded ({LABEL})")
            print(f"plist on disk: {PLIST.exists()}")
            return 0
        for line in out.splitlines():
            if any(k in line for k in ("state =", "runs =", "last exit", "path =")):
                print(" ", line.strip())
        log = LOG_DIR / "tick.log"
        if log.exists():
            print(f"\nlast lines of {log}:")
            print("\n".join(log.read_text(errors="replace").splitlines()[-12:]))
        return 0

    if args.action == "run-now":
        code, out = run("launchctl", "kickstart", target)
        print(out or f"kickstarted {LABEL} (exit {code})")
        return 0

    if args.action == "uninstall":
        run("launchctl", "bootout", target)
        PLIST.unlink(missing_ok=True)
        print(f"removed {LABEL} and its plist")
        return 0

    payload = plistlib.dumps(build(args.interval))
    prepare_logs(("tick.log", "tick.err"))
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    if PLIST.is_symlink():
        raise configuration.ConfigurationError("LaunchAgent plist cannot be a symbolic link")
    fd = os.open(PLIST, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
    run("launchctl", "bootout", target)                                        
    code, out = run("launchctl", "bootstrap", f"gui/{uid()}", str(PLIST))
    if code != 0:
        print(f"bootstrap failed: {out}", file=sys.stderr)
        return 1
    print(f"installed {LABEL}, every {args.interval}s")
    print(f"  plist  {PLIST}")
    print(f"  log    {LOG_DIR / 'tick.log'}")
    print("  RunAtLoad is false on purpose: a login is not a reason to burn a scan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
