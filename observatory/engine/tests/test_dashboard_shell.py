"""UI-02/04/08: real page markup and bounded attention previews, offline."""
from __future__ import annotations

import ast
import copy
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dashboard_shell", ROOT / "dashboard/shell.py")
shell = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shell)


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.mains = []
        self.elements = {}
        self.ids = []
        self.links = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "main":
            self.mains.append(attrs)
        if "id" in attrs:
            self.elements[attrs["id"]] = (tag, attrs, tuple(self.stack))
            self.ids.append(attrs["id"])
        if tag == "a":
            self.links.append(attrs)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, attrs.get("id")))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def findings(items, silenced=None):
    return {"items": items, "counts": {severity: sum(item["severity"] == severity for item in items)
                                       for severity in ("critical", "warning", "info")},
            "silenced": silenced or [], "folded_by_type": {"example": 12}}


class DashboardShellTests(unittest.TestCase):
    def test_all_pages_have_one_main_containing_their_primary_content(self):
        source = ast.parse((ROOT / "dashboard/build_dashboard.py").read_text())
        template = next(ast.literal_eval(node.value) for node in source.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "TEMPLATE" for t in node.targets))
        primary = {"index": "findings", "findings": "findings", "health": "observer"}
        for page in shell.NAMES:
            with self.subTest(page=page):
                parsed = Markup()
                parsed.feed(shell.page_html(template, page, {}))
                self.assertEqual([m["id"] for m in parsed.mains], ["workspace"])
                self.assertEqual(parsed.mains[0]["tabindex"], "-1")
                self.assertNotIn("hidden", parsed.mains[0])
                self.assertIn(("main", "workspace"), parsed.elements[primary.get(page, "out")][2])
                self.assertEqual(parsed.elements["out"][0], "div")
                self.assertTrue(any(a.get("class") == "skip-link" and a.get("href") == "#workspace"
                                    for a in parsed.links))
                routes = [a for a in parsed.links if a.get("class") == "pg"]
                self.assertEqual({a["href"] for a in routes}, {f"{name}.html" for name in shell.NAMES})
                self.assertEqual([a["href"] for a in routes if a.get("aria-current") == "page"], [f"{page}.html"])
                for group in ("work", "infrastructure", "access", "system"):
                    self.assertIn("nav-" + group, parsed.elements)
                if page == "index":
                    self.assertLess(parsed.ids.index("findings"), parsed.ids.index("tiles"))
                    self.assertLess(parsed.ids.index("findings"), parsed.ids.index("work"))

    def test_warning_only_preview_is_not_empty_and_preserves_counts(self):
        payload = {"findings": findings([{"id": "w", "severity": "warning", "detail": "evidence", "folded": True}])}
        preview = shell.slice_for("index", payload)["findings"]
        self.assertEqual([f["id"] for f in preview["items"]], ["w"])
        self.assertEqual(preview["counts"], {"critical": 0, "warning": 1, "info": 0})
        self.assertFalse(preview["items"][0]["folded"])
        self.assertEqual(preview["elsewhere"], 0)

    def test_overflow_is_bounded_visible_ranked_and_does_not_mutate_source(self):
        items = [{"id": "info", "severity": "info", "detail": "info"}]
        items += [{"id": str(i), "severity": "critical", "detail": "evidence", "action": "long action", "folded": i >= 8}
                  for i in range(12)]
        payload = {"findings": findings(items)}
        before = copy.deepcopy(payload)
        preview = shell.slice_for("index", payload)["findings"]
        self.assertEqual([f["id"] for f in preview["items"]], [str(i) for i in range(8)])
        self.assertTrue(all(not f["folded"] and not f["detail"] and not f["action"] for f in preview["items"]))
        self.assertEqual(preview["elsewhere"], 5)
        self.assertEqual(preview["counts"], before["findings"]["counts"])
        self.assertEqual(payload, before)
        self.assertEqual(shell.slice_for("findings", payload)["findings"], before["findings"])

    def test_acknowledged_only_history_survives_and_sensitive_payloads_stay_scoped(self):
        payload = {"findings": findings([], [{"id": "hidden", "acked": {"why": "reviewed"}}]),
                   "keys": {"private-metadata": []}, "remote": {"private-metadata": []},
                   "env": {"files": []}, "creds": {"credentials": []}}
        preview = shell.slice_for("index", payload)
        self.assertEqual(preview["findings"]["silenced"][0]["id"], "hidden")
        self.assertEqual(preview["findings"]["elsewhere"], 0)
        for key in ("keys", "remote", "env", "creds"):
            self.assertIsNone(preview[key])

    def test_summary_routes_have_no_inventory_badge_and_queue_stays_labelled(self):
        payload = {"health": {"proposed": 304},
                   "findings": {"counts": {"critical": 27, "warning": 100, "info": 5}}}
        counts = shell.counts_of(payload)
        self.assertEqual(counts["index"], "")
        self.assertEqual(counts["health"], "")
        self.assertEqual(counts["findings"], 132)
        self.assertIn("ждут решения 304", shell.cards_html(payload, counts))

    def test_traffic_summary_distinguishes_unknown_zero_and_partial_resource_sum(self):
        self.assertEqual(shell._traffic_line({}), "аналитика не сканировалась")
        unknown = shell._traffic_line({"google": {"totals": {
            "users_30d": None, "users_30d_unclaimed": None,
            "unknown_properties": 2, "measured_properties": 0}}})
        self.assertIn("не измерена", unknown)
        self.assertIn("без измерения: 2", unknown)
        self.assertNotIn("0 польз.", unknown)
        self.assertNotIn("без проекта", unknown)
        zero = shell._traffic_line({"google": {"totals": {
            "users_30d": 0, "users_30d_unclaimed": 0,
            "unknown_properties": 0, "measured_properties": 1}}})
        self.assertIn("0 польз./30 дн", zero)
        self.assertIn("сумма по ресурсам", zero)
        self.assertIn("0 без проекта", zero)
        self.assertNotIn("частично", zero)
        partial = shell._traffic_line({"google": {"totals": {
            "users_30d": 1200, "users_30d_unclaimed": 400,
            "unknown_properties": 3, "measured_properties": 2}}})
        for part in ("1 200 польз./30 дн", "сумма по ресурсам", "частично",
                     "измерено ресурсов: 2", "без измерения: 3", "400 без проекта"):
            self.assertIn(part, partial)


if __name__ == "__main__":
    unittest.main()
