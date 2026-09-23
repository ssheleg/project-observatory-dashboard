"""PB-123: the deployed commit comes from the release description, never from a branch."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "collectors"))


class DeployedCommit(unittest.TestCase):
    def test_only_a_stated_commit_is_taken(self):
        import scan_heroku as sh
        self.assertEqual(sh.deployed_commit("Deploy 1a2b3c4d"), "1a2b3c4d")
        self.assertEqual(sh.deployed_commit("Deploy " + "a" * 40), "a" * 40)
        for desc in ("Deploy main", "Deploy feature-cafe123", "Deploy cafe123 to main",
                     "Rollback to v41", "Promote from staging", "Set FOO config vars", "", None):
            self.assertIsNone(sh.deployed_commit(desc), desc)

    def test_the_registry_names_its_source_and_never_falls_back_to_the_branch(self):
        import heroku_registry as hr
        hr.load_verified = lambda: {}
        base = {"team": None, "github": "example-org/app", "branch": "main", "auto_deploy": True}
        scan = {"apps": [
            {**base, "name": "stated", "last_deploy": {"version": 7, "at": "2026-09-01T00:00:00Z",
                                                       "desc": "Deploy 1a2b3c4d", "commit": "1a2b3c4d"}},
            {**base, "name": "unstated", "last_deploy": {"version": 8, "at": "2026-09-02T00:00:00Z",
                                                         "desc": "Rollback to v7", "commit": None}},
        ]}
        apps = {a["name"]: a for a in hr.records(scan, [], [], [])[0]}
        self.assertEqual(apps["stated"]["deployed_commit"],
                         {"sha": "1a2b3c4d", "release": 7, "source": "heroku-release-description"})
        self.assertIsNone(apps["unstated"]["deployed_commit"], "a branch is not a deployed commit")


if __name__ == "__main__":
    unittest.main()
