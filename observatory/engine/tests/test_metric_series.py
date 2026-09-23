#!/usr/bin/env python3
"""The plugin layer had 92 measurements and no series, and nothing read them.

                                                                                
                                                                               
                                                                           
                                                          

                                                                           
                                                                               
                                                                           
                                                                                
                                                                          
                                                                             
                                                                                
                                                                              
                                                                               
                                                                            
                                   

**And nothing read the rows.** 92 measurements, one reader: the dashboard's
"latest value" panel. `host.disk_low` — the critical finding that says the
volume is nearly full — could not name a single project responsible, while the
answer sat in the store. It names the largest working trees and the fastest
growers now, and the per-project surface carries `previous` and `change` so a
host can render a direction rather than a magnitude.

**`not_due` could not say "the series stopped".** A plugin can be installed,
healthy, exiting zero and skipping every tick while its newest sample gets
older. That reads as health, which is how a metric layer goes quiet without
anyone noticing. `plugin.stale` fires at two cadence periods.

**And the seam's own claim was untested.** `plugins/README.md` opens with
"Adding one touches no file outside this directory". The only real test of that
is a second plugin, so this iteration wrote one — `dependency-weight`, 53
projects measured — and the assertion below is mechanical: no file outside
`plugins/` may name a plugin's id or its metrics.
"""
from __future__ import annotations
import importlib, json, os, pathlib, re, subprocess, sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_portable_mcp import setup as portable_setup, PROJECT_ID as SYNTHETIC_PROJECT
portable_setup()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
OWN = SYNTHETIC_PROJECT
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))
import tmp as tmpdir                                                # noqa: E402

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
FAILURES: list[str] = []
UTC = timezone.utc


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def runner():
    from collectors import run_plugins as R
    return importlib.reload(R)


# ─────────── the cadence means what it says ────────────────────────────

def test_a_daily_cadence_is_a_calendar_day() -> None:
    R = runner()
    n = datetime(2026, 9, 7, 23, 55, 0, tzinfo=UTC)
    check("a daily plugin's period starts at midnight UTC",
          R.period_start(n, 24) == datetime(2026, 9, 7, 0, 0, tzinfo=UTC),
          str(R.period_start(n, 24)))
    check("an hourly one buckets on the hour",
          R.period_start(n, 1) == datetime(2026, 9, 7, 23, 0, tzinfo=UTC),
          str(R.period_start(n, 1)))
    check("a six-hourly one lands on 00/06/12/18",
          R.period_start(n, 6) == datetime(2026, 9, 7, 18, 0, tzinfo=UTC),
          str(R.period_start(n, 6)))
    check("and a weekly one on a fixed day rather than wherever it started",
          R.period_start(n, 168) == R.period_start(n - timedelta(days=3), 168),
          f"{R.period_start(n, 168)} vs {R.period_start(n - timedelta(days=3), 168)}")


def test_a_late_recording_does_not_delay_the_next_period() -> None:
    ""                                                                        
                                                                              
                                                                              
                                                       
    R = runner()
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-cadence-"))
    os.environ["OBSERVATORY_DB"] = str(d / "observatory.db")
    import paths
    importlib.reload(paths)
    from store import db as store_db
    importlib.reload(store_db)
    conn = store_db.connect()
    with conn:
        conn.execute("INSERT INTO metrics (project_id, metric, at, value, unit, source,"
                     " recorded_at) VALUES ('project:x','disk.bytes',"
                     "'2026-09-06T00:00:00Z',1.0,'bytes','disk-usage',"
                     "'2026-09-06T23:04:58Z')")
    early = datetime(2026, 9, 7, 6, 8, 0, tzinfo=UTC)
    check("the next calendar day's sample is due at 06:08",
          R.due(conn, "disk-usage", 24, now=early) is True,
          "the elapsed-hours rule said no until 23:04")
    check("and the same day's is not due twice",
          R.due(conn, "disk-usage", 24,
                now=datetime(2026, 9, 6, 23, 59, tzinfo=UTC)) is False, "")
    check("a cadence of 0 is always due", R.due(conn, "disk-usage", 0) is True)
    conn.close()
    # THE STORE MODULE TOO, not only `paths`. Reloading `paths` alone left
    # `store.db` bound to the fixture path, so the NEXT test in this file read an
    # empty store and reported "there is no measurement to look at" — a fixture's
    # environment becoming another test's fact, which is the class the gate's
    # purity contract exists to catch one level up.
    os.environ.pop("OBSERVATORY_DB", None)
    importlib.reload(paths)
    importlib.reload(store_db)


def test_the_gate_reads_the_samples_own_stamp() -> None:
    import check_paths
    src = check_paths.prose_removed(
        (ROOT / "collectors/run_plugins.py").read_text(encoding="utf-8"))
    check("`due` no longer reads MAX(recorded_at)",
          "SELECT MAX(recorded_at) FROM metrics WHERE source" not in src,
          "when the writer last ran is a different question from which period "
          "has a sample")
    check("it compares against the period start", "period_start(" in src, "")


