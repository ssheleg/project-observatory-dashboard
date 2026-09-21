#!/usr/bin/env python3
""                                                                              

                                                                            
                                                                               
                                                                               
                                                                               
                                             
   
from __future__ import annotations
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import tmp as tmpdir                                                           

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def vault(store: pathlib.Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run([PY, "tools/vault.py", *args], input=stdin, cwd=ROOT,
                          env={**os.environ, "OBSERVATORY_VAULT_DIR": str(store)},
                          capture_output=True, text=True, timeout=120)


def fresh() -> pathlib.Path:
    return pathlib.Path(tmpdir.mkdtemp(prefix="observatory-vault-")).resolve() / "projects"


def test_a_value_travels_only_on_stdin() -> None:
    s = fresh()
    p = vault(s, "put", "demo", "local", "API_TOKEN")                                
    check("empty stdin is refused", p.returncode != 0 and "empty" in p.stderr,
          p.stderr[:120])
    src = (ROOT / "tools/vault.py").read_text(encoding="utf-8")
    check("no subcommand takes a value argument",
          "add_argument(\"value\"" not in src and "--value" not in src,
          "a value in argv is a value in `ps` and the shell history")


def test_put_list_rotate_and_the_archive() -> None:
    s = fresh()
    p = vault(s, "put", "demo", "prod", "DB_URL", stdin="postgres://u:p@h/db")
    check("put reports length without the value or its tail", p.returncode == 0
          and "length" in p.stdout and "postgres" not in p.stdout
          and "h/db" not in p.stdout, p.stdout[:150])
    slot = s / "demo/prod/DB_URL"
    check("the file is mode 600", oct(slot.stat().st_mode & 0o777) == "0o600",
          oct(slot.stat().st_mode & 0o777))
                                                                              
                                                                               
                                                                           
    dirs = {str(d.relative_to(s.parent)): oct(d.stat().st_mode & 0o777)
            for d in (s, s / "demo", s / "demo/prod")}
    check("every directory from the store down is mode 700",
          set(dirs.values()) == {"0o700"}, str(dirs))
    p = vault(s, "put", "demo", "prod", "DB_URL", stdin="other")
    check("a second put is refused toward rotate", p.returncode != 0
          and "rotate" in p.stderr, p.stderr[:120])
    p = vault(s, "list")
    check("list never prints a value", "postgres" not in p.stdout, p.stdout[:200])
    p = vault(s, "rotate", "demo", "prod", "DB_URL", stdin="postgres://u:NEW@h/db")
    check("rotate archives the old value", p.returncode == 0 and "archived" in p.stdout,
          p.stdout[:150])
    archives = list((s / "demo/prod").glob("DB_URL.retired-*"))
    check("the archive exists at mode 600", len(archives) == 1
          and oct(archives[0].stat().st_mode & 0o777) == "0o600", str(archives))
    check("and rotate warns the retired value still works until revoked",
          "until revoked" in p.stdout, p.stdout)
    p = vault(s, "rotate", "demo", "prod", "DB_URL", stdin="postgres://u:NEW@h/db")
    check("rotating to the same value is refused", p.returncode != 0
          and "not a rotation" in p.stderr, p.stderr[:120])


def test_the_vocabulary_is_enforced() -> None:
    s = fresh()
    p = vault(s, "put", "demo", "production", "X", stdin="v")
    check("an env outside local/stage/prod is refused",
          p.returncode != 0 and "local, stage, prod" in p.stderr, p.stderr[:120])
    p = vault(s, "put", "demo", "local", "api-token", stdin="v")
    check("a name that is not UPPER_SNAKE_CASE is refused",
          p.returncode != 0 and "UPPER_SNAKE_CASE" in p.stderr, p.stderr[:120])


def test_inject_refuses_a_committable_env_and_writes_an_ignored_one() -> None:
    s = fresh()
    vault(s, "put", "demo", "local", "API_TOKEN", stdin="sk-test-1234abcd")
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-vault-inj-")).resolve()
    subprocess.run(["git", "init", "-q"], cwd=d, capture_output=True, timeout=60)
    p = vault(s, "inject", "demo", "local", str(d))
    check("inject refuses while .env is committable", p.returncode != 0
          and "NOT gitignored" in p.stderr, p.stderr[:160])
    check("and wrote nothing", not (d / ".env").exists())
    (d / ".gitignore").write_text(".env\n", encoding="utf-8")
    p = vault(s, "inject", "demo", "local", str(d))
    check("inject writes once .env is ignored", p.returncode == 0, p.stderr[:120])
    body = (d / ".env").read_text(encoding="utf-8")
    check("the .env carries the value for the NAME the agent will use",
          "API_TOKEN=sk-test-1234abcd" in body, body[:150])
    check("at mode 600", oct((d / ".env").stat().st_mode & 0o777) == "0o600")
    check("and the report speaks names, not values",
          "API_TOKEN" in p.stdout and "sk-test-1234abcd" not in p.stdout, p.stdout[:200])
    (d / ".env").write_text("HANDMADE=1\n" + body, encoding="utf-8")
    p = vault(s, "inject", "demo", "local", str(d))
    check("re-inject keeps lines it does not own",
          "HANDMADE=1" in (d / ".env").read_text(encoding="utf-8"),
          "an inject that truncates the file destroys hand-kept settings")


def test_a_leak_needs_a_place_and_stays_open_until_rotation() -> None:
    s = fresh()
    vault(s, "put", "demo", "prod", "API_TOKEN", stdin="sk-live-zzzz")
    p = vault(s, "leak", "demo", "prod", "API_TOKEN", "--where", "log")
    check("a leak record without a real place is refused", p.returncode != 0
          and "names no place" in p.stderr.replace("\n", " ") or "cannot be judged" in p.stderr,
          p.stderr[:160])
    p = vault(s, "leak", "demo", "prod", "API_TOKEN",
              "--where", "committed in demo repo at abc123, file config.py")
    check("a leak with a place is recorded", p.returncode == 0 and "recorded" in p.stdout,
          p.stdout[:150])
    p = vault(s, "leaks", "--check")
    check("`leaks --check` exits non-zero while one is open", p.returncode == 1
          and "OPEN" in p.stdout, p.stdout[:200])
    reg = json.loads((s / "leaks.jsonl").read_text(encoding="utf-8").splitlines()[0])
    check("the register holds names and places, never values",
          "sk-live-zzzz" not in json.dumps(reg), str(reg)[:150])
    vault(s, "rotate", "demo", "prod", "API_TOKEN", stdin="sk-live-NEW")
    p = vault(s, "leaks", "--check")
    check("rotation settles the leak", p.returncode == 0 and "0 still unrotated" in p.stdout,
          p.stdout[:200])
    lines = (s / "leaks.jsonl").read_text(encoding="utf-8").splitlines()
    check("the register is append-only — the leak row is still there",
          len(lines) == 2 and '"settled"' in lines[1], str(lines))


def test_a_leak_of_a_key_the_store_never_held_is_still_recorded() -> None:
    s = fresh()
    p = vault(s, "leak", "demo", "prod", "UNKNOWN_KEY",
              "--where", "found in an old CI log, job 4412")
    check("recorded with the note", p.returncode == 0 and "recorded anyway" in p.stdout,
          p.stdout[:200])


def test_a_leak_rotated_at_the_provider_is_settled_by_hand_with_evidence() -> None:
    ""                                                                      
    store = fresh()
    vault(store, "leak", "example-app", "prod", "DATABASE_URL", "--where", "a traceback in a transcript")
    p = vault(store, "rotate", "example-app", "prod", "DATABASE_URL", stdin="new-value")
    check("rotate on a slotless name points at settle, not at put alone",
          p.returncode != 0 and "settle" in (p.stdout + p.stderr), (p.stdout + p.stderr)[-200:])
    p = vault(store, "settle", "example-app", "prod", "DATABASE_URL", "--how", "short")
    check("a settlement with no real evidence is refused", p.returncode != 0
          and "evidence" in (p.stdout + p.stderr), (p.stdout + p.stderr)[-160:])
    p = vault(store, "settle", "example-app", "prod", "DATABASE_URL",
              "--how", "heroku pg:credentials:rotate on example-app; releases v1080/v1081 2026-09-14")
    check("with evidence it settles", p.returncode == 0 and "settled 1 open leak" in p.stdout, p.stdout[-200:] + p.stderr[-100:])
    p = vault(store, "leaks")
    check("the register shows it settled, not open", "OPEN" not in p.stdout and "0 still unrotated" in p.stdout, p.stdout[-200:])
    p = vault(store, "settle", "example-app", "prod", "DATABASE_URL", "--how", "the same evidence again, long enough")
    check("settling twice says there is nothing open", p.returncode != 0 and "no open leak" in (p.stdout + p.stderr))


def test_every_movement_lands_in_the_journal_and_hand_moves_are_recordable() -> None:
    ""                                                                     
                                                                 
    store = fresh()
    vault(store, "put", "alpha", "prod", "API_TOKEN", stdin="value-one")
    vault(store, "rotate", "alpha", "prod", "API_TOKEN", stdin="value-two")
    vault(store, "leak", "alpha", "prod", "API_TOKEN", "--where", "a log line in CI")
    vault(store, "settle", "alpha", "prod", "API_TOKEN", "--how", "rotated above, archive kept, 2026-09-14")
    p = vault(store, "moved", "beta", "prod", "DB_PASSWORD", "--how", "x")
    check("a hand move with no evidence is refused", p.returncode != 0 and "evidence" in (p.stdout + p.stderr))
    p = vault(store, "moved", "beta", "prod", "DB_PASSWORD", "--at", "digitalocean",
              "--how", "rotated in the DO app dashboard, deployment 2026-09-14T01:00Z")
    check("a hand move with evidence is recorded with its provider",
          p.returncode == 0 and "digitalocean" in p.stdout, p.stdout[-160:])
    rows = [json.loads(l) for l in (store / "movements.jsonl").read_text().splitlines() if l.strip()]
    check("put, rotate, leak, settle and moved are all in the journal",
          [r["event"] for r in rows] == ["put", "rotate", "leak", "settle", "moved"], str([r["event"] for r in rows]))
    check("and no value is", "value-one" not in (store / "movements.jsonl").read_text()
          and "value-two" not in (store / "movements.jsonl").read_text())
    p = vault(store, "movements", "beta")
    check("movements lists by project, names and places only",
          "beta/prod/DB_PASSWORD" in p.stdout and "1 movement(s)" in p.stdout, p.stdout[-200:])


def test_the_board_carries_an_open_leak_and_drops_a_settled_one() -> None:
    ""                                                                  
    import importlib.util
    s = fresh()
    vault(s, "put", "demo", "prod", "API_TOKEN", stdin="v1")
    vault(s, "leak", "demo", "prod", "API_TOKEN", "--where", "planted for the board test")
    os.environ["OBSERVATORY_VAULT_DIR"] = str(s)
    try:
        spec = importlib.util.spec_from_file_location("bf_v", ROOT / "tools/build_findings.py")
        bf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bf)
        got = [f for f in bf.collect() if f["type"] == "secret.leaked_unrotated"]
        check("an open leak raises secret.leaked_unrotated at critical",
              len(got) == 1 and got[0]["severity"] == "critical", str(got)[:200])
        check("the finding names the slot and the place, never the value",
              got and "demo/prod/API_TOKEN" in got[0]["title"]
              and "planted for the board test" in got[0]["detail"]
              and "v1" not in json.dumps(got), str(got)[:200])
        vault(s, "rotate", "demo", "prod", "API_TOKEN", stdin="v2")
        spec = importlib.util.spec_from_file_location("bf_v2", ROOT / "tools/build_findings.py")
        bf2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bf2)
        got = [f for f in bf2.collect() if f["type"] == "secret.leaked_unrotated"]
        check("a settled leak raises nothing", not got, str(got)[:150])
    finally:
        os.environ.pop("OBSERVATORY_VAULT_DIR", None)


