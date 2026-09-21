#!/usr/bin/env python3
""                                                                             
from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
with tempfile.TemporaryDirectory(prefix="observatory-import-boundary-") as import_home:
    with patch.dict(os.environ, {"OBSERVATORY_HOME": str(Path(import_home).resolve())}):
        import keyserver


class KeyserverBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix="observatory-keyserver-boundary-")
        self.root = Path(self.sandbox.name)
        self.token = "-".join(("only", "a", "synthetic", "test", "token"))
        self.patches = [
            patch.object(keyserver, "TOKEN_FILE", self.root / "private" / "token"),
            patch.object(keyserver, "AUDIT", self.root / "audit" / "journal.jsonl"),
            patch.object(keyserver.paths, "REGISTRY", self.root / "registry"),
            patch.object(keyserver.paths, "SCRATCH", self.root / "scratch"),
            patch.object(keyserver.paths, "DATA", self.root / "projects"),
        ]
        for item in self.patches:
            item.start()
        self.server = keyserver.Server(("127.0.0.1", 0), keyserver.Handler, self.token)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.effects = []
        self.action = patch.dict(keyserver.ACTIONS, {"probe": lambda body: self.effects.append(body) or {"ok": True}})
        self.action.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.action.stop()
        for item in reversed(self.patches):
            item.stop()
        self.sandbox.cleanup()

    def request(self, method="POST", path="/api/probe", headers=None, body=b"{}"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        all_headers = {"X-Observatory-Token": self.token, **(headers or {})}
        try:
            conn.request(method, path, body=body if method == "POST" else None, headers=all_headers)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_same_origin_and_cli_reach_action(self):
        for host in ("127.0.0.1", "localhost"):
            authority = f"{host}:{self.port}"
            code, _, _ = self.request(headers={"Host": authority, "Origin": f"http://{authority}"})
            self.assertEqual(code, 200)
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(len(self.effects), 3)

    def test_origin_prefix_and_different_port_refused_before_effects(self):
        for origin in (
            "http://localhost.evil.invalid", "http://127.0.0.1.evil.invalid",
            "http://" + f"localhost:{self.port}" + "@evil.invalid", "null",
            "http://127.0.0.1:1", f"https://127.0.0.1:{self.port}",
            f"http://127.0.0.1:{self.port}/", f"http://127.0.0.1:{self.port}?x=1",
            f"http://127.0.0.1:{self.port}#fragment", f"http://localhost:{self.port}",
        ):
            with self.subTest(origin=origin):
                self.assertEqual(self.request(headers={"Origin": origin})[0], 403)
        self.assertEqual(self.effects, [])
        self.assertFalse(keyserver.AUDIT.exists())

    def test_rebinding_host_cannot_obtain_page_token(self):
        with patch.object(keyserver.Handler, "_page_for") as page:
            for host in ("evil.invalid", "localhost.evil.invalid", "127.0.0.1:1", "localhost", ""):
                code, _, raw = self.request("GET", "/", headers={"Host": host})
                self.assertEqual(code, 403)
                self.assertNotIn(self.token.encode(), raw)
            page.assert_not_called()

    def test_duplicate_host_origin_and_token_are_refused(self):
        for name, value in (("Host", f"127.0.0.1:{self.port}"),
                            ("Origin", f"http://127.0.0.1:{self.port}"),
                            (keyserver.HEADER, self.token)):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
            try:
                conn.putrequest("POST", "/api/probe", skip_host=True)
                conn.putheader("Host", f"127.0.0.1:{self.port}")
                conn.putheader(keyserver.HEADER, self.token)
                if name == "Origin":
                    conn.putheader("Origin", value)
                conn.putheader(name, value)
                conn.putheader("Content-Length", "2")
                conn.endheaders(b"{}")
                response = conn.getresponse()
                self.assertIn(response.status, (401, 403))
                response.read()
            finally:
                conn.close()
        self.assertEqual(self.effects, [])

    def test_token_is_checked_with_compare_digest(self):
        with patch.object(keyserver.hmac, "compare_digest", wraps=keyserver.hmac.compare_digest) as compare:
            self.assertEqual(self.request(headers={keyserver.HEADER: "wrong"})[0], 401)
            compare.assert_called_once()
        self.assertEqual(self.effects, [])

    def test_bad_json_and_body_bounds_do_not_reach_action(self):
        for body in (b"[]", b"null", b'"text"', b'{"limit": NaN}', b'{"limit": Infinity}', b"\xff"):
            self.assertEqual(self.request(body=body)[0], 400)
        self.assertEqual(self.request(headers={"Content-Length": "-1"})[0], 400)
        self.assertEqual(self.request(headers={"Content-Length": "65537"})[0], 413)
        self.assertEqual(self.request(headers={"Transfer-Encoding": "chunked"})[0], 400)
        self.assertEqual(self.effects, [])

    def test_token_page_is_uncacheable_and_not_frameable(self):
        page = self.root / "page.html"
        page.write_text("<!doctype html><html><head></head><body>fixture</body></html>")
        with patch.object(keyserver.Handler, "_page_for", return_value=(page, "text/html")):
            code, headers, raw = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn(self.token.encode(), raw)

    def test_empty_tokens_and_routable_bind_are_refused(self):
        for address, tok in (("0.0.0.0", self.token), ("127.0.0.1", "")):
            with self.assertRaises(ValueError):
                keyserver.Server((address, 0), keyserver.Handler, tok)

    def test_token_created_private_reused_and_symlinks_refused(self):
        first = keyserver.token()
        self.assertEqual(first, keyserver.token())
        self.assertEqual(keyserver.TOKEN_FILE.stat().st_mode & 0o777, 0o600)
        target = self.root / "unrelated"
        target.write_text("untouched")
        keyserver.TOKEN_FILE.unlink()
        keyserver.TOKEN_FILE.symlink_to(target)
        with self.assertRaises(SystemExit):
            keyserver.token()
        self.assertEqual(target.read_text(), "untouched")

    def test_empty_and_publicly_readable_token_files_refused(self):
        keyserver.TOKEN_FILE.parent.mkdir()
        keyserver.TOKEN_FILE.write_text("")
        keyserver.TOKEN_FILE.chmod(0o600)
        with self.assertRaises(SystemExit):
            keyserver.token()
        keyserver.TOKEN_FILE.write_text(self.token)
        keyserver.TOKEN_FILE.chmod(0o644)
        with self.assertRaises(SystemExit):
            keyserver.token()

    def test_nonfinite_limits_refused_before_audit_or_provider(self):
        with patch.object(keyserver, "_door") as door:
            for value in ("NaN", "Infinity", "-Infinity"):
                for action, body in ((keyserver.act_mint, {"destination": "observatory", "limit": value}),
                                     (keyserver.act_limit, {"label": "fixture", "limit": value})):
                    with self.assertRaises(ValueError):
                        action(body)
            door.assert_not_called()
        self.assertFalse(keyserver.AUDIT.exists())

    def test_annotation_audit_does_not_copy_free_text_or_value(self):
        import sign_credential
        synthetic = "sk-" + "f" * 48
        with patch.object(sign_credential, "write", side_effect=ValueError("refused")):
            with self.assertRaises(ValueError):
                keyserver.act_annotate({"id": "fixture", "purpose": synthetic, "owner": synthetic})
        text = keyserver.AUDIT.read_text()
        self.assertNotIn(synthetic, text)
        self.assertEqual(json.loads(text)["action"], "annotate")
        self.assertEqual(keyserver.AUDIT.stat().st_mode & 0o777, 0o600)

    def test_accidental_value_shaped_label_is_redacted_in_audit(self):
        synthetic = "sk-" + "a" * 48
        keyserver.audit("fixture", synthetic, {})
        record = json.loads(keyserver.AUDIT.read_text())
        self.assertEqual(record["subject"], "[redacted]")
        self.assertNotIn(synthetic, keyserver.AUDIT.read_text())

    def test_explicit_reveal_is_inventory_scoped_and_audited_without_value(self):
        keyserver.paths.SCRATCH.mkdir()
        keyserver.paths.DATA.mkdir()
        synthetic = "synthetic-" + "b" * 32
        target = keyserver.paths.DATA / "fixture.env"
        target.write_text("EXAMPLE_KEY=" + synthetic + "\n")
        (keyserver.paths.SCRATCH / "env.json").write_text(json.dumps({"files": [
            {"path": "fixture.env", "variables": [{"name": "EXAMPLE_KEY", "class": "fixture"}]}]}))
        code, _, raw = self.request(path="/api/reveal", body=json.dumps(
            {"path": "fixture.env", "name": "EXAMPLE_KEY"}).encode())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["value"], synthetic)
        self.assertNotIn(synthetic, keyserver.AUDIT.read_text())
        self.assertEqual(json.loads(keyserver.AUDIT.read_text())["action"], "reveal")
        code, _, raw = self.request(path="/api/reveal", body=json.dumps(
            {"path": "other.env", "name": "EXAMPLE_KEY"}).encode())
        self.assertEqual(code, 400)
        self.assertNotIn(synthetic.encode(), raw)

    def test_symlink_audit_refuses_before_provider(self):
        target = self.root / "unrelated"
        target.write_text("untouched")
        keyserver.AUDIT.parent.mkdir()
        keyserver.AUDIT.symlink_to(target)
        with patch.object(keyserver, "_door") as door:
            with self.assertRaises(OSError):
                keyserver.act_limit({"label": "fixture", "limit": 1})
            door.assert_not_called()
        self.assertEqual(target.read_text(), "untouched")

    def test_unexpected_exception_does_not_reflect_sensitive_detail(self):
        synthetic = "private-" + "v" * 48
        def fail(body):
            raise RuntimeError(synthetic)
        with patch.dict(keyserver.ACTIONS, {"probe": fail}):
            code, _, raw = self.request()
        self.assertEqual(code, 500)
        self.assertNotIn(synthetic.encode(), raw)


if __name__ == "__main__":
    unittest.main()