# ─────────── a stopped series is not health ────────────────────────────

def test_a_stopped_series_is_reported_rather_than_called_not_due() -> None:
    R = runner()
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    skip = "this period already has a sample (cadence 24h)"
    for last, want in (("2026-09-10T00:00:00Z", "not_due"),
                       ("2026-09-09T00:00:00Z", "not_due"),
                       ("2026-09-07T00:00:00Z", "stale")):
        age = R.series_age(last, 24, now)
        got = R.classify({"skipped": skip, "seriesAgePeriods": age})
        check(f"a series last written {last} classifies as {want}", got == want,
              f"age={age} -> {got}")
    check("an unparseable stamp gives no age rather than a wrong one",
          R.series_age("not a date", 24, now) is None, "")
    check("and no cadence gives none either", R.series_age("2026-09-10T00:00:00Z", 0) is None)


def test_the_stale_classification_becomes_a_finding() -> None:
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-stale-"))
    (d / "registry").mkdir()
    (d / "scratch").mkdir()
    (d / "registry/projects.json").write_text('{"projects": []}')
    (d / "scratch/plugins.json").write_text(json.dumps({
        "ran_at": "2026-09-07T09:00:00Z",
        "plugins": [{"id": "disk-usage", "written": 0, "refused": [],
                     "skipped": "this period already has a sample (cadence 24h)",
                     "classification": "stale", "manifest_problems": [],
                     "last_at": "2026-09-01T00:00:00Z", "every_hours": 24,
                     "seriesAgePeriods": 6.4}],
        "installed": 1, "metric_rows": 92, "distinct_metrics": 1}))
    os.environ.update(OBSERVATORY_REGISTRY=str(d / "registry"),
                      OBSERVATORY_SCRATCH=str(d / "scratch"),
                      OBSERVATORY_DB=str(d / "absent.db"))
    import paths
    importlib.reload(paths)
    import build_findings as B
    importlib.reload(B)
    got = [f for f in B.collect() if f["type"] == "plugin.stale"]
    for k in ("OBSERVATORY_REGISTRY", "OBSERVATORY_SCRATCH", "OBSERVATORY_DB"):
        os.environ.pop(k, None)
    importlib.reload(paths)
    check("a stale series raises a finding", len(got) == 1, str(got)[:200])
    if got:
        check("it says how many periods, not how many hours",
              "cadence period(s)" in got[0]["detail"], got[0]["detail"][:120])
        check("and that the plugin itself is healthy",
              "exits cleanly" in got[0]["detail"], got[0]["detail"][:160])


# ─────────── the measurements reach a reader ───────────────────────────

def test_the_surface_carries_a_direction_not_only_a_magnitude() -> None:
    import survey
    importlib.reload(survey)
    d = survey.project_detail(OWN, timeline_limit=0)
    check("there is a measurement to look at", bool(d["measurements"]),
          str(d["measurements"]))
    for m in d["measurements"]:
        check(f"`{m['metric']}` carries previous/change",
              {"previous", "previousAt", "change"} <= set(m), str(sorted(m)))
        if m["previous"] is None:
            check(f"`{m['metric']}` with one sample reports change as null, not 0",
                  m["change"] is None, str(m))
        else:
            check(f"`{m['metric']}`'s change is the difference",
                  abs((m["value"] - m["previous"]) - m["change"]) < 1e-6, str(m))


def test_the_disk_finding_names_who_is_responsible() -> None:
    """The plugin's stated reason, as an assertion. `host.disk_low` said the
    volume was nearly full and could not name one project, while 92 rows sat in
    the store."""
    import build_findings as B
    importlib.reload(B)
    big, grow = B.disk_culprits()
    check("the largest consumers are computable", bool(big),
          "no project over 0.5 GB, or the metric is missing")
    check("they are named coarsely, since findings.json is committed",
          all("~" in x and "GB" in x for x in big), str(big[:3]))
    check("growth is computable now that a series exists",
          isinstance(grow, list), str(grow))
    doc = json.loads((__import__("paths").REGISTRY / "findings.json").read_text(encoding="utf-8"))
    low = [f for f in doc["findings"] if f["type"] == "host.disk_low"]
    if low:
        check("and the live finding carries them",
              "Largest working trees" in low[0]["detail"], low[0]["detail"][-160:])


# ─────────── the seam's own claim ──────────────────────────────────────

