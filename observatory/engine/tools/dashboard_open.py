#!/usr/bin/env python3
"""Open the private dashboard: build it if needed, then show it in a browser.

Without --serve the pages open straight from the workspace as files; they are
self-contained and need no server. With --serve a loopback-only server is
started (or an already running one is reused) and the page opens at
http://127.0.0.1:PORT/ - the live verbs on the keys page need it.
Nothing is sent anywhere; the server binds 127.0.0.1 only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configuration  # noqa: E402

DEFAULT_PORT = int(os.environ.get("OBSERVATORY_SERVER_PORT", "47311"))


def _paths():
    import paths
    return paths


def build(py: str = sys.executable) -> int:
    """Run the dashboard step; returns its exit code."""
    return subprocess.run([py, str(ROOT / "observatory.py"), "dashboard"], cwd=ROOT,
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode


def healthy(port: int, timeout: float = 1.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")) if r.status == 200 else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def start_server(port: int, wait: float = 20.0) -> dict:
    """Start tools/serverd.py detached on loopback and wait for /health."""
    paths = _paths()
    logs = paths.STATE / "logs"
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(logs / "serverd.out", "ab") as out:
        subprocess.Popen([sys.executable, str(ROOT / "tools/serverd.py"), "--run", "--port", str(port)],
                         cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         start_new_session=True)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        beat = healthy(port)
        if beat:
            return beat
        time.sleep(0.3)
    raise configuration.ConfigurationError(
        f"The dashboard server did not answer on 127.0.0.1:{port} within {wait:.0f}s; "
        f"see {logs / 'serverd.out'} or open the files without --serve")


def open_dashboard(*, serve: bool, port: int, rebuild: bool, browser: bool) -> dict:
    configuration.validate_workspace(required=True)
    paths = _paths()
    index = paths.DASHBOARD_DIR / "index.html"
    built = False
    if rebuild or not index.is_file():
        code = build()
        if code != 0 or not index.is_file():
            raise configuration.ConfigurationError(
                "The dashboard could not be built; run `project-observatory full local` first")
        built = True
    result = {"built": built, "path": str(index), "served": False}
    if serve:
        beat = healthy(port)
        result["server"] = "reused" if beat else "started"
        if not beat:
            start_server(port)
        result.update(served=True, url=f"http://127.0.0.1:{port}/dashboard/index.html")
    else:
        result["url"] = index.resolve().as_uri()
    result["opened"] = bool(browser) and webbrowser.open(result["url"])
    if not result["opened"]:
        result["next"] = "Open the url above in a browser."
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="project-observatory full open", description=__doc__.splitlines()[0])
    ap.add_argument("--serve", action="store_true", help="serve on 127.0.0.1 instead of opening files")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--rebuild", action="store_true", help="rebuild the pages before opening")
    ap.add_argument("--no-browser", action="store_true", help="print the address only")
    a = ap.parse_args(argv)
    if not 0 < a.port < 65536:
        print("Observatory: port must be between 1 and 65535", file=sys.stderr)
        return 2
    try:
        result = open_dashboard(serve=a.serve, port=a.port, rebuild=a.rebuild,
                                browser=not a.no_browser)
    except configuration.ConfigurationError as exc:
        print(f"Observatory: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
