#!/usr/bin/env python3
"""Five numbers on a project's row, three of them unreadable without a mouse.

Take a typical project whose row renders:

    70 packages · 92 МБ · 2.6 ГБ · 8 days · 6 tags

* the two byte figures are `disk.bytes` and `disk.reclaimable_bytes` — what the
  project COSTS and what deleting its package directories would GIVE BACK,
  opposite meanings, distinguishable only by hovering for the `title`;
* `8 days` is `release.days_since_last` — days of what, unlabelled;
* `70 packages` and `6 tags` happen to read because their unit is a noun.

92 of the 159 rows carry three or more metrics, so this is the common case, and
it is the plugin seam's own output: **every metric a future plugin declares lands
in this renderer**, which is the thing the operator asked to grow.

**The core may not name a plugin's metric.** That is the six-file problem this
whole indirection exists to prevent — `dashboard/build_dashboard.py` already
carries the scar, its own comment recording that the first version read
`disk.bytes` explicitly and the plugin suite caught it. So a mapping from metric
name to caption cannot live here.

**So the plugin says it.** A metric declaration may carry `label`: the author's
own short caption, beside `unit`, `means` and `role`, which already come from the
manifest. When it is absent the renderer falls back to the metric's NAME —
`disk.bytes 92 МБ`, verbose and unambiguous — so a plugin that declares nothing
still reads, and no core file has learned a name.

**The label replaces the unit word rather than joining it.** "пакетов 70" reads;
"пакетов 70 packages" does not. A declared label is the whole caption, which puts
the whole caption in the hands of the person who knows what the number means.

**Russian, because the page is.** `unit` values are already English nouns
rendered onto a Russian page (`70 packages`), so the page mixes today; a Russian
caption is the improvement, and a manifest is configuration rather than prose.
`unit` itself is left alone: it is stored in the `metrics` table beside every
value and changing it would rewrite data to fix a caption.
"""
from __future__ import annotations
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "collectors"))

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable
FAILURES: list[str] = []


def fixture_page():
    import dashboard_fixture
    import tmp as tmpdir
    return dashboard_fixture.build(pathlib.Path(tmpdir.mkdtemp(prefix='observatory-labels-')))


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def manifests() -> list[dict]:
    import run_plugins
    return [m for m in run_plugins.manifests() if not m.get("_broken")]


# ─────────── the declaration ───────────────────────────────────────────

def test_every_installed_metric_declares_a_label() -> None:
    """Not a hard requirement of the seam — the renderer falls back to the name —
    but the three plugins shipped here are the example the next author copies."""
    missing = []
    for m in manifests():
        for met in m.get("metrics", []):
            if not str(met.get("label") or "").strip():
                missing.append(f"{m['id']}:{met['name']}")
    check("the installed plugins caption every metric they declare", not missing,
          str(missing))


def test_a_label_is_short_enough_to_sit_in_a_chip() -> None:
    long = []
    for m in manifests():
        for met in m.get("metrics", []):
            lab = str(met.get("label") or "")
            if len(lab) > 18:
                long.append(f"{met['name']}={lab!r}")
    check("no caption is longer than a chip", not long,
          "a caption that wraps is worse than the metric name: " + str(long))


def test_the_label_does_not_repeat_the_unit() -> None:
    """"пакетов 70 packages" is what happens when the caption joins the unit
    instead of replacing it."""
    bad = []
    for m in manifests():
        for met in m.get("metrics", []):
            lab, unit = str(met.get("label") or ""), str(met.get("unit") or "")
            if lab and unit and unit.lower() in lab.lower():
                bad.append(f"{met['name']}: {lab!r} contains {unit!r}")
    check("a caption does not contain its own unit", not bad, str(bad))


# ─────────── the payload carries it ────────────────────────────────────

def test_the_payload_carries_a_caption_per_metric() -> None:
    page = fixture_page()
    html = page.read_text(encoding="utf-8")
    m = re.search(r'const D = (\{.*?\});\n', html, re.S)
    if not m:
        check("the page carries a payload", False, "")
        return
    payload = json.loads(m.group(1))
    withm = [r for r in payload["rows"] if r.get("metrics")]
    check("some rows carry metrics", bool(withm), str(len(withm)))
    if not withm:
        return
    nolabel = [f"{r['id']}:{x['n']}" for r in withm for x in r["metrics"]
               if not str(x.get("l") or "").strip()]
    check("every metric in the payload carries its caption", not nolabel,
          str(nolabel[:6]))