def test_an_unreadable_register_is_reported_not_read_as_empty() -> None:
    ""                                                                           

                                                                              
                                                                        
                                                                
       
    import importlib.util
    s = fresh()
    s.mkdir(parents=True, exist_ok=True)
    (s / "leaks.jsonl").write_text("{not json at all\n", encoding="utf-8")
    os.environ["OBSERVATORY_VAULT_DIR"] = str(s)
    try:
        spec = importlib.util.spec_from_file_location("bf_v3", ROOT / "tools/build_findings.py")
        bf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bf)
        got = [f for f in bf.collect() if f["type"] == "secret.register_unreadable"]
        check("a register that does not parse raises its own row", len(got) == 1,
              str([f["type"] for f in bf.collect() if f["type"].startswith("secret")]))
        check("and no leak row is invented from it",
              not [f for f in bf.collect() if f["type"] == "secret.leaked_unrotated"],
              "an unreadable file must not produce findings about its contents")
    finally:
        os.environ.pop("OBSERVATORY_VAULT_DIR", None)


def test_an_old_retired_archive_is_reported() -> None:
    ""                                                                         

                                                                            
                                                                            
       
    import subprocess as _sp
    s = fresh()
    vault(s, "put", "demo", "prod", "API_TOKEN", stdin="v1")
    old_dir = s / "demo/prod"
    (old_dir / "API_TOKEN.retired-2026-01-01T000000Z").write_text("dead-value",
                                                                  encoding="utf-8")
    code = ("import importlib.util, json, pathlib, sys\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            f"spec = importlib.util.spec_from_file_location('bf', {str(ROOT / 'tools/build_findings.py')!r})\n"
            "bf = importlib.util.module_from_spec(spec); spec.loader.exec_module(bf)\n"
            "print(json.dumps([f for f in bf.collect()"
            " if f['type'] == 'secret.retired_unrevoked']))\n")
    p = _sp.run([PY, "-c", code], cwd=ROOT,
                env={**os.environ, "OBSERVATORY_VAULT_DIR": str(s)},
                capture_output=True, text=True, timeout=900)
    got = json.loads(p.stdout or "[]")
    check("a month-old retired archive raises secret.retired_unrevoked",
          len(got) == 1, (p.stdout + p.stderr)[-200:])
    check("the row names the archive and never its value",
          got and "API_TOKEN.retired-2026-01-01" in got[0]["detail"]
          and "dead-value" not in json.dumps(got), str(got)[:200])


