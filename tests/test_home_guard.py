"""Private state never lives inside the installed code or its source checkout."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "observatory"


def run(*args, home):
    env = {**os.environ, "OBSERVATORY_HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("OBSERVATORY_FULL_HOME", None)
    return subprocess.run([sys.executable, "-m", "observatory", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


class HomeGuardTest(unittest.TestCase):
    def assert_refused(self, home, *args):
        p = run(*args, home=home)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("outside the installed code", p.stdout + p.stderr)
        self.assertNotIn("Traceback", p.stdout + p.stderr)
        self.assertFalse(home.exists(), "a refused home must not be created")

    def test_portable_refuses_home_inside_package_and_checkout(self):
        for home in (PACKAGE / "state-here", PACKAGE / "engine" / "state-here", ROOT / "state-here"):
            with self.subTest(home=home):
                self.assert_refused(home, "init")

    def test_full_launcher_refuses_home_inside_package(self):
        self.assert_refused(PACKAGE / "engine" / "state-here", "full", "init")

    def test_symlink_into_the_package_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "link"
            link.symlink_to(PACKAGE)
            p = run("init", home=link / "state-here")
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertFalse((PACKAGE / "state-here").exists())

    def test_home_outside_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = run("init", home=Path(tmp).resolve() / "home")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertTrue(json.loads(p.stdout)["initialized"])


if __name__ == "__main__":
    unittest.main()
