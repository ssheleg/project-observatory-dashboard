"""tools/demo_estate.py builds the dashboard over a fictional estate without
reading the invoking user's workspace: its OBSERVATORY_HOME is its own."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DemoEstate(unittest.TestCase):
    def test_demo_uses_its_own_home_and_renders_both_languages(self):
        base = Path(tempfile.mkdtemp(prefix="observatory-demo-")).resolve()
        self.addCleanup(shutil.rmtree, base, True)
        # A "real" workspace the demo must not read: a Russian locale it would pick up.
        real = base / "real-home"
        (real / "config").mkdir(parents=True)
        (real / "config/settings.json").write_text(
            '{"schema_version": 1, "sources": {}, "integrations": {}, "features": {}, '
            '"interface": {"locale": "ru"}}')
        env = {**os.environ, "OBSERVATORY_HOME": str(real)}
        env.pop("OBSERVATORY_LOCALE", None)
        for locale in ("en", "ru"):
            out = base / f"demo-{locale}"
            done = subprocess.run([sys.executable, str(ROOT / "tools/demo_estate.py"), str(out), "--locale", locale],
                                  env=env, capture_output=True, text=True, timeout=300)
            self.assertEqual(done.returncode, 0, done.stderr[-600:])
            page = (out / "pages/index.html").read_text(encoding="utf-8")
            self.assertIn(f'<html lang="{locale}"', page)
            projects = (out / "pages/projects.html").read_text(encoding="utf-8")
            self.assertIn("Atlas Billing", projects)
            self.assertIn("northwind-labs", projects)
            self.assertNotIn(str(real), page, "the demo read the invoking user's workspace")
            self.assertIn(str(out / "home"), page)
        refused = subprocess.run([sys.executable, str(ROOT / "tools/demo_estate.py"), str(base / "demo-en")],
                                 env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(refused.returncode, 2, "a non-empty output directory is refused")


if __name__ == "__main__":
    unittest.main()