def test_the_core_still_names_no_plugin_metric() -> None:
    """The invariant the whole indirection exists for, re-asserted because this
    change adds a second thing the dashboard reads from the manifest."""
    src = (ROOT / "dashboard/build_dashboard.py").read_text(encoding="utf-8")
    # TWO READERS, one per half, and the reason is not pedantry. My first
    # version stripped only `#` comments and reported that the file names
    # `disk.bytes` — it does, twice, both times in a COMMENT recording this very
    # scar, one of them a `//` comment inside the embedded script. The fifth
    # source-level assertion this session to misfire on its reader rather than
    # on the code.
    #
    # `source_reader.code_only` blanks Python comments AND string literals, so it
    # covers the Python half exactly — but the page's script lives INSIDE a
    # string, so that reader blanks the JS wholesale and would not see a branch
    # written there. Hence the second pass: the embedded script with its `//`
    # comments removed.
    sys.path.insert(0, str(ROOT / "tests"))
    import source_reader
    python_half = source_reader.code_only(src)
    js = src[src.find("function metrics(list)"):] if "function metrics(list)" in src else ""
    js_half = "\n".join(l.split("//", 1)[0] for l in js.splitlines())
    for name in ("disk.bytes", "disk.reclaimable_bytes", "release.tags",
                 "deps.direct", "release.days_since_last"):
        check(f"the dashboard's Python does not name {name}",
              name not in python_half,
              "a core file naming a plugin's metric is the six-file problem")
        check(f"and its script does not name {name}", name not in js_half,
              "the embedded script is a core file too")
    check("and it reads the captions through the plugin reader",
          "manifests" in python_half or "run_plugins" in python_half,
          "one reader of the manifests, not a second glob")


# ─────────── the page renders it ───────────────────────────────────────

def test_the_rendered_chip_shows_the_caption() -> None:
    import shutil
    if shutil.which("node") is None:
        print("  NOTE  node is absent; the rendered assertion cannot run here — "
              "see tests/test_dashboard_render.py for the executed-page cases")
        return
    page = fixture_page()
    html = page.read_text(encoding='utf-8')
    match = re.search(r'const D = (\{.*?\});\n', html, re.S)
    payload = json.loads(match.group(1))
    metric = next(m for row in payload['rows'] for m in row.get('metrics', []))
    def drive(needle):
        p = subprocess.run(['node', str(ROOT/'tests/render_dashboard.mjs'), str(page), '--count', needle],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
        check('the rendered harness exits successfully', p.returncode == 0, p.stderr[-200:])
        if p.returncode:
            return {}
        got = json.loads(p.stdout)
        check('the page script runs without throwing', not got.get('threw'), str(got.get('threw')))
        return got
    got = drive(metric['l'])
    check('the rendered chip contains its declared caption', sum(got.get('counts', {}).values()) > 0)
    for row in payload['rows']:
        for m in row.get('metrics', []):
            m.pop('l', None)
    page.write_text(html[:match.start(1)] + json.dumps(payload, ensure_ascii=False) + html[match.end(1):])
    got = drive(metric['n'])
    check('without a caption the rendered chip contains the metric name', sum(got.get('counts', {}).values()) > 0)


if __name__ == "__main__":
    print("metric captions — five numbers, three of them a guess\n")
    for fn in (test_every_installed_metric_declares_a_label,
               test_a_label_is_short_enough_to_sit_in_a_chip,
               test_the_label_does_not_repeat_the_unit,
               test_the_payload_carries_a_caption_per_metric,
               test_the_core_still_names_no_plugin_metric,
               test_the_rendered_chip_shows_the_caption):
        fn()
    print()
    if FAILURES:
        print(f"\033[31m{len(FAILURES)} failed\033[0m")
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("\033[32mevery number on a project's row says what it is\033[0m")
