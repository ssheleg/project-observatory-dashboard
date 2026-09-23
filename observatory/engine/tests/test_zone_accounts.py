"""A zone name held by two Cloudflare accounts yields two distinct zone ids."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "collectors"))


class ZoneAccounts(unittest.TestCase):
    def test_a_repeated_name_is_qualified_by_account_and_a_single_one_is_not(self):
        import estate_surfaces as es
        zone = lambda name, acc: {"name": name, "account_id": acc, "account_label": acc, "status": "active"}
        scan = {"zones": [zone("example.org", "acct-a"), zone("example.org", "acct-b"), zone("solo.example", "acct-a")]}
        ids = sorted(r["id"] for r in es.zone_rows(scan, [], []))
        self.assertEqual(ids, ["zone:example.org@acct-a", "zone:example.org@acct-b", "zone:solo.example"])
        self.assertEqual(len(ids), len(set(ids)))
        rows = {r["id"]: r for r in es.zone_rows(scan, [], [])}
        self.assertEqual(rows["zone:solo.example"]["account_id"], "acct-a", "the account id is kept")


if __name__ == "__main__":
    unittest.main()
