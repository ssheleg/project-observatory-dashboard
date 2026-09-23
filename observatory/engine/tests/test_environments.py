"""PB-128: environments are explicit or unknown, scoped by project (docs/design/DEPLOYMENTS.md, PB-004b)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "collectors"))
import environments as E  # noqa: E402

DOT = ".env"   # file names below are built from this: synthetic, no file is read


def rec(name, project):
    return {"id": f"heroku:{name}", "name": name, "project": project}


def scan(name, stage=None, pipeline=True, error=None):
    row = {"name": name}
    if pipeline:
        row["pipeline"] = {"id": "p", "name": "pipe", "stage": stage} if stage else None
        row["pipeline_error"] = error
    return row


def build(records, scans, *, creds=(), files=(), projects=(), overrides=None, problems=()):
    return E.build(records, scans, list(creds), list(files), list(projects), overrides or {}, list(problems), "2026-09-24")


class Environments(unittest.TestCase):
    def test_two_projects_production_apps_are_two_environments(self):
        doc, edges = build([rec("a-web", "project:a"), rec("b-web", "project:b")],
                           [scan("a-web", "production"), scan("b-web", "production")])
        self.assertEqual({e["to"] for e in edges}, {"environment:project:a/production", "environment:project:b/production"})
        self.assertEqual({e["rule"] for e in edges}, {"heroku-pipeline-stage"})

    def test_a_name_is_not_evidence(self):
        doc, edges = build([rec("shop-prod", "project:a")], [scan("shop-prod")])
        self.assertEqual(edges, [])
        self.assertEqual(doc["unassigned"][0]["deployment"], "heroku:shop-prod")

    def test_an_override_wins_and_is_named_as_the_rule(self):
        doc, edges = build([rec("a-web", "project:a")], [scan("a-web", "staging")],
                           overrides={"heroku:a-web": "production"})
        self.assertEqual([(e["to"], e["rule"]) for e in edges], [("environment:project:a/production", "override")])

    def test_slots_and_files_show_an_environment_exists_but_bind_no_app(self):
        doc, edges = build([rec("a-web", "project:a")], [scan("a-web")],
                           creds=[{"source": "vault", "env": "prod", "used_by": ["project:a"]}],
                           files=[{"kind": "env", "path": f"/x/a/{DOT}.staging", "project": "a"},
                                  {"kind": "env", "path": f"/x/a/{DOT}.agent-sync", "project": "a"},
                                  {"kind": "template", "path": f"/x/a/{DOT}.production.example", "project": "a"}],
                           projects=[{"id": "project:a", "local_folders": ["a"]}])
        self.assertEqual(edges, [])
        self.assertEqual({(e["name"], tuple(e["evidence"])) for e in doc["environments"]},
                         {("production", ("vault-slot",)), ("staging", ("env-file",))})
        self.assertTrue(all(not e["deployments"] for e in doc["environments"]))

    def test_names_are_normalised_and_unknown_names_are_not_environments(self):
        self.assertEqual([E.normalise(n) for n in ("prod", "Stage", "dev", "banana")],
                         ["production", "staging", "development", None])
        self.assertEqual(E.file_environment(f"{DOT}.prod.do"), "production")
        self.assertIsNone(E.file_environment(DOT))

    def test_no_project_means_no_environment_to_belong_to(self):
        doc, edges = build([rec("orphan", None)], [scan("orphan", "production")])
        self.assertEqual(edges, [])
        self.assertIn("no project claims this app", doc["unassigned"][0]["why"])

    def test_old_scan_and_failed_pipeline_read_say_why(self):
        doc, _ = build([rec("a", "project:a"), rec("b", "project:a")],
                       [scan("a", pipeline=False), scan("b", error="503")])
        whys = {u["deployment"]: u["why"] for u in doc["unassigned"]}
        self.assertEqual(whys["heroku:a"], "the scan predates pipeline stages")
        self.assertIn("503", whys["heroku:b"])
        self.assertTrue(any(d["source"] == "heroku" for d in doc["degraded"]))

    def test_override_file_problems_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "environments.json"
            p.write_text(json.dumps({"deployments": {"heroku:a": {"environment": "prod"}, "heroku:b": "banana"}}))
            got, problems = E.load_overrides(p)
            self.assertEqual(got, {"heroku:a": "production"})
            self.assertEqual(len(problems), 1)


class ScannerReadsThePipelineStage(unittest.TestCase):
    def scan(self, pipeline_answer):
        import scan_heroku as sh
        saved = sh.get

        def fake(url, tok, **kw):
            if url.endswith("/pipeline-couplings"):
                return pipeline_answer
            if url.endswith("/github"):
                return {"__error__": "404"}
            return []
        sh.get = fake
        try:
            return sh.scan_app({"id": "app-1", "name": "demo", "team": {"id": "t1", "name": "team"}}, "token")
        finally:
            sh.get = saved

    def test_stage_none_and_failure_are_three_different_answers(self):
        staged = self.scan({"pipeline": {"id": "p1", "name": "demo"}, "stage": "staging"})
        self.assertEqual((staged["pipeline"]["stage"], staged["pipeline_error"]), ("staging", None))
        uncoupled = self.scan({"__error__": "404"})
        self.assertEqual((uncoupled["pipeline"], uncoupled["pipeline_error"]), (None, None))
        failed = self.scan({"__error__": "503"})
        self.assertEqual((failed["pipeline"], failed["pipeline_error"]), (None, "503"))


if __name__ == "__main__":
    unittest.main()
