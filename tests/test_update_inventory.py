import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_inventory", ROOT / "tools/update_inventory.py")
inv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inv)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = Path(self.tmp.name)
        (self.engine / "a.py").write_bytes(b"a = 1\n")
        (self.engine / "b.py").write_bytes(b"b = 2\n")
        self.doc = {"format_version": 1, "file_count": 2, "files": [
            {"path": "a.py", "source_sha256": "orig-a", "export_sha256": sha(b"a = 1\n"), "bytes": 6},
            {"path": "gone.py", "source_sha256": "orig-g", "export_sha256": "x", "bytes": 1}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_unchanged_file_is_not_marked(self):
        new, changes = inv.refreshed(self.doc, self.engine, ["a.py", "b.py"])
        row = next(r for r in new["files"] if r["path"] == "a.py")
        self.assertNotIn("upstream_modified", row)
        self.assertEqual(row["source_sha256"], "orig-a")
        self.assertNotIn("changed: a.py", changes)

    def test_added_changed_and_removed_are_reported(self):
        (self.engine / "a.py").write_bytes(b"a = 3\n")
        new, changes = inv.refreshed(self.doc, self.engine, ["a.py", "b.py"])
        self.assertEqual(sorted(changes), ["added: b.py", "changed: a.py", "removed: gone.py"])
        rows = {r["path"]: r for r in new["files"]}
        self.assertEqual(rows["a.py"]["export_sha256"], sha(b"a = 3\n"))
        self.assertTrue(rows["a.py"]["upstream_modified"])
        self.assertEqual(rows["a.py"]["source_sha256"], "orig-a")
        self.assertIsNone(rows["b.py"]["source_sha256"])
        self.assertEqual(new["file_count"], 2)

    def test_repository_inventory_is_current(self):
        self.assertEqual(inv.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
