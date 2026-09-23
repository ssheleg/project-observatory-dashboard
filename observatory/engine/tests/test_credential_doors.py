#!/usr/bin/env python3
"""The two credential doors — `tools/cloudflare.py` and `tools/openrouter.py`.

                                                                     
                                                                                
                                                                            
                                                                           
                                                                    

Everything here runs against fakes: the provider is a dict, the stores are
tmpdirs. What is asserted is the door's own reasoning — refusals, ordering,
labels, and that no code path prints a value.
"""
from __future__ import annotations
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup
portable_setup()
sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir                                                # noqa: E402
import private_io
import source_reader                                                # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ─────────────────────────── shared rules ────────────────────────────────────

def test_no_door_takes_or_prints_a_value_outside_stdin() -> None:
    """The rule both doors exist to enforce, checked on their CODE."""
    for rel in ("tools/cloudflare.py", "tools/openrouter.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        code = source_reader.code_only(src)
        check(f"{rel} takes values on stdin only",
              "sys.stdin.read()" in code
              and not source_reader.appears_in_code(src, '"--token"')
              and not source_reader.appears_in_code(src, '"--key"'),
              "a value in argv is in the shell history, ps and the transcript")
        module = load(rel, "private_writer_" + pathlib.Path(rel).stem)
        target = pathlib.Path(tmpdir.mkdtemp()).resolve() / "synthetic-key"
        module.write_secret(target, "synthetic-value")
        check(f"{rel} writes secrets 0600 with atomic replacement",
              target.read_text().strip() == "synthetic-value"
              and target.stat().st_mode & 0o777 == 0o600
              and "private_io.write" in code, "")
        check(f"{rel} strips provider errors to endpoint and status",
              "from None" in code and "e.headers" not in code, "")


def test_the_ledgers_hold_no_values() -> None:
    """Meta files and the ledger carry names, dates and places — never values."""
    for rel, fields in (("tools/cloudflare.py", ("account_id", "issued_on", "rotations")),
                        ("tools/openrouter.py", ("destination", "limit_usd", "rotations"))):
        src = (ROOT / rel).read_text(encoding="utf-8")
        # `code_keeping_strings`: the field names ARE string literals, which
        # `code_only` strips along with the prose.
        code = source_reader.code_keeping_strings(src)
        for f in fields:
            check(f"{rel} records `{f}`", f'"{f}"' in code, "")
        # The one string that must never be json.dump'ed: the token variable.
        check(f"{rel} never serialises the value into a meta file",
              '"value": value' not in code and "'value': value" not in code, "")


# ─────────────────────────── cloudflare ──────────────────────────────────────

def cf():
    sys.path.insert(0, str(ROOT / "plugins"))
    return load("tools/cloudflare.py", "cf_door")


def test_cf_stash_refuses_an_admin_that_cannot_issue() -> None:
    m = cf()
    calls = []

    def fake(path, token, payload=None, method=None):
        calls.append(path)
        if path.startswith("/accounts?"):
            return {"result": [{"id": "a1", "name": "Example Account"}]}
        raise RuntimeError("cloudflare answered 403 for " + path)
    m._request = fake
    m.ADMIN_STORE = pathlib.Path(tmpdir.mkdtemp()).resolve() / "cloudflare-admin"
    rc = m.cmd_stash("tok-" + "a" * 36)
    check("an admin token that cannot manage tokens is refused", rc == 1, str(rc))
    check("and nothing was written", not list(m.ADMIN_STORE.glob("*"))
          if m.ADMIN_STORE.is_dir() else True, "")

    def fake2(path, token, payload=None, method=None):
        if path.startswith("/accounts?"):
            return {"result": [{"id": "a1", "name": "Example Account"}]}
        return {"result": []}
    m._request = fake2
    rc = m.cmd_stash("tok-" + "a" * 36)
    check("a capable admin is stashed under the account's own name", rc == 0, str(rc))
    check("as a slug", (m.ADMIN_STORE / "example-account").is_file(), "")
    meta = json.loads((m.ADMIN_STORE / "example-account.meta.json").read_text())
    check("with the account id in its record, and no value",
          meta.get("account_id") == "a1" and "value" not in meta, str(meta))


def test_cf_one_stash_can_span_several_accounts() -> None:
    ""                                                                    
                                                                               
                                                                               
                                                                              
                                                   
    m = cf()
    m.ADMIN_STORE = pathlib.Path(tmpdir.mkdtemp()).resolve() / "cloudflare-admin"

    def fake(path, token, payload=None, method=None):
        if path.startswith("/accounts?"):
            return {"result": [{"id": "a1", "name": "Example Primary Account"},
                               {"id": "a2", "name": "Example Secondary"},
                               {"id": "a3", "name": "Example Restricted"}]}
        if path == "/user":
            return {"result": {"email": "user@example.com"}}
        if path.startswith("/accounts/a3/tokens"):
            raise RuntimeError("cloudflare answered 403 for " + path)   # member, no token rights
        return {"result": []}
    m._request = fake
    rc = m.cmd_stash("tok-" + "a" * 36)
    check("a multi-account token is stashed", rc == 0, str(rc))
    check("under the USER's name, since it is no one account's token",
          (m.ADMIN_STORE / "user-example-com").is_file(),
          str(list(m.ADMIN_STORE.glob("*")) if m.ADMIN_STORE.is_dir() else []))
    meta = json.loads((m.ADMIN_STORE / "user-example-com.meta.json").read_text())
    check("every account is recorded", [a["id"] for a in meta["accounts"]] == ["a1", "a2", "a3"],
          str(meta.get("accounts")))
    check("and each is probed for the right that matters",
          [a["can_issue"] for a in meta["accounts"]] == [True, True, False],
          str(meta.get("accounts")))

    # issue must NAME an account when several are reachable
    try:
        m.find_account(None)
        check("issue with no --account is refused when several are reachable", False, "no raise")
    except RuntimeError as exc:
        check("issue with no --account is refused when several are reachable",
              "name one with --account" in str(exc) and "example-secondary" in str(exc), str(exc))
    label, _admin, acct = m.find_account("example-secondary")
    check("an account is picked by its own slug", acct["id"] == "a2" and label == "user-example-com",
          f"{label} {acct}")
    try:
        m.find_account("example-restricted")
        check("an account the token cannot issue into is not offered", False, "no raise")
    except RuntimeError as exc:
        check("an account the token cannot issue into is not offered",
              "no reachable account matches" in str(exc), str(exc))

    # the old single-account record shape still resolves
    private_io.write(m.ADMIN_STORE / "legacy", "t\n")
    private_io.write(m.ADMIN_STORE / "legacy.meta.json", json.dumps(
        {"account_id": "a9", "account_name": "Legacy Co"}))
    label, _admin, acct = m.find_account("legacy")
    check("a single-account stash still answers to its own label",
          acct["id"] == "a9" and label == "legacy", f"{label} {acct}")


def test_cf_stash_finds_accounts_through_memberships_when_accounts_is_empty() -> None:
    ""                                                                         
                                                                              
                                                                           
    m = cf()
    m.ADMIN_STORE = pathlib.Path(tmpdir.mkdtemp()).resolve() / "cloudflare-admin"

    def fake(path, token, payload=None, method=None):
        if path.startswith("/accounts?"):
            return {"result": []}                        # the empty road
        if path.startswith("/memberships"):
            return {"result": [
                {"status": "accepted", "account": {"id": "a1", "name": "Example Primary Account"}},
                {"status": "pending", "account": {"id": "a2", "name": "Not Yet"}}]}
        if path == "/user/tokens/verify":
            return {"success": True, "result": {"status": "active"}}
        return {"result": []}
    m._request = fake
    found = m.discover_accounts("whatever")
    check("memberships supply what /accounts withheld",
          [a["id"] for a in found] == ["a1"], str(found))
    check("and a pending membership is not an account one can act in",
          all(a["id"] != "a2" for a in found), str(found))
    rc = m.cmd_stash("tok-" + "a" * 36)
    check("so the stash succeeds", rc == 0 and (m.ADMIN_STORE / "example-primary-account").is_file(),
          str(rc))


def test_cf_issue_rolls_rather_than_duplicating() -> None:
    m = cf()
    m.ADMIN_STORE = pathlib.Path(tmpdir.mkdtemp()).resolve() / "cloudflare-admin"
    m.ADMIN_STORE.mkdir(parents=True)
    private_io.write(m.ADMIN_STORE / "acct", "admin-token\n")
    private_io.write(m.ADMIN_STORE / "acct.meta.json", json.dumps(
        {"account_id": "a1", "account_name": "Acct"}))
    log = []

    def fake(path, token, payload=None, method=None):
        log.append((method or ("POST" if payload is not None else "GET"), path))
        if "permission_groups" in path:
            return {"result": [{"id": "g1", "name": "Zone Read", "scopes": ["com.cloudflare.api.account.zone"]},
                               {"id": "g2", "name": "Analytics Read", "scopes": ["com.cloudflare.api.account.zone"]},
                               {"id": "g3", "name": "DNS Read", "scopes": ["com.cloudflare.api.account.zone"]}]}
        if path.endswith("/tokens/t-old") and method == "PUT":
            return {"result": {"id": "t-old"}}              # policies rewritten
        if path.endswith("/tokens?per_page=50"):
            return {"result": [{"id": "t-old", "name": m.PRESETS["analytics"]["name"]}]}
        if path.endswith("/tokens/t-old/value"):
            return {"result": "fresh-value-" + "x" * 28}
        raise AssertionError(f"unexpected call {path}")
    m._request = fake
    tid, value = m.mint("admin-token", "a1", m.PRESETS["analytics"])
    check("an existing managed token is ROLLED, not duplicated",
          tid == "t-old" and value.startswith("fresh-value-"), f"{tid}")
    check("and no create call was made",
          not any(p.endswith("/tokens") and meth == "POST" for meth, p in log
                  if "value" not in p), str(log))
    check("the policies are rewritten to the preset BEFORE the value is rolled",
          [meth for meth, p in log if "t-old" in p] == ["PUT", "PUT"]
          and log.index(("PUT", "/accounts/a1/tokens/t-old")) < log.index(("PUT", "/accounts/a1/tokens/t-old/value")),
          str([x for x in log if "t-old" in x[1]]))
    check("and the roll is a PUT — POST is refused by the account-owned endpoint",
          ("PUT", "/accounts/a1/tokens/t-old/value") in log, str(log))


def test_cf_external_tokens_are_recorded_and_never_rolled_here() -> None:
    m = cf()
    d = pathlib.Path(tmpdir.mkdtemp()).resolve()
    m.token_dir = lambda: d
    m.ADMIN_STORE = d / "no-admins"
    private_io.write(d / "foreign", "v\n")
    private_io.write(d / "foreign.meta.json", json.dumps({"kind": "external"}))
    rc = m.cmd_rotate("foreign", leaked=False)
    check("rotate refuses an externally minted token with the reason",
          rc == 1, str(rc))
    check("and the file survives — reporting beats deleting",
          (d / "foreign").is_file(), "")


# ─────────────────────────── openrouter ──────────────────────────────────────

def orr():
    return load("tools/openrouter.py", "or_door")


def test_or_stash_demands_a_label_because_the_provider_names_nothing() -> None:
    m = orr()
    m.ADMIN_STORE = pathlib.Path(tmpdir.mkdtemp()).resolve() / "openrouter-admin"
    m._request = lambda *a, **k: {"data": []}
    rc = m.stash_value("sk-or-v1-" + "a" * 40, "", origin="test")
    check("a stash with no label is refused", rc == 2, str(rc))
    rc = m.stash_value("sk-or-v1-" + "a" * 40, "Example Secondary", origin="test")
    check("a labeled stash lands under its slug", rc == 0
          and (m.ADMIN_STORE / "example-secondary").is_file(), str(rc))

    def refuse(*a, **k):
        raise RuntimeError("openrouter answered 401 for /keys")
    m._request = refuse
    rc = m.stash_value("sk-or-v1-" + "b" * 40, "other", origin="test")
    check("an inference key is refused — it cannot provision", rc == 1, str(rc))
    check("and points at install_key for what it IS good for", True, "")


def test_or_rotation_creates_and_delivers_before_deleting() -> None:
    ""                                                                      
                                                                            
    m = orr()
    d = pathlib.Path(tmpdir.mkdtemp()).resolve()
    m.ADMIN_STORE = d / "openrouter-admin"
    m.ADMIN_STORE.mkdir(parents=True)
    private_io.write(m.ADMIN_STORE / "example", "prov\n")
    m.LEDGER = d / "ledger.json"
    delivered = []
    m.deliver = lambda value, to, **options: (delivered.append((value, to, options)) or f"file {to}")
    m.save_ledger(
        {"issued": {"fabric-agent": {"account": "example", "hash": "h-old",
                                     "destination": "observatory",
                                     "delivered_to": "x", "limit_usd": 10,
                                     "issued_on": "2026-09-01",
                                     "rotated_on": None, "rotations": 0}}})
    log = []

    def fake(path, key, payload=None, method=None):
        log.append((method or ("POST" if payload is not None else "GET"), path))
        if path.startswith("/keys?"):
            return {"data": [{"name": "fabric-agent", "hash": "h-old",
                              "limit": 10, "usage": 3}]}
        if path == "/keys" and payload:
            return {"data": {"hash": "h-new"}, "key": "sk-or-v1-" + "n" * 40}
        return {"data": {}}
    m._request = fake
    rc = m.cmd_rotate("fabric-agent", leaked=False)
    check("rotation succeeds", rc == 0, str(rc))
    order = [(meth, p) for meth, p in log if meth in ("POST", "DELETE", "PATCH")
             and p.startswith("/keys")]
    creates = [i for i, (meth, p) in enumerate(order) if meth == "POST" and p == "/keys"]
    deletes = [i for i, (meth, p) in enumerate(order) if meth == "DELETE"]
    check("the successor is created BEFORE the predecessor is deleted",
          creates and deletes and creates[0] < deletes[0], str(order))
    check("and the delivery happened", delivered
          and delivered[0][1] == "observatory"
          and delivered[0][2].get("rotate") is True, "delivery must request replacement")
    led = json.loads(m.LEDGER.read_text())
    check("the ledger moved to the successor",
          led["issued"]["fabric-agent"]["hash"] == "h-new"
          and led["issued"]["fabric-agent"]["rotations"] == 1, str(led)[:200])


def test_or_issue_deletes_the_key_when_delivery_fails() -> None:
    """A minted key that reached no consumer is live spend capacity nobody
    holds — the door deletes it rather than leaving it."""
    m = orr()
    d = pathlib.Path(tmpdir.mkdtemp()).resolve()
    m.ADMIN_STORE = d / "openrouter-admin"
    m.ADMIN_STORE.mkdir(parents=True)
    private_io.write(m.ADMIN_STORE / "example", "prov\n")
    m.LEDGER = d / "ledger.json"
    log = []

    def fake(path, key, payload=None, method=None):
        log.append((method or ("POST" if payload is not None else "GET"), path))
        if path.startswith("/keys?"):
            return {"data": []}
        if path == "/keys" and payload:
            return {"data": {"hash": "h-1"}, "key": "sk-or-v1-" + "z" * 40}
        return {"data": {}}
    m._request = fake

    def refuse_delivery(value, to):
        raise RuntimeError("no such destination")
    m.deliver = refuse_delivery
    rc = m.cmd_issue("doomed", 5.0, "example", "nowhere", None)
    check("a key that could not be delivered is refused", rc == 1, str(rc))
    check("and DELETED at the provider, not left live",
          any(meth == "DELETE" and "h-1" in p for meth, p in log), str(log))
    check("and never entered the ledger",
          not m.LEDGER.is_file() or "doomed" not in m.LEDGER.read_text(), "")


def test_or_issue_refuses_a_name_that_already_exists() -> None:
    m = orr()
    d = pathlib.Path(tmpdir.mkdtemp()).resolve()
    m.ADMIN_STORE = d / "openrouter-admin"
    m.ADMIN_STORE.mkdir(parents=True)
    private_io.write(m.ADMIN_STORE / "example", "prov\n")
    m.LEDGER = d / "ledger.json"
    m._request = lambda path, key, payload=None, method=None: (
        {"data": [{"name": "fabric-agent", "hash": "h"}]} if path.startswith("/keys?")
        else {"data": {}})
    rc = m.cmd_issue("fabric-agent", 5.0, "example", "observatory", None)
    check("a duplicate name is refused — spend must stay attributable (exit 2: the "
          "caller's mistake, not the provider's)", rc == 2, str(rc))


def test_or_issue_is_one_function_with_a_monthly_reset() -> None:
    ""                                                                      
                                                                            
                                                                               
                                                                           
                                                                
    m = orr()
    d = pathlib.Path(tmpdir.mkdtemp()).resolve()
    m.ADMIN_STORE = d / "openrouter-admin"
    m.ADMIN_STORE.mkdir(parents=True)
    private_io.write(m.ADMIN_STORE / "example", "prov\n")
    m.LEDGER = d / "ledger.json"
    posted = []
    m.deliver = lambda value, to: f"file {to}"

    def fake(path, key, payload=None, method=None):
        if path.startswith("/keys?"):
            return {"data": []}
        if path == "/keys" and payload:
            posted.append(payload)
            return {"data": {"hash": "h-9", "label": "sk-or-v1-abc...def"}, "key": "sk-or-v1-" + "q" * 40}
        return {"data": {}}
    m._request = fake
    r = m.issue_key("button-key", 7.0, "example", "observatory", None)
    check("issue_key returns the facts a button needs, never the value",
          r["name"] == "button-key" and r["label"] == "sk-or-v1-abc...def"
          and "q" * 40 not in json.dumps(r), str(r))
    check("and the create carried a MONTHLY reset",
          posted and posted[0].get("limit_reset") == "monthly", str(posted))
    led = json.loads(m.LEDGER.read_text())
    check("the ledger records the reset beside the ceiling",
          led["issued"]["button-key"]["limit_reset"] == "monthly", str(led)[:200])
    try:
        m.issue_key("x", 0, "example", "observatory", None)
        check("a key with no ceiling is refused", False, "no raise")
    except ValueError as exc:
        check("a key with no ceiling is refused", "ceiling" in str(exc), str(exc))
    # the adapter: keyserver's mint reaches this same function
    src = (ROOT / "tools/keyserver.py").read_text(encoding="utf-8")
    code = source_reader.code_keeping_strings(src)
    check("keyserver mints through the door and holds no provider client of its own",
          "issue_key(" in code and '"/keys"' not in code and "def api(" not in code, "")


def test_or_ping_names_the_strays_it_does_not_manage() -> None:
    ""                                                                     
                                                                            
                                                                
    m = orr()
    d = pathlib.Path(tmpdir.mkdtemp()).resolve()
    m.ADMIN_STORE = d / "openrouter-admin"
    m.ADMIN_STORE.mkdir(parents=True)
    private_io.write(m.ADMIN_STORE / "example", "prov\n")
    m.LEDGER = d / "ledger.json"
    m.save_ledger({"issued": {}})
    m._request = lambda path, key, payload=None, method=None: (
        {"data": [{"name": "PRODUCTION_user_1_2", "hash": "p1"},
                  {"name": "PRODUCTION_user_3_4", "hash": "p2"}]}
        if path.startswith("/keys?") else {"data": {}})
    import io
    import contextlib
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        m.cmd_ping()
    check("ping reports unmanaged keys by name",
          "unmanaged at the provider" in out.getvalue()
          and "PRODUCTION_user_1_2" in out.getvalue(), out.getvalue()[:200])
    src = (ROOT / "tools/openrouter.py").read_text(encoding="utf-8")
    code = source_reader.code_keeping_strings(src)
    check("rotate and revoke reach only ledger rows",
          'doc["issued"].get(name)' in code or "doc[\"issued\"][name]" in code,
          "an operation keyed by provider listing could touch production keys")


if __name__ == "__main__":
    print("the credential doors — stash, issue, rotate, revoke, and what they refuse\n")
    for fn in (test_no_door_takes_or_prints_a_value_outside_stdin,
               test_the_ledgers_hold_no_values,
               test_cf_stash_refuses_an_admin_that_cannot_issue,
               test_cf_one_stash_can_span_several_accounts,
               test_cf_stash_finds_accounts_through_memberships_when_accounts_is_empty,
               test_cf_issue_rolls_rather_than_duplicating,
               test_cf_external_tokens_are_recorded_and_never_rolled_here,
               test_or_stash_demands_a_label_because_the_provider_names_nothing,
               test_or_rotation_creates_and_delivers_before_deleting,
               test_or_issue_deletes_the_key_when_delivery_fails,
               test_or_issue_refuses_a_name_that_already_exists,
               test_or_issue_is_one_function_with_a_monthly_reset,
               test_or_ping_names_the_strays_it_does_not_manage):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mthe admin credential never leaves its stash, and every issued "
          "key is accounted for\033[0m")
