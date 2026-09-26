"""UI-01/04/05/06: execute built dashboard views against synthetic inventories.

This checks rendered records and action semantics, not browser layout. The shared
renderer supplies its minimal DOM; fixtures never read a personal registry.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import dashboard_fixture


# Reuse the real rendering harness's DOM and browser globals, but return full
# output instead of excerpts so an assertion cannot miss a row beyond the clip.
RUNNER = r'''
import { readFileSync } from "node:fs";
const harness = readFileSync(process.argv[2], "utf8");
const spec = JSON.parse(readFileSync(process.argv[3], "utf8"));
let prefix = harness.slice(harness.indexOf('const file ='), harness.indexOf('let threw = null;'));
prefix = prefix.replace('const file = process.argv[2];', 'const file = ' + JSON.stringify(spec.page) + ';');
// Finding controls ask descendants for stable nodes. The existing smoke DOM
// deliberately omits this, but these tests need their filter inputs.
prefix = prefix.replace('querySelector() { return null; },',
  'querySelector(selector) { this._sub ||= new Map(); if (!this._sub.has(selector)) this._sub.set(selector, makeEl(selector)); return this._sub.get(selector); }, closest() { return null; }, remove() {},');
const exercise = `
const chips = [...html.matchAll(/<button\\b[^>]*data-f="([^"]+)"[^>]*>([\\s\\S]*?)<\\/button>/g)].map(match => {
  const chip = makeEl("chip-" + match[1]);
  chip.dataset.f = match[1]; chip.textContent = match[2]; chip.attrs = {"aria-pressed": "false"};
  chip.setAttribute = (key, value) => { chip.attrs[key] = String(value); };
  chip.getAttribute = key => chip.attrs[key] ?? null;
  return chip;
});
const selectChips = selector => chips.filter(chip => {
  const exact = /data-f="([^"]+)"/.exec(selector);
  return (!exact || chip.dataset.f === exact[1]) && (!selector.includes('aria-pressed="true"') || chip.getAttribute('aria-pressed') === "true");
});
const originalQuery = document.querySelector.bind(document);
document.querySelectorAll = selector => selector.includes("data-f") ? selectChips(selector) : [];
document.querySelector = selector => selector.includes("data-f") ? selectChips(selector)[0] || null : originalQuery(selector);
let body = scripts.join("\\n;\\n");
body = body.replace(/const PAGE = [^;]+;/, "const PAGE = " + JSON.stringify(spec.view) + ";");
body = body.replace("const RUNTIME =", "Object.assign(D, " + JSON.stringify(spec.data || {}) + ");\\nconst RUNTIME =");
body += "\\n;" + (spec.after || "");
const run = new Function(...Object.keys(globals), "\\\"use strict\\\";\\n" + body);
run(...Object.values(globals));
process.stdout.write(JSON.stringify(written));
`;
const run = new Function('readFileSync', 'spec', prefix + exercise);
run(readFileSync, spec);
'''


class WorkspaceRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise RuntimeError("node is required for dashboard behavior checks")
        cls.tmp = tempfile.TemporaryDirectory(prefix="observatory-workspace-ui-")
        cls.base = Path(cls.tmp.name).resolve()
        (cls.base / "fixture").mkdir()
        cls.page = dashboard_fixture.build(cls.base / "fixture")
        cls.runner = cls.base / "run.mjs"
        cls.runner.write_text(RUNNER, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def render(self, view, data=None, after=""):
        spec = self.base / "case.json"
        spec.write_text(json.dumps({"page": str(self.page), "view": view,
                                    "data": data or {}, "after": after}), encoding="utf-8")
        p = subprocess.run(["node", str(self.runner), str(ROOT / "tests/render_dashboard.mjs"), str(spec)],
                           cwd=ROOT, text=True, capture_output=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr[-2500:])
        return json.loads(p.stdout)

    def test_projects_and_env_show_records_without_expanding_groups(self):
        for view, row_marker in (("projects", "fixture-a"), ("env", "TEST_LOCAL")):
            with self.subTest(view=view):
                out = self.render(view)["out"]
                self.assertIn(row_marker, out)
                self.assertIsNone(re.search(r'<tbody\b[^>]*class="[^"]*\bfolded\b', out), "default view conceals records")
                self.assertGreater(len(re.findall(r'<tr\b', out)), 1)

    @staticmethod
    def traffic():
        return {"google": {"properties": [
            {"id": "zero", "name": "Measured zero", "account_name": "A", "users_30d": 0,
             "standing": "linked", "project": "project:fixture-a", "report_url": "https://example.invalid/zero"},
            {"id": "unknown", "name": "Unknown metric", "account_name": "B", "users_30d": None,
             "standing": "unclaimed", "error": "not measured", "report_url": "https://example.invalid/unknown"},
            {"id": "busy", "name": "Measured traffic", "account_name": "A", "users_30d": 12,
             "standing": "unclaimed", "report_url": "https://example.invalid/busy"}],
            "totals": {}, "scanned_on": "2026-01-01"}}

    def test_no_users_filter_means_measured_zero_not_unknown(self):
        out = self.render("traffic", self.traffic(), 'active.add("t-quiet"); renderTraffic();')["out"]
        self.assertIn("Measured zero", out)
        self.assertFalse("Unknown metric" in out, "unknown metric matched measured-zero filter")
        self.assertNotIn("Measured traffic", out)

    def test_unknown_unclaimed_total_is_not_reported_as_zero(self):
        data = self.traffic()
        data["google"]["properties"] = [data["google"]["properties"][1]]
        data["google"]["totals"] = {"unclaimed": 1, "users_30d_unclaimed": None,
                                     "users_30d": None, "unknown_properties": 1}
        out = self.render("traffic", data)["out"]
        self.assertIn("1 ничьих (аудитория не измерена)", out)
        self.assertNotIn("1 ничьих (0", out)

    def test_contradictory_traffic_status_chips_replace_each_other(self):
        out = self.render("traffic", self.traffic(),
                          'document.querySelector(\'[data-f="t-linked"]\').onclick(); '
                          'document.querySelector(\'[data-f="t-unclaimed"]\').onclick();')["out"]
        self.assertIn("Measured traffic", out, "choosing unclaimed must release linked filter")
        self.assertNotIn("Measured zero", out)

    def test_traffic_is_comparable_across_account_boundaries(self):
        data = self.traffic()
        data["google"]["properties"].append({"id": "middle", "name": "Middle traffic", "account_name": "B",
                                            "users_30d": 6, "standing": "unclaimed", "report_url": "https://example.invalid/middle"})
        out = self.render("traffic", data, 'SORT.key="users"; SORT.dir="descending"; renderTraffic();')["out"]
        names = ["Measured traffic", "Middle traffic", "Measured zero", "Unknown metric"]
        indices = [out.index(name) for name in names]
        self.assertEqual(indices, sorted(indices), "global comparison must not restart for each account")

    def test_copy_only_credentials_and_refresh_say_command(self):
        creds = {"creds": {"credentials": [{"id": "credential:fixture", "name": "Fixture credential",
                                            "kind": "llm-api-key", "used_by": []}]}}
        for view, data in (("creds", creds), ("traffic", self.traffic())):
            with self.subTest(view=view):
                out = self.render(view, data)["out"]
                labels = [re.sub(r'<[^>]+>', '', m) for m in
                          re.findall(r'<button\b[^>]*\bdata-copy="[^"]*"[^>]*>(.*?)</button>', out, re.S)]
                self.assertTrue(labels, "fixture must expose at least one copied command")
                self.assertTrue(all("команд" in label.lower() for label in labels), labels)
                self.assertNotIn("страница открыта из файла", out,
                                 "copy mode also includes a served read-only dashboard")

    @staticmethod
    def findings(items, silenced=None):
        return {"findings": {"items": items, "counts": {"critical": 0, "warning": len(items), "info": 0},
                             "silenced": silenced or [], "built_at": "2026-01-01T00:00:00Z"}}

    def test_warning_only_overview_keeps_attention_visible(self):
        item = {"id": "warning-fixture", "severity": "warning", "type": "fixture.warning",
                "subject": "project:fixture-a", "title": "Attention fixture", "detail": "Measured issue", "action": "Inspect"}
        out = self.render("index", self.findings([item]))["findings"]
        self.assertIn("Attention fixture", out)
        self.assertFalse('class="flist folded"' in out, "warning-only overview hides the attention row")
        self.assertNotIn("ничего открытого", out)

    def test_acknowledged_only_findings_retain_reason_and_undo(self):
        item = {"id": "ack-fixture", "title": "Acknowledged fixture",
                "acked": {"why": "Synthetic review reason", "by": "fixture"}}
        out = self.render("findings", self.findings([], [item]))["findings"]
        self.assertIn("Acknowledged fixture", out)
        self.assertIn("Synthetic review reason", out)
        self.assertIn("--undo", out)
        self.assertRegex(out, r'data-(?:cmd|copy)="[^"]*--undo')


if __name__ == "__main__":
    unittest.main(verbosity=2)
