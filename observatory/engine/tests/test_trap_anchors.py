"""PB-134: every declared source mutation finds its anchor exactly once in this tree.

tools/trap_efficacy.py mutates code to prove a guard fails. An anchor that moved
or a file that is not in this distribution reports INCONCLUSIVE on every run and
proves nothing; this makes such a declaration a test failure the day it goes stale.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TrapAnchors(unittest.TestCase):
    def test_every_source_anchor_exists_exactly_once(self):
        sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
        spec = importlib.util.spec_from_file_location("trap_efficacy_under_test", ROOT / "tools/trap_efficacy.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        stale = []
        for mut in m.MUTATIONS:
            if mut["subject"] != "source":
                continue
            path = ROOT / mut["file"]
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            for find in ([mut["find"]] if "find" in mut else [e[0] for e in mut.get("edits", [])]):
                if text.count(find) != 1:
                    stale.append(f"{mut['trap']} {mut['file']}: {text.count(find)} occurrence(s)")
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
