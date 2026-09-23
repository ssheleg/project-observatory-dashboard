"""PB-127: provider accounts are entities (docs/design/DEPLOYMENTS.md, slice PB-004a)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "collectors"))
import accounts as A  # noqa: E402


def app(name, team=None, team_id=None, owner_id=None, ids=True):
    row = {"name": name, "team": team or "personal"}
    if ids:
        row.update(team_id=team_id, owner_id=owner_id)
    return row


class Accounts(unittest.TestCase):
    def test_two_teams_are_two_accounts_and_a_personal_app_is_its_owner(self):
        apps = [app("a", "team-one", "t1"), app("b", "team-two", "t2"), app("c", owner_id="u9")]
        doc, edges = A.build(apps, [], "2026-09-24", True, False)
        self.assertEqual({e["from"]: e["to"] for e in edges},
                         {"heroku:a": "account:heroku/t1", "heroku:b": "account:heroku/t2", "heroku:c": "account:heroku/u9"})
        self.assertEqual({e["rule"] for e in edges}, {"heroku-team", "heroku-owner"})
        self.assertEqual([a["label"] for a in doc["accounts"]], ["team-one", "team-two", "personal"])

    def test_the_label_is_not_the_id(self):
        one, _ = A.build([app("a", "old-name", "t1")], [], "d", True, False)
        two, _ = A.build([app("a", "new-name", "t1")], [], "d", True, False)
        self.assertEqual(one["accounts"][0]["id"], two["accounts"][0]["id"])

    def test_nothing_stated_means_no_edge_and_a_reason(self):
        zones = [{"id": "zone:example.org", "account_id": None}, {"id": "zone:example.net", "account_id": "c1"}]
        doc, edges = A.build([app("x")], zones, "d", True, True)
        self.assertEqual([e["from"] for e in edges], ["zone:example.net"],
                         "an app with no team and no owner id is not given the only account in sight")
        self.assertEqual({u["resource"] for u in doc["unattributed"]}, {"heroku:x", "zone:example.org"})

    def test_a_scan_from_before_account_ids_is_degraded_not_guessed(self):
        doc, edges = A.build([app("a", "team-one", ids=False)], [], "d", True, False)
        self.assertEqual(edges, [])
        self.assertEqual(doc["unattributed"][0]["why"], "the scan predates account ids")
        self.assertTrue(any(d["source"] == "heroku" for d in doc["degraded"]))

    def test_no_email_becomes_an_id(self):
        doc, _ = A.build([app("a", owner_id="u1") | {"owner": "someone@example.invalid"}], [], "d", True, False)
        self.assertNotIn("@", doc["accounts"][0]["id"])


if __name__ == "__main__":
    unittest.main()
