"""The five behaviours the 2026-09-23 audit reproduced in the published 0.2.0 wheel.

Each case drives the real module on synthetic values only, in the suite's own
sandbox, and asserts the safe answer. They stay here so the next release cannot
quietly bring one back.

RA-01  a local rotate must not settle an open leak
RA-02  fingerprints under two salt namespaces are not compared
RA-03  an unreadable acknowledgement file is preserved, not replaced
RA-04  reading the salt never creates it, and an empty salt is refused
"""
from __future__ import annotations
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


class AuditRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ra01_local_rotate_leaves_the_leak_open(self):
        vault = importlib.import_module("tools.vault")
        store = self.root / "vault"
        vault.STORE, vault.LEAKS, vault.MOVES = store, store / "leaks.jsonl", store / "movements.jsonl"
        args = types.SimpleNamespace(project="demo", env="local", name="TOKEN", force=False)
        stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("synthetic-first-value-4c1d")
            quiet(vault.cmd_put, args)
            vault.LEAKS.write_text(json.dumps({"event": "leaked", "id": "fixture-1",
                                               "secret": "demo/local/TOKEN"}) + "\n")
            vault.LEAKS.chmod(0o600)
            sys.stdin = io.StringIO("synthetic-second-value-9e2b")
            quiet(vault.cmd_rotate, args)
        finally:
            sys.stdin = stdin
        rows = [json.loads(line) for line in vault.LEAKS.read_text().splitlines() if line.strip()]
        self.assertFalse(any(r.get("event") == "settled" for r in rows), rows)
        self.assertEqual([r["id"] for r in vault.open_leaks()], ["fixture-1"])

    def test_ra02_fingerprints_from_two_namespaces_are_not_compared(self):
        registry = importlib.import_module("collectors.remote_registry")
        remote = {"fingerprint_namespace": "synthetic-A", "apps": [{"app": "demo", "folders": ["/srv/demo"],
                  "vars": [{"name": "TOKEN", "class": "secret", "fingerprint": "a" * 24}]}]}
        local = {"fingerprint_namespace": "synthetic-B", "files": [{"kind": "env", "project": "demo",
                 "path": "demo/.env", "variables": [{"name": "TOKEN", "class": "secret", "fingerprint": "b" * 24}]}]}
        doc = registry.document(remote, local, "2026-09-23")
        self.assertEqual(doc["apps"][0]["vars"][0]["verdict"], "not_compared")

    def test_ra03_an_unreadable_ack_file_is_preserved(self):
        ack = importlib.import_module("tools.ack")
        f = self.root / "acks.json"
        f.write_text("{broken")
        ack.paths.FINDING_ACKS = f
        ack.board_ids = lambda: {"fixture:demo": {"severity": "warning", "title": "synthetic"}}
        with self.assertRaises((ack.AckStoreError, SystemExit)):
            quiet(ack.cmd_ack, types.SimpleNamespace(why="synthetic reason", until=None,
                                                     id="fixture:demo", by="fixture"))
        self.assertEqual(f.read_text(), "{broken")

    def test_ra04_reading_the_salt_never_creates_it_and_refuses_an_empty_one(self):
        scan = importlib.import_module("collectors.scan_env")
        scan.SALT_FILE = self.root / "salt"
        with self.assertRaises(Exception):
            quiet(scan.salt)
        self.assertFalse(scan.SALT_FILE.exists(), "a read must not mint a salt")
        scan.SALT_FILE.write_text("")
        scan.SALT_FILE.chmod(0o600)
        with self.assertRaises(Exception):
            quiet(scan.salt)
        self.assertEqual(scan.SALT_FILE.read_text(), "", "a refused salt is left as it was")


if __name__ == "__main__":
    unittest.main()
