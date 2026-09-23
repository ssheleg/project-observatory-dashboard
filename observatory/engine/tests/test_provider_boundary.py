#!/usr/bin/env python3
"""The provider boundary: three literals that a config also declared, and a chain that shrank in silence.

`agent/providers.py` is the only file that names a model, a price or a spend
ceiling. Most of it measures well — this suite records what was measured and
found SOUND as carefully as what was wrong, because the next reader should not
have to re-derive it:

* **The health mark expires.** `unhealthy()` re-probes after
  `health.probe_after_minutes`, so a model marked bad by one outage does not
  leave the chain for ever — "a health check that only runs on failure never
  recovers", as its own docstring says. And it IS applied: `complete()` consults
  it per model and marks on every failure shape (HTTP, no choices, unparseable
  structured output).
* **The catalogue has a real TTL** — 24 hours by default, and its provenance
  string comes back in three shapes: `cached Nm ago`, `STALE (…)`, `fetched
  now`. It never raises while a cache exists, which is the right trade for a
  scheduled run.
* **The confidence cap and the guardrail message are honest.** The refusal names
  the KEY, the provider, this project's own journal figure and says the
  remainder belongs to another consumer. The synthetic fixture distinguishes
  the shared key total from this project's journal.

**What was wrong is small and exactly the class this repository keeps closing.**
`charge()` pruned the spend journal with three literals — `[-500:]`, `[:-60]`,
`[:-12]` — while `store/retention.json`, the file that holds every other horizon
in the project, declared two of them (`wallet_events`, `wallet_days`) and was
read by NOTHING. The numbers agreed by coincidence: editing the config did
nothing, and editing the code made the config a lie. The third, twelve months,
was declared nowhere at all. A horizon lives in the config and the code reads it.

**A correction to my own first reading**, recorded because the class repeats: I
reported `wallet_days` as "enforced nowhere". It was enforced — by the literal
that happened to equal it. The defect was the duplication, not an absence.

**And a chain that lost a model said nothing.** `resolve_chain` skipped a
configured id missing from the catalogue with `continue  # not fatal`, which is
the right POLICY — the point of a chain is surviving one model leaving — carried
out invisibly: a three-model chain could become one and the only visible sign
would be the bill. The loss now travels with the answer, the `chain` CLI prints
it before the survivors, and `agent/observe.py` puts it in the run report where
a reader looks.
"""
from __future__ import annotations
import json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup, PROJECT_ID as SYNTHETIC_PROJECT
portable_setup()

sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "agent"))
import tmp as tmpdir                                                # noqa: E402

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def providers():
    import importlib
    import providers as pr
    return importlib.reload(pr)


# ─────────── the horizons live in one file ─────────────────────────────

def test_the_wallet_horizons_come_from_the_config() -> None:
    pr = providers()
    cfg = json.loads((__import__("paths").config_file("retention.json")).read_text(encoding="utf-8"))
    for key in ("wallet_events", "wallet_days", "wallet_months"):
        check(f"`{key}` is declared", isinstance(cfg.get(key), int), str(cfg.get(key)))
    check("all retention horizons are positive",
          all(cfg.get(k, 0) > 0 for k in ("wallet_events", "wallet_days", "wallet_months")),
          (cfg.get("wallet_note") or "")[:120])
    got = pr.retention_config()
    check("and `charge` reads that file",
          all(got.get(k) == cfg.get(k) for k in
              ("wallet_events", "wallet_days", "wallet_months")),
          str({k: got.get(k) for k in ("wallet_events", "wallet_days", "wallet_months")}))
    src = (ROOT / "agent/providers.py").read_text(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "tools"))
    import check_paths
    code = check_paths.prose_removed(src)
    for literal in ("[-500:]", "[:-60]", "[:-12]"):
        check(f"the literal {literal} is gone from the code", literal not in code,
              "a number in two places is a number that disagrees with itself")


def test_changing_the_config_changes_the_pruning() -> None:
    """The point of reading a config is that editing it does something. Driven
    against a redirected wallet, so existing user journals are never read or changed."""
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-wallet-"))
    (d / "store").mkdir()
    # `paths.STORE` is deliberately not overridable, so the config is edited in
    # a COPY of the repository's own store directory and the module is pointed
    # at it — the same reason the retention suite copies rather than redirects.
    cfg = json.loads((__import__("paths").config_file("retention.json")).read_text(encoding="utf-8"))
    cfg["wallet_events"] = 3
    (d / "store/retention.json").write_text(json.dumps(cfg), encoding="utf-8")
    pr = providers()
    import paths
    real_store, paths.CONFIG = paths.CONFIG, d / "store"
    pr.WALLET = d / "store/wallet.json"
    try:
        got = pr.retention_config()
        check("the copy is read", got.get("wallet_events") == 3, str(got.get("wallet_events")))
        for i in range(6):
            pr.charge(f"vendor/m{i}", 0.0, 1, 1, provider="test")
        w = json.loads((d / "store/wallet.json").read_text(encoding="utf-8"))
        check("the journal is pruned to the CONFIGURED length",
              len(w["events"]) == 3, str(len(w["events"])))
        check("keeping the newest", w["events"][-1]["model"] == "vendor/m5",
              str([e["model"] for e in w["events"]]))
    finally:
        paths.CONFIG = real_store


# ─────────── a chain that loses a model says so ────────────────────────

