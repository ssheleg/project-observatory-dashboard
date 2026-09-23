"""Every place that states the application version states the same one."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def found(path: str, pattern: str) -> str:
    match = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"), re.M)
    assert match, f"no version in {path}"
    return match.group(1)


class VersionConsistency(unittest.TestCase):
    def test_one_version_everywhere(self):
        versions = {
            "pyproject.toml": found("pyproject.toml", r'^version = "([\d.]+)"'),
            "observatory/__init__.py": found("observatory/__init__.py", r'^__version__ = "([\d.]+)"'),
            "engine configuration": found("observatory/engine/configuration.py", r'^VERSION = "([\d.]+)"'),
            "docs/COMPATIBILITY.md": found("docs/COMPATIBILITY.md", r"application release is \*\*([\d.]+)\*\*"),
            "engine COMPATIBILITY": found("observatory/engine/docs/COMPATIBILITY.md", r"application release is \*\*([\d.]+)\*\*"),
        }
        self.assertEqual(len(set(versions.values())), 1, versions)

    def test_changelog_names_the_current_version(self):
        version = found("pyproject.toml", r'^version = "([\d.]+)"')
        self.assertRegex((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), rf"(?m)^## {re.escape(version)} ")


if __name__ == "__main__":
    unittest.main()
