"""PB-131: the leak scan reads the companion store from its last mark, like a transcript.

tools/scan_leaks.py `scan_sqlite` + tools/sqlite_scan.py: a complete pass, then
only rows added since; a complete pass again when the value set changes, with
--full, or weekly. A sighting is reported by the pass that first reads its row.
The mark never holds a value.
"""
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "collectors"):
    sys.path.insert(0, str(p))

import paths  # noqa: E402
import scan_env  # noqa: E402
import scan_leaks as L  # noqa: E402

SECRET_A = "synthetic-value-" + "a" * 24
SECRET_B = "synthetic-value-" + "b" * 24


class LeakScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.db = base / "companion.db"
        c = sqlite3.connect(self.db)
        c.execute("CREATE TABLE observations(title TEXT, facts TEXT)")
        c.executemany("INSERT INTO observations VALUES (?, ?)", [(f"t{i}", f"fact {i}") for i in range(900)])
        c.execute("INSERT INTO observations VALUES ('x', ?)", (f"has {SECRET_A} inside",))
        c.commit(); c.close()
        self.values = {SECRET_A: "demo/A"}
        self.saved = (L.STATE, L.OUT, L.known_values, L.targets, paths.COMPANION_DB, scan_env.salt)
        L.STATE, L.OUT = base / "leak-scan-state.json", base / "leak-scan.json"
        L.known_values = lambda: (dict(self.values), [], [])
        L.targets = lambda days: ([], [])
        paths.COMPANION_DB = self.db
        scan_env.salt = lambda: "d" * 64

    def tearDown(self):
        (L.STATE, L.OUT, L.known_values, L.targets, paths.COMPANION_DB, scan_env.salt) = self.saved
        self.tmp.cleanup()

    def scan(self, *args):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(L.main(["leaks", *args]), 0)
        return json.loads(L.OUT.read_text())

    def insert(self, text):
        c = sqlite3.connect(self.db); c.execute("INSERT INTO observations VALUES ('n', ?)", (text,)); c.commit(); c.close()

    def test_a_row_is_read_once_and_a_new_row_is_read_next(self):
        first = self.scan()
        self.assertEqual((first["companion_store"]["mode"], first["companion_store"]["rows_read"]), ("full", 901))
        self.assertEqual([h["secret"] for h in first["hits"]], ["demo/A"])
        again = self.scan()
        self.assertEqual((again["companion_store"]["mode"], again["companion_store"]["rows_read"]), ("incremental", 0))
        self.assertEqual(again["hits"], [], "a sighting is reported by the pass that first reads its row")
        self.insert(f"new {SECRET_A}")
        third = self.scan()
        self.assertEqual(third["companion_store"]["rows_read"], 1)
        self.assertEqual(third["hits"][0]["occurrences"], 1)

    def test_a_new_value_is_looked_for_in_old_rows(self):
        self.scan()
        c = sqlite3.connect(self.db); c.execute("UPDATE observations SET facts=? WHERE rowid=3", (SECRET_B,)); c.commit(); c.close()
        self.values[SECRET_B] = "demo/B"
        out = self.scan()
        self.assertEqual(out["companion_store"]["mode"], "full")
        self.assertIn("demo/B", {h["secret"] for h in out["hits"]})

    def test_full_forces_a_complete_pass(self):
        self.scan()
        self.assertEqual(self.scan("--full")["companion_store"]["rows_read"], 901)

    def test_without_a_salt_every_pass_is_complete_and_no_mark_is_kept(self):
        def missing():
            raise RuntimeError("identity is missing")
        scan_env.salt = missing
        self.scan()
        self.assertEqual(self.scan()["companion_store"]["rows_read"], 901)
        self.assertNotIn("sqlite", json.loads(L.STATE.read_text()))

    def test_an_unreadable_store_keeps_its_old_mark(self):
        self.scan()
        before = json.loads(L.STATE.read_text())["sqlite"]
        self.db.write_bytes(b"not a database at all" * 100)
        out = self.scan()
        self.assertFalse(out["companion_store"]["read"])
        self.assertEqual(json.loads(L.STATE.read_text())["sqlite"]["stores"], before["stores"])

    def test_the_mark_holds_no_value(self):
        self.scan()
        self.assertNotIn(SECRET_A, L.STATE.read_text())


if __name__ == "__main__":
    unittest.main()