def test_a_retired_model_is_named_rather_than_skipped() -> None:
    pr = providers()
    real = pr.config
    try:
        pr.config = lambda: {**real(),
                             "chain": [{"id": "vendor/retired-yesterday",
                                        "why": "planted by the suite"}]
                                      + list(real()["chain"])}
        chain, level, prov = pr.resolve_chain()
        check("the chain still resolves", len(chain) == len(real()["chain"]),
              f"{len(chain)} of {len(real()['chain'])}")
        check("and the missing id is named",
              chain[0].get("chain_retired") == ["vendor/retired-yesterday"],
              str(chain[0].get("chain_retired")))
    finally:
        pr.config = real
    chain, _, _ = pr.resolve_chain()
    check("a healthy chain names nothing", not chain[0].get("chain_retired"),
          str(chain[0].get("chain_retired")))


def test_the_cli_prints_the_loss_before_the_survivors() -> None:
    src = (ROOT / "agent/providers.py").read_text(encoding="utf-8")
    check("the CLI reads the field", 'get("chain_retired")' in src)
    check("and says what to check",
          "agent/models.json against the provider" in src,
          "a warning with no remedy is a warning nobody acts on")
    p = subprocess.run([PY, "agent/providers.py", "chain"], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    check("the live chain prints cleanly", p.returncode == 0, p.stderr[-200:])
    check("and reports no loss today", "were skipped" not in p.stdout,
          p.stdout[:200])


def test_the_run_report_carries_the_loss() -> None:
    f = __import__("paths").SCRATCH / "agent.json"
    settings_path = __import__("paths").config_file("settings.json")
    settings = json.loads(settings_path.read_text())
    settings.setdefault("features", {})["agent"] = True
    settings_path.write_text(json.dumps(settings))
    # An empty synthetic queue exercises the real no-spend report writer.
    result = subprocess.run([PY, "agent/observe.py"], cwd=ROOT,
                            env=dict(os.environ), capture_output=True, text=True,
                            timeout=30)
    check("the empty queue emits a report without calling a provider",
          result.returncode == 0 and f.is_file(), result.stderr[-200:])
    if not f.is_file():
        return
    doc = json.loads(f.read_text(encoding="utf-8"))
    check("`chain_retired` is in the report", "chain_retired" in doc,
          str(sorted(doc)))
    check("and is a list, empty when nothing was lost",
          isinstance(doc.get("chain_retired"), list),
          str(doc.get("chain_retired")))


# ─────────── measured and found sound ──────────────────────────────────

def test_the_health_mark_expires() -> None:
    """Recorded as a check so nobody has to investigate it again: a model marked bad by
    one outage must not leave the chain for ever."""
    pr = providers()
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-health-"))
    real = pr.HEALTH
    pr.HEALTH = d / "provider-health.json"
    try:
        pr.mark_unhealthy("vendor/m", "a 503 from the edge")
        check("a fresh mark makes it unusable",
              pr.unhealthy("vendor/m") == "a 503 from the edge",
              str(pr.unhealthy("vendor/m")))
        # Age the mark past the probe window rather than waiting for it.
        h = json.loads(pr.HEALTH.read_text(encoding="utf-8"))
        h["vendor/m"]["since"] = "2020-01-01T00:00:00Z"
        pr.HEALTH.write_text(json.dumps(h), encoding="utf-8")
        check("an aged mark is due for a probe and reads as usable",
              pr.unhealthy("vendor/m") is None, str(pr.unhealthy("vendor/m")))
        pr.mark_healthy("vendor/m")
        check("and a success clears it", pr.unhealthy("vendor/m") is None)
    finally:
        pr.HEALTH = real
    src = (ROOT / "agent/providers.py").read_text(encoding="utf-8")
    check("the mark is consulted per model in `complete`",
          "why_not = unhealthy(model[\"id\"])" in src,
          "a health file nothing reads is a file nothing reads")
    check("and set on every failure shape",
          src.count("mark_unhealthy(model[") >= 4,
          f"{src.count('mark_unhealthy(model[')} call sites")


def test_the_catalogue_states_its_own_age() -> None:
    pr = providers()
    models, prov = pr.catalogue()
    check("the catalogue resolves", set(models) == {"vendor/synthetic"}, str(len(models)))
    check("and its provenance says where it came from",
          any(w in prov for w in ("cached", "fetched", "STALE")), prov)
    src = (ROOT / "agent/providers.py").read_text(encoding="utf-8")
    check("a TTL bounds the cache", "catalogue_ttl_hours" in src)
    check("and a stale answer beats no answer, with the age stated",
          'f"STALE ({exc.__class__.__name__}); cached {age}"' in src,
          "a run that cannot start is worse than a priced list an hour old")


def test_the_guardrail_names_whose_spend_stopped_it() -> None:
    """Shared-key exhaustion must distinguish the project journal from other spend."""
    pr = providers()
    from unittest.mock import patch
    with patch.object(pr, "provider_usage", return_value={"limit": 10, "limit_remaining": 0, "limit_reset": "monthly",
                                                      "total": 10, "daily": 3, "monthly": 10}):
        why = pr.check_budget()
    check("a planted shared-key spend trips the guardrail", why is not None)
    if why is None: return
    check("the refusal names the key rather than the project",
          "on this KEY" in why, why[:160])
    check("and quotes this project's own journal figure",
          "this project's own journal holds" in why, why[:200])
    check("saying the remainder is somebody else",
          "another consumer of the same key" in why, why[-120:])


if __name__ == "__main__":
    print("the provider boundary — one file for the horizons, and a chain that speaks\n")
    for fn in (test_the_wallet_horizons_come_from_the_config,
               test_changing_the_config_changes_the_pruning,
               test_a_retired_model_is_named_rather_than_skipped,
               test_the_cli_prints_the_loss_before_the_survivors,
               test_the_run_report_carries_the_loss,
               test_the_health_mark_expires,
               test_the_catalogue_states_its_own_age,
               test_the_guardrail_names_whose_spend_stopped_it):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mthe horizons live in one file, and a chain that loses a model says which\033[0m")