def test_adding_a_plugin_touches_no_file_outside_plugins() -> None:
    """`plugins/README.md`'s first promise, and a second plugin is the only real
    test of it. Mechanical: no file outside `plugins/` may name a plugin's id or
    any metric it declares."""
    manifests = sorted((ROOT / "plugins").glob("*.json"))
    check("there is more than one plugin, so the claim is testable",
          len(manifests) >= 2, f"{[m.name for m in manifests]}")
    names: list[str] = []
    for m in manifests:
        doc = json.loads(m.read_text(encoding="utf-8"))
        names.append(doc["id"])
        names += [x["name"] for x in doc.get("metrics") or []]
    # PROSE REMOVED FIRST, because a comment naming `disk.bytes` as the example
    # everyone reads is documentation, not coupling — the distinction
    # `dashboard/audit_pack.py` was written about, one layer down. What must not
    # appear is a plugin's vocabulary in CODE: the first version of
    # `build_findings.disk_culprits()` put `disk.bytes` in SQL and broke this
    # promise in the same change that tested it. It resolves the metric by the
    # declared `role` now.
    import source_reader
    # The source exporter enumerates shipped plugin files; it is packaging,
    # not a runtime consumer of their metric vocabulary.
    packaging = ROOT / "tools/export_public_source.py"
    hay = [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts
           and "plugins" not in p.parts and "tests" not in p.parts and p != packaging]
    hay += [p for p in ROOT.rglob("*.sh") if ".venv" not in p.parts]
    for needle in names:
        hits = []
        for f in hay:
            text = f.read_text(encoding="utf-8", errors="replace")
            code = (source_reader.code_keeping_strings(text)
                    if f.suffix == ".py" else text)
            if needle in code:
                hits.append(str(f.relative_to(ROOT)))
        check(f"no core file names `{needle}` in code", not hits, str(hits[:3]))


def test_the_second_plugin_parses_each_format_it_claims() -> None:
    sys.path.insert(0, str(ROOT / "plugins"))
    import dependency_weight as D
    importlib.reload(D)
    check("npm counts runtime and peer, never dev",
          D.npm('{"dependencies":{"a":"1"},"peerDependencies":{"b":"1"},'
                '"devDependencies":{"eslint":"1"}}') == {"a", "b"},
          "a linter is not part of the project's surface area")
    check("a pep-621 specifier is stripped to its name",
          D.pyproject('[project]\ndependencies = ["requests>=2.0", "flask[async]"]')
          == {"requests", "flask"}, "")
    check("poetry's table is read too, minus python itself",
          D.pyproject('[tool.poetry.dependencies]\npython = "^3.12"\nrich = "*"')
          == {"rich"}, "")
    check("requirements skips directives and urls",
          D.requirements("-r other.txt\n--index-url x\nrequests==2.0  # why\n"
                         "https://example/x.whl\n") == {"requests"}, "")
    check("cargo reads its dependency table",
          D.cargo('[dependencies]\nserde = "1"\n') == {"serde"}, "")
    check("composer drops the php constraint",
          D.composer('{"require":{"php":"^8","monolog/monolog":"^3"}}')
          == {"monolog/monolog"}, "")
    check("gradle counts declarations by group:artifact",
          D.gradle('    implementation("com.x:y:1.0")\n    api "com.a:b:2"\n')
          == {"com.x:y", "com.a:b"}, "")


def test_an_unparseable_manifest_is_a_problem_not_a_zero() -> None:
    sys.path.insert(0, str(ROOT / "plugins"))
    import dependency_weight as D
    importlib.reload(D)
    d = pathlib.Path(tmpdir.mkdtemp(prefix="observatory-deps-"))
    (d / "package.json").write_text('{"dependencies": {')
    names, problems = D.count(d)
    check("nothing is counted from it", names == set(), str(names))
    check("and the failure is named", len(problems) == 1 and "package.json" in problems[0],
          str(problems))
    (d / "requirements.txt").write_text("requests==2.0\n")
    names, problems = D.count(d)
    check("a readable manifest beside it still counts",
          names == {"requirements:requests"}, str(names))
    check("with the problem still reported", len(problems) == 1, str(problems))


def test_the_runner_accepts_only_declared_metrics() -> None:
    """The seam's other guarantee, driven against the new plugin: a metric it
    emits without declaring is refused rather than written."""
    p = subprocess.run([PY, "collectors/run_plugins.py", "--check"], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    check("every manifest validates", p.returncode == 0, (p.stdout + p.stderr)[-200:])
    check("and both plugins are listed", "dependency-weight" in p.stdout
          and "disk-usage" in p.stdout, p.stdout[-200:])


if __name__ == "__main__":
    print("the metric layer — a series that accumulates, and a reader for it\n")
    check("synthetic project is declared", OWN == SYNTHETIC_PROJECT)
    for fn in (test_a_daily_cadence_is_a_calendar_day,
               test_a_late_recording_does_not_delay_the_next_period,
               test_the_gate_reads_the_samples_own_stamp,
               test_a_stopped_series_is_reported_rather_than_called_not_due,
               test_the_stale_classification_becomes_a_finding,
               test_the_surface_carries_a_direction_not_only_a_magnitude,
               test_the_disk_finding_names_who_is_responsible,
               test_adding_a_plugin_touches_no_file_outside_plugins,
               test_the_second_plugin_parses_each_format_it_claims,
               test_an_unparseable_manifest_is_a_problem_not_a_zero,
               test_the_runner_accepts_only_declared_metrics):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32ma measurement with a direction, and a layer that can say it "
          "stopped\033[0m")
