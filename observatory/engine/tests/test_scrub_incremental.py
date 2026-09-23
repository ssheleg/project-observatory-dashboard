"""PB-125: the companion scrub reads each row once, not on every tick.

tools/scrub_companion.py, "PB-125" block: a complete pass, then only rows added
since; a complete pass again when the value set changes, after FULL_EVERY, or
when a table was recreated. The watermark never holds a value.
"""
import datetime
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

import configuration  # noqa: E402
import scan_env  # noqa: E402
import scan_leaks  # noqa: E402
import scrub_companion as s  # noqa: E402

SECRET_A = "synthetic-value-" + "a" * 24
SECRET_B = "synthetic-value-" + "b" * 24


class Scrub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.db = base / "claude-mem.db"
        c = sqlite3.connect(self.db)
        c.execute("CREATE TABLE observations(title TEXT, facts TEXT)")
        c.executemany("INSERT INTO observations VALUES (?, ?)",
                      [(f"t{i}", f"plain fact {i}") for i in range(1200)])
        c.commit(); c.close()
        self.values = {SECRET_A: "demo/A"}
        self.salt = "c" * 64
        self.saved = (s.STORES, s.WATERMARK, s.JOURNAL, s.BACKUP_DIR, scan_leaks.known_values,
                      configuration.enabled, scan_env.salt)
        s.STORES, s.WATERMARK = [self.db], base / "state" / "scrub-watermark.json"
        s.JOURNAL, s.BACKUP_DIR = base / "state" / "scrub.jsonl", base / "backups"
        scan_leaks.known_values = lambda: (dict(self.values), [], [])
        configuration.enabled = lambda *a, **k: True
        scan_env.salt = lambda: self.salt

    def tearDown(self):
        (s.STORES, s.WATERMARK, s.JOURNAL, s.BACKUP_DIR, scan_leaks.known_values,
         configuration.enabled, scan_env.salt) = self.saved
        self.tmp.cleanup()

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(s.main(["scrub", *args]), 0)
        return out.getvalue()

    def insert(self, facts):
        c = sqlite3.connect(self.db); c.execute("INSERT INTO observations VALUES ('new', ?)", (facts,)); c.commit(); c.close()

    def facts(self):
        c = sqlite3.connect(self.db); rows = [r[0] for r in c.execute("SELECT facts FROM observations ORDER BY rowid")]; c.close()
        return rows

    def test_page_screening_rewrites_only_the_cell_that_holds_a_value(self):
        c = sqlite3.connect(self.db)
        c.execute("UPDATE observations SET facts = ? WHERE rowid = 700", (f"key {SECRET_A} here",)); c.commit(); c.close()
        out = self.run_main()
        self.assertIn("1 cell(s) rewritten (full", out)
        facts = self.facts()
        self.assertEqual(facts[699], "key [REDACTED:demo/A] here")
        self.assertEqual(facts[698], "plain fact 698")
        self.assertNotIn(SECRET_A, s.JOURNAL.read_text() + s.WATERMARK.read_text(), "no value is ever stored")

    def test_later_ticks_read_only_new_rows_until_the_value_set_changes(self):
        self.assertIn("1200 row(s) read (full: first pass)", self.run_main())
        self.insert("another plain fact")
        self.assertIn("1 row(s) read (incremental", self.run_main())
        self.assertIn("0 row(s) read (incremental", self.run_main())
        # A value learned later must be looked for in rows already read.
        c = sqlite3.connect(self.db)
        c.execute("UPDATE observations SET facts = ? WHERE rowid = 5", (SECRET_B,)); c.commit(); c.close()
        self.values[SECRET_B] = "demo/B"
        out = self.run_main()
        self.assertIn("rewritten (full", out)
        self.assertEqual(self.facts()[4], "[REDACTED:demo/B]")

    def test_a_week_old_complete_pass_forces_another(self):
        self.run_main()
        mark = json.loads(s.WATERMARK.read_text())
        mark["full_on"] = (datetime.date.today() - datetime.timedelta(days=8)).isoformat()
        s.WATERMARK.write_text(json.dumps(mark))
        self.assertIn("1200 row(s) read (full: last complete pass", self.run_main())

    def test_a_recreated_table_is_read_from_the_start(self):
        self.run_main()
        c = sqlite3.connect(self.db)
        c.execute("DELETE FROM observations"); c.execute("INSERT INTO observations VALUES ('x', ?)", (SECRET_A,))
        c.commit(); c.close()
        self.assertIn("1 cell(s) rewritten (incremental", self.run_main())

    def test_without_a_salt_every_pass_is_complete_and_nothing_is_recorded(self):
        def missing():
            raise RuntimeError("identity is missing")
        scan_env.salt = missing
        self.assertIn("full: no salt", self.run_main())
        self.assertFalse(s.WATERMARK.exists())
        self.assertIn("1200 row(s) read (full: no salt", self.run_main())

    def test_a_dry_run_reads_everything_and_moves_nothing(self):
        self.run_main()
        before = s.WATERMARK.read_text()
        self.insert(SECRET_A)
        out = self.run_main("--dry-run")
        self.assertIn("dry run, nothing written", out)
        self.assertEqual(s.WATERMARK.read_text(), before)
        self.assertIn(SECRET_A, self.facts()[-1])


if __name__ == "__main__":
    unittest.main()
