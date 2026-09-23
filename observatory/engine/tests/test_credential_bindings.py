"""PB-129: a credential edge says where the value is read (docs/design/DEPLOYMENTS.md rule 5, PB-004c)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "collectors"))
import credentials_registry as CR  # noqa: E402
import remote_registry as RR  # noqa: E402
import scan_remote_env as SR  # noqa: E402


class Bindings(unittest.TestCase):
    def test_every_rule_has_a_binding_and_run_is_never_inferred_from_a_rule(self):
        self.assertEqual(set(CR.BINDING_BY_RULE.values()) - {"local", "unknown"}, set())

    def test_a_production_var_equal_to_a_slot_is_a_run_binding(self):
        app = {"app": "shop-web", "folders": [], "vars": [
            {"name": "API_TOKEN", "class": "secret", "fingerprint": "fp-1"},
            {"name": "PUBLIC_URL", "class": "config", "fingerprint": "fp-1"},
            {"name": "OTHER", "class": "secret", "fingerprint": "fp-9"}]}
        current = [{"project": "shop", "env": "prod", "name": "API_TOKEN", "fingerprint": "fp-1"}]
        out = RR.compare(app, {}, [], current=current)
        self.assertEqual(out["vault_in_use"], [{"name": "API_TOKEN", "slot": "shop/prod/API_TOKEN"}],
                         "only a secret-class variable is matched, and only on an equal fingerprint")
        edges = CR.run_edges({"apps": [out]}, [{"name": "shop-web", "project": "project:shop"}],
                             {"credential:vault/shop/prod/API_TOKEN"},
                             {"heroku:shop-web": "environment:project:shop/production"})
        [e] = edges
        self.assertEqual((e["binding"], e["deployment"], e["rule"], e["environment"]),
                         ("run", "heroku:shop-web", "config-var-fingerprint", "environment:project:shop/production"))

    def test_no_project_or_unknown_credential_gives_no_run_edge(self):
        doc = {"apps": [{"app": "x", "vault_in_use": [{"name": "K", "slot": "p/prod/K"}]}]}
        self.assertEqual(CR.run_edges(doc, [{"name": "x", "project": None}], {"credential:vault/p/prod/K"}, {}), [])
        self.assertEqual(CR.run_edges(doc, [{"name": "x", "project": "project:p"}], set(), {}), [])

    def test_current_values_skip_metadata_archives_and_temporary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            slot = store / "shop" / "prod"
            slot.mkdir(parents=True)
            (slot / "API_TOKEN").write_text("synthetic-value-" + "c" * 20)
            (slot / "API_TOKEN.meta.json").write_text("{}")
            (slot / "API_TOKEN.retired-2026-09-01T00-00-00Z").write_text("old")
            (slot / "API_TOKEN.tmp").write_text("partial")
            rows = SR.current_values("e" * 64, store)
            self.assertEqual([(r["project"], r["env"], r["name"]) for r in rows], [("shop", "prod", "API_TOKEN")])
            self.assertNotIn("synthetic-value", repr(rows), "a fingerprint, never the value")


if __name__ == "__main__":
    unittest.main()