def test_the_mandatory_rules_ship_as_a_skill() -> None:
    ""                                                                         
    skill = ROOT / "skill/plugins/observatory-log/skills/handling-secrets/SKILL.md"
    check("the skill exists in the shipped plugin", skill.is_file(), str(skill))
    body = skill.read_text(encoding="utf-8")
    for phrase, why in (("stdin", "how a value travels"),
                        ("names", "the vocabulary after inject"),
                        ("--where", "a sighting is recorded with its place"),
                        ("rotate", "replacement and revocation"),
                        ("vault.py leaks", "the register that keeps exposures visible"),
                        ("Never ask the user to paste a credential", "credentials stay out of chat"),
                        ("not a sandbox", "the output filter's security boundary")):
        check(f"the skill states {why}", phrase.casefold() in body.casefold(),
              f"{phrase!r} is missing")
    check("provider operations require explicitly configured integration",
          "explicitly configured integration" in body
          and "cloudflare.py" in body and "openrouter.py" in body)



if __name__ == "__main__":
    print("the vault — one door in, one door out, leaks on the record\n")
    for fn in (test_a_value_travels_only_on_stdin,
               test_put_list_rotate_and_the_archive,
               test_the_vocabulary_is_enforced,
               test_inject_refuses_a_committable_env_and_writes_an_ignored_one,
               test_a_leak_needs_a_place_and_stays_open_until_rotation,
               test_a_leak_of_a_key_the_store_never_held_is_still_recorded,
               test_the_board_carries_an_open_leak_and_drops_a_settled_one,
               test_an_unreadable_register_is_reported_not_read_as_empty,
               test_an_old_retired_archive_is_reported,
               test_the_mandatory_rules_ship_as_a_skill,
               test_a_leak_rotated_at_the_provider_is_settled_by_hand_with_evidence,
               test_every_movement_lands_in_the_journal_and_hand_moves_are_recordable):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mthe vault holds, refuses, records and settles\033[0m")
