"""`full agent` and `full open`: plugin install with auto-update, and opening the dashboard.

A fake `claude` records its arguments and mimics the plugin state files, so the
real Claude Code configuration of whoever runs the tests is never touched.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = "ssheleg/project-observatory-dashboard"

FAKE_CLAUDE = textwrap.dedent('''\
    #!{py}
    import json, os, sys
    from pathlib import Path
    home = Path(os.environ["CLAUDE_CONFIG_DIR"]); plugins = home / "plugins"; plugins.mkdir(parents=True, exist_ok=True)
    with open(home / "calls.log", "a") as log: log.write(" ".join(sys.argv[1:]) + "\\n")
    known_f, inst_f = plugins / "known_marketplaces.json", plugins / "installed_plugins.json"
    known = json.loads(known_f.read_text()) if known_f.exists() else {{}}
    inst = json.loads(inst_f.read_text()) if inst_f.exists() else {{"plugins": {{}}}}
    a = sys.argv[1:]
    if a[:3] == ["plugin", "marketplace", "add"]:
        known["observatory-log"] = {{"source": {{"source": "github", "repo": a[3]}}}}
    elif a[:3] == ["plugin", "marketplace", "remove"]:
        if a[3] not in known: sys.exit(1)
        known.pop(a[3]); inst["plugins"].pop("observatory-log@observatory-log", None)
    elif a[:3] == ["plugin", "marketplace", "update"]:
        pass
    elif a[:2] == ["plugin", "install"]:
        if a[2] in inst["plugins"]: print("already installed", file=sys.stderr); sys.exit(1)
        inst["plugins"][a[2]] = [{{"version": os.environ.get("FAKE_VERSION", "0.11.0")}}]
    elif a[:2] == ["plugin", "update"]:
        inst["plugins"][a[2]] = [{{"version": os.environ.get("FAKE_VERSION", "0.11.0")}}]
    elif a[:2] == ["plugin", "uninstall"]:
        if a[2] not in inst["plugins"]: sys.exit(1)
        inst["plugins"].pop(a[2])
    known_f.write_text(json.dumps(known)); inst_f.write_text(json.dumps(inst))
''')


def clean_env(**extra) -> dict:
    """Parent environment minus every OBSERVATORY_* override, plus the given keys."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OBSERVATORY_", "CLAUDE_"))}
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


def free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    return port


class AgentPluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.claude_home = base / "claude"
        self.claude_home.mkdir()
        fake = base / "bin" / "claude"
        fake.parent.mkdir()
        fake.write_text(FAKE_CLAUDE.format(py=sys.executable))
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.home = base / "workspace"
        self.env = clean_env(CLAUDE_CONFIG_DIR=str(self.claude_home), CLAUDE_BIN=str(fake),
                             OBSERVATORY_HOME=str(self.home))
        self.run_cli("init")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, code=0):
        p = subprocess.run([sys.executable, str(ROOT / "observatory.py"), *args], cwd=ROOT, env=self.env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return json.loads(p.stdout) if p.stdout.strip().startswith("{") else p

    def settings(self) -> dict:
        return json.loads((self.claude_home / "settings.json").read_text())

    def known(self) -> dict:
        return json.loads((self.claude_home / "plugins/known_marketplaces.json").read_text())

    def test_install_turns_auto_update_on_and_points_hooks_at_this_workspace(self):
        (self.claude_home / "settings.json").write_text(json.dumps({"theme": "dark", "env": {"KEEP": "1"}}))
        out = self.run_cli("agent", "install")
        self.assertTrue(out["auto_update"])
        s = self.settings()
        self.assertEqual(s["theme"], "dark", "unrelated settings are preserved")
        self.assertEqual(s["env"]["KEEP"], "1")
        self.assertEqual(s["extraKnownMarketplaces"]["observatory-log"],
                         {"source": {"source": "github", "repo": REPO}, "autoUpdate": True})
        self.assertTrue(s["enabledPlugins"]["observatory-log@observatory-log"])
        self.assertEqual(s["env"]["OBSERVATORY_HOME"], str(self.home))
        self.assertEqual(Path(s["env"]["OBSERVATORY_ROOT"]), ROOT)
        self.assertTrue(self.known()["observatory-log"]["autoUpdate"])
        self.assertTrue((self.claude_home / "settings.json.bak-observatory").is_file(), "backed up first")
        status = self.run_cli("agent", "status")
        self.assertTrue(status["ok"], status["problems"])
        self.assertTrue(status["auto_update"])

    def test_opt_out_keeps_auto_update_off_and_status_says_so(self):
        out = self.run_cli("agent", "install", "--no-auto-update")
        self.assertFalse(out["auto_update"])
        self.assertFalse(self.settings()["extraKnownMarketplaces"]["observatory-log"]["autoUpdate"])
        self.assertFalse(self.known()["observatory-log"]["autoUpdate"])
        status = self.run_cli("agent", "status", code=1)
        self.assertIn("auto-update is off", " ".join(status["problems"]))

    def test_a_directory_marketplace_is_replaced_by_the_github_one(self):
        plugins = self.claude_home / "plugins"; plugins.mkdir()
        (plugins / "known_marketplaces.json").write_text(json.dumps(
            {"observatory-log": {"source": {"source": "directory", "path": "/somewhere/skill"}}}))
        (plugins / "installed_plugins.json").write_text(json.dumps(
            {"plugins": {"observatory-log@observatory-log": [{"version": "0.8.0"}]}}))
        before = self.run_cli("agent", "status", code=1)
        self.assertIn("not GitHub", " ".join(before["problems"]))
        self.assertIn("installed 0.8.0", " ".join(before["problems"]))
        out = self.run_cli("agent", "install")
        self.assertIn("replaced marketplace source directory", out["steps"])
        self.assertEqual(self.known()["observatory-log"]["source"], {"source": "github", "repo": REPO})
        calls = (self.claude_home / "calls.log").read_text().splitlines()
        self.assertEqual(calls[:3], ["plugin marketplace remove observatory-log",
                                     f"plugin marketplace add {REPO}",
                                     "plugin install observatory-log@observatory-log"])

    def test_reinstall_updates_instead_of_failing(self):
        self.run_cli("agent", "install")
        out = self.run_cli("agent", "install")
        self.assertIn("plugin updated", out["steps"])
        self.assertIn("marketplace updated", out["steps"])

    def test_uninstall_removes_only_what_install_added(self):
        (self.claude_home / "settings.json").write_text(json.dumps({"env": {"KEEP": "1"}}))
        self.run_cli("agent", "install")
        self.run_cli("agent", "uninstall")
        s = self.settings()
        self.assertNotIn("observatory-log", s.get("extraKnownMarketplaces", {}))
        self.assertNotIn("observatory-log@observatory-log", s.get("enabledPlugins", {}))
        self.assertEqual(s["env"], {"KEEP": "1"})
        self.assertTrue(self.home.is_dir(), "the workspace is never touched")

    def test_missing_claude_and_invalid_settings_are_refused_without_writes(self):
        (self.claude_home / "settings.json").write_text("{broken")
        p = self.run_cli("agent", "install", code=2)
        self.assertIn("not valid JSON", p.stderr)
        self.assertEqual((self.claude_home / "settings.json").read_text(), "{broken")
        self.env["CLAUDE_BIN"] = ""
        self.env["PATH"] = "/nonexistent"
        p = self.run_cli("agent", "install", code=2)
        self.assertIn("not on PATH", p.stderr)


class OpenDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve() / "workspace"
        self.env = clean_env(OBSERVATORY_HOME=str(self.home))
        self.procs = []

    def tearDown(self):
        subprocess.run(["pkill", "-f", f"serverd.py --run --port {getattr(self, 'port', 0)}"],
                       capture_output=True)
        self.tmp.cleanup()

    def run_cli(self, *args, code=0):
        p = subprocess.run([sys.executable, str(ROOT / "observatory.py"), *args], cwd=ROOT, env=self.env,
                           capture_output=True, text=True, timeout=180)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return p

    def test_open_refuses_without_a_workspace(self):
        p = self.run_cli("open", "--no-browser", code=2)
        self.assertIn("Observatory:", p.stderr)

    def test_open_builds_missing_pages_and_prints_a_file_url(self):
        self.run_cli("init")
        out = json.loads(self.run_cli("open", "--no-browser").stdout)
        self.assertTrue(out["built"])
        self.assertTrue(Path(out["path"]).is_file())
        self.assertTrue(out["url"].startswith("file://") and out["url"].endswith("/dashboard/index.html"))
        self.assertFalse(out["opened"])
        again = json.loads(self.run_cli("open", "--no-browser").stdout)
        self.assertFalse(again["built"], "existing pages are reused unless --rebuild")

    def test_serve_starts_a_loopback_server_then_reuses_it(self):
        import urllib.request
        self.run_cli("init")
        self.port = free_port()
        out = json.loads(self.run_cli("open", "--serve", "--no-browser", "--port", str(self.port)).stdout)
        self.assertEqual(out["server"], "started")
        self.assertEqual(out["url"], f"http://127.0.0.1:{self.port}/dashboard/index.html")
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/dashboard/app.css", timeout=5) as r:
            self.assertEqual(r.status, 200)
        again = json.loads(self.run_cli("open", "--serve", "--no-browser", "--port", str(self.port)).stdout)
        self.assertEqual(again["server"], "reused")
        other = Path(self.tmp.name).resolve() / "other"
        env = dict(self.env, OBSERVATORY_HOME=str(other))
        subprocess.run([sys.executable, str(ROOT / "observatory.py"), "init"], cwd=ROOT, env=env,
                       capture_output=True, timeout=120, check=True)
        p = subprocess.run([sys.executable, str(ROOT / "observatory.py"), "open", "--serve", "--no-browser",
                            "--port", str(self.port)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("already serves another workspace", p.stderr)


if __name__ == "__main__":
    unittest.main()
