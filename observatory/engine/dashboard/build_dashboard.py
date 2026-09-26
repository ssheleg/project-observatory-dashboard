#!/usr/bin/env python3
"""Render the project dashboard from the typed inventory. Standard library only.

Reads registry/{projects,repositories,relations,domains}.json and writes a
self-contained HTML page that opens over file:// with no server.
"""
from __future__ import annotations
import html, json, os, re, sys
from datetime import datetime, timedelta, timezone
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atomic
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))                       
import paths                                                                    
# `paths`, not `ROOT / "registry"`. The third tool found with the path inlined —
# after the validator — and the consequence is the same: it is the
# one file `OBSERVATORY_REGISTRY` cannot redirect, so a test that points it at a
# copy silently renders the live registry and passes for the wrong reason.
INV = paths.REGISTRY
OUT = paths.DASHBOARD_HTML


def load(name):
    with (INV / name).open(encoding="utf-8") as handle:
        return json.load(handle)


#: The rolling windows the work tiles report over. Rolling rather than calendar
#: weeks, because every one of the 852 rows in `project_week` is still `open` —
#: the freeze rule fires at `week_start < today - 365d` and the oldest week is
#: exactly one year old — so a "this week" tile would be comparing a partial week
#: against a whole one.
WORK_WINDOWS = (7, 28)



#: The clone states that assert work on this disk and possibly nowhere else.
#: Named here rather than repeated: `collectors/scan_remotes.AT_RISK_STATES` is
#: the same list at the measuring end, and the two must not drift.
AT_RISK_SYNC = ("ahead", "local-only-branch", "unpushed-and-remote-moved",
                "diverged")


def at_risk_total(repos: dict) -> dict:
    """One tile: how many commits across all checkouts are on no remote.

    Three outcomes, and the middle one is the reason this is a function. No
    at-risk checkout means there is nothing to say. At-risk checkouts that all
    carry a count give their sum. At-risk checkouts with NO count mean the
    remotes probe has not measured them yet, and printing `0` there would be a
    reassurance about work nobody has looked at.
    """
    risky = [r for r in repos.values()
             if (r.get("local") or {}).get("sync") in AT_RISK_SYNC]
    if not risky:
        return {}
    counted = [r for r in risky if isinstance((r.get("local") or {}).get("unpushed"), int)]
    # MEASURED AS NOTHING is its own group, not part of the unmeasured. Two
    # `local-only-branch` checkouts hold no commit any remote lacks, and calling
    # them "not counted" overstated the uncertainty of the estate's own figure.
    nothing = [r for r in risky if (r.get("local") or {}).get("nothing_exclusive")]
    unmeasured = len(risky) - len(counted) - len(nothing)
    if not counted:
        return {"коммитов ни на одном remote":
                "нечего терять" if nothing and not unmeasured else "не измерено"}
    total = sum(r["local"]["unpushed"] for r in counted)
    if unmeasured:
        return {"коммитов ни на одном remote":
                f"{total}+ ({unmeasured} чекаут(ов) не посчитаны)"}
    return {"коммитов ни на одном remote": total}


def work_stats() -> dict:
    """What HAPPENED across all projects, as tiles.

    The other tiles count what exists — projects, repositories, sites, notes —
    and none of them counts work, although the store holds every commit event
    and watching where the work went is part of this system's purpose.

    COUNTED FROM `events`, never by summing a rollup column. `active_days`,
    `authors` and `worked_days` are set sizes folded at write time, and adding
    them across projects would count one Tuesday once per project. A distinct
    count over the event rows is the one place the question can be answered
    without that error.

    ABSENT, NOT ZERO, without a store. A fresh clone has none — it is gitignored
    — and `0 commits` where the truth is "there is no store" would be an
    inversion of the facts. So an unreadable store yields `{}` and the tiles
    simply do not appear.
    """
    import sqlite3
    if not paths.DB.exists():
        return {}
    out: dict[str, object] = {}
    try:
        conn = sqlite3.connect(f"file:{paths.DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return {}
    try:
        for days in WORK_WINDOWS:
            r = conn.execute(
                "SELECT count(*) c, count(DISTINCT project_id) p FROM events"
                " WHERE kind='commit' AND occurred_at >= date('now', ?)",
                (f"-{days} days",)).fetchone()
            if r is None:
                continue
            # The window is IN THE LABEL. "2222" means nothing on its own, and a
            # tile is one number beside one caption.
            out[f"коммитов за {days} дн"] = r["c"]
            out[f"проектов в работе, {days} дн"] = r["p"]
        # WHERE the work went, not only how much. A name rather than a number,
        # which the tile renderer prints identically.
        top = conn.execute(
            "SELECT project_id, count(*) c FROM events WHERE kind='commit'"
            "   AND project_id IS NOT NULL"
            f"  AND occurred_at >= date('now', '-{max(WORK_WINDOWS)} days')"
            " GROUP BY project_id ORDER BY c DESC LIMIT 1").fetchone()
        if top is not None:
            out[f"больше всего работы, {max(WORK_WINDOWS)} дн"] = (
                top["project_id"].split(":", 1)[-1])
    except sqlite3.Error as exc:
        # NAMED. A silent handler here would drop the tiles and leave the page
        # looking exactly as it did before this existed.
        print(f"  work tiles unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {}
    finally:
        conn.close()
    return out


def _queue(conn, limit: int = 12) -> list[dict]:
    """The newest proposals awaiting a human, newest first.

    Newest rather than oldest, deliberately: the oldest are closest to expiry
    and saying so as a NUMBER is `ledger.review_backlog`'s job. What a person
    scanning the page wants is what the agent has just concluded, which is the
    half a count cannot carry.
    """
    # THE CURRENT REVISION ONLY, and the join is not decoration: counting every
    # `proposed` ROW overcounts against the health panel's `proposed`, because
    # a superseded revision keeps its state. Two numbers for "waiting" on one
    # page is worse than one number that is harder to compute — so this uses
    # the panel's own definition, character for character.
    CURRENT = ("ledger l JOIN (SELECT memory_id, MAX(revision) r FROM ledger"
               " GROUP BY memory_id) m ON m.memory_id = l.memory_id"
               " AND m.r = l.revision WHERE l.state = 'proposed'")
    return [{"id": r["memory_id"], "rev": r["revision"], "kind": r["kind"],
             "project": r["project_id"], "at": (r["created_at"] or "")[:16].replace("T", " "),
             "statement": (r["statement"] or "")[:200]}
            for r in conn.execute(
                "SELECT l.memory_id, l.revision, l.kind, l.project_id, l.created_at,"
                f" l.statement FROM {CURRENT}"
                " ORDER BY l.created_at DESC LIMIT ?", (limit,))]


def _digest(conn) -> dict:
    """The review queue in one line: how many rows wait, of which kinds, and
    what retention erases first — the same arithmetic `tools/review.py digest`
    prints, read here so the health page can say it above the rows instead of
    leaving the operator to count. Retention's horizon is the store's own
    (`retention.json → ledger.proposed_days`, 90 when unstated); the exempt
    owners are `review.py`'s to know, so this counts every waiting row and
    says "erases" of the ones whose day has come, not of the exempt.
    """
    CURRENT = ("ledger l JOIN (SELECT memory_id, MAX(revision) r FROM ledger"
               " GROUP BY memory_id) m ON m.memory_id = l.memory_id"
               " AND m.r = l.revision WHERE l.state = 'proposed'")
    horizon = 90
    try:
        cfg = json.loads((paths.config_file("retention.json")).read_text(encoding="utf-8"))
        horizon = int(cfg["ledger"]["proposed_days"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    rows = [dict(r) for r in conn.execute(
        f"SELECT l.kind, l.created_at FROM {CURRENT}")]
    by_kind = Counter((r.get("kind") or "?") for r in rows)
    now = datetime.now(timezone.utc)
    soon_n, first = 0, None
    for r in rows:
        try:
            made = datetime.strptime(r.get("created_at") or "", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        gone = made + timedelta(days=horizon)
        if gone <= now + timedelta(days=7):
            soon_n += 1
            first = gone if first is None or gone < first else first
    return {"waiting": len(rows), "by_kind": dict(by_kind.most_common()),
            "horizon_days": horizon, "erases_within_7d": soon_n,
            "first_erase_on": first.strftime("%Y-%m-%d") if first else None}


def from_store() -> dict:
    """What the STORE knows, or an honest emptiness.

    Without this the page would read `registry/*.json` and nothing else, and
    the events, weekly rollups, plugin measurements, the wallet and the
    provider health would all be invisible on the one screen that exists to
    show them. The registry says what EXISTS; only the store says what
    HAPPENED.

    It degrades rather than failing: a fresh clone has no store — it is
    gitignored — and a dashboard that cannot be built without one would make
    the gate unrunnable there.
    """
    import sqlite3
    out = {"weeks": {}, "metrics": {}, "timeline": {}, "notes": {},
       "health": {}, "degraded": "", "queue": []}
    if not paths.DB.exists():
        out["degraded"] = "нет локального хранилища — история и метрики недоступны"
        return out
    try:
        conn = sqlite3.connect(f"file:{paths.DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        out["degraded"] = f"хранилище не открылось: {type(exc).__name__}"
        return out
    try:
        out["queue"] = _queue(conn)
        out["digest"] = _digest(conn)
    except sqlite3.Error as exc:
        # The queue is the least of what this function returns; a store that
        # cannot answer for it must not cost the caller the weeks, metrics and
        # health beside it.
        out["queue"] = []
        out["degraded"] = (out["degraded"] or "") + f" очередь не прочиталась: {type(exc).__name__}"
    try:
        # Twenty-six weeks: half a year is the longest span a sparkline this
        # size can show without becoming a smear, and the rollup keeps the rest.
        for r in conn.execute(
                "SELECT project_id, week_start, commits, sessions, worked_days"
                " FROM project_week"
                " WHERE week_start >= date('now', '-182 days') ORDER BY week_start"):
            # `s` and `d` may be NULL: a row computed before the session columns
            # existed. Carried through as null rather than 0 so the
            # page can tell "no work" from "not measured" — the reason those
            # columns are nullable at all.
            out["weeks"].setdefault(r["project_id"], []).append(
                {"w": r["week_start"], "c": r["commits"],
                 "s": r["sessions"], "d": r["worked_days"]})
        # EVERY metric, by name and unit, never a name this file knows. The
        # first version read `disk.bytes` explicitly and the plugin suite caught
        # it: a core file naming a plugin's metric is the six-file problem
        # returning one row at a time. The manifest declares the unit; this
        # renders whatever arrives.
        # THE CAPTIONS, from the manifests, through the plugin layer's own
        # reader. Five numbers sat on a project's row — `70 packages · 92 МБ ·
        # 2.6 ГБ · 8 days · 6 tags` — and three were a guess without a mouse:
        # the two byte figures are what the project COSTS and what deleting its
        # package directories GIVES BACK, opposite meanings told apart only by
        # a `title` attribute. A map from metric name to caption may not live
        # here (the six-file problem), so the plugin declares it and this reads
        # it.
        labels: dict[str, str] = {}
        try:
            sys.path.insert(0, str(paths.ROOT / "collectors"))
            import run_plugins
            for man in run_plugins.manifests():
                for met in man.get("metrics", []) or []:
                    lab = str(met.get("label") or "").strip()
                    if lab and met.get("name"):
                        labels[met["name"]] = lab
        except Exception as exc:                                                    
            # NAMED, not swallowed. Without captions the page still renders —
            # the script falls back to the metric name — so this degrades rather
            # than fails, and says which.
            print(f"  metric captions unavailable: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
        # THE PREVIOUS VALUE, because retention keeps it for exactly this and
        # nothing was showing it. `store/retention.json` holds
        # `metrics_keep_per_series: 2` with the reason written beside it — "the
        # newest, plus one so a reader can see whether it moved" — and the page
        # rendered only the newest, so the second row was kept for a reader who
        # had no way to read it. Measured 2026-09-09: 911 metric rows, seven
        # series, two or three samples each, and no movement visible anywhere.
        #
        # ABSENT, never zero: a series with one sample carries no `p` at all,
        # and the script renders nothing rather than "+0" — a first measurement
        # and an unchanged one are different facts.
        rows = list(conn.execute(
            "SELECT project_id, metric, unit, value, at FROM metrics"
            " ORDER BY project_id, metric, at DESC"))
        seen: dict[tuple[str, str], int] = {}
        for r in rows:
            key = (r["project_id"], r["metric"])
            rank = seen.get(key, 0)
            seen[key] = rank + 1
            if rank == 0:
                out["metrics"].setdefault(r["project_id"], []).append(
                    {"n": r["metric"], "v": r["value"], "u": r["unit"],
                     "l": labels.get(r["metric"], ""), "at": r["at"]})
            elif rank == 1:
                for m in out["metrics"][r["project_id"]]:
                    if m["n"] == r["metric"]:
                        m["p"], m["pat"] = r["value"], r["at"]
                        break
        # S3: the story of ONE project. Ten commits is what a panel can show
        # without becoming a log; the rest is what `observatory_timeline` is for.
        for r in conn.execute(
                "SELECT project_id, occurred_at, actor, payload_json FROM events"
                " WHERE kind='commit' AND project_id IS NOT NULL"
                " ORDER BY occurred_at DESC"):
            bucket = out["timeline"].setdefault(r["project_id"], [])
            if len(bucket) >= 10:
                continue
            try:
                pay = json.loads(r["payload_json"] or "{}")
            except json.JSONDecodeError:
                pay = {}
            bucket.append({"at": r["occurred_at"][:10], "who": r["actor"] or "",
                           "what": (pay.get("subject") or "")[:110],
                           "repo": pay.get("repo") or ""})
        # What the observatory CONCLUDED, with its confidence and its state — the
        # agent proposes and never asserts (AGENTS.md rule 3), so a reader must
        # see `proposed` beside the sentence or the caveat is lost.
        # THE TOMBSTONE JOIN, and this query had none. Every other
        # read of the ledger is record-wide — `live()`, the search, the review
        # queue, `build_findings` — so an erased conclusion was hidden
        # everywhere EXCEPT the one surface a person looks at. The fragment is
        # shared with `survey.project_detail` rather than spelled out again.
        import survey as survey_mod
        for r in conn.execute(
                "SELECT l.project_id, l.created_at, l.statement, l.state, l.confidence"
                " FROM ledger l" + survey_mod.LIVE_LEDGER_JOIN +
                " WHERE l.project_id IS NOT NULL AND" + survey_mod.LIVE_LEDGER_WHERE +
                " ORDER BY l.created_at DESC"):
            bucket = out["notes"].setdefault(r["project_id"], [])
            if len(bucket) >= 5:
                continue
            bucket.append({"at": (r["created_at"] or "")[:10],
                           "text": (r["statement"] or "")[:400],
                           "state": r["state"] or "",
                           "conf": r["confidence"]})
        last = conn.execute(
            "SELECT started_at, finished_at, degraded_json FROM scans"
            " ORDER BY started_at DESC LIMIT 1").fetchone()
        deg = json.loads(last["degraded_json"] or "[]") if last else []
        out["health"] = {
            "last_scan": last["finished_at"] if last else "",
            "degraded_sources": len(deg),
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "weeks": conn.execute("SELECT COUNT(*) FROM project_week").fetchone()[0],
            "metrics": conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0],
            "proposed": conn.execute(
                "SELECT COUNT(*) FROM ledger l JOIN (SELECT memory_id, MAX(revision) r"
                " FROM ledger GROUP BY memory_id) m ON m.memory_id=l.memory_id"
                " AND m.r=l.revision WHERE l.state='proposed'").fetchone()[0],
            # Registry proposals are a DIFFERENT queue from ledger memories, and
            # it had no reader anywhere: `observatory_propose` is declared MCP
            # surface, it writes here, and neither this page nor any CLI looked.
            # A caller told its patch landed, in a table nobody reads, is the
            # dead-data shape this pass exists to close.
            "registry_proposals": conn.execute(
                "SELECT COUNT(*) FROM proposals WHERE status='proposed'").fetchone()[0],
        }
        # The projection's lag. Both search indexes are fed by the outbox, so a
        # pending queue means the answer any search gives is missing these
        # revisions — and this page is where "the observer is still watching" is
        # supposed to be legible.
        lag = conn.execute(
            "SELECT count(*) AS n, min(l.created_at) AS oldest FROM outbox o"
            " JOIN ledger l ON l.memory_id = o.memory_id AND l.revision = o.revision"
            " WHERE o.consumed_at IS NULL").fetchone()
        if lag and lag["n"]:
            out["health"]["projection_lag"] = lag["n"]
            out["health"]["projection_oldest"] = lag["oldest"]
        # THE ALWAYS-ON SERVER, from its own heartbeat. Three states, spelled
        # apart: beating (age and what it watches), silent (installed and not
        # reporting — `server.silent` on the board says the same louder), and
        # absent (never ran here / turned off) — the page says which, because
        # "no row" would read as "no server exists" on a machine where one is
        # supposed to be up.
        import datetime as _dt
        sd = paths.SCRATCH / "serverd.json"
        if sd.is_file():
            try:
                beat = json.loads(sd.read_text(encoding="utf-8"))
                at = _dt.datetime.strptime(beat.get("at", ""), "%Y-%m-%dT%H:%M:%SZ")
                age_s = int((_dt.datetime.utcnow() - at).total_seconds())
                out["health"]["server_age_s"] = age_s
                out["health"]["server_port"] = beat.get("port")
                out["health"]["server_uptime_s"] = beat.get("uptime_s")
                r = beat.get("remote") or {}
                out["health"]["server_at_risk"] = r.get("at_risk_total")
                l = beat.get("leaks") or {}
                out["health"]["leaks_open"] = l.get("open")
            except (ValueError, OSError):
                out["health"]["server_age_s"] = None
        else:
            out["health"]["server_age_s"] = -1                           
    except sqlite3.Error as exc:
        out["degraded"] = f"хранилище нечитаемо: {str(exc)[:60]}"
    finally:
        conn.close()

    # The wallet and the provider's health are FILES, not tables, and they are
    # the half `docs/ARCHITECTURE.md:114` promised would be on this page: "the
    # agent degrades to collectors-only and SAYS SO IN THE DASHBOARD".
    for key, name in (("wallet", "wallet.json"), ("provider", "provider-health.json")):
        f = paths.STATE / name
        if f.is_file():
            try:
                out["health"][key] = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    # PREPARED HERE, because the page must not read a field the file does not
    # have. `store/wallet.json` keeps per-month and per-day maps with no scalar
    # "this month" field, so a page testing for one would find it false on
    # every render and the spend row would never appear. A branch whose true
    # side is unreachable is found only by EXECUTING the page, not by checking
    # the data behind it — so the scalars are computed once, here.
    #
    # And it is THIS PROJECT's own spend, from its own journal, labelled as
    # such. A provider-side counter can measure a key shared with other
    # consumers, and showing that number here would report somebody else's
    # spending as this installation's. The date arithmetic stays in Python: a
    # browser deriving "which month is it" is a second place for the answer to
    # be wrong.
    w = out["health"].get("wallet") or {}
    if w:
        today = datetime.now(timezone.utc)
        out["health"]["spend_today"] = round(
            (w.get("days") or {}).get(today.strftime("%Y-%m-%d"), 0.0), 6)
        out["health"]["spend_month"] = round(
            (w.get("months") or {}).get(today.strftime("%Y-%m"), 0.0), 6)
        out["health"]["spend_denomination"] = w.get("denomination") or "credits"
    return out


#: How many findings the page carries BEFORE every remaining type is given a
#: row. It was a bare `[:40]` in the middle of a dict literal — a policy nobody
#: could find and nobody was told about — and the sentence that
#: justified it said what falls off the end is "the tail of `info`, the right
#: end to drop". Measured 2026-09-09, on 64 open findings: the tail held **ten
#: whole classes with no row on the page at all** — `store.faults_recurring`,
#: `project.unobservable`, `work.unwitnessed` and seven more. Dropping more of a
#: kind the reader can already see is a cap. Dropping the only instance of a
#: kind is a silence, and it is the one this repository refuses everywhere else.
FINDINGS_ON_PAGE = 8                                                                                     


def _findings_panel(FINDINGS: dict) -> dict:
    """The findings the page carries, grouped so none is omitted.

    The header prints the counts, so a list shorter than the count beside it
    would tell the reader two different things without saying which was the
    whole.

    The arithmetic happens HERE because both filters are known here: `counts`
    in `registry/findings.json` already excludes acknowledged findings, and so
    does the list below, so the two agree exactly. Recomputing a total in the
    page's script would duplicate what the payload already holds.

    **Every open row is carried.** Rows are kept in the builder's own order —
    severity, then deadline, then id — and each type's rows beyond
    `FINDINGS_ON_PAGE` are marked `folded`, so the page shows them under a
    per-type control that names their count instead of dropping them.

    The findings surface is the ONLY one a row of severity `info` reaches: the
    notifier sends `critical` and `warning` by default, and the review digest
    is about the ledger's queue rather than the board. So an info row cut from
    this page would reach nobody at all.
    """
    # NO OMISSION. A cap that dropped rows of a kind already shown, however
    # honestly it counted them, still left rows the operator could not reach
    # and so could not act on. Every open row is CARRIED; what a type has
    # beyond `FINDINGS_ON_PAGE` rows is FOLDED under a per-type control that
    # names its count, so the page grows by disclosure and never by omission.
    open_ = [f for f in FINDINGS["findings"] if not f.get("acked")]
    per_type: dict[str, int] = {}
    items = []
    for f in open_:
        n = per_type.get(f["type"], 0)
        per_type[f["type"]] = n + 1
        items.append({**f, "folded": n >= FINDINGS_ON_PAGE})
    folded_by_type = {k: v - FINDINGS_ON_PAGE for k, v in per_type.items() if v > FINDINGS_ON_PAGE}
    # WHAT THE OPERATOR SILENCED, beside what speaks (S5). Withheld from the
    # list and the counts, shown here with the reason — a silence nobody can
    # see later is the silence this file refuses.
    silenced = [{"id": f["id"], "type": f["type"], "severity": f["severity"],
                 "title": f["title"], "acked": f["acked"]}
                for f in FINDINGS["findings"] if f.get("acked")]
    return {"counts": FINDINGS["counts"],
            "built_at": FINDINGS.get("built_at"),
            "items": items,
            "folded_by_type": folded_by_type,
            "silenced": silenced,
            "omitted": 0}


def hosting_context(relations: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """({deployment id: environment name}, {resource id: account label}).

    From the `serves` and `in_account` edges and the documents they point at
    (docs/design/DEPLOYMENTS.md). A deployment with no `serves` edge has no
    environment here, and the page shows it as not specified, never as a guess
    (PB-130). Either document may be absent in an older registry.
    """
    envs = {e["id"]: e["name"] for e in (load("environments.json")["environments"]
                                         if (INV / "environments.json").is_file() else [])}
    labels = {a["id"]: a["label"] for a in (load("accounts.json")["accounts"]
                                           if (INV / "accounts.json").is_file() else [])}
    env_of = {r["from"]: envs[r["to"]] for r in relations if r["type"] == "serves" and r["to"] in envs}
    account_of = {r["from"]: labels[r["to"]] for r in relations
                  if r["type"] == "in_account" and r["to"] in labels}
    return env_of, account_of


def build():
    pdoc, rdoc = load("projects.json"), load("repositories.json")
    projects, repos = pdoc["projects"], {r["id"]: r for r in rdoc["repositories"]}
    relations = load("relations.json")["relations"]
    domains = {d["name"] for d in load("domains.json")["domains"]}
    dups = load("duplicate-repo-names.json")["groups"]

    _fd = INV / "findings.json"
    FINDINGS = json.loads(_fd.read_text(encoding="utf-8")) if _fd.is_file() else None
    # ABSENT IS NOT EMPTY. A fresh clone has no scan and `heroku-apps.json` will
    # not exist; the tab then says the estate was never asked, rather than
    # showing nothing and reading as "you host nothing".
    _hd = paths.REGISTRY / "heroku-apps.json"
    HEROKU = json.loads(_hd.read_text(encoding="utf-8")) if _hd.is_file() else None
    # NEVER A VALUE, and the document is built so it cannot hold one: a `label`
    # is what the provider calls a key. `tools/check_secrets.py` reads it on
    # every gate run, so the page inherits that guarantee rather than restating it.
    _cd = paths.REGISTRY / "credentials.json"
    CREDS = json.loads(_cd.read_text(encoding="utf-8")) if _cd.is_file() else None
    # WHICH KEYS A PROJECT USES, for its panel. The credential document is
    # heavy and rides only on the keys page; this is the small inverse of its
    # `used_by` edges — a name, its kind, where it sits and the anchor of its
    # row — so the project panel can answer "what does this authenticate with"
    # and hand the reader to the keys page by row. Names and places only, as
    # everywhere: the document never held a value to leak.
    KEYS: dict[str, list] = {}
    for _c in (CREDS or {}).get("credentials") or []:
        _slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(_c.get("id", "")).replace("credential:", "", 1))
        for _pid in _c.get("used_by") or []:
            KEYS.setdefault(_pid, []).append({
                "name": _c.get("name"), "kind": _c.get("kind"), "slug": _slug,
                "env": _c.get("env"), "leaked": bool(_c.get("leaked")),
                "signed": bool((_c.get("signature") or {}).get("purpose")),
                "where": (f"vault:{_c['vault_project']}" if _c.get("vault_project")
                          else f"{_c['in_project']}/{_c.get('path') or ''}" if _c.get("in_project")
                          else _c.get("source") or ""),
            })
    for _pid in KEYS:
        KEYS[_pid].sort(key=lambda k: (k["kind"] or "", (k["name"] or "").lower()))
    # THE MOVEMENTS JOURNAL, for the keys page — read by the same module the
    # board's `secret.moved_unrecorded` finding reads it with, so the page and
    # the finding cannot disagree. The journal sits beside the leak register in
    # the vault's store; names, dates and places, never a value.
    if CREDS is not None:
        sys.path.insert(0, str(ROOT / "tools"))
        import movements as _movements
        _leaks = Path(os.environ.get("OBSERVATORY_VAULT_DIR",
                                     paths.source_path("secret_store", paths.SECRETS) / "projects")) / "leaks.jsonl"
        _hk_trail: dict[str, list] = {}
        _hk_project: dict[str, str] = {}
        _hkf = paths.SCRATCH / "heroku.json"
        if _hkf.is_file():
            try:
                for _app in json.loads(_hkf.read_text(encoding="utf-8")).get("apps") or []:
                    if _app.get("config_releases"):
                        _hk_trail[_app["name"]] = _app["config_releases"]
            except (OSError, ValueError):
                _hk_trail = {}
        for _a in (HEROKU or {}).get("apps") or []:
            if _a.get("project"):
                _hk_project[_a["name"]] = str(_a["project"]).split(":", 1)[-1]
        CREDS["movements"] = _movements.journal_tail(_leaks, 30)
        CREDS["unrecorded"] = [{**u, "project": _hk_project.get(u["app"])}
                               for u in _movements.unrecorded(_hk_trail, _movements.read_moves(_leaks))]

    # WHAT IS ON THIS DISK, as names. The credential document above answers
    # "which accounts exist"; this answers "what is sitting in the working copy",
    # and the whole document is sent rather than a trimmed one: the trim saved
    # 156KB of a 1.1MB page and cost a paragraph explaining what had been left
    # out, which is a bad trade for a file opened locally.
    _ed = paths.REGISTRY / "env-inventory.json"
    ENVD = json.loads(_ed.read_text(encoding="utf-8")) if _ed.is_file() else None
    # THE KEYS A PROJECT HOLDS IN ITS OWN `.env` FILES join the panel's key
    # list too. The credential document knows the vault, the machine store and
    # the shared secrets directory — not the variables sitting in a checkout,
    # which is where most of a project's keys actually are, so without this a
    # panel could claim no credential is linked when that is false.
    # Names, file, class and git state — the value never leaves the file. Each
    # row links to its own env row (`#e-<file>:<NAME>`).
    # `project` in the inventory is the FOLDER name, joined to the project id
    # through the same folder index the credential collector uses — a match by
    # project name alone would miss a project whose folder is named differently.
    _folder_pid = {f: p["id"] for p in pdoc["projects"] for f in (p.get("local_folders") or [])}
    _name_pid = {p["name"]: p["id"] for p in pdoc["projects"]}
    for _f in (ENVD or {}).get("files") or []:
        _pid = _folder_pid.get(_f.get("project")) or _name_pid.get(_f.get("project"))
        if not _pid:
            continue
        for _v in _f.get("variables") or []:
            if _v.get("class") not in ("secret",):
                continue
            KEYS.setdefault(_pid, []).append({
                "name": _v.get("name"), "kind": "env-file", "slug": None,
                "env": None, "leaked": False, "signed": True,                                          
                "where": _f.get("path"), "git": _f.get("git"),
                "href": "env.html#e-" + re.sub(r"[^A-Za-z0-9_.:/-]+", "-", f"{_f.get('path')}:{_v.get('name')}"),
            })
    for _pid in KEYS:
        KEYS[_pid].sort(key=lambda k: (k["kind"] or "", (k["name"] or "").lower()))

    # WHAT PRODUCTION HOLDS, as the four verdicts and never a value. Two pages
    # read it: the Heroku row says how its configuration compares in one line,
    # and the ENV row says it per variable.
    # WHAT GOOGLE SEES. The whole inventory goes to its own page; the
    # per-project summary rides everywhere, because "how many people came" is a
    # fact about a project and belongs beside the project.
    _gf = paths.REGISTRY / "google-properties.json"
    GOOGLE = json.loads(_gf.read_text(encoding="utf-8")) if _gf.is_file() else None
    from collectors.google_registry import normalize_document, project_traffic
    if GOOGLE is not None:
        GOOGLE = normalize_document(GOOGLE)
    TRAFFIC = project_traffic((GOOGLE or {}).get("properties", []))
    # SEARCH CONSOLE, JOINED THE SAME WAY: a site is a host, and a host already
    # resolves to a project through the registry — so the console link lands on
    # the project rather than on a list nobody opens.
    import sys as _sys
    _sys.path.insert(0, str(paths.ROOT / "plugins"))
    import hostmap as _hostmap
    HOSTMAP = _hostmap.build()
    _sc = {}
    for _s in (GOOGLE or {}).get("search_console", []):
        _host = (_s.get("site") or "").replace("sc-domain:", "").replace("https://", "").replace("http://", "").strip("/")
        _owner = HOSTMAP.get(_host) or HOSTMAP.get(_host.replace("www.", ""))
        if _owner:
            _sc.setdefault(_owner, []).append({"site": _s.get("site"), "url": _s.get("console_url")})
    for _pid, _sites in _sc.items():
        TRAFFIC.setdefault(_pid, {"users_30d": None, "properties": []})["search_console"] = _sites

    _rf = paths.REGISTRY / "remote-env.json"
    REMOTE = json.loads(_rf.read_text(encoding="utf-8")) if _rf.is_file() else None

    # THE WHOLE DOMAIN LIST, not just the ones a project claims. 53 registered,
    # 9 on a project row: the rest were a tile with a number and no way to see
    # WHICH. The same omission Heroku had until it got a tab (audit 2026-09-09).
    DOMAINS = load("domains.json")["domains"]
    # WHAT THE ESTATE HOLDS AND HOW IT GROUPS. Both are projections;
    # a fresh clone without a Cloudflare scan simply has no zones, and the page
    # says so rather than showing an empty table.
    _zf = paths.REGISTRY / "cloudflare-zones.json"
    ZONES = load("cloudflare-zones.json")["zones"] if _zf.is_file() else None
    _mf = paths.REGISTRY / "mcp-servers.json"
    MCP = load("mcp-servers.json") if _mf.is_file() else None
    _pf = paths.REGISTRY / "products.json"
    PRODUCTS = load("products.json")["products"] if _pf.is_file() else []
    PRODUCT_OF = {}
    for pr in PRODUCTS:
        for mbr in pr["members"]:
            PRODUCT_OF.setdefault(mbr["project"], []).append(
                {"id": pr["id"], "name": pr["name"], "kind": pr["kind"], "role": mbr["role"]})
    LIVE = {}
    _lv = INV / "domain-liveness.json"
    if _lv.is_file():
        for h in json.loads(_lv.read_text(encoding="utf-8"))["hosts"]:
            LIVE[h["host"]] = {"resolves": h["resolves"], "http": h["http_status"],
                               "on": h["checked_on"]}
    members, sites, domain_owner = {}, {}, {}
    for rel in relations:
        if rel["type"] == "implemented_by":
            members.setdefault(rel["from"], []).append(rel["to"])
        elif rel["type"] == "public_domain_of":
            domain_owner.setdefault(rel["from"].split(":", 1)[1], []).append(rel["to"])
            sites.setdefault(rel["to"], []).append(rel["from"].split(":", 1)[1])

    rows = []
    for project in projects:
        ids = sorted(members.get(project["id"], []))
        rows.append({
            "id": project["id"],
            "name": project["name"],
            "owner": (project["owners"] or ["—"])[0] if len(project["owners"]) == 1
                     else ("multi" if project["owners"] else "—"),
            "owners": project["owners"],
            "ownership": project["ownership"],
            "anchor": project["anchor"],
            "lifecycle": project["lifecycle"],
            "description": project.get("description", ""),
            "stack": project.get("stack", []),
            "folders": project.get("local_folders", []),
            "last": project.get("last_activity_on", ""),
            "tier": project.get("activity_tier", ""),
            "note": project.get("canonical_page", "") if project.get("has_vault_note") else "",
            "rules": project.get("membership_rules", []),
            # `vault_notes`, and it is called `wiki_notes` here for one reason:
            # the store's own conclusions were also written to `r["notes"]`
            # twenty lines below, so the second assignment replaced this COUNT
            # with a LIST and the wiki chip rendered
            # "[object Object],[object Object] зам." on every row that had a
            # note. One word for two populations, and the page said so out loud
            # (2026-09-09). Seen by opening the page, which is why it lived.
            "wiki_notes": project.get("vault_notes", 0),
            # Measured liveness, folded in per host. A homepage that does not
            # resolve is the one fact about a site an operator must not have to
            # discover by clicking it.
            "sites": [{**x, "live": LIVE.get(x["host"])} for x in project.get("sites", [])],
            "products": PRODUCT_OF.get(project["id"], []),
            "repos": [{
                "nwo": repos[i]["name_with_owner"],
                "url": repos[i]["url"],
                "host": repos[i]["host"],
                "visibility": repos[i]["visibility"],
                "archived": repos[i]["archived"],
                "fork": repos[i]["fork"],
                "branch": repos[i].get("default_branch", ""),
                "path": (repos[i].get("local") or {}).get("path", ""),
                "checked_out": (repos[i].get("local") or {}).get("checked_out_branch", ""),
                "dirty": (repos[i].get("local") or {}).get("uncommitted_files", 0),
                "sync": (repos[i].get("local") or {}).get("sync", ""),
                # HOW MUCH IS AT STAKE. The count reached the registry and the
                # findings and stopped short of the page — the same enumerated
                # key list that lost it in `emit_registry.py`, one layer further
                # on. `None` when the probe could not count, never 0.
                "unpushed": (repos[i].get("local") or {}).get("unpushed"),
                "unpushedOn": (repos[i].get("local") or {}).get("unpushed_newest_on"),
                "nothing_exclusive": (repos[i].get("local") or {}).get("nothing_exclusive"),
                "pushed": repos[i].get("last_pushed_on", ""),
                "status": repos[i].get("status"),
                "supersededBy": repos[i].get("superseded_by"),
                "movedTo": repos[i].get("moved_to"),
                "statusEvidence": repos[i].get("status_evidence"),
                "language": repos[i].get("language", ""),
            } for i in ids if i in repos],
        })
    rows.sort(key=lambda r: (r["ownership"] != "owned", r["owner"].lower(), -len(r["repos"]), r["name"].lower()))

    stats = {
        # WHAT HAPPENED, first, because the estate's inventory answers a
        # different question and answered it alone until now.
        **work_stats(),
        # WHAT IS AT RISK, beside what happened. Registry-derived rather than
        # store-derived, which is why it is not inside `work_stats()`.
        **at_risk_total(repos),
        "projects": len(rows),
        "repositories": len(repos),
        "with_site": sum(1 for r in rows if r["sites"]),
        "with_note": sum(1 for r in rows if r["note"]),
        "with_folder": sum(1 for r in rows if r["folders"]),
        "no_note": sum(1 for r in rows if not r["note"]),
        "dirty": sum(1 for r in rows for x in r["repos"] if x["dirty"]),
        "unsynced": sum(1 for r in rows for x in r["repos"]
                        if x["sync"] and x["sync"] != "current"),
        # Counted although it is shown nowhere. An inactive repository anchors no
        # project, so it cannot appear in a row — and a registry that hides a
        # thing without saying how many it hid is lying by omission.
        "inactive_repos": sum(1 for r in repos.values()
                              if r.get("status") == "inactive"),
        "dead_site": sum(1 for r in rows
                         if any(s.get("live") and not s["live"]["resolves"] for s in r["sites"])),
        # PROJECTS whose lifecycle is archived — not archived repositories, of
        # which there are more. One word for two populations reads as a
        # contradiction the moment both are on screen.
        "archived": sum(1 for r in rows if r["lifecycle"] == "archived"),
        "archived_repos": sum(1 for r in repos.values() if r.get("archived")),
        "domains": len(domains),
        # THE SAME OMISSION AS `inactive_repos`, one subject over, and it went
        # unnoticed until the page was asked what it hides. A domain no project
        # claims has no row to sit in, so of 53 registered domains the page
        # showed nine and printed "53" beside them — the operator's assets, most
        # of them costing a renewal a year, counted and not listed. Measured
        # 2026-09-09. The count is the honest half of what a page can do here;
        # which of them matter is `domain.dark`, `domain.expiring` and
        # `domain.hold` on the board.
        "domains_no_row": len(domains - {s["host"] for r in rows for s in r["sites"]}),
        "owners": len({r["owner"] for r in rows}),
        # THE COUNT OF WHAT IS RUNNING, beside the count of what exists. An
        # application nothing claims is the same omission as a domain nothing
        # claims, one provider over, and it is the reason this tile is a pair.
        "heroku_apps": len(HEROKU["apps"]) if HEROKU else 0,
        "heroku_unlinked": (HEROKU.get("totals", {}).get("unlinked", 0) if HEROKU else 0),
        "heroku_cost": (HEROKU.get("totals", {}).get("monthly_cost", 0) if HEROKU else 0),
        "creds": len(CREDS["credentials"]) if CREDS else 0,
        "creds_leaked": (CREDS.get("totals", {}).get("leaked_unrotated", 0) if CREDS else 0),
        "creds_unclaimed": (CREDS.get("totals", {}).get("unclaimed", 0) if CREDS else 0),
        "heroku_down": (sum(1 for a in HEROKU["apps"]
                            if a["state"] in ("down", "suspended") or a["crashed"])
                        if HEROKU else 0),
    }
    # A project's own applications, folded onto its row. `state` and `cost`
    # travel with it because the two questions an operator asks of a hosted
    # project — is it up, what does it cost — must be answerable without
    # leaving the row.
    if HEROKU:
        env_of, account_of = hosting_context(relations)
        by_project = {}
        for a in HEROKU["apps"]:
            if a.get("project"):
                by_project.setdefault(a["project"], []).append(
                    {"name": a["name"], "state": a["state"], "cost": a["monthly_cost"],
                     "rule": a["link_rule"], "env": env_of.get(a["id"]),
                     "account": account_of.get(a["id"])})
        for r in rows:
            r["heroku"] = sorted(by_project.get(r["id"], []), key=lambda x: x["name"])
    else:
        for r in rows:
            r["heroku"] = []

    owners = [o for o, _ in Counter(r["owner"] for r in rows).most_common()]
    store = from_store()
    for r in rows:
        r["weeks"] = store["weeks"].get(r["id"], [])
        r["metrics"] = store["metrics"].get(r["id"], [])
        r["timeline"] = store["timeline"].get(r["id"], [])
        r["notes"] = store["notes"].get(r["id"], [])
    # THE QUEUE, READ-ONLY. 401 revisions sit `proposed` and the default outcome
    # for every one of them is expiry at 90 days; the only door was a terminal
    # command, so the operator could not even SEE what was waiting without
    # opening one. Deciding still needs the terminal — `tools/review.py` refuses
    # a write without one on purpose — but a queue nobody can look at is a queue
    # nobody works (audit 2026-09-09).
    PAYLOAD = {"runtime": {"projects": str(paths.DATA), "secrets": str(paths.source_path("secret_store", paths.SECRETS)), "engine": str(paths.ROOT), "home": str(paths.HOME), "python": sys.executable, "scratch": str(paths.SCRATCH)}, "rows": rows, "stats": stats, "owners": owners, "dups": dups,
                          "queue": store.get("queue") or [],
                          "digest": store.get("digest"),
                          "health": store["health"], "store_degraded": store["degraded"],
                          # Acknowledged findings are withheld from the page on
                          # purpose: the operator silenced them, and a panel that
                          # shows them anyway teaches that silencing does nothing.
                          "findings": (_findings_panel(FINDINGS)
                                       if FINDINGS else None),
                          # TWO DIFFERENT FACTS, and the page showed the weaker
                          # one as its headline. `updated_on` is when the
                          # registry's CONTENT last changed; `last_scan` is when
                          # the estate was last MEASURED. A reader asking "is
                          # this current?" wants the second, and until
                          # 2026-09-07 the first was a hardcoded literal
                          # (`OBS="2026-09-03"`) so the headline was a constant
                          #. Both are shown now, each labelled.
                          "heroku": HEROKU,
                          "creds": CREDS,
                          "env": ENVD,
                          "mcp": MCP,
                          "remote": REMOTE,
                          "google": GOOGLE,
                          "traffic": TRAFFIC,
                          "keys": KEYS,
                          "zones": ZONES,
                          "products": PRODUCTS,
                          "domains": [{
                              "name": d["name"],
                              "registrar": d.get("registrar"),
                              "expires_on": (d.get("namecheap") or {}).get("expires_on"),
                              "auto_renew": (d.get("namecheap") or {}).get("auto_renew"),
                              "status": (d.get("namecheap") or {}).get("status"),
                              "live": LIVE.get(d["name"]),
                              "projects": sorted(domain_owner.get(d["name"], [])),
                          } for d in DOMAINS],
                          "updated": pdoc.get("updated_on", ""),
                          "measured": store["health"].get("last_scan", "")}
    build.last_payload = PAYLOAD                                                  
    payload = json.dumps(PAYLOAD, ensure_ascii=False)
    return (TEMPLATE.replace("__PAGE__", "").replace("__NAV__", "").replace("__CARDS__", "")
            .replace("__TITLE__", "Проекты — операторский реестр")
            .replace("__H1__", "Проекты — операторский реестр")
            .replace("__SUB__", "Реестр из подключённых источников: папки проектов, репозитории и заметки. "
                     "Каждая связь проект↔репозиторий несёт правило, которым проведена.")
            .replace("__DATA__", payload.replace("</", "<\\/")))


def build_pages(payload: dict) -> dict[str, int]:
    """docs/dashboard/<page>.html for every page in `shell.PAGES`, from the
    same template and the same data, each carrying only what it renders
. Returns bytes written per page."""
    import shell
    paths.DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    page_tpl, css, js = shell.split_template(TEMPLATE)
    atomic.write_text(paths.DASHBOARD_DIR / shell.ASSET_CSS, css)
    atomic.write_text(paths.DASHBOARD_DIR / shell.ASSET_JS, js)
    sizes = {}
    for name, _title, _kind in shell.PAGES:
        html = shell.page_html(page_tpl, name, payload)
        atomic.write_text(paths.DASHBOARD_DIR / f"{name}.html", html)
        sizes[name] = len(html.encode("utf-8"))
    return sizes


TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script>
/* THE THEME, BEFORE FIRST PAINT (backlog D-04). The choice is the reader's —
   «система», «светлая» or «тёмная» — kept in localStorage; applying it from the
   main script at the bottom of the page would paint one theme and then the
   other. Guarded: the smoke harness has no localStorage and no matchMedia. */
(function () {
  var mode = "system";
  try { mode = localStorage.getItem("observatory.theme") || "system"; } catch (e) {}
  var dark = mode === "dark" || (mode === "system" && typeof matchMedia === "function"
             && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme-mode", mode);
})();
</script>
<style>
/* DESIGN TOKENS. Every colour, radius, size and duration below is a variable,
 * so the dark theme only has to redefine values, never rules. */
:root {
  --bg: #f7f8fa;
  --panel: #ffffff;
  --panel-2: #f7f8fa;
  --ink: #1a1f2b;
  --muted: #5b6472;
  --border: #e6e9ef;
  --border-strong: #d7dce4;
/* The accent pair: a strong colour for links and focus, a weak tint for
 * selected and targeted rows. */
  --accent: #2f6feb;
  --accent-weak: #eaf0fe;
  --accent-ink: #ffffff;                                              
  --ok: #1a7f37;
  --ok-weak: #e6f4ea;
  --warn: #9a6700;
  --warn-weak: #fff3d6;
  --danger: #d1242f;
  --danger-weak: #fde8e9;
  --info: #2f6feb;
  --info-weak: #eaf0fe;

  --r-control: 6px;
  --r-card: 10px;
  --r-pill: 999px;


  --motion-ease: cubic-bezier(0.2, 0, 0, 1);                                    
  --dur-hover: 0.12s;                                   

  --font-ui: -apple-system, "SF Pro", "Segoe UI", sans-serif;
  --font-data: ui-monospace, "SF Mono", Menlo, monospace;

/* TYPE SCALE. Five sizes and no more; a new element takes one of these
 * rather than inventing a sixth. */
  --t-chip: 11px;                  
  --t-label: 12px;                                     
  --t-body: 13px;                                        
  --t-section: 20px;                       
  --t-page: 28px;                 

/* SPACING, on a 4px grid. */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;

  background-color: var(--bg);
  color: var(--ink);
  color-scheme: light;                                                    
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0f1218;
  --panel: #161b24;
  --panel-2: #1b212c;
  --ink: #e8ecf3;
  --muted: #8a93a6;
  --border: #232a36;
  --border-strong: #2c3441;
  --accent: #4b8bff;
  --accent-weak: #1b2740;
  --accent-ink: #0f1218;                                                             
  --ok: #3fb960;
  --ok-weak: #12281a;
  --warn: #d9a93f;
  --warn-weak: #2b2210;
  --danger: #e5534b;
  --danger-weak: #2d1517;
  --info: #4b8bff;
  --info-weak: #1b2740;
}

/* Reduced motion: hover transitions collapse to instant. */

@media (prefers-reduced-motion: reduce) {
  :root {
    --dur-hover: 0s;
  }
}

/* BASE */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 400 var(--t-body)/1.5 var(--font-ui);
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-control); }
.mono { font-family: var(--font-data); font-variant-numeric: tabular-nums; }

/* HEADER */
header {
  padding: var(--space-5) var(--space-5) var(--space-4);
  background: var(--panel); border-bottom: 1px solid var(--border);
}
h1 { margin: 0 0 var(--space-1); font: 700 var(--t-page)/1.2 var(--font-ui); letter-spacing: -.01em; }
.sub { color: var(--muted); max-width: 74ch; }

/* TILES and the review queue rows */
.tiles { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
.tile {
  border: 1px solid var(--border); border-radius: var(--r-card);
  padding: var(--space-2) var(--space-3); min-width: 104px; background: var(--panel);
}
.qrow { display: grid; grid-template-columns: 128px 1fr; gap: var(--space-3);
  padding: var(--space-2) 0; border-bottom: 1px solid var(--border);
  font-size: var(--t-body); }
.qrow:last-child { border-bottom: 0; }
.qrow .qacts { margin-top: var(--space-2); display: flex; gap: var(--space-2); }
/* Filter bar above a list: type selector, free-text query, shown count. */
.verbs { display: flex; flex-wrap: wrap; gap: 4px; }
.fbar { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center;
  margin: var(--space-2) 0 var(--space-3); }
.fbar .ftype, .fbar .fq { font: 400 var(--t-body) var(--font-ui); color: var(--ink);
  background: var(--panel); border: 1px solid var(--border); border-radius: var(--r-control);
  padding: 4px 8px; }
.fbar .fq { min-width: 220px; }
.fbar .fshown { font: 400 var(--t-chip) var(--font-data); color: var(--muted); margin-left: auto; }
.f.fhide { display: none !important; }
.f:target { background: var(--accent-weak); }
.fsubj { font-family: var(--font-data); font-size: var(--t-chip); margin-left: 6px; }
.fperma { color: var(--muted); text-decoration: none; margin-left: 6px; font-family: var(--font-data); }
.fperma:hover { color: var(--ink); }
.filters { font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  margin: var(--space-3) var(--space-5) 0; }
.filters b { color: var(--ink); font-weight: 600; }
tr:target > td { background: var(--accent-weak); }
/* A folded group shows its first row and hides the rest behind a toggle. */
tbody.grp.folded tr + tr { display: none; }
.grp-fold { font: inherit; color: inherit; background: none; border: 0; padding: 0;
  cursor: pointer; text-align: left; width: 100%; }
.grp-fold::before { content: "▸ "; color: var(--muted); }
.grp-fold[aria-expanded="true"]::before { content: "▾ "; }
/* Sortable column headers: the header is a button, the arrow follows
 * aria-sort. */
th[data-sort] .sort { font: inherit; color: inherit; background: none; border: 0; padding: 0;
  cursor: pointer; text-align: inherit; }
th[data-sort] .sort:hover, th[data-sort] .sort:focus-visible { text-decoration: underline; }
th[aria-sort="ascending"] .sort::after { content: " ▴"; color: var(--muted); }
th[aria-sort="descending"] .sort::after { content: " ▾"; color: var(--muted); }
/* Long identifiers in cells wrap anywhere rather than widening the table. */
td .mono { overflow-wrap: anywhere; }
.qrow .qm { color: var(--muted); font-family: var(--font-data); font-size: var(--t-chip); }
.tile.more-tiles { cursor: pointer; border-style: dashed; font: inherit; text-align: left;
  color: var(--muted); }
.tile.more-tiles:hover { border-color: var(--accent); color: var(--ink); }
.tile b { display: block; font: 600 var(--t-section)/1.2 var(--font-data);
  font-variant-numeric: tabular-nums; }
.tile span { color: var(--muted); font-size: var(--t-label);
  text-transform: uppercase; letter-spacing: .1em; }

/* FINDINGS */
#findings { margin: var(--space-4) var(--space-5) 0; }
.fh { display: flex; align-items: baseline; gap: var(--space-3);
  font: 600 var(--t-label) var(--font-ui); text-transform: uppercase;
  letter-spacing: .1em; color: var(--muted); margin-bottom: var(--space-2); }
.fh .when { font-family: var(--font-data); text-transform: none; letter-spacing: 0; }
.flist { border: 1px solid var(--border); border-radius: var(--r-card);
  background: var(--panel); }
.f { display: flex; gap: var(--space-3); align-items: baseline; flex-wrap: wrap;
  padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border); }
.f:last-child { border-bottom: 0; }
.f .t { font-weight: 600; }
.f .d { color: var(--muted); flex: 1 1 24ch; }
.f .due { font-family: var(--font-data); font-size: var(--t-chip); color: var(--muted);
  white-space: nowrap; }
.f .act { font-size: var(--t-chip); color: var(--muted); font-style: italic; }
.tier { font-size: var(--t-chip); color: var(--muted); }
/* Lower-severity findings hide while the list is folded. */
.flist.folded .f.finfo, .flist.folded .f.fwarning { display: none; }
button.fold { margin: var(--space-2) 0 0 var(--space-3); }
/* Deltas: a rise is a warning colour, a fall is calm. */
.delta { font-family: var(--font-data); }
.delta.up { color: var(--warn); }
.delta.down { color: var(--ok); }
.spark { display: flex; align-items: center; gap: 4px; color: var(--muted);
         font-size: var(--t-chip); font-family: var(--font-data); }
.spark svg { display: block; }
/* The sessions line of a sparkline is drawn fainter than commits. */
.spark-sess { opacity: 0.6; }
.panel { padding: 16px; margin-bottom: 12px; }

/* TABS */
.tabs { display: flex; gap: var(--space-2); align-items: flex-end;
  border-bottom: 1px solid var(--border); margin: var(--space-4) 0 0; }
.tab { appearance: none; border: 1px solid transparent; border-bottom: 0;
  background: none; color: var(--muted); cursor: pointer;
  font: 500 var(--t-body)/1 var(--font-ui);
  padding: var(--space-2) var(--space-3); border-radius: var(--r-control) var(--r-control) 0 0;
  transition: color var(--dur-hover) var(--motion-ease); }
.tab:hover { color: var(--ink); }
.tab[aria-selected="true"] { background: var(--panel); border-color: var(--border);
  color: var(--ink); font-weight: 600; margin-bottom: -1px; }
.tab .n { font-family: var(--font-data); font-variant-numeric: tabular-nums;
  color: var(--muted); margin-left: var(--space-1); }
.seg[hidden] { display: none; }
/* STATUS DOT: a coloured marker beside a state word. */
.st { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.st > * { white-space: normal; }
.st i { width: 8px; height: 8px; border-radius: var(--r-pill); flex: none; }
.st-running i { background: var(--ok); }
.st-down i, .st-suspended i { background: var(--danger); }
.st-resources-only i { background: var(--warn); }
.st-idle i { background: var(--border-strong); }
.unlinked { color: var(--warn); }
.dhead { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.dmeta { font-size: var(--t-chip); color: var(--muted); margin: 0 0 8px; }
.dlist { margin: 4px 0 12px; padding-left: 18px; }
.dlist li { font-size: var(--t-chip); line-height: 1.5; }
.plink { color: inherit; text-decoration: none; border-bottom: 1px solid var(--border); }
.plink:hover, .plink:focus { border-bottom-color: var(--accent); }
.health { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 4px 16px; margin: 8px 0; }
.hrow { display: flex; justify-content: space-between; gap: 8px;
        font-size: var(--t-chip); color: var(--muted); }
.hrow b { font-family: var(--font-data); color: var(--ink); font-weight: 400; }
@media (max-width: 1100px) { #findings { margin: var(--space-4) var(--space-3) 0; } }

/* CONTROLS: the sticky search and filter bar. */
.controls {
  position: sticky; top: var(--topbar, 0px); z-index: 20;
  display: flex; flex-wrap: wrap; gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  background: var(--panel); border-bottom: 1px solid var(--border);
}
input[type=search], select {
  font: 400 var(--t-body) var(--font-ui); color: var(--ink);
  background: var(--panel); border: 1px solid var(--border-strong);
  border-radius: var(--r-control); padding: 6px var(--space-2);
}
input[type=search] { flex: 1; min-width: 240px; }
.seg { display: flex; flex-wrap: wrap; gap: var(--space-1); }
/* View switch: pill buttons, pressed state is the active one. */
.view { display: flex; gap: var(--space-1); margin: var(--space-2) var(--space-5) 0; justify-content: flex-end; }
.chip-btn {
  font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  background: var(--panel); border: 1px solid var(--border-strong);
  border-radius: var(--r-pill); padding: 3px 10px; cursor: pointer;
  transition: background var(--dur-hover) var(--motion-ease),
              border-color var(--dur-hover) var(--motion-ease),
              color var(--dur-hover) var(--motion-ease);
}
.chip-btn:hover { background: var(--panel-2); }
.chip-btn[aria-pressed="true"] {
  background: var(--accent-weak); border-color: var(--accent); color: var(--ink);
}

/* A value shown on request: monospace, selectable in one click, wrapping
 * anywhere. */
code.val {
  display: block; font: 400 var(--t-chip) var(--font-data);
  color: var(--ink); background: var(--danger-weak, var(--panel-2));
  border: 1px solid var(--border-strong); border-radius: var(--r-control);
  padding: 4px 6px; margin-bottom: 4px;
  word-break: break-all; user-select: all;
}

/* Transient confirmation toast at the bottom of the viewport. */
.toast {
  position: fixed; left: 50%; bottom: var(--space-5, 24px);
  transform: translateX(-50%); z-index: 40;
  font: 400 var(--t-chip) var(--font-data); color: var(--ink);
  background: var(--panel-2); border: 1px solid var(--accent);
  border-radius: var(--r-pill); padding: 8px 16px; max-width: 80vw;
}

main { padding: 0 var(--space-5) var(--space-6); }

/* MAIN */

/* CARD: the panel that holds a table. */
.card { background: var(--panel); border: 1px solid var(--border);
  border-radius: var(--r-card); margin-top: var(--space-4); }

/* TABLE */
table { border-collapse: separate; border-spacing: 0; width: 100%;
  table-layout: fixed; }
/* Fixed layout with explicit column widths, so a long cell cannot push the
 * other columns around. */
col.c-name { width: 11%; } col.c-site { width:  8%; }
col.c-dir  { width:  9%; } col.c-repo { width: 16%; }
col.c-desc { width: 12%; } col.c-stack{ width:  8%; }
col.c-when { width: 13%; } col.c-host { width:  9%; }
col.c-users{ width:  8%; } col.c-note { width:  6%; }
thead th {
  position: sticky; top: var(--stick, 56px); z-index: 10;
  background: var(--panel-2); color: var(--muted);
  font: 600 var(--t-label) var(--font-ui);
  text-transform: uppercase; letter-spacing: .1em;
  text-align: left; padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-strong); white-space: nowrap;
}
thead th:first-child { border-top-left-radius: var(--r-card); }
thead th:last-child  { border-top-right-radius: var(--r-card); }

/* Group header rows */
tbody.grp th {
  text-align: left; padding: var(--space-3) var(--space-3) var(--space-2);
  font: 600 var(--t-label) var(--font-ui);
  text-transform: uppercase; letter-spacing: .1em; color: var(--muted);
  border-bottom: 1px solid var(--border-strong);
  border-top: 1px solid var(--border);
}
tbody.grp:first-of-type th { border-top: 0; }
tbody.grp th .n { font-family: var(--font-data); font-variant-numeric: tabular-nums;
  color: var(--muted); }
tbody td {
  padding: var(--space-2) var(--space-3); vertical-align: top;
  border-bottom: 1px solid var(--border);
}
tbody.grp tr:last-child td { border-bottom: 0; }
tbody tr { transition: background var(--dur-hover) var(--motion-ease); }
tbody tr:hover { background: var(--panel-2); }
td.num { text-align: right; font-family: var(--font-data);
  font-variant-numeric: tabular-nums; white-space: nowrap; }
/* Numeric cells align right and do not wrap; their captions may. */
td.num .tier, td.num .anchor { white-space: normal; }

.name { font-weight: 600; overflow-wrap: anywhere; }
.nwo, .folder { overflow-wrap: anywhere; }
/* The "more" control that unfolds a long list inside a cell. */
.more {
  font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  background: transparent; border: 1px dashed var(--border-strong);
  border-radius: var(--r-pill); padding: 1px 8px; margin-top: 2px; cursor: pointer;
  transition: background var(--dur-hover) var(--motion-ease),
              color var(--dur-hover) var(--motion-ease);
}
.more:hover { background: var(--panel-2); color: var(--ink); }
.repos.folded .item:nth-child(n+4) { display: none; }
.anchor { color: var(--muted); font-size: var(--t-chip); font-family: var(--font-data); }
.desc { color: var(--muted); max-width: 52ch;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.none { color: var(--muted); opacity: .55; }

/* CHIPS */
.chip {
  display: inline-flex; align-items: center; gap: 5px;
  font: 400 var(--t-chip) var(--font-data); color: var(--ink);
  background: var(--panel); border: 1px solid var(--border-strong);
  border-radius: var(--r-pill); padding: 1px 8px; margin: 1px 3px 1px 0;
  /* A chip may wrap its own text rather than overflow its cell. */
  white-space: normal;
}
.chip .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); flex: none; }
.chip.ok { background: var(--ok-weak); border-color: var(--ok); }
.chip.ok .dot { background: var(--ok); }
.chip.warn { background: var(--warn-weak); border-color: var(--warn); }
.chip.warn .dot { background: var(--warn); }
.chip.danger { background: var(--danger-weak); border-color: var(--danger); }
.chip.danger .dot { background: var(--danger); }

/* REPOSITORIES inside a row */
.repos { display: flex; flex-direction: column; gap: 3px; }
.repo { display: flex; align-items: baseline; gap: var(--space-2); flex-wrap: wrap; }
.repo .nwo { font-family: var(--font-data); font-size: var(--t-chip); }
/* A superseded repository is shown struck through and faded. */
.repo.sub { opacity: .62; }
.repo.sub .nwo { text-decoration: line-through; text-decoration-thickness: 1px; }
.rule {
  font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  padding-left: var(--space-3); border-left: 1px solid var(--border);
  margin-left: 2px; max-width: 60ch;
}
/* Site links: monospace, one per line, wrapping anywhere. */
.sites a { font-family: var(--font-data); font-size: var(--t-chip); display: block;
  overflow-wrap: anywhere; }
/* TOP BAR: brand, page links and the theme switch, sticky above
 * everything else. */
.topbar { position: sticky; top: 0; z-index: 30; display: flex; flex-wrap: wrap;
  align-items: center; gap: var(--space-2) var(--space-4);
  padding: var(--space-2) var(--space-5); background: var(--panel);
  border-bottom: 1px solid var(--border); }
.brand { font-weight: 600; color: var(--ink); text-decoration: none; font-size: var(--t-body);
  letter-spacing: .02em; padding: 6px 0; }
.theme { display: inline-flex; margin-left: auto; border: 1px solid var(--border);
  border-radius: var(--r-pill); overflow: hidden; }
.theme button { font: 400 var(--t-chip) var(--font-data); color: var(--muted);
  background: var(--panel); border: 0; padding: 5px 10px; cursor: pointer; }
.theme button + button { border-left: 1px solid var(--border); }
.theme button[aria-pressed="true"] { background: var(--accent-weak); color: var(--ink); }
.theme button:hover { background: var(--panel-2); }
.pages { display: flex; flex-wrap: wrap; gap: var(--space-2); margin: 0; }
.pages a.pg { text-decoration: none; padding: 6px 12px; border: 1px solid var(--border);
  border-radius: var(--r-pill); background: var(--panel); color: var(--ink); font-size: var(--t-chip); }
.pages a.pg[aria-current="page"] { background: var(--ink); color: var(--panel); border-color: var(--ink); }
.pages a.pg .n { font-family: var(--font-data); font-variant-numeric: tabular-nums; margin-left: 4px; opacity: .7; }
.mods { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-3); margin: var(--space-3) 0; }
.mods a.mod { display: block; text-decoration: none; color: inherit; padding: var(--space-3); }
.mods a.mod b { display: block; margin-bottom: 4px; }
body[data-page] .tabs, body[data-page] .controls, body[data-page] .seg, body[data-page] .view { display: none; }
body[data-page="projects"] .controls, body[data-page="projects"] #seg-projects, body[data-page="projects"] #view-projects,
body[data-page="heroku"] .controls, body[data-page="heroku"] #seg-heroku,
body[data-page="domains"] .controls, body[data-page="domains"] #seg-domains,
body[data-page="creds"] .controls, body[data-page="creds"] #seg-creds,
body[data-page="env"] .controls, body[data-page="env"] #seg-env,
body[data-page="mcp"] .controls, body[data-page="mcp"] #seg-mcp,
body[data-page="traffic"] .controls, body[data-page="traffic"] #seg-traffic { display: flex; }
/* SPLIT PAGES. Each page shows only its own controls and sections; the
 * rules below hide what belongs to another page. */
body[data-page]:not([data-page="index"]):not([data-page="findings"]) #findings { display: none; }
body[data-page]:not([data-page="index"]):not([data-page="health"]) #tiles,
body[data-page]:not([data-page="index"]):not([data-page="health"]) #more-tiles { display: none; }
/* Health-only and projects-only sections. */
body[data-page]:not([data-page="health"]) #observer,
body[data-page]:not([data-page="health"]) #queue-s { display: none; }
body[data-page]:not([data-page="projects"]) #reading,
body[data-page]:not([data-page="projects"]) #dups-s { display: none; }
body[data-page="index"] #out, body[data-page="findings"] #out, body[data-page="health"] #out,
body[data-page="index"] #panel, body[data-page="findings"] #panel, body[data-page="health"] #panel { display: none; }
body[data-page="findings"] .flist.folded .finfo, body[data-page="findings"] .flist.folded .fwarning { display: block; }
/* The index page puts the inventory tiles first and the work tiles after
 * them. */
body[data-page="index"] header { display: flex; flex-direction: column; }
body[data-page="index"] header > #tiles { order: 1; }
body[data-page="index"] header > #work-h, body[data-page="index"] header > #work { order: 2; }
body[data-page]:not([data-page="index"]):not([data-page="health"]) #work,
body[data-page]:not([data-page="index"]):not([data-page="health"]) #work-h { display: none; }
#work-h { font-size: var(--t-chip); letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); margin: var(--space-3) 0 var(--space-2); }
.tile.name { text-decoration: none; color: inherit; }
.tile.name b { font-size: var(--t-body); }
.f.ftype-folded:not(.ftype-open) { display: none; }
.silenced { margin: 8px 0; } .silenced summary { cursor: pointer; font-size: var(--t-chip); color: var(--muted); }
.fsilenced { opacity: .75; }
.folder { font-family: var(--font-data); font-size: var(--t-chip); color: var(--muted); display: block; }

footer {
  margin-top: var(--space-6); padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border); color: var(--muted); font-size: var(--t-chip);
}
footer h3 { margin: 0 0 var(--space-1); font: 600 var(--t-label) var(--font-ui);
  text-transform: uppercase; letter-spacing: .1em; }
footer ul { margin: 0 0 var(--space-3); padding-left: var(--space-4); }
.empty { padding: var(--space-6); text-align: center; color: var(--muted); }

/* NARROW SCREENS: a table row becomes a stacked card, each cell labelled
 * from its data-label attribute. */
@media (max-width: 1100px) {
  table, tbody, tr, td, tbody.grp th { display: block; width: 100%; }
  thead { display: none; }
  tbody.grp th { border-top: 0; }
  tbody tr { border-bottom: 1px solid var(--border-strong); padding: var(--space-2) 0; }
  tbody td { border: 0; padding: 2px var(--space-3); }
  tbody td::before {
    content: attr(data-label); display: block;
    font: 600 var(--t-chip) var(--font-ui); text-transform: uppercase;
    letter-spacing: .1em; color: var(--muted); margin-top: var(--space-2);
  }
  td.num { text-align: left; }
  td.e { display: none; }                                             
  .desc { max-width: none; }
}
</style>
</head>
<body>
__NAV__
<header>
  <h1>__H1__</h1>
  <p class="sub">__SUB__ Измерено <span class="mono" id="upd"></span>, содержимое
  реестра менялось <span class="mono" id="content-stamp"></span>.</p>
<div class="tiles" id="tiles"></div>
  <h3 id="work-h">Движение</h3>
  <div class="tiles work" id="work"></div>
  <section id="findings"></section>
</header>

<nav class="tabs" role="tablist" aria-label="Что показывать">
  <button class="tab" type="button" id="tab-projects" role="tab" aria-selected="true"
          aria-controls="out">Проекты <span class="n" id="n-projects"></span></button>
  <button class="tab" type="button" id="tab-heroku" role="tab" aria-selected="false"
          aria-controls="out">Heroku <span class="n" id="n-heroku"></span></button>
  <button class="tab" type="button" id="tab-domains" role="tab" aria-selected="false"
          aria-controls="out">Домены <span class="n" id="n-domains"></span></button>
  <button class="tab" type="button" id="tab-creds" role="tab" aria-selected="false"
          aria-controls="out">Ключи <span class="n" id="n-creds"></span></button>
  <button class="tab" type="button" id="tab-env" role="tab" aria-selected="false"
          aria-controls="out">ENV <span class="n" id="n-env"></span></button>
  <button class="tab" type="button" id="tab-mcp" role="tab" aria-selected="false"
          aria-controls="out">MCP <span class="n" id="n-mcp"></span></button>
</nav>

<div class="controls">
  <input type="search" id="q" placeholder="Поиск: имя, описание, репозиторий, папка, домен, стек"
         aria-label="Поиск по реестру">
  <select id="owner" aria-label="Владелец"></select>
  <div class="seg" id="seg-projects" role="group" aria-label="Фильтры проектов">
    <button class="chip-btn" data-f="heroku" aria-pressed="false">есть Heroku</button>
    <button class="chip-btn" data-f="noheroku" aria-pressed="false">нет Heroku</button>
    <button class="chip-btn" data-f="site" aria-pressed="false">есть сайт</button>
    <button class="chip-btn" data-f="note" aria-pressed="false">есть заметка</button>
    <button class="chip-btn" data-f="nonote" aria-pressed="false">нет заметки</button>
    <button class="chip-btn" data-f="folder" aria-pressed="false">есть папка</button>
    <button class="chip-btn" data-f="dirty" aria-pressed="false">незакоммиченное</button>
    <button class="chip-btn" data-f="unsynced" aria-pressed="false">клон не синхронен</button>
    <button class="chip-btn" data-f="dead" aria-pressed="false">сайт не резолвится</button>
    <button class="chip-btn" data-f="drift" aria-pressed="false">объявлен живым, измерен мёртвым</button>
    <button class="chip-btn" data-f="owned" aria-pressed="false">только своё</button>
  </div>
  <!-- D-21: a VIEW switch, not a filter. «правила» changes what each
       row shows, never which rows show — so it sits outside the filter group,
       and `narrowing()`, which reads chips inside `.seg` only, does not count
       it among the filters. -->
  <div class="view" id="view-projects" role="group" aria-label="Вид таблицы">
    <button class="chip-btn" data-f="rules" aria-pressed="false" title="показать правило каждой связи проект↔репозиторий">правила: показать</button>
  </div>
  <div class="seg" id="seg-heroku" role="group" aria-label="Фильтры приложений" hidden>
    <button class="chip-btn" data-f="noproject" aria-pressed="false">нет проекта</button>
    <button class="chip-btn" data-f="nofolder" aria-pressed="false">нет папки</button>
    <button class="chip-btn" data-f="norepo" aria-pressed="false">нет репозитория</button>
    <button class="chip-btn" data-f="down" aria-pressed="false">не работает</button>
    <button class="chip-btn" data-f="waste" aria-pressed="false">платит впустую</button>
    <button class="chip-btn" data-f="stale" aria-pressed="false">год без деплоя</button>
    <button class="chip-btn" data-f="oldstack" aria-pressed="false">устаревший стек</button>
  </div>
  <div class="seg" id="seg-domains" role="group" aria-label="Фильтры доменов" hidden>
    <button class="chip-btn" data-f="d-noproject" aria-pressed="false">нет проекта</button>
    <button class="chip-btn" data-f="d-dark" aria-pressed="false">не резолвится</button>
    <button class="chip-btn" data-f="d-http" aria-pressed="false">HTTP ошибка</button>
    <button class="chip-btn" data-f="d-expiring" aria-pressed="false">истекает ≤90 дней</button>
    <button class="chip-btn" data-f="d-norenew" aria-pressed="false">без автопродления</button>
    <button class="chip-btn" data-f="d-unmeasured" aria-pressed="false">не измерен</button>
  </div>
  <div class="seg" id="seg-creds" role="group" aria-label="Фильтры ключей" hidden>
    <button class="chip-btn" data-f="c-leaked" aria-pressed="false">утечки не закрыты</button>
    <button class="chip-btn" data-f="c-unclaimed" aria-pressed="false">ничей</button>
    <button class="chip-btn" data-f="c-shared" aria-pressed="false">общий: 2+ проекта</button>
    <button class="chip-btn" data-f="c-norotate" aria-pressed="false">никогда не ротировался</button>
    <button class="chip-btn" data-f="c-disabled" aria-pressed="false">отключён</button>
    <button class="chip-btn" data-f="c-untracked" aria-pressed="false">не в хранилище</button>
  </div>
  <div class="seg" id="seg-traffic" role="group" aria-label="Фильтры трафика" hidden>
    <button class="chip-btn" data-f="t-unclaimed" aria-pressed="false">нет проекта</button>
    <button class="chip-btn" data-f="t-linked" aria-pressed="false">привязана</button>
    <button class="chip-btn" data-f="t-quiet" aria-pressed="false">нет пользователей</button>
    <button class="chip-btn" data-f="t-app" aria-pressed="false">только приложение</button>
  </div>
  <div class="seg" id="seg-mcp" role="group" aria-label="Фильтры MCP" hidden>
    <button class="chip-btn" data-f="m-url" aria-pressed="false">ключ в URL</button>
    <button class="chip-btn" data-f="m-down" aria-pressed="false">не отвечает</button>
    <button class="chip-btn" data-f="m-auth" aria-pressed="false">нужен вход</button>
    <button class="chip-btn" data-f="m-alone" aria-pressed="false">только в одном агенте</button>
  </div>
  <div class="seg" id="seg-env" role="group" aria-label="Фильтры ENV" hidden>
    <button class="chip-btn" data-f="e-shared" aria-pressed="false">общее с другим проектом</button>
    <button class="chip-btn" data-f="e-reuse" aria-pressed="false">пусто, есть в другом проекте</button>
    <button class="chip-btn" data-f="e-git" aria-pressed="false">в git</button>
    <button class="chip-btn" data-f="e-open" aria-pressed="false">читает не только владелец</button>
    <button class="chip-btn" data-f="e-all" aria-pressed="false">+ конфиг и пустые</button>
    <button class="chip-btn" data-f="e-tpl" aria-pressed="false">+ шаблоны</button>
  </div>
</div>

<div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
<section id="panel" class="card panel" role="dialog" aria-labelledby="panel-title" hidden></section>
__CARDS__
<div id="list-tools" class="list-tools"></div>
<main id="out" aria-live="polite"></main>

<footer>
  <section id="reading">
    <h3>Как это читать</h3>
    <p>Правило под репозиторием — причина, по которой он привязан к проекту: имя папки,
    упоминание в заметке, организация, или связь, проверенная вручную. Репозиторий,
    вытеснённый другим или пустой, показан приглушённо и зачёркнуто и называет преемника —
    он не равноправен тому, что его заменил.</p>
  </section>
  <section id="observer">
    <h3>Состояние наблюдателя</h3>
    <p>Что обсерватория знает о себе: когда она смотрела в последний раз, сколько
    собрала и сколько выводов ждёт решения человека. Пусто здесь означает, что
    локального хранилища нет — реестр при этом читается по-прежнему.</p>
    <div id="health" class="health"></div>
  </section>
  <section id="queue-s">
    <h3 id="queue-h">Ждёт решения человека</h3>
    <div id="queue"></div>
  </section>
  <section id="dups-s">
    <h3 id="dups-h">Имена репозиториев у нескольких владельцев</h3>
    <ul id="dups"></ul>
  </section>
</footer>

<script>
// THE DATA. `__DATA__` is replaced by the builder with the JSON payload; the
// runtime block carries the paths commands on this page are built from.
const PAGE = "__PAGE__";
const TABLE_PAGES = ["projects", "domains", "heroku", "creds", "env", "mcp", "traffic"];
const D = __DATA__;
const RUNTIME = D.runtime || {};
const shellArg = value => "'" + String(value).replace(/'/g, "'\\''") + "'";
const projectFile = value => String(RUNTIME.projects || ".").replace(/\/$/, "") + "/" + value;
const secretFile = value => String(RUNTIME.secrets || ".").replace(/\/$/, "") + "/" + value;
const engineCommand = (file, args = []) =>
  (RUNTIME.home ? "env " + shellArg("OBSERVATORY_HOME=" + RUNTIME.home) + " " : "") +
  shellArg(RUNTIME.python || "python3") + " " +
  shellArg(String(RUNTIME.engine || ".").replace(/\/$/, "") + "/" + file) +
  args.map(value => " " + shellArg(value)).join("");
const toolCommand = (name, args = []) => engineCommand("tools/" + name, args);
const cliCommand = (...args) => engineCommand("observatory.py", args);
const privateInput = command => command + " < " + shellArg("/absolute/path/to/private-input");

// __SHARED_BELOW__ — the split pages keep everything above this line inline
// Everything below is shared by every page and may move to a separate
// script file. The rows are normalised first, so that every renderer can
// assume the list fields exist rather than guarding each access.
for (const r of D.rows || []) {
  r.folders = r.folders || [];
  r.stack = r.stack || [];
  r.repos = r.repos || [];
  r.sites = r.sites || [];
}
const E = s => String(s == null ? "" : s).replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// THE THEME SWITCH. The choice is applied before first paint in the head;
// this keeps the buttons in step with it and follows the system setting
// while the mode is "system".
const mq = window.matchMedia("(prefers-color-scheme: dark)");
const THEME_KEY = "observatory.theme";
function themeMode() {
  try { return localStorage.getItem(THEME_KEY) || "system"; } catch (e) { return "system"; }
}
function applyTheme(mode) {
  const dark = mode === "dark" || (mode === "system" && mq.matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme-mode", mode);
  document.querySelectorAll(".theme button[data-mode]").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
}
applyTheme(themeMode());
mq.addEventListener("change", () => { if (themeMode() === "system") applyTheme("system"); });
document.querySelectorAll(".theme button[data-mode]").forEach(b => b.addEventListener("click", () => {
  try { localStorage.setItem(THEME_KEY, b.dataset.mode); } catch (e) {}
  applyTheme(b.dataset.mode);
}));
// `/` focuses the search box, unless the reader is already typing.
document.addEventListener("keydown", ev => {
  if (ev.key !== "/" || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const tag = (ev.target && ev.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return;
  const q = PAGE === "findings" ? document.querySelector(".fq") : document.getElementById("q");
  if (q && q.offsetParent) { ev.preventDefault(); q.focus(); q.select(); }
});

// Two timestamps, each labelled: when the estate was last MEASURED, and when
// the registry's content last changed.
document.getElementById("upd").textContent = D.measured
  ? D.measured.replace("T", " ").replace("Z", " UTC")
  : "не измерено";
const cs = document.getElementById("content-stamp");
if (cs) cs.textContent = D.updated || "—";
const S = D.stats;
// INVENTORY TILES. The primary set is always visible; the rest sit behind a
// "more" control so the header stays short.
const TILES_PRIMARY = [
  ["проектов", S.projects], ["репозиториев", S.repositories],
  ["приложений Heroku", S.heroku_apps], ["не работает", S.heroku_down],
  ["доменов", S.domains], ["сайт не резолвится", S.dead_site],
  ["клон не синхронен", S.unsynced], ["Heroku $/мес", Math.round(S.heroku_cost)],
];
const TILES_REST = [
  ["владельцев", S.owners], ["с сайтом", S.with_site], ["с папкой", S.with_folder],
  ["с заметкой", S.with_note], ["без заметки", S.no_note],
  ["архивных проектов", S.archived], ["архивных репо", S.archived_repos],
  ["неактивных репо", S.inactive_repos], ["доменов без проекта", S.domains_no_row],
  ["Heroku без проекта", S.heroku_unlinked],
  // Local state of the working copies, and the credential counts.
  ["грязных рабочих копий", S.dirty], ["ключей в реестре", S.creds],
  ["ключей утекло", S.creds_leaked], ["ключей без проекта", S.creds_unclaimed],
];
// DRIFT: projects declared active whose measured activity says dormant or
// cold — a claim and a measurement that disagree.
const DRIFT = D.rows.filter(r => r.lifecycle === "active"
                            && (r.tier === "dormant" || r.tier === "cold")).length;
// WORK TILES: what happened, over the rolling windows the builder computes.
// A key absent from the stats (no store) is simply not shown.
const WORK_KEYS = ["коммитов за 7 дн", "проектов в работе, 7 дн",
                   "коммитов за 28 дн", "проектов в работе, 28 дн",
                   "коммитов ни на одном remote"];
const TILES_WORK = WORK_KEYS.filter(k => S[k] != null).map(k => [k, S[k]]);
const tileHTML = ts => ts.map(([k, v]) =>
  `<div class="tile"><b>${v}</b><span>${k}</span></div>`).join("");
{
  const host = document.getElementById("work");
  const top = S["больше всего работы, 28 дн"];
  // The busiest project is a NAME, so it is a link to that project rather
  // than a number in a tile.
  if (host) host.innerHTML = TILES_WORK.length
    ? tileHTML(TILES_WORK) + (top
        ? `<a class="tile name" href="projects.html#project:${E(top)}"><b>${E(top)}</b>` +
          `<span>больше всего работы, 28 дн</span></a>` : "")
    : '<div class="tile"><b>—</b><span>хранилища нет, движение не измерено</span></div>';
}
  // An empty registry says how to fill it, instead of showing a row of zeros
  // that would read as "measured, and nothing there".
document.getElementById("tiles").innerHTML = !D.rows.length
  ? `<div class="tile empty-estate"><b>—</b><span>реестр пуст: ни одного проекта ещё не измерено —
       <button class="chip-btn" type="button" data-copy="${E(cliCommand("local"))}" title="скопировать команду">${E(cliCommand("local"))}</button>
       соберёт его из этой машины</span></div>`
  : tileHTML(TILES_PRIMARY) +
  (DRIFT ? `<a class="tile" href="projects.html?f=drift"><b>${DRIFT}</b>` +
           `<span>объявлены живыми, измерены мёртвыми</span></a>` : "") +
  `<button class="tile more-tiles" id="more-tiles" type="button" aria-expanded="false"
     ><b>+${TILES_REST.length}</b><span>ещё счётчики</span></button>`;
const MORE_TILES = document.getElementById("more-tiles");                                      
if (MORE_TILES) MORE_TILES.onclick = e => {
  const b = e.currentTarget, open = b.getAttribute("aria-expanded") === "true";
  b.setAttribute("aria-expanded", String(!open));
  if (open) { document.querySelectorAll(".tile.extra").forEach(t => t.remove());
              b.querySelector("span").textContent = "ещё счётчики"; return; }
  b.insertAdjacentHTML("beforebegin",
    tileHTML(TILES_REST).replaceAll('class="tile"', 'class="tile extra"'));
  b.querySelector("span").textContent = "свернуть";
};


// OBSERVER HEALTH: what the observatory knows about itself, row by row. A
// missing field is left out rather than shown as zero.
const H = D.health || {};
const hb = [];
if (D.store_degraded) hb.push(["хранилище", D.store_degraded]);
if (H.last_scan) hb.push(["последний скан", H.last_scan.replace("T", " ").replace("Z", " UTC")]);
if (H.events != null) hb.push(["событий", H.events.toLocaleString("ru")]);
if (H.weeks != null) hb.push(["недельных срезов", H.weeks.toLocaleString("ru")]);
if (H.metrics != null) hb.push(["измерений плагинов", H.metrics.toLocaleString("ru")]);
// The local server, from its heartbeat: not running, alive, or silent — three
// states, spelled apart.
if (H.server_age_s != null) {
  if (H.server_age_s === -1) hb.push(["локальный сервер", "не запущен"]);
  else if (H.server_age_s < 90) {
    const up = H.server_uptime_s >= 3600
      ? Math.floor(H.server_uptime_s / 3600) + " ч" : Math.floor(H.server_uptime_s / 60) + " мин";
    hb.push(["локальный сервер", `отвечал при измерении · порт ${H.server_port} · аптайм ${up}`]);
    if (H.server_at_risk != null)
      hb.push(["remote под риском", `${H.server_at_risk} чекаут(ов) с работой только на этом диске`]);
  } else hb.push(["локальный сервер", `МОЛЧИТ ${Math.floor(H.server_age_s / 60)} мин — store/logs/serverd.err`]);
}
// When the server is down or silent, the row carries the command that
// starts or inspects it, ready to copy.
const SERVERD_FIX = {
  down: ["наблюдатель не запущен — запустить в терминале", toolCommand("serverd.py", ["--run"])],
  silent: ["наблюдатель молчит — проверить", toolCommand("serverd.py", ["--status"])],
};
if (H.leaks_open > 0) hb.push(["утечки секретов", `${H.leaks_open} не ротировано — vault.py leaks`]);
if (H.proposed != null) hb.push(["ждут решения оператора", H.proposed]);
if (H.registry_proposals) hb.push(["правок реестра предложено", H.registry_proposals]);
if (H.projection_lag) hb.push(["не проиндексировано выводов",
  `${H.projection_lag}, старейший от ${(H.projection_oldest || "").slice(0, 10)}`]);
if (H.degraded_sources) hb.push(["источников деградировало", H.degraded_sources]);
// This project's own spend, prepared by the builder from its own journal —
// the page does no date arithmetic of its own.
if (H.spend_month != null)
  hb.push(["потрачено этим проектом за месяц",
           `${(+H.spend_month).toFixed(4)} ${E(H.spend_denomination || "")}`]);
if (H.spend_today != null)
  hb.push(["из них сегодня", `${(+H.spend_today).toFixed(4)}`]);
// Models the provider-health file holds in quarantine, named up to three.
{
  const q = Object.keys(H.provider || {});
  if (q.length)
    hb.push([`моделей в карантине: ${q.length}`, q.slice(0, 3).join(", ")
             + (q.length > 3 ? ` и ещё ${q.length - 3}` : "")]);
}
{
  const state = H.server_age_s == null ? null
    : H.server_age_s === -1 ? "down" : H.server_age_s < 90 ? "up" : "silent";
  const fix = SERVERD_FIX[state];
  document.getElementById("health").innerHTML = (hb.length
    ? hb.map(([k, v]) => `<div class="hrow"><span>${E(k)}</span><b>${E(String(v))}</b></div>`).join("")
    : '<div class="hrow"><span>наблюдатель</span><b>данных нет</b></div>')
    + (fix ? `<div class="hrow"><span>${E(fix[0])}</span><b><span class="mono">${E(fix[1])}</span>` +
             ` <button class="chip-btn" type="button" data-copy="${E(fix[1])}">копировать</button></b></div>` : "");
}

document.getElementById("dups").innerHTML = D.dups.map(g =>
  `<li class="mono">${g.map(E).join("  ·  ")}</li>`).join("")
  || '<li class="none">нет</li>';

// TABS AND FILTERS. One table area, one selector and one chip group per tab;
// the current tab decides which of them apply.
let tab = "projects";

const sel = document.getElementById("owner");
// The selector's meaning changes with the tab: owner, team, registrar,
// section, project, agent or account.
const SEL_BY_TAB = {
  projects: ["все владельцы", "Владелец", () => D.owners],
  heroku:   ["все команды", "Команда",
             () => [...new Set(((D.heroku && D.heroku.apps) || []).map(a => a.team))].sort()],
  domains:  ["все регистраторы", "Регистратор",
             () => [...new Set((D.domains || []).map(d => d.registrar).filter(Boolean))].sort()],
  creds:    ["все разделы", "Раздел",
             () => CRED_SECTIONS.map(s => s[1])],
  env:      ["все проекты", "Проект",
             () => [...new Set(ENVF.map(f => f.project).filter(Boolean))].sort()],
  mcp:      ["все агенты", "Агент",
             () => [...new Set(((D.mcp && D.mcp.servers) || []).map(s => s.agent).filter(Boolean))].sort()],
  traffic:  ["все аккаунты", "Аккаунт",
             () => [...new Set(((D.google && D.google.properties) || []).map(p => p.account_name).filter(Boolean))].sort()],
};
function fillOwners() {
  const [all, label, vals] = SEL_BY_TAB[tab];
  sel.innerHTML = `<option value="">${all}</option>` +
    vals().map(o => `<option value="${E(o)}">${E(o)}</option>`).join("");
  sel.setAttribute("aria-label", label);
}
fillOwners();

// Active filter chips, kept per tab, so switching tabs never carries one
// tab's filters into another.
const activeBy = { projects: new Set(), heroku: new Set(), domains: new Set(),
                   creds: new Set(), env: new Set(), mcp: new Set(),
                   traffic: new Set() };
let active = activeBy[PAGE] || activeBy.projects;
document.querySelectorAll(".chip-btn[data-f]").forEach(c => c.onclick = () => {
  const on = c.getAttribute("aria-pressed") === "true";
  c.setAttribute("aria-pressed", String(!on));
  on ? active.delete(c.dataset.f) : active.add(c.dataset.f);
  const opposite = {heroku:"noheroku", noheroku:"heroku", note:"nonote", nonote:"note",
                    "t-linked":"t-unclaimed", "t-unclaimed":"t-linked"}[c.dataset.f];
  if (!on && opposite) {
    active.delete(opposite);
    document.querySelectorAll('.chip-btn[data-f="' + opposite + '"]').forEach(b => b.setAttribute("aria-pressed", "false"));
  }
  render();
});
// Filters can arrive in the URL (`?f=drift`), so a tile can link to an
// already-filtered view; such a chip is marked as switched on by a link.
{
  const wanted = new Set(new URLSearchParams(location.search || "").getAll("f"));
  document.querySelectorAll(".chip-btn[data-f]").forEach(c => {
    if (!wanted.has(c.dataset.f)) return;
    c.setAttribute("aria-pressed", "true");
    c.dataset.fromUrl = "1";
    c.title = "включён ссылкой";
    active.add(c.dataset.f);
  });
}

const APPS = (D.heroku && D.heroku.apps) || [];
const ENV_ORDER = ["production", "staging", "review", "development", "test", "local"];
const ENV_LABEL = {production: "прод", staging: "стейджинг", review: "ревью", development: "разработка",
                   test: "тест", local: "локально"};
function hostingGroups(apps) {
  const rank = h => h.env ? ENV_ORDER.indexOf(h.env) : ENV_ORDER.length;
  const groups = new Map();
  [...apps].sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
    .forEach(h => { const k = h.env || ""; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(h); });
  // One group needs no heading when nothing is known about environments at all.
  const bare = groups.size === 1 && groups.has("");
  return [...groups].map(([env, list]) =>
    `<div class="envgroup" data-env="${E(env || "unassigned")}">` +
    (bare ? "" : `<div class="tier">${env ? chip(ENV_LABEL[env] || env, env === "production" ? "ok" : "")
                                         : chip("окружение не указано", "warn")}</div>`) +
    list.map(h =>
      `<div class="st st-${E(h.state)}" title="${E(h.rule)}${h.account ? " · аккаунт " + E(h.account) : ""}"><i></i>` +
      `<span class="mono">${E(h.name)}</span>` +
      (h.cost ? `<span class="anchor"> $${Math.round(h.cost)}</span>` : "") +
      `</div>`).join("") + `</div>`).join("");
}
const DOMS = D.domains || [];
const LIVE_BY_HOST = h => { const d = DOMS.find(x => x.name === h); return d ? d.live : null; };
const CREDS = (D.creds && D.creds.credentials) || [];
const ENVF = (D.env && D.env.files) || [];
// One row per variable, flattened from the env files, with the file's own
// facts carried on every row.
const ENVV = ENVF.flatMap(f => f.variables.map(v => ({
  path: f.path, project: f.project, kind: f.kind, git: f.git, mode: f.mode,
  modified_on: f.modified_on, name: v.name, cls: v["class"],
  shared: v.shared_with || [], copies: v.copies || 1,
  available: v.available_in || [],
})));
const PROJ_NAME = new Map(D.rows.map(r => [r.id, r.name]));
function selectTab(next) {
  tab = next;
  active = activeBy[tab];
  for (const t of ["projects", "heroku", "domains", "creds", "env", "mcp"]) {
    const tb = document.getElementById("tab-" + t), sg = document.getElementById("seg-" + t);
    if (tb) tb.setAttribute("aria-selected", String(tab === t));
    if (sg) sg.hidden = tab !== t;
  }
  // The rules view switch belongs to the projects tab only.
  const vw = document.getElementById("view-projects");
  if (vw) vw.hidden = tab !== "projects";
  fillOwners();
  render();
}
for (const t of ["projects", "heroku", "domains", "creds", "env", "mcp"]) {
  const tb = document.getElementById("tab-" + t);
  if (tb) tb.onclick = () => selectTab(t);
}
document.getElementById("q").oninput = render;
sel.onchange = render;

const hay = r => [r.name, r.description, r.owner, r.last, r.folders.join(" "),
  r.stack.join(" "), r.sites.map(s => s.host).join(" "),

  // Heroku app names are searchable from the project row.
  (r.heroku || []).map(h => h.name).join(" "),
  r.repos.map(x => x.nwo + " " + x.path).join(" ")].join(" ").toLowerCase();

function keep(r, q, owner) {
  if (q && !hay(r).includes(q)) return false;
  if (owner && r.owner !== owner) return false;
  if (active.has("site") && !r.sites.length) return false;
  if (active.has("note") && !r.note) return false;
  if (active.has("nonote") && r.note) return false;
  if (active.has("folder") && !r.folders.length) return false;
  if (active.has("dirty") && !r.repos.some(x => x.dirty)) return false;
  if (active.has("dead") &&
      !r.sites.some(s => s.live && !s.live.resolves)) return false;
  if (active.has("unsynced") &&
      !r.repos.some(x => x.sync && x.sync !== "current")) return false;
  if (active.has("owned") && r.ownership !== "owned") return false;
  // Drift: declared active, measured dormant or cold.
  if (active.has("drift") &&
      !(r.lifecycle === "active" && (r.tier === "dormant" || r.tier === "cold"))) return false;
  if (active.has("heroku") && !(r.heroku || []).length) return false;
  if (active.has("noheroku") && (r.heroku || []).length) return false;
  return true;
}

// HEROKU FILTERS. "Stale" means no deploy in a year.
const YEAR_AGO = new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
const hayApp = a => [a.name, a.team, a.state, a.stack, a.region, a.github || "",
  a.project ? (PROJ_NAME.get(a.project) || a.project) : "",
  (a.local_folders || []).join(" "),
  (a.addons || []).map(x => x.plan).join(" ")].join(" ").toLowerCase();

function keepApp(a, q, team) {
  if (q && !hayApp(a).includes(q)) return false;
  if (team && a.team !== team) return false;
  if (active.has("noproject") && a.project) return false;
  if (active.has("nofolder") && (a.local_folders || []).length) return false;
  // No repository means neither a linked GitHub repo nor a project.
  if (active.has("norepo") && (a.github || a.project)) return false;
  if (active.has("down") &&
      !(a.state === "down" || a.state === "suspended" || (a.crashed || []).length)) return false;
  if (active.has("waste") && a.state !== "resources-only") return false;
  // `resources-only`: add-ons are billed while no dyno runs.
  if (active.has("stale") && !(a.last_deploy_on && a.last_deploy_on < YEAR_AGO)) return false;
  if (active.has("oldstack") && !a.stack_superseded) return false;
  return true;
}

const chip = (text, kind) =>
  `<span class="chip${kind ? " " + kind : ""}"><span class="dot"></span>${E(text)}</span>`;

function repoLine(x, rules) {
  // A superseded, placeholder or moved repository is rendered faded and
  // struck through, and names its successor.
  const sub = ["superseded", "placeholder", "moved"].includes(x.status);
  const bits = [];
  if (x.visibility === "public") bits.push(chip("public"));
  if (x.archived) bits.push(chip("архивный", "warn"));
  if (x.fork) bits.push(chip("форк"));
  if (x.host === "bitbucket") bits.push(chip("bitbucket"));
  if (x.dirty) bits.push(chip(x.dirty + " несохр.", "danger"));
  // Sync states that put work at risk are danger; merely behind is a warning.
  const SYNC = {
    "behind":             ["отстаёт", "warn"],
    "stale":              ["отстаёт", "warn"],
    "behind-or-diverged": ["отстаёт или разошёлся", "warn"],
    "diverged":           ["разошёлся", "danger"],
    "ahead":              ["не запушено", "danger"],
    "unpushed-and-remote-moved": ["не запушено, remote ушёл", "danger"],
    "local-only-branch":  ["ветка только здесь", "danger"],
    "unreachable":        ["remote недоступен", "danger"],
    "unknown":            ["состояние неизвестно", "warn"],
  };
  if (SYNC[x.sync]) {
    // The chip carries what is at stake: the unpushed count when measured.
    const [label, tone] = SYNC[x.sync];
    bits.push(chip(label + stakeText(x), tone));
  }
  if (x.checked_out && x.branch && x.checked_out !== x.branch)
    bits.push(chip("ветка " + x.checked_out, "warn"));
  if (x.status === "superseded")
    bits.push(chip("вытеснен → " + x.supersededBy, "warn"));
  if (x.status === "placeholder") bits.push(chip("пустой", "warn"));
  if (x.status === "moved") bits.push(chip("переехал → " + x.movedTo, "warn"));
  const rule = rules.find(s => s.startsWith(x.nwo + ":"));
  // The linking rule is shown only while the rules view is switched on.
  return `<div class="item"><div class="repo${sub ? " sub" : ""}">` +
    `<a class="nwo" href="${E(x.url)}" target="_blank" rel="noopener">${E(x.nwo)}</a>` +
    bits.join("") + `</div>` +
    (active.has("rules") && rule ? `<div class="rule">${E(rule.slice(x.nwo.length + 2))}</div>` : "") +
    `</div>`;
}

const NONE = '<span class="none">—</span>';
// Activity tiers, in the reader's language.
const TIER_RU = {active: "активен", cooling: "остывает", dormant: "спит",
                 cold: "холодный", unknown: "дата неизвестна"};

// SPARKLINE: weekly commits as a solid line and sessions as a dashed one,
// on one shared scale. Weeks whose sessions were never measured are left out
// of the dashed line rather than drawn as zero, so "no work" and "not
// measured" stay apart.
function spark(weeks) {
  if (!weeks || !weeks.length) return "";
  const vals = weeks.map(w => w.c);
  const sess = weeks.map(w => (w.s == null ? null : w.s));
  const max = Math.max(...vals, ...sess.filter(v => v != null), 1);
  const total = vals.reduce((a, b) => a + b, 0);
  const stotal = sess.reduce((a, b) => a + (b || 0), 0);
  const measured = sess.some(v => v != null);
  const W = 72, H = 14, step = W / Math.max(vals.length - 1, 1);
  const line = (arr) => arr.map((v, i) => v == null ? null :
      `${(i * step).toFixed(1)},${(H - (v / max) * (H - 2)).toFixed(1)}`)
    .filter(Boolean).join(" ");
  const worked = weeks.filter(w => w.d != null && w.d > 0).length;
  const title = `${vals.length} нед., ${total} коммитов` +
    (measured ? `, ${stotal} сессий, ${worked} нед. с работой` : "");
  return `<div class="spark" title="${title}">` +
    `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true">` +
    `<polyline points="${line(vals)}" fill="none" stroke="currentColor" stroke-width="1"/>` +
    (stotal ? `<polyline points="${line(sess)}" fill="none" stroke="currentColor"` +
              ` stroke-width="1" stroke-dasharray="2 2" opacity="0.55"/>` : "") +
    `</svg><span>${total}</span>` +
    (stotal ? `<span class="spark-sess">+${stotal}с</span>` : "") +
    `</div>`;
}

// Russian plural forms: one, few, many.
function plural(n, one, few, many) {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  return b === 1 ? one : many;
}

function metrics(list) {
  if (!list || !list.length) return "";
  // PLUGIN METRICS. The caption comes from the plugin's manifest and falls
  // back to the metric name; the unit is printed only when there is no
  // caption to carry it.
  return list.map(m => {
    const cap = (m.l || m.n || "").trim();
    const val = m.u === "bytes" ? bytes(m.v)
              : (m.l ? `${(+m.v).toLocaleString("ru")}`
                     : `${(+m.v).toLocaleString("ru")} ${E(m.u || "")}`.trim());
    // The change since the previous sample, when retention kept one. A
    // series with a single sample shows no delta at all, not "+0".
    let d = "";
    if (m.p != null && +m.p !== +m.v) {
      const up = +m.v > +m.p, diff = Math.abs(+m.v - +m.p);
      const shown = m.u === "bytes" ? bytes(diff) : diff.toLocaleString("ru");
      const was = m.u === "bytes" ? bytes(m.p) : (+m.p).toLocaleString("ru");
      d = ` <span class="delta ${up ? "up" : "down"}" title="было ${was}` +
          ` — ${E((m.pat || "").slice(0, 10))}">${up ? "↑" : "↓"}${shown}</span>`;
    }
    return `<div class="tier" title="${E(m.n)}">` +
           `<span class="cap">${E(cap)}</span> ${val}${d}</div>`;
  }).join("");
}

// WHAT IS AT STAKE in a checkout: the count of commits on no remote and the
// date of the newest, when the probe could count them.
function stakeText(x) {
  if (typeof x.unpushed === "number" && x.unpushed > 0)
    return ` · ${x.unpushed}` + (x.unpushedOn ? ` от ${x.unpushedOn}` : "");
  // Measured and found to hold nothing a remote lacks.
  if (x.nothing_exclusive) return " · ничего исключительного";
  return "";
}

function bytes(n) {
  if (!n) return "";
  const u = ["Б", "КБ", "МБ", "ГБ"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

function row(r) {
  const link = `#${E(r.id)}`;
  const sites = r.sites.slice(0, 2).map(x =>
    `<a href="https://${E(x.host)}" target="_blank" rel="noopener">${E(x.host)}</a>` +
    (x.live && !x.live.resolves ? chip("не отвечает", "danger") : "")).join(" ");
  const repos = r.repos.slice(0, 1).map(x => repoLine(x, r.rules || [])).join("");
  const dirty = r.repos.filter(x => x.dirty || ["ahead", "diverged", "unpushed-and-remote-moved", "local-only-branch"].includes(x.sync)).length;
  const traffic = (D.traffic || {})[r.id];
  return `<tr data-project="${E(r.id)}">
    <td data-label="Проект"><div class="name"><a class="plink" href="${link}">${E(r.name)}</a></div>
      <div class="desc">${E(r.description) || '<span class="none">Описание не задано</span>'}</div>
      <div class="project-meta">${E(r.owner || "Владелец не указан")} · ${E(r.lifecycle || "статус не указан")}</div></td>
    <td data-label="Активность"><div>${chip(TIER_RU[r.tier] || r.tier || "не измерена")}</div>
      <div class="anchor mono">${E(r.last) || "дата не измерена"}</div>${spark(r.weeks)}
      ${dirty ? chip(dirty + " репоз. требуют внимания", "warn") : ""}</td>
    <td data-label="Код и сайты"><div class="resource-links">${repos}${sites}</div>
      <a class="plink anchor" href="${link}">${r.repos.length} репоз. · ${r.sites.length} сайтов · ${r.folders.length} папок</a></td>
    <td data-label="Размещение">${(r.heroku || []).length ? hostingGroups(r.heroku) : '<span class="none">Нет привязанных приложений</span>'}</td>
    <td data-label="Аудитория / 30 дней">${traffic && traffic.users_30d != null
      ? `<span class="mono">${Number(traffic.users_30d).toLocaleString("ru")}</span><div class="anchor">сумма по ресурсам${traffic.unknown_properties ? " · частично" : ""}</div>`
      : '<span class="none">Не измерена</span>'}
      <div class="anchor"><a class="plink" href="${link}">Подробнее о проекте →</a></div></td>
  </tr>`;
}

// THE PROJECT PANEL: everything known about one project, opened from its row
// by the URL hash.
function detail(id) {
  const r = D.rows.find(x => x.id === id);
  const box = document.getElementById("panel");
  if (!r) { box.hidden = true; box.innerHTML = ""; return; }
  const list = (items, empty, fn) => items && items.length
    ? `<ul class="dlist">${items.map(fn).join("")}</ul>`
    : `<p class="none">${empty}</p>`;
  // Without a store, the store-backed sections say so instead of "none".
  const gone = D.store_degraded
    ? `<p class="none">${E(D.store_degraded)}</p>` : "";
  box.innerHTML = `
    <div class="dhead">
      <h2 id="panel-title">${E(r.name)}</h2>
      <button id="dclose" class="chip-btn" type="button" aria-label="Закрыть">закрыть</button>
    </div>
    <p class="dmeta">${E(r.anchor)} · ${E(r.lifecycle)} · ${E(TIER_RU[r.tier] || r.tier || "")}
      · последняя активность ${E(r.last) || "—"}</p>
    ${r.description ? `<p class="project-description">${E(r.description)}</p>` : ""}
    <h3>Из чего состоит</h3>
    ${                                                                          
      list(r.repos, "репозиториев нет", x => `<li>${repoLine(x, r.rules || [])}</li>`)}
    ${list(r.folders, "локальных папок нет", f => `<li class="mono">${E(f)}</li>`)}
    ${list(r.sites, "сайтов не заявлено", s => `<li class="mono"><a href="https://${E(s.host)}" target="_blank" rel="noopener">${E(s.host)}</a>` +
        `<span class="anchor"> ${E((s.evidence || [])[0] || "")}</span></li>`)}
    <h3>Размещение и окружения</h3>
    ${(r.heroku || []).length ? hostingGroups(r.heroku) : '<p class="none">Нет привязанных приложений</p>'}
    <h3>Технологии и документация</h3>
    <p>${(r.stack || []).map(x => chip(x)).join(" ") || "Стек не измерен"} · ${r.wiki_notes || 0} заметок</p>
    <h3>Продукт</h3>
    ${(r.products || []).length
      ? `<ul class="dlist">${r.products.map(p => `<li>${E(p.name)} — ${E(p.role)}` +
          (p.kind === "suggested" ? ` <span class="anchor">предложено по общему домену, не решение</span>` : "") +
          `</li>`).join("")}</ul>`
      : `<p class="none">ни в один продукт не входит — сгруппировать: collectors/products.json</p>`}
    <h3>Что происходило</h3>
    ${gone || list(r.timeline, "коммитов в окне нет",
      c => `<li><span class="mono">${E(c.at)}</span> ${E(c.what)}
            <span class="none">${E(c.who)}</span></li>`)}
    <h3>Что заключила обсерватория</h3>
    ${gone || list(r.notes, "выводов нет",
      n => `<li><span class="mono">${E(n.at)}</span> ${E(n.text)}
            <span class="none">${E(n.state)}${n.conf != null ? ", уверенность " + n.conf : ""}</span></li>`)}
    ${                                                                       
                                                          ""}
    <h3>Аналитика</h3>
    ${(() => {
      const tr = (D.traffic || {})[r.id];
      if (!tr) return `<p class="none">ни одна property Google Analytics не привязана к этому проекту — ` +
        `назовите её в <span class="mono">plugins/config/ga4_properties.json</span>, если она есть</p>`;
      return `<ul class="dlist">` + (tr.properties || []).map(g =>
        `<li><b>${g.users_30d == null ? "не измерено" : Number(g.users_30d).toLocaleString("ru")}</b> — сумма пользователей по ресурсам за 30 дней${g.unknown_properties ? " · без измерения: " + g.unknown_properties : ""} · ` +
        `${Number(g.sessions_30d || 0).toLocaleString("ru")} сессий — ${E(g.name || "")}` +
        `<span class="none"> · ${E(RULE_RU[g.rule] || g.rule || "")}` +
        `${(g.hosts || []).length ? " · " + E(g.hosts.slice(0, 2).join(", ")) : ""}</span> ` +
        `<a href="${E(g.report_url)}" target="_blank" rel="noopener">GA4</a>` +
        (g.admin_url ? ` · <a href="${E(g.admin_url)}" target="_blank" rel="noopener">админка</a>` : "") +
        `</li>`).join("") +
        (tr.search_console || []).map(s =>
          `<li>Search Console: <a href="${E(s.url)}" target="_blank" rel="noopener">${E(s.site)}</a></li>`).join("") +
        `</ul>`;
    })()}
    <h3>Ключи</h3>
    ${(() => {
      // Names, kinds and places only — the payload holds no value to show.
      const ks = (D.keys || {})[r.id] || [];
      if (!ks.length) return `<p class="none">ни один кред в реестре не привязан к этому проекту — ` +
        `ничьи перечислены на <a href="creds.html">странице ключей</a></p>`;
      const KIND_RU = {"llm-api-key": "ключ LLM", "machine-secret": "машинный секрет",
                       "project-secret": "слот хранилища", "project-secret-file": "файл рядом с кодом",
                       "leaked-untracked": "известен по утечке", "env-file": "в .env проекта"};
      // A key file tracked by git is danger; one merely not ignored is a
      // warning.
      const GIT_RU = {tracked: chip("файл в git", "danger"), loose: chip("не в .gitignore", "warn"), ignored: "", "no-repo": ""};
      return `<ul class="dlist">` + ks.map(k =>
        `<li><a class="mono" href="${E(k.href || ("creds.html#c-" + k.slug))}">${E(k.name || "")}</a>` +
        `<span class="none"> · ${E(KIND_RU[k.kind] || k.kind || "")}${k.env ? " · " + E(k.env) : ""}` +
        `${k.where ? " · " + E(k.where) : ""}</span>` +
        (k.leaked ? ` ${chip("утечка не закрыта", "danger")}` : "") +
        (k.kind !== "env-file" && !k.signed ? ` ${chip("не подписан", "warn")}` : "") +
        (k.kind === "env-file" ? ` ${GIT_RU[k.git] || ""}` : "") +
        `</li>`).join("") + `</ul>`;
    })()}
    <h3>Что измерили плагины</h3>
    ${gone || (r.metrics && r.metrics.length
        ? `<ul class="dlist">${r.metrics.map(m => `<li><span class="mono">${E(m.l || m.n)}</span> ` +
            `${m.u === "bytes" ? bytes(m.v)
                : (+m.v).toLocaleString("ru") + (m.l ? "" : " " + E(m.u || ""))}` +
            `${m.p != null && +m.p !== +m.v
               ? ` <span class="delta ${+m.v > +m.p ? "up" : "down"}">${+m.v > +m.p ? "↑" : "↓"}` +
                 `${m.u === "bytes" ? bytes(Math.abs(m.v - m.p)) : Math.abs(m.v - m.p).toLocaleString("ru")}</span>`
               : ""}</li>`).join("")}</ul>`
        : '<p class="none">измерений нет</p>')}`;
  box.hidden = false;
  document.getElementById("dclose").onclick = () => { location.hash = ""; };
  box.scrollIntoView({block: "start"});
  // Focus moves into the panel, so a keyboard reader lands on what opened.
  const closeBtn = document.getElementById("dclose");
  if (closeBtn && closeBtn.focus) closeBtn.focus();
}

let PANEL_OPENER = null;
document.addEventListener("click", ev => {
  const a = ev.target && ev.target.closest && ev.target.closest('a.plink[href^="#project:"]');
  if (!a) return;
  // On another page the project panel lives on the projects page, so the
  // link navigates there with the same hash.
  if (PAGE && PAGE !== "projects") {
    ev.preventDefault();
    location.href = "projects.html" + a.getAttribute("href");
    return;
  }
  PANEL_OPENER = a;
});
window.addEventListener("hashchange", () => {
  if (!location.hash && PANEL_OPENER && PANEL_OPENER.focus) { PANEL_OPENER.focus(); PANEL_OPENER = null; }
});
function fromHash() {
  // The hash names either a tab or a project.
  const raw = typeof location !== "undefined" ? (location.hash || "") : "";
  const id = decodeURIComponent(raw.replace(/^#/, ""));
  if (["projects", "heroku", "domains", "creds", "env"].includes(id)) {
    detail("");
    if (id !== tab) selectTab(id);
    return;
  }
  detail(id.startsWith("project:") ? id : "");
}
addEventListener("hashchange", fromHash);
addEventListener("keydown", e => { if (e.key === "Escape" && location.hash) location.hash = ""; });

// WHAT NARROWS THE VIEW, stated beside the count. A table showing fewer rows
// than exist must say by what: the pressed chips of this tab (and which came
// from a link), the selector and the search text. `narrowing()` reads only
// the chips inside `.seg`, so a view switch is never counted as a filter.
function narrowing() {
  const seg = document.getElementById("seg-" + tab);
  const chips = seg ? [...seg.querySelectorAll('.chip-btn[data-f][aria-pressed="true"]')]
    .map(b => b.textContent.trim() + (b.dataset.fromUrl ? " (из ссылки)" : "")) : [];
  const q = (document.getElementById("q") || {}).value || "";
  const s = (sel && sel.value && sel.selectedIndex >= 0) ? sel.options[sel.selectedIndex].text : "";
  return { chips, q: q.trim(), sel: s };
}
function narrowingText(n) {
  const bits = [];
  if (n.chips.length) bits.push("фильтры: " + n.chips.map(E).join(", "));
  if (n.sel) bits.push("выбрано: " + E(n.sel));
  if (n.q) bits.push(`поиск: «${E(n.q)}»`);
  return bits.join(" · ");
}
function filterLine(shown, total, unit) {
  const what = narrowingText(narrowing());
  return `<div class="filters" role="status">Показано <b>${shown}</b> из ${total}${unit ? " " + unit : ""}` +
    (what ? ` · ${what} · <button class="chip-btn" type="button" data-clear>сбросить</button>` : "") + `</div>`;
}
// GROUP FOLDING. Groups start folded, and open by themselves as soon as
// anything narrows the view — a search hit hidden inside a folded group would
// read as "not found".
function foldOpen(defaultOpen) {
  const n = narrowing();
  return !!(defaultOpen || n.q || n.chips.length || n.sel);
}
function grpHead(colspan, inner, open) {
  return `<tr class="group-heading"><th colspan="${colspan}" scope="colgroup">${inner}</th></tr>`;
}
// A hash naming a row reveals it: its folded group opens and the row
// scrolls into view. Finding and project hashes are handled elsewhere.
let REVEALED = "";
function revealHash() {
  const raw = typeof location !== "undefined" ? (location.hash || "") : "";
  if (!raw || raw.startsWith("#f-") || raw.startsWith("#project:")) return;
  // Once per hash, so a re-render does not keep scrolling the reader back.
  if (raw === REVEALED) return;
  const id = decodeURIComponent(raw.slice(1));
  let target = document.getElementById(id);
  if (!target && id.startsWith("e-") && typeof CSS !== "undefined" && CSS.escape) {
    target = document.querySelector('tr[data-file="' + CSS.escape(id.slice(2)) + '"]');
  }
  if (!target) return;
  const body = target.closest("tbody.grp.folded");
  if (body) {
    body.classList.remove("folded");
    const b = body.querySelector(".grp-fold");
    if (b) b.setAttribute("aria-expanded", "true");
  }
  if (target.scrollIntoView) target.scrollIntoView({block: "center"});
  REVEALED = raw;
}
addEventListener("hashchange", () => { REVEALED = ""; revealHash(); });
// COLUMN SORTING. A header click cycles ascending, descending, none. The
// choice is kept per page for the session only, and empty values always sort
// last whichever the direction.
const SORT = (() => {
  try { return JSON.parse(sessionStorage.getItem("observatory.sort." + PAGE) || "{}") || {}; }
  catch (e) { return {}; }
})();
function sortTh(label, key) {
  const dir = SORT.key === key && SORT.dir ? SORT.dir : "none";
  return `<th aria-sort="${dir}" data-sort="${E(key)}"><button class="sort" type="button" title="сортировать">${label}</button></th>`;
}
function sortInPlace(list, getters) {
  const g = SORT.key && getters[SORT.key];
  if (!g) return list;
  const m = SORT.dir === "descending" ? -1 : 1;
  const copy = [...list].sort((a, b) => {
    const x = g(a), y = g(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * m;
  });
  list.splice(0, list.length, ...copy);
  return list;
}
document.addEventListener("click", ev => {
  const th = ev.target.closest && ev.target.closest("th[data-sort]");
  if (!th) return;
  const key = th.dataset.sort;
  const cur = SORT.key === key ? SORT.dir : "none";
  const next = cur === "none" ? "ascending" : cur === "ascending" ? "descending" : "none";
  SORT.key = next === "none" ? "" : key;
  SORT.dir = next === "none" ? "" : next;
  try { sessionStorage.setItem("observatory.sort." + PAGE, JSON.stringify(SORT)); } catch (e) {                      }
  render();
});
const lower = s => String(s || "").toLowerCase() || null;
const dateOr = s => (s ? String(s) : null);
const numOr = n => (typeof n === "number" ? n : (n == null || n === "" ? null : Number(n)));
function nothingFound(total, note) {
  const what = narrowingText(narrowing());
  // An empty result says whether a filter caused it or the registry is empty.
  if (!what) return `<p class="empty">${total ? "Ничего не найдено" : "Здесь пусто — в реестре нет ни одной строки этого вида"}${note ? ". " + note : ""}</p>`;
  return `<p class="empty">Ничего не найдено с этим сужением — ${what}. ` +
    `<button class="chip-btn" type="button" data-clear>сбросить</button>${note ? "<br>" + note : ""}</p>`;
}
document.addEventListener("click", ev => {
  const b = ev.target && ev.target.closest && ev.target.closest("[data-clear]");
  if (!b) return;
  const seg = document.getElementById("seg-" + tab);
  if (seg) seg.querySelectorAll('.chip-btn[data-f]').forEach(c => { c.setAttribute("aria-pressed", "false"); delete c.dataset.fromUrl; });
  if (active) active.clear();
  const q = document.getElementById("q"); if (q) q.value = "";
  if (sel) sel.value = "";
  render();
});

function render() {
  const search = document.getElementById("q");
  if (search) search.placeholder = ({projects:"Поиск: проект, описание, репозиторий, папка или домен", heroku:"Поиск: приложение, проект или папка", domains:"Поиск: домен, регистратор или проект", creds:"Поиск: ключ, провайдер или проект", env:"Поиск: переменная, файл или проект", mcp:"Поиск: сервер, агент или адрес", traffic:"Поиск: ресурс, сайт или проект"})[tab] || "Поиск";
  const out = drawTab();
  const tools = document.getElementById("list-tools");
  const table = document.getElementById("out");
  if (tools && table) {
    const fields = [...table.querySelectorAll("th[data-sort]")].map(h => [h.dataset.sort, h.textContent]);
    tools.innerHTML = fields.length ? '<label>Сортировка <select id="list-sort" aria-label="Сортировка списка">' +
      '<option value="">Исходный порядок</option>' + fields.map(([key, label]) =>
        ["ascending", "descending"].map(dir => '<option value="' + E(key + ":" + dir) + '"' +
          (SORT.key === key && SORT.dir === dir ? ' selected' : '') + '>' + E(label) +
          (dir === "ascending" ? ' ↑' : ' ↓') + '</option>').join("")).join("") + '</select></label>' : '';
    const select = document.getElementById("list-sort");
    if (select) select.onchange = () => {
      [SORT.key, SORT.dir] = select.value ? select.value.split(":") : ["", ""];
      try { sessionStorage.setItem("observatory.sort." + PAGE, JSON.stringify(SORT)); } catch (e) {}
      render();
      document.getElementById("list-sort").focus();
    };
  }
  revealHash();                                                                  
  return out;
}
function drawTab() {
  if (PAGE && !TABLE_PAGES.includes(PAGE)) return;                                             
  // Tab counters are refreshed on every render.
  const setN = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setN("n-projects", D.rows.length);
  setN("n-mcp", D.mcp ? (D.mcp.totals || {}).distinct_servers || 0 : "—");
  setN("n-domains", new Set([...DOMS.map(d => d.name), ...(D.zones || []).map(z => z.name)]).size);
  setN("n-heroku", APPS.length || "—");
  setN("n-creds", CREDS.length || "—");
  setN("n-env", (D.env && D.env.totals ? D.env.totals.secrets : 0) || "—");
  if (tab === "heroku") return renderHeroku();
  if (tab === "domains") return renderDomains();
  if (tab === "mcp") return renderMcp();
  if (tab === "traffic") return renderTraffic();
  if (tab === "creds") return renderCreds();
  if (tab === "env") return renderEnv();
  const q = document.getElementById("q").value.trim().toLowerCase();
  const owner = sel.value;
  const rows = D.rows.filter(r => keep(r, q, owner));
  const out = document.getElementById("out");
  if (!rows.length) { out.innerHTML = nothingFound(D.rows.length); return; }
  sortInPlace(rows, {name: r => lower(r.name), activity: r => dateOr(r.last)});
  out.innerHTML = filterLine(rows.length, D.rows.length, "проектов") + `<div class="card"><table class="project-summary">
    <colgroup><col style="width:26%"><col style="width:17%"><col style="width:23%"><col style="width:21%"><col style="width:13%"></colgroup>
    <thead><tr>${sortTh("Проект", "name")}${sortTh("Активность", "activity")}
      <th>Код и сайты</th><th>Размещение</th><th>Аудитория / 30 дней</th></tr></thead>
    <tbody>${rows.map(row).join("")}</tbody></table></div>`;
}

// ACTIONS. The page is read-only when opened as a file. Served by the local
// server, it carries a session token and can call that server's API; each
// action is then a button, and the same action is always available as a
// command to copy.

// The token comes from a meta tag the server writes into the page it serves;
// a page opened from disk has none.
const TOKEN = (document.querySelector('meta[name="observatory-token"]') || {}).content;
// LIVE only over http(s) with a token: every other way of opening the page
// stays copy-only.
const LIVE = typeof location !== "undefined"
  && String(location.protocol || "").startsWith("http") && !!TOKEN;

// A short confirmation at the bottom of the screen, gone after four seconds.
function toast(text) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 4000);
}

// Copy to the clipboard, with a textarea fallback where the async clipboard
// API is unavailable or refused (a file:// page, an older browser).
async function copyText(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {                                                                   }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.top = "-1000px";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
  document.body.removeChild(ta);
  return ok;
}

// Any element with `data-copy` copies its command on click.
document.addEventListener("click", ev => {
  const btn = ev.target && ev.target.closest && ev.target.closest("[data-copy]");
  if (!btn) return;
  // The toast names what was copied, shortened to one line.
  const what = String(btn.dataset.copy || "").replace(/\s+/g, " ").slice(0, 48);
  copyText(btn.dataset.copy).then(ok =>
    toast(ok ? `скопировано: ${what}${btn.dataset.copy.length > 48 ? "…" : ""}`
             : "буфер недоступен — скопируйте из подсказки"));
});
// Credential action buttons, handled in one place.
document.addEventListener("click", ev => {
  const btn = ev.target && ev.target.closest && ev.target.closest("[data-act][data-cred]");
  if (!btn || btn.disabled) return;
  const c = CREDS.find(x => x.id === btn.dataset.cred);
  if (!c) { toast("строка не найдена — пересканируйте"); return; }
  credAction(btn, c);
});

// THREE OUTCOMES, not two (PB-038). A refusal the server explained is
// definite: nothing happened, and trying again is safe. A timeout, a dropped
// connection, an unreadable answer to success, or a server fault after the
// action began is UNCERTAIN: the provider may already have revoked or minted,
// and "failed" would invite a second mint. Only the first may say "не вышло".
class Uncertain extends Error {}
const CALL_TIMEOUT_MS = 60000;
async function call(action, body, ms = CALL_TIMEOUT_MS) {
  const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = ctl ? setTimeout(() => ctl.abort(), ms) : null;
  let r;
  try {
    r = await fetch("/api/" + action, {
      method: "POST",
      // The token authorises the call; the caller header names which page made
      // it, for the server's own journal (a label, never an authority:
      // docs/design/ACCESS.md).
      headers: {"Content-Type": "application/json", "X-Observatory-Token": TOKEN,
                "X-Observatory-Caller": "page:" + (document.body.dataset.page || "index")},
      body: JSON.stringify(body),
      signal: ctl ? ctl.signal : undefined,
    });
  } catch (_) {
    throw new Uncertain(ctl && ctl.signal.aborted ? `нет ответа за ${Math.round(ms / 1000)} с`
                                                  : "соединение оборвалось");
  } finally {
    if (timer) clearTimeout(timer);
  }
  let d = null;
  try { d = await r.json(); } catch (_) { d = null; }
  if (r.ok) {
    if (!d) throw new Uncertain("ответ пришёл, но не читается");
    return d;
  }
  const said = (d && d.error) || ("HTTP " + r.status);
  // 502 is the provider's own refusal, relayed; any other 5xx is a fault that
  // may have struck after the action took effect.
  if (r.status >= 500 && r.status !== 502) throw new Uncertain(said);
  throw new Error(said);
}

// One credential action: confirm what cannot be undone, ask for what the
// action needs, call the server, and report the outcome.
function credAction(btn, c) {
  const act = btn.dataset.act;
  const ask = act === "revoke"
    ? `Отозвать ключ ${c.label}? Он перестанет работать немедленно и навсегда.`
    : act === "limit"
      ? `Новый месячный потолок для ${c.name || c.label}:`
      : act === "leak"
        ? `Где это значение засветилось? Одной строкой — транскрипт, лог, скрин:`
        : act === "rotate-key"
          ? `Ротировать ${c.name || c.label}? Дверь создаст новый ключ, доставит его туда же и удалит старый.`
          : act === "disable"
            ? `Отключить ${c.name || c.label}? Он перестанет тратить до «включить».`
            : null;
  if ((act === "revoke" || act === "rotate-key" || act === "disable") && !confirm(ask)) return;
  // Keys managed by name use `name`; the rest are addressed by label.
  let body = ["disable", "enable", "rotate-key"].includes(act)
    ? {name: c.name || c.label} : {label: c.label};
  if (act === "limit") {
    const v = prompt(ask, String(c.limit || 100));
    if (v === null) return;
    body = {label: c.label, limit: Number(v), limit_reset: "monthly"};
  }
  // SIGNING: a purpose and the evidence for it are required; the owner is
  // optional.
  if (act === "annotate") {
    const purpose = prompt(`Для чего нужен ${c.name || c.label}? Одной фразой:`, "");
    if (!purpose || !purpose.trim()) return;
    const evidence = prompt("Откуда это известно — конфиг, письмо, разговор, файл:", "");
    if (!evidence || !evidence.trim()) return;
    const owner = prompt("Кто за него отвечает (человек или команда, можно пусто):", "") || "";
    body = {id: c.id, purpose: purpose.trim(), evidence: evidence.trim(),
            owner: owner.trim()};
  }
  // MINTING a new key: its name at the provider, a monthly ceiling and
  // where it is delivered. The value is delivered by the server and never
  // reaches this page.
  if (act === "mint") {
    const name = prompt("Имя ключа у провайдера (его увидит только леджер):", "");
    if (!name || !name.trim()) return;
    const limit = prompt(`Месячный потолок для ${name.trim()}, в долларах:`, "10");
    if (limit === null || !(Number(limit) > 0)) return;
    const dest = prompt("Куда доставить — observatory, claude-mem или "
                        + "vault:<проект>/<env>/<NAME>:", "vault:<проект>/prod/OPENROUTER_API_KEY");
    if (!dest || !dest.trim()) return;
    body = {name: name.trim(), limit: Number(limit), destination: dest.trim()};
  }
  // RECORDING A LEAK: where the value was seen, in one line.
  if (act === "leak") {
    const where = prompt(ask, "");
    if (!where || !where.trim()) return;
    body = {project: c.vault_project, env: c.env, name: c.name, where: where.trim()};
  }
  btn.disabled = true; btn.textContent = "…";
  call(act, body)
    .then(d => { toast(act === "annotate" ? "подписан — пересканируйте"
                       : act === "revoke" ? "отозван"
                       : act === "leak" ? "отмечен как утёкший — ротируйте у провайдера"
                       : act === "mint" ? `выпущен и доставлен в ${d.destination}`
                       : `потолок ${d.limit}/мес`);
                 btn.textContent = "готово · пересканируйте"; })
    .catch(e => {
      if (e instanceof Uncertain) {
        // Kept disabled: repeating an action whose first attempt may have
        // landed is how one mint becomes two. A rescan says what happened.
        btn.textContent = "исход неизвестен · проверьте";
        btn.title = "Исход неизвестен: " + e.message;
        toast(("исход неизвестен (" + e.message + ") — пересканируйте и проверьте, прежде чем повторять").slice(0, 160));
        return;
      }
      btn.disabled = false; btn.textContent = "не вышло";
      toast(String(e.message).slice(0, 120));
    });
}

// A finding's subject becomes a link to the row it is about, on the page
// that holds that kind of row.
function subjectHref(subject) {
  const m = /^([a-z]+):(.+)$/.exec(String(subject || ""));
  if (!m) return null;
  const [, kind, rest] = m;
  if (kind === "domain") return ["domains.html#d-" + rest, rest];
  if (kind === "app") return ["heroku.html#a-" + rest, rest];
  if (kind === "credential") return ["creds.html#c-" + rest.replace(/[^A-Za-z0-9_.-]+/g, "-"), rest];
  if (kind === "project") return ["projects.html#project:" + rest, rest];

  // Env and MCP anchors use the same slug their rows are rendered with.
  if (kind === "env") return ["env.html#e-" + anchorSlug(rest), rest];
  if (kind === "mcp") return ["mcp.html#m-" + anchorSlug(rest), rest];
  return null;
}
// The one slug rule shared by row ids and the links to them.
function anchorSlug(s) { return String(s).replace(/[^A-Za-z0-9_.:/-]+/g, "-"); }

// Credentials read by a provider tool have a "door": the tool that can
// issue, list and revoke them.
const doorOf = c => {
  const m = /^tools\/(openrouter|cloudflare)\.py$/.exec(c.read_by || "");
  return m ? m[1] : null;
};

// THE VERBS OF A CREDENTIAL: label, command, and the live action when the
// server can perform it (null means copy-only). Every verb is a command a
// reader can run in a terminal, so the page never becomes the only way to
// act. Placeholders in capitals are for the reader to fill in.
const ISSUE_CMD = {
  openrouter: toolCommand("openrouter.py", ["issue", "--name", "KEY_NAME", "--limit", "AMOUNT", "--to", "vault:PROJECT/prod/NAME"]),
  cloudflare: toolCommand("cloudflare.py", ["issue", "--account", "ACCOUNT_ID", "--preset", "analytics"]),
};
function credVerbs(c) {
  const door = doorOf(c);
  const n = c.name || c.label || "";
  const sign = ["подписать…", toolCommand("sign_credential.py", ["set", c.id, "--purpose", "…", "--evidence", "…"]), "annotate"];
  if (c.kind === "llm-api-key")
    return [
      sign,
      ["потолок…", toolCommand("openrouter.py", ["limit", n, "--set", "AMOUNT"]), "limit"],
      [c.disabled ? "включить" : "отключить", toolCommand("openrouter.py", [c.disabled ? "enable" : "disable", n]), c.disabled ? "enable" : "disable"],
      ["ротировать", toolCommand("openrouter.py", ["rotate", n, ...(c.leaked ? ["--leaked"] : [])]), "rotate-key"],
      ["отозвать", toolCommand("openrouter.py", ["revoke", n]), "revoke"],
    ];
  if (door)
    return [sign,
      ["пинг", toolCommand(door + ".py", ["ping"]), null],
      ["что выпущено", toolCommand(door + ".py", ["list"]), null],
      ["выпустить…", ISSUE_CMD[door], door === "openrouter" ? "mint" : null],
    ];
  if (c.vault_project) {
    const slot = [c.vault_project, c.env, c.name];
    const settle = ["закрыть утечку…", toolCommand("vault.py", ["settle", ...slot, "--how", "…", "--revocation-evidence", "…", "--consumer-evidence", "…"]), null];
    const rotate = ["ротировать из файла…", privateInput(toolCommand("vault.py", ["rotate", ...slot])), null];
    if (c.known_only_from_the_leak)
      return [sign, settle, ["завести слот из файла…", privateInput(toolCommand("vault.py", ["put", ...slot])), null]];
    return c.leaked ? [sign, settle, rotate]
      : [sign, ["отметить утечку…", toolCommand("vault.py", ["leak", ...slot, "--where", "…"]), "leak"], rotate];
  }
  if (c.kind === "project-secret-file") {
    const owner = (c.used_by || [])[0];
    const vaultProject = owner ? (PROJ_NAME.get(owner) || String(owner).split(":")[1]) : c.in_project;
    const slotName = String(c.name).replace(/^\.+/, "").replace(/\.[A-Za-z0-9]+$/, "")
      .replace(/[^A-Za-z0-9]+/g, "_").toUpperCase();
    const file = projectFile(c.in_project + "/" + c.path);
    return [sign,
      ["в хранилище", toolCommand("vault.py", ["put", vaultProject, "local", slotName]) + " < " + shellArg(file), null],
      ["что это", "ls -l -- " + shellArg(file), null]];
  }
  return [sign, ["что это", "ls -l -- " + shellArg(secretFile(n)), null]];
}

const CRED_SECTIONS = [
  ["door", "Двери", "админские стэши: из них выпускается всё остальное; значение не выдаётся никому"],
  ["issued", "Выпущенные ключи", "леджер двери: имя у провайдера, потолок, расход, дата выпуска"],
  ["slot", "Секреты проектов", "слоты хранилища — значение живёт в vault и идёт только через stdin"],
  ["projfile", "Секреты рядом с кодом",
   "файлы в собственной папке secrets/ проекта; " +
   "«в хранилище» переносит значение в vault через stdin, чтобы им можно было пользоваться из любого проекта"],
  ["machine", "Секреты машины", "файлы, которыми аутентифицируются сборщики и плагины этой машины"],
];
const credSection = c => doorOf(c) ? "door"
  : c.kind === "llm-api-key" ? "issued"
  : c.kind === "project-secret-file" ? "projfile"
  : c.vault_project ? "slot" : "machine";

const credCmd = c => (credVerbs(c)[0] || ["", ""])[1];

const hayCred = c => [c.id, c.name || "", c.provider || "", c.kind, c.serves || "",
  (c.used_by || []).join(" "), c.label || ""].join(" ").toLowerCase();

function keepCred(c, q, section) {
  if (q && !hayCred(c).includes(q)) return false;
  if (section && (CRED_SECTIONS.find(s => s[1] === section) || [])[0] !== credSection(c))
    return false;
  if (active.has("c-leaked") && !c.leaked) return false;
  if (active.has("c-unclaimed") && (c.used_by || []).length) return false;
  // Shared: used by two or more projects, so a rotation touches all of them.
  if (active.has("c-shared") && (c.used_by || []).length < 2) return false;
  if (active.has("c-norotate") && c.rotated_on) return false;
  if (active.has("c-disabled") && !c.disabled) return false;
  if (active.has("c-untracked") && c.kind !== "leaked-untracked") return false;
  return true;
}

function renderCreds() {
  const out = document.getElementById("out");
  if (!D.creds) {
    out.innerHTML = `<p class="empty">Учётные данные не сканировались — ` +
      `<span class="mono">${E(cliCommand("openrouter"))}</span></p>`;
    return;
  }
  const q = document.getElementById("q").value.trim().toLowerCase();
  const rows = CREDS.filter(c => keepCred(c, q, sel.value));
  if (!rows.length) { out.innerHTML = nothingFound(CREDS.length); return; }
  const cell = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  const cap = c => c.limit == null ? NONE
    : `<span class="mono">${c.limit}</span>` +
      `<div class="tier">${E(c.limit_reset || "без сброса")}` +
      (c.limit_reset ? "" : " " + chip("пожизненный", "warn")) +
      `</div><div class="anchor">потрачено ${(+c.usage || 0).toFixed(3)}</div>`;
  const who = c => (c.used_by || []).length
    ? (c.used_by || []).map(p =>
        `<a class="plink" href="#${E(p)}">${E(p.split(":")[1])}</a>`).join(", ") +
      ((c.used_by || []).length > 1
        ? `<div class="tier">${chip("общий · ротация затронет всех", "warn")}</div>` : "")
    // No project uses it: name the tool that reads it, or say it is nobody's.
    : c.read_by
      ? `<span class="mono">${E(c.read_by)}</span><div class="anchor">читает его</div>`
      : `<span class="unlinked" title="${E(c.unclaimed_reason || "")}">ничей</span>`;
  const state = c => {
    const bits = [];
    if (c.leaked) bits.push(chip("утечка не закрыта", "danger"));
    if (c.disabled) bits.push(chip("отключён", "warn"));
    if (c.kind === "leaked-untracked") bits.push(chip("в хранилище нет", "warn"));
    // A key file sitting in a checkout: its git state and file mode matter.
    if (c.git === "tracked") bits.push(chip("в git", "danger"));
    if (c.git === "loose") bits.push(chip("не игнорируется", "warn"));
    if (c.kind === "project-secret-file" && String(c.mode).slice(-2) !== "00")
      bits.push(chip(`права ${E(c.mode)}`, "warn"));
    if (!bits.length) bits.push(chip("в порядке", "ok"));
    // Where a leaked value was seen, shortened, with the whole text on hover.
    const w = String(c.leaked_where || "");
    return bits.join(" ") + (c.leaked && w
      ? `<div class="anchor" title="${E(w)}">${E(w.slice(0, 110))}${w.length > 110 ? "…" : ""}</div>`
      : "");
  };
  sortInPlace(rows, {name: c => lower(c.name)});
  const groups = new Map();
  rows.forEach(c => { const k = SORT.key ? "sorted" : credSection(c);
    if (!groups.has(k)) groups.set(k, []); groups.get(k).push(c); });
  const row = c => `<tr id="c-${E(String(c.id).replace(/^credential:/, "").replace(/[^A-Za-z0-9_.-]+/g, "-"))}">
    <td data-label="Учётные данные"><div class="name">${E(c.name || c.id)}</div>
      ${                                                                   
                                                                            ""}
      <div class="anchor mono" title="${E(c.id)}">${E(c.label
        || [c.vault_project, c.env].filter(Boolean).join("/") || c.id)}</div>
      ${c.provider ? `<div class="anchor">${E(c.provider)}${c.serves ? " · " + E(c.serves) : ""}</div>` : ""}
      ${c.identity ? `<div class="anchor mono">${E(c.identity)}</div>` : ""}
      ${                                                                        
                                                                     ""}
      ${c.signature && c.signature.purpose
        ? `<div class="tier">${E(c.signature.purpose)}</div>` +
          `<div class="anchor">${E(c.signature.owner || "владельца нет")}` +
          `${c.signature.rotation_days ? ` · ротация раз в ${c.signature.rotation_days} дн.` : ""}` +
          ` · подписан ${E(c.signature.signed_on || "")}</div>`
        : `<div class="anchor"><span class="unlinked">не подписан — для чего он, никто не сказал</span></div>`}</td>
    ${cell("Состояние", state(c))}
    ${cell("Потолок", cap(c), "num")}
    ${cell("Проекты", who(c))}
    ${cell("Ротация", c.rotated_on
      ? E(c.rotated_on) + `<div class="anchor">×${c.rotations || 1}</div>`
      // Never rotated: show when it was issued, or since when it has sat
      // here, before admitting "never".
      : c.created_on
        ? `<span class="mono">выпущен ${E(c.created_on)}</span>`
        : c.installed_on
          ? `<span class="mono">лежит с ${E(c.installed_on)}</span>`
          : `<span class="unlinked">никогда</span>`)}
    ${cell("Действие", `<div class="verbs">` + credVerbs(c).map(([label, cmd, act]) =>
      LIVE && act
        ? `<button class="chip-btn" type="button" data-cred="${E(c.id)}" data-act="${E(act)}"
            >${E(label)}</button>`
        : `<button class="chip-btn" type="button" data-copy="${E(cmd)}"
            title="${E(cmd)}">Команда: ${E(label)}</button>`).join(" ") + `</div>`)}</tr>`;
  const leaked = rows.filter(c => c.leaked).length;
  const howto = LIVE
    ? `кнопки действуют: страницу отдаёт <span class="mono">tools/keyserver.py</span>`
    : `режим команд: кнопки копируют команду; выполните её в терминале;` +
      ` перед импортом замените /absolute/path/to/private-input путём к приватному файлу со значением;` +
      ` запустите <span class="mono">${E(toolCommand("keyserver.py"))}</span>, чтобы они действовали`;
  // Grouped by section, in a fixed order, and every section is shown even
  // when empty — an empty section is a fact, not a missing one.
  out.innerHTML = filterLine(rows.length, CREDS.length, "записей") + `<div class="action-mode"><b>${LIVE ? "Действия подключены" : "Режим команд"}</b> · ${LIVE ? "Кнопки выполняют указанное действие." : "Кнопки копируют команды для терминала."}<details><summary>Как пользоваться действиями</summary>${howto}</details></div><div class="card"><table>
    <colgroup><col style="width:23%"><col style="width:24%"><col style="width:10%">
      <col style="width:16%"><col style="width:11%"><col style="width:16%"></colgroup>
    <thead><tr>${sortTh("Учётные данные", "name")}<th>Состояние</th><th>Потолок</th>
      <th>Проекты</th><th>Ротация</th><th>Действие</th></tr></thead>
    ${(SORT.key ? [["sorted", "Выбранные записи", "Общий порядок по выбранному столбцу"]] : CRED_SECTIONS).map(([key, title, says]) => {
      const cs = groups.get(key) || [];
      return `<tbody class="grp">
      ${grpHead(6, `${E(title)} <span class="n">${cs.length}</span><div class="anchor">${E(says)}</div>`, true)}
      ${cs.length ? cs.map(row).join("")
        : `<tr><td colspan="6" class="e">${key === "issued"
            ? "ни одного ключа ещё не выпущено — «выпустить…» на строке двери"
            : "здесь пусто"}</td></tr>`}</tbody>`;
    }).join("")}</table></div>
    <p class="dmeta">Показано ${rows.length} из ${CREDS.length} ·
      ${leaked} незакрытых утечек · измерено ${E(D.creds.scanned_on || "—")} ·
      значений здесь нет: метка — это то, как ключ называет сам провайдер;<br>
      запись и ротация секрета проекта отсюда <b>отказаны намеренно</b> — значение идёт только через stdin</p>
    ${movementsSection()}`;
}

// KEY MOVEMENTS. The journal records every time a value was put, rotated,
// moved or revoked. Beside it, the production configuration changes that
// have no journal row, each with the command that records it — the rule is
// that whoever moved a key records the movement in the same step.
function movementsSection() {
  const mv = (D.creds && D.creds.movements) || [];
  const un = (D.creds && D.creds.unrecorded) || [];
  const EVENT_RU = {put: "положен", rotate: "ротирован", moved: "перемещён (рукой)", settled: "утечка закрыта",
                    issue: "выпущен", disable: "отключён", enable: "включён", revoke: "отозван",
                    leak: "утечка записана"};
  const unrows = un.map(u => {
    const proj = u.project || (u.app || "").replace(/-/g, "_");
    const cmds = (u.vars || []).map(v =>
      toolCommand("vault.py", ["moved", u.project || "PROJECT", "prod", v, "--at", "heroku", "--how", `set on Heroku app ${u.app}, release v${u.version}, ${String(u.at || "").slice(0, 16)}Z by ${u.by || "?"}`]));
    return `<li><b>${E(u.app)}</b> v${E(String(u.version || ""))} · ${E(String(u.at || "").slice(0, 16))}Z · ${E(u.by || "?")}:
      <span class="mono">${(u.vars || []).map(E).join(", ")}</span>
      ${cmds.map((c, i) => `<button class="chip-btn" type="button" data-copy="${E(c)}" title="скопировать запись движения">Команда: записать ${E(u.vars[i])}</button>`).join(" ")}</li>`;
  }).join("");
  const rows = mv.map(m => `<tr>
      <td class="num"><span class="mono">${E(String(m.at || "").slice(0, 16).replace("T", " "))}</span></td>
      <td>${E(EVENT_RU[m.event] || m.event || "")}</td>
      <td><span class="mono">${E(m.secret || m.of || "")}</span></td>
      <td>${E(m.by || "")}${m.tool ? ` <span class="none">· ${E(m.tool)}</span>` : ""}</td>
      <td>${E(m.at_provider ? "у провайдера: " + m.at_provider : (m.to ? "→ " + m.to : ""))}${m.how ? `<div class="anchor">${E(String(m.how).slice(0, 160))}</div>` : ""}</td>
    </tr>`).join("");
  return `<h2 id="movements">Движения ключей</h2>
    ${un.length ? `<div class="card"><p class="dmeta">${un.length} изменение(й) на Heroku за неделю, которых нет в журнале — правило оператора: записывает тот, кто двигал, в тот же ход</p>
      <ul class="dlist">${unrows}</ul></div>` : `<p class="none">каждое движение за неделю записано — на Heroku нет изменений без строки в журнале</p>`}
    ${rows ? `<div class="card"><table><colgroup><col style="width:12%"><col style="width:12%"><col style="width:30%"><col style="width:14%"><col></colgroup>
      <thead><tr><th>Когда</th><th>Что</th><th>Ключ</th><th>Кто</th><th>Куда / как</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
      <p class="dmeta">Последние ${mv.length} движений · полный журнал: <span class="mono">${E(toolCommand("vault.py", ["movements"]))}</span></p>`
      : `<p class="none">журнал движений пуст</p>`}`;
}

// THE ENV PAGE: one row per variable in the projects' env files, by name,
// class and git state. Values never reach the payload; a value is shown only
// on request from the local server, and only for a short time.

const CLS_RU = {secret: "секрет", config: "конфиг",
                placeholder: "заглушка", empty: "пусто"};
const CLS_KIND = {secret: "warn", config: "", placeholder: "", empty: ""};

const hayEnv = e => [e.name, e.path, e.project, e.cls,
  e.shared.join(" "), e.available.join(" ")].join(" ").toLowerCase();

// By default only secrets are shown, plus any variable whose value exists
// in another project; the two extra chips widen the view to config, empty
// values and templates.
function keepEnv(e, q, project) {
  if (q && !hayEnv(e).includes(q)) return false;
  if (project && e.project !== project) return false;
  if (!active.has("e-tpl") && e.kind === "template") return false;
  if (!active.has("e-all") && e.cls !== "secret" && !e.available.length) return false;
  if (active.has("e-shared") && !e.shared.length) return false;
  if (active.has("e-reuse") && !e.available.length) return false;
  if (active.has("e-git") && e.git !== "tracked") return false;
  if (active.has("e-open") && String(e.mode).slice(-2) === "00") return false;
  return true;
}

const envKey = e => e.path + " " + e.name;

// The rows currently on screen, by key, for the action buttons to find.
let ENV_ON_SCREEN = new Map();

// REVEAL: ask the local server for one value, then either copy it or show
// it for thirty seconds before it is hidden again.
function envReveal(btn, e, show) {
  const cell = btn.closest("td");
  btn.disabled = true;
  btn.textContent = "…";
  call("reveal", {path: e.path, name: e.name})
    .then(d => {
      if (!show) {
        return copyText(d.value).then(ok => {
          cell.innerHTML = envActions(e);
          toast(ok ? e.name + " скопирован" : "буфер недоступен");
        });
      }
      cell.innerHTML =
        '<code class="val" tabindex="0">' + E(d.value) + '</code>' +
        '<div class="anchor"><button class="chip-btn" type="button" data-envhide="1"' +
        '>скрыть</button> <button class="chip-btn" type="button" data-copy="' +
        E(d.value) + '">копировать</button> · скроется через 30с</div>';
      const t = setTimeout(() => {
        if (cell.isConnected) cell.innerHTML = envActions(e);
      }, 30000);
      cell.dataset.timer = String(t);
    })
    .catch(err => {
      cell.innerHTML = envActions(e);
      toast(((err instanceof Uncertain ? "исход неизвестен: " : "") + String(err.message)).slice(0, 140));
    });
}

function envActions(e) {
  if (LIVE) {
    return '<button class="chip-btn" type="button" data-env="' + E(envKey(e)) +
      '" data-show="1">показать</button> <button class="chip-btn" type="button" data-env="' +
      E(envKey(e)) + '">копировать</button>';
  }
  // Opened from a file: nothing can be revealed, so the button copies the
  // command that locates the value in a terminal.
  const project = e.project || (String(e.path || "").includes("/") ? String(e.path).split("/")[0] : "");
  if (!project || !e.name) return '<span class="unlinked">проект или имя не определены</span>';
  return '<button class="chip-btn" type="button" data-copy="' +
    E(toolCommand("use_secret.py", ["where", project, e.name])) +
    '">скопировать команду</button>';
}

document.addEventListener("click", ev => {
  const t = ev.target;
  if (!t || !t.closest) return;
  const hide = t.closest("[data-envhide]");
  if (hide) {
    const cell = hide.closest("td");
    clearTimeout(Number(cell.dataset.timer || 0));
    const e = ENV_ON_SCREEN.get(cell.dataset.key);
    if (e) cell.innerHTML = envActions(e);
    return;
  }
  const fold = t.closest(".grp-fold");
  if (fold) {
    const body = fold.closest("tbody");
    const open = fold.getAttribute("aria-expanded") === "true";
    fold.setAttribute("aria-expanded", String(!open));
    body.classList.toggle("folded", open);
    return;
  }
  const btn = t.closest("[data-env]");
  if (!btn) return;
  const e = ENV_ON_SCREEN.get(btn.dataset.env);
  if (e) envReveal(btn, e, btn.dataset.show === "1");
});

function renderEnv() {
  const out = document.getElementById("out");
  if (!D.env) {
    out.innerHTML = '<p class="empty">Файлы окружения не сканировались — ' +
      '<span class="mono">' + E(cliCommand('env')) + '</span></p>';
    return;
  }
  const q = document.getElementById("q").value.trim().toLowerCase();
  const rows = ENVV.filter(e => keepEnv(e, q, sel.value));
  ENV_ON_SCREEN = new Map(rows.map(e => [envKey(e), e]));
  if (!rows.length) {
    out.innerHTML = nothingFound(ENVV.length, 'По умолчанию показаны только секреты ' +
      'живых файлов — «+ конфиг и пустые» и «+ шаблоны» расширяют выборку.');
    return;
  }
  const state = e => {
    const bits = [chip(CLS_RU[e.cls] || e.cls, CLS_KIND[e.cls] || "")];
    if (e.kind === "template") bits.push(chip("шаблон", ""));
    if (e.git === "tracked") bits.push(chip("в git", e.cls === "secret" ? "danger" : "warn"));
    if (e.git === "loose") bits.push(chip("не игнорируется", "warn"));
    if (String(e.mode).slice(-2) !== "00") bits.push(chip(e.mode, "warn"));
    return bits.join(" ");
  };
  const links = e => {
    if (e.shared.length) {
      return e.shared.map(p => '<a class="plink" href="#project:' + E(p) + '">' + E(p) + '</a>').join(", ") +
        '<div class="tier">' + chip("то же значение · ротация затронет всех", "warn") + '</div>';
    }
    if (e.available.length) {
      return '<span class="anchor">значение есть в:</span> ' +
        e.available.map(p => '<a class="plink" href="#project:' + E(p) + '">' + E(p) + '</a>').join(", ");
    }
    return e.copies > 1
      ? '<span class="anchor">' + e.copies + ' копии в этом же проекте</span>'
      : NONE;
  };
  sortInPlace(rows, {name: e => lower(e.name), modified: e => dateOr(e.modified_on)});
  const groups = new Map();
  rows.forEach(e => {
    const key = SORT.key ? "Выбранные записи" : e.project;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
  });
  const row = e => '<tr id="e-' + E(anchorSlug(e.path + ":" + e.name)) + '" data-file="' + E(anchorSlug(e.path)) + '">' +
    '<td data-label="Переменная"><div class="name mono">' + E(e.name) + '</div>' +
    '<div class="anchor mono" title="' + E(e.path) + '">' + E(e.path) + '</div></td>' +
    '<td data-label="Что это">' + state(e) + '</td>' +
    '<td data-label="Связи">' + links(e) + '</td>' +
    '<td data-label="Изменён" class="num"><span class="mono">' + E(e.modified_on) + '</span></td>' +
    // Production: how the deployed configuration compares for this name.
    '<td data-label="Прод">' + (() => {
      const m = REMOTE_BY_FOLDER.get(e.project);
      if (!D.remote) return '<span class="anchor">не сканировалось</span>';
      if (!m) return NONE;
      const vs = (m.get(e.name) || []).slice().sort((a, b) =>
        VERDICT_ORDER.indexOf(a.verdict) - VERDICT_ORDER.indexOf(b.verdict) || String(a.app).localeCompare(String(b.app)));
      if (!vs.length) return '<span class="unlinked">нет у прода</span>';
      return vs.map(v => {
        const [word, kind] = VERDICT_RU[v.verdict] || [v.verdict, ""];
        return chip(word, kind) + '<div class="anchor">' + E(v.app) + '</div>';
      }).join("");
    })() + '</td>' +
    '<td data-label="Значение" data-key="' + E(envKey(e)) + '">' + envActions(e) + '</td></tr>';
  const t = D.env.totals || {};
  const howto = LIVE
    ? '«показать» и «копировать» действуют: страницу отдаёт ' +
      '<span class="mono">tools/keyserver.py</span>, и каждое раскрытие пишется в ' +
      '<span class="mono">store/logs/keyserver.jsonl</span> до того, как файл будет прочитан'
    : 'режим команд: кнопка копирует команду в буфер; выполните её в терминале. ' +
      'Запустите <span class="mono">' + E(toolCommand('keyserver.py')) + '</span>, ' +
      'чтобы раскрывать и копировать прямо отсюда';
  out.innerHTML = filterLine(rows.length, ENVV.length, "переменных") + '<div class="action-mode"><b>' + (LIVE ? 'Действия подключены' : 'Режим команд') + '</b> · ' + (LIVE ? 'Значение открывается только по запросу и затем скрывается.' : 'Кнопки копируют команды для терминала; значения здесь не показаны.') + '<details><summary>Как пользоваться действиями</summary>' + howto + '</details></div><div class="card"><table>' +
    '<colgroup><col style="width:26%"><col style="width:17%"><col style="width:20%">' +
    '<col style="width:9%"><col style="width:14%"><col style="width:14%"></colgroup>' +
    '<thead><tr>' + sortTh("Переменная", "name") + '<th>Что это</th><th>Связи</th>' + sortTh("Изменён", "modified") +
    '<th>Прод</th><th>Значение</th></tr></thead>' +
    [...groups].map(([p, es]) => {
      // Project headings provide context without hiding any variable metadata.
      const alarming = es.filter(e => e.cls === "secret" && e.git === "tracked");
      const open = true; // Metadata is visible; secret values still require explicit reveal.
      const secrets = es.filter(e => e.cls === "secret").length;
      return '<tbody class="grp' + (open ? '' : ' folded') + '" data-envgroup="' + E(p || "-") + '">' +
      '<tr><th colspan="6" scope="colgroup"><button class="grp-fold" type="button"' +
      ' aria-expanded="' + (open ? 'true' : 'false') + '">' + E(p || "вне проекта") +
      ' <span class="n">' + es.length + ' ' + plural(es.length, 'переменная', 'переменные', 'переменных') +
      (secrets ? ' · ' + secrets + ' ' + plural(secrets, 'секрет', 'секрета', 'секретов') : '') + '</span>' +
      (alarming.length ? ' ' + chip(alarming.length + " секрет(ов) в git", "danger") : '') +
      '</button></th></tr>' +
      es.map(row).join("") + '</tbody>';
    }).join("") + '</table></div>' +
    '<p class="dmeta">Показано ' + rows.length + ' из ' + ENVV.length + ' переменных · ' +
    (t.env_files || 0) + ' ' + plural(t.env_files || 0, 'живой файл', 'живых файла', 'живых файлов') + ' и ' +
    (t.templates || 0) + ' ' + plural(t.templates || 0, 'шаблон', 'шаблона', 'шаблонов') + ' в ' +
    (t.projects || 0) + ' ' + plural(t.projects || 0, 'проекте', 'проектах', 'проектах') + ' · ' + (t.secrets || 0) + ' читаются как секрет · ' +
    'общих значений: ' + (t.shared_across_projects || 0) + ' · измерено ' +
    E(D.env.scanned_on || "—") + '<br>' +
    '. Значений нет ни в этой странице, ни в реестре: «общее значение» установлено ' +
    'солёным отпечатком, а соль лежит вне git и не покидает машину.</p>';
}

// DOMAINS: the registrar's list joined with the Cloudflare zones, with
// measured liveness and expiry.
const DAY = 864e5;
const daysUntil = iso => iso ? Math.round((Date.parse(iso) - Date.now()) / DAY) : null;
const hayDom = d => [d.name, d.registrar || "", d.status || "",
  (d.projects || []).join(" ")].join(" ").toLowerCase();

function keepDom(d, q, registrar) {
  if (q && !hayDom(d).includes(q)) return false;
  if (registrar && d.registrar !== registrar) return false;
  if (active.has("d-noproject") && (d.projects || []).length) return false;
  // Liveness filters: not resolving, not measured, or answering with an
  // HTTP error.
  if (active.has("d-dark") && !(d.live && d.live.resolves === false)) return false;
  if (active.has("d-unmeasured") && d.live) return false;
  if (active.has("d-http") && !(d.live && d.live.resolves && (d.live.http >= 400 || d.live.http === 0))) return false;
  if (active.has("d-expiring")) { const n = daysUntil(d.expires_on); if (n === null || n > 90) return false; }
  if (active.has("d-norenew") && d.auto_renew !== false) return false;
  return true;
}

// MCP SERVERS, as each agent declares them: where the key sits and whether
// the server answered the last probe.
function renderMcp() {
  const out = document.getElementById("out");
  if (!D.mcp) {
    out.innerHTML = `<p class="empty">MCP не сканировался — <span class="mono">${E(cliCommand("scan-mcp"))}</span></p>`;
    return;
  }
  const q = document.getElementById("q").value.trim().toLowerCase();
  const ALL = D.mcp.servers || [];
  const rows = ALL.filter(s => (!q || [s.name, s.agent, s.scope, s.target || "", s.command || ""].join(" ").toLowerCase().includes(q))
    && (!sel.value || s.agent === sel.value)
    && (!active.has("m-url") || s.key_in_url)
    && (!active.has("m-down") || s.liveness === "failed")
    && (!active.has("m-auth") || s.liveness === "needs-auth")
    && (!active.has("m-alone") || ALL.filter(x => x.name === s.name).length === 1));
  if (!rows.length) { out.innerHTML = nothingFound(ALL.length); return; }
  const live = s => ({ connected: chip("отвечает", "ok"), failed: chip("не отвечает", "danger"),
    "needs-auth": chip("нужен вход", "warn"), "not-listed": chip("не в списке", "warn"),
    "not-probed": chip("не проверялся") })[s.liveness] || chip(s.liveness || "—");
  const keyPlace = s => s.key_in_url ? chip("в URL", "danger") : s.key_in_header ? "в заголовке" : s.key_in_env ? "в env" : NONE;
  sortInPlace(rows, {name: s => lower(s.name)});
  const groups = new Map();
  rows.forEach(s => { const k = SORT.key ? "Выбранные записи" : s.agent; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(s); });
  const row = s => `<tr id="m-${E(anchorSlug(s.agent + "/" + s.name))}">
    <td data-label="Сервер"><div class="name mono">${E(s.name)}</div><div class="anchor">${E(s.agent)} · ${E(s.scope)}</div></td>
    <td data-label="Транспорт">${E(s.transport || "—")}${s.command ? `<div class="anchor mono">${E(s.command)}${s.command_present === false ? " · нет на диске" : ""}</div>` : ""}</td>
    <td data-label="Цель"><span class="mono">${E(s.target || "")}</span></td>
    <td data-label="Ключ">${keyPlace(s)}</td>
    <td data-label="Связь">${live(s)}${s.liveness_detail ? `<div class="anchor">${E(s.liveness_detail)}</div>` : ""}</td></tr>`;
  const t = D.mcp.totals || {};
  out.innerHTML = filterLine(rows.length, ALL.length, "объявлений") + `<div class="card"><table>
    <colgroup><col style="width:22%"><col style="width:16%"><col style="width:26%"><col style="width:14%"><col style="width:22%"></colgroup>
    <thead><tr>${sortTh("Сервер", "name")}<th>Транспорт</th><th>Цель</th><th>Ключ</th><th>Связь</th></tr></thead>
    ${[...groups].map(([agent, ss]) => `<tbody class="grp">
      ${grpHead(5, `${E(agent)} <span class="n">${ss.length}</span>`, true)}
      ${ss.map(row).join("")}</tbody>`).join("")}</table></div>
    <p class="dmeta">${t.declarations || 0} объявлений · ${t.distinct_servers || 0} серверов ·
      ${t.in_one_agent_only || 0} только в одном агенте · ${t.key_in_url || 0} с ключом в URL ·
      собственный сервер обсерватории ${D.mcp.own_declared ? "объявлен" : "<b>не объявлен</b>"} ·
      скан ${E(D.mcp.scanned_on || "—")}</p>`;
}

// ANALYTICS PROPERTIES, grouped by account, each linked to a project by a
// named rule. An unclaimed property is not a defect by itself — it may belong
// to someone else — but it has a row, so the decision can be made.
const TRAFFIC_STANDING = { linked: ["привязан", "ok"], outside: ["вне эстейта", ""],
                           unclaimed: ["ничей", "warn"] };
const RULE_RU = { declared: "объявлено оператором", "declared-host": "хост из файла",
                  "stream-host": "по хосту потока", "app-id": "по id приложения",
                  name: "по имени property" };
function renderTraffic() {
  const out = document.getElementById("out");
  if (!D.google) {
    out.innerHTML = `<p class="empty">Аналитика не сканировалась — ` +
      `<span class="mono">${E(cliCommand("google"))}</span></p>`;
    return;
  }
  const ALL = D.google.properties || [];
  const q = document.getElementById("q").value.trim().toLowerCase();
  const rows = ALL.filter(p => (!q || [p.name, p.account_name, (p.hosts || []).join(" "),
      (p.app_ids || []).join(" "), p.project || ""].join(" ").toLowerCase().includes(q))
    && (!sel.value || p.account_name === sel.value)
    && (!active.has("t-unclaimed") || p.standing === "unclaimed")
    && (!active.has("t-linked") || p.standing === "linked")
    && (!active.has("t-quiet") || (p.users_30d === 0 && !p.error))
    && (!active.has("t-app") || ((p.app_ids || []).length && !(p.hosts || []).length)));
  if (!rows.length) { out.innerHTML = nothingFound(ALL.length); return; }
  const cell = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  const num = n => n == null ? NONE : `<span class="mono">${Number(n).toLocaleString("ru")}</span>`;
  sortInPlace(rows, {name: p => lower(p.name), users: p => numOr(p.users_30d)});
  const groups = new Map();
  rows.forEach(p => { const k = SORT.key ? "Выбранные записи" : p.account_name || "—";
    if (!groups.has(k)) groups.set(k, []); groups.get(k).push(p); });
  const row = p => `<tr id="g-${E(String(p.id).replace(/[^A-Za-z0-9_.:-]+/g, "-"))}">
    <td data-label="Property"><div class="name">${E(p.name || p.property)}</div>
      <div class="anchor mono">${E(p.property || "")} · ${E(p.account_name || "аккаунт не указан")}</div>
      ${(p.hosts || []).length ? `<div class="anchor">${(p.hosts || []).slice(0, 3).map(E).join(" · ")}${p.hosts.length > 3 ? ` +${p.hosts.length - 3}` : ""}</div>` : ""}
      ${(p.app_ids || []).length ? `<div class="anchor mono">${(p.app_ids || []).slice(0, 2).map(E).join(" · ")}${p.app_ids.length > 2 ? ` +${p.app_ids.length - 2}` : ""}</div>` : ""}</td>
    ${cell("Польз./30 дн", num(p.users_30d), "num")}
    ${cell("Сессий/30 дн", num(p.sessions_30d), "num")}
    ${cell("Просмотров", num(p.views_30d), "num")}
    ${cell("Проект", p.project
      ? `<a class="plink" href="#${E(p.project)}">${E(String(p.project).split(":")[1] || p.project)}</a>` +
        `<div class="anchor" title="${E(p.link_evidence || "")}">${E(RULE_RU[p.link_rule] || p.link_rule || "")}</div>`
      : `<span class="unlinked" title="${E(p.unlinked_reason || p.boundary_why || "")}">${
          p.standing === "outside" ? "вне эстейта" : "нет проекта"}</span>`)}
    ${cell("Связь", (() => { const [w, k] = TRAFFIC_STANDING[p.standing] || [p.standing, ""];
       return chip(w, k) + (p.error ? `<div class="tier">${chip(p.observation_conflicts ? "измерения расходятся" : "не ответила", "warn")}</div>` : ""); })())}
    ${cell("Куда смотреть", `<div class="verbs">` +
      `<a class="chip-btn" href="${E(p.report_url)}" target="_blank" rel="noopener" title="отчёт GA4">GA4</a>` +
      (p.admin_url ? `<a class="chip-btn" href="${E(p.admin_url)}" target="_blank" rel="noopener" title="настройки property">админка</a>` : "") +
      `</div>`)}</tr>`;
  const tt = D.google.totals || {};
  const creds = (D.google.credentials || []).map(c =>
    `<a class="chip-btn" href="${E(c.console_url)}" target="_blank" rel="noopener" title="${E(c.client_email || "")}">Cloud: ${E(c.cloud_project || "")}</a>`).join(" ");
  const sites = (D.google.search_console || []).map(s =>
    `<a class="chip-btn" href="${E(s.console_url)}" target="_blank" rel="noopener">Search Console: ${E(s.site)}</a>`).join(" ");
  out.innerHTML = filterLine(rows.length, ALL.length, "property") +
    `<div class="list-summary"><b>За 30 дней</b> · измерено ${E(D.google.scanned_on || "—")} · сумма по ресурсам не означает уникальных людей между ними${tt.unknown_properties ? " · без измерения: " + tt.unknown_properties : ""}. <button class="chip-btn" type="button" data-copy="${E(engineCommand("collectors/scan_google.py", [String(RUNTIME.scratch || ".") + "/google.json", "--force"]) + " && " + cliCommand("merge") + " && " + cliCommand("emit") + " && " + cliCommand("dashboard"))}"
        title="перечитать у Google и пересобрать страницы">Скопировать команду обновления</button></div>` +
    `<div class="card"><table>
    <colgroup><col style="width:26%"><col style="width:11%"><col style="width:11%"><col style="width:10%"><col style="width:14%"><col style="width:12%"><col style="width:16%"></colgroup>
    <thead><tr>${sortTh("Property", "name")}${sortTh("Польз./30 дн", "users")}<th>Сессий/30 дн</th><th>Просмотров</th>
      <th>Проект</th><th>Связь</th><th>Куда смотреть</th></tr></thead>
    ${[...groups].map(([acc, ps]) => `<tbody class="grp">
      ${grpHead(7, `${E(acc)} <span class="n">${ps.length}</span> <span class="n">${ps.some(p => p.users_30d != null) ? Number(ps.reduce((n, p) => n + (p.users_30d || 0), 0)).toLocaleString("ru") + " — сумма польз./30 дн" : "аудитория не измерена"}${ps.some(p => p.users_30d == null) ? " · неполное измерение" : ""}</span>`, true)}
      ${ps.map(row).join("")}</tbody>`).join("")}</table></div>
    <div class="verbs" style="margin: var(--space-3) var(--space-5) 0">${creds}${sites}</div>
    <p class="dmeta">Показано ${rows.length} из ${ALL.length} · ${tt.linked_to_a_project || 0} привязано,
      ${tt.unclaimed || 0} ничьих (${tt.users_30d_unclaimed == null ? "аудитория не измерена" : Number(tt.users_30d_unclaimed).toLocaleString("ru") + " польз. по измеренным ресурсам"}) ·
      сумма по измеренным ресурсам: ${tt.users_30d == null ? "не измерено" : Number(tt.users_30d).toLocaleString("ru")} польз. за 30 дней ·
      измерено ${E(D.google.scanned_on || "—")}
<br>
      Цифры кэшируются на 12 часов; время обновления зависит от числа подключённых ресурсов.
      Аналитика может обновляться с задержкой. «Ничей» — не дефект: по правилу оператора это продукт,
      которым занимается кто-то другой, — но строка есть, чтобы решение можно было принять один раз.</p>`;
}

function renderDomains() {
  const out = document.getElementById("out");
  const q = document.getElementById("q").value.trim().toLowerCase();
  // The registrar list and the Cloudflare zones are joined by name; a zone
  // no registrar lists still gets a row, marked as known from Cloudflare.
  const zoneBy = new Map((D.zones || []).map(z => [z.name, z]));
  const rows0 = DOMS.map(d => ({ ...d, zone: zoneBy.get(d.name) || null, source: zoneBy.has(d.name) ? "both" : "registrar" }));
  (D.zones || []).forEach(z => { if (!DOMS.some(d => d.name === z.name))
    rows0.push({ name: z.name, registrar: z.registrar ? z.registrar + " (по данным Cloudflare)" : "—",
      status: z.status, live: LIVE_BY_HOST(z.name), projects: z.project ? [z.project] : [],
      zone: z, source: "cloudflare" }); });
  const doms = rows0.filter(d => keepDom(d, q, sel.value));
  if (!doms.length) { out.innerHTML = nothingFound(rows0.length); return; }
  const PROD_BY_PROJECT = new Map(D.rows.map(r => [r.id, r.products || []]));
  const standing = d => {
    if (!d.zone) return d.projects && d.projects.length ? chip("привязан", "ok") : chip("нет проекта");
    const s = d.zone.standing;
    if (s === "linked") return chip("привязан", "ok");
    if (s === "outside") return `<span title="${E(d.zone.boundary_why || "")}">${chip("вне эстейта")}</span>`;
    if (s === "pending") return chip("ждёт слова", "warn");
    if (s === "dormant") return `<span title="DNS прочитан: апекс и www никуда не указывают">${chip("спит")}</span>`;
    if (s === "product") return chip("продукт", "ok");
    return chip("без слова", "warn");
  };
  const cfCell = d => d.zone
    ? `<span class="mono">${E(d.zone.account_label || "")}</span><div class="anchor">${E(d.zone.status || "")}${d.zone.paused ? " · paused" : ""} · ${E(d.zone.plan || "")}</div>`
    : NONE;
  const PROD_NAME = new Map((D.products || []).map(p => [p.id, p.name]));
  const prodCell = d => { const ps = (d.projects || []).flatMap(p => PROD_BY_PROJECT.get(p) || []);
    if (!ps.length && d.zone && d.zone.product) return E(PROD_NAME.get(d.zone.product) || d.zone.product);
    return ps.length ? ps.map(p => `<span title="${E(p.kind)}">${E(p.name)}${p.kind === "suggested" ? "?" : ""}</span>`).join(", ") : NONE; };
  const cell = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  const liveCell = d => {
    if (!d.live) return chip("не измерен");
    if (d.live.resolves === false) return chip("не резолвится", "danger");
  // Resolving but not answering is its own state, not an HTTP error.
    if (!d.live.http) return chip("резолвится, не отвечает", "warn");
    if (d.live.http >= 400) return chip("HTTP " + d.live.http, "warn");
    return chip("HTTP " + d.live.http, "ok");
  };
  const expiry = d => {
    const n = daysUntil(d.expires_on);
    if (n === null) return NONE;
    const word = n < 0 ? chip("истёк", "danger")
      : n <= 90 ? chip(n + " дн.", "warn") : `${n} дн.`;
    return `${E(d.expires_on)}<div class="tier">${word}` +
      (d.auto_renew === false ? " " + chip("без автопродления", "warn") : "") + `</div>`;
  };
  sortInPlace(doms, {name: d => lower(d.name), expiry: d => dateOr(d.expires_on)});
  const groups = new Map();
  doms.forEach(d => { const k = SORT.key ? "Выбранные записи" : d.registrar || "—";
    if (!groups.has(k)) groups.set(k, []); groups.get(k).push(d); });
  const row = d => `<tr id="d-${E(d.name)}">
    <td data-label="Домен"><div class="name"><a href="https://${E(d.name)}"
      target="_blank" rel="noopener">${E(d.name)}</a></div>
      <div class="anchor">${E(d.registrar || "регистратор не указан")} · ${E(d.status || "")}</div></td>
    ${cell("Отвечает", liveCell(d) + (d.live ? `<div class="anchor">${E(d.live.on)}</div>` : ""))}
    ${cell("Истекает", expiry(d), "num")}
    ${cell("Проект", (d.projects || []).length
      ? (d.projects || []).map(p => `<a class="plink" href="#${E(p)}">${E(p.split(":")[1])}</a>`).join(", ")
      : `<span class="unlinked">нет проекта</span>`)}
    ${cell("Связь", standing(d))}
    ${cell("Cloudflare", cfCell(d))}
    ${cell("Продукт", prodCell(d))}
    ${                                                                       
                                                                               ""}
    ${cell("Куда смотреть", `<div class="verbs">` +
      `<a class="chip-btn" href="https://rdap.org/domain/${E(d.name)}"
         target="_blank" rel="noopener" title="что говорит регистратор">RDAP</a>` +
      `<button class="chip-btn" type="button" data-copy="${E("dig +short " + shellArg(d.name) + " A AAAA CNAME")}"
         title="скопировать диагностическую команду">Команда: DNS</button>` +
      (d.zone ? `<a class="chip-btn" href="https://dash.cloudflare.com/?to=/:account/${E(d.name)}"
         target="_blank" rel="noopener" title="зона в Cloudflare">зона</a>` : "") +
      `</div>`)}</tr>`;
  out.innerHTML = filterLine(doms.length, rows0.length, "имён") + `<div class="card"><table>
    <colgroup><col style="width:18%"><col style="width:10%"><col style="width:11%"><col style="width:13%"><col style="width:11%"><col style="width:11%"><col style="width:12%"><col style="width:14%"></colgroup>
    <thead><tr>${sortTh("Домен", "name")}<th>Отвечает</th>${sortTh("Истекает", "expiry")}<th>Проект</th><th>Связь</th><th>Cloudflare</th><th>Продукт</th><th>Куда смотреть</th></tr></thead>
    ${[...groups].map(([reg, ds]) => `<tbody class="grp">
      ${grpHead(8, `${E(reg)} <span class="n">${ds.length}</span>`, true)}
      ${ds.map(row).join("")}</tbody>`).join("")}</table></div>
    <p class="dmeta">Показано ${doms.length} из ${rows0.length} ·
      ${rows0.filter(d => !(d.projects || []).length).length} не привязано ни к одному проекту ·
      ${D.zones ? `${D.zones.length} зон Cloudflare в ${new Set(D.zones.map(z => z.account_label)).size} аккаунтах` : "Cloudflare не сканировался"} ·
      цена продления здесь не измеряется</p>`;
}

const STATE_RU = { running: "работает", down: "упало", suspended: "приостановлено",
                   "resources-only": "только ресурсы", idle: "пусто" };

// PRODUCTION CONFIGURATION, compared with the local checkouts, indexed by app
// and by folder. Only verdicts arrive here, never a value.
const REMOTE_BY_APP = new Map(((D.remote && D.remote.apps) || []).map(a => [a.app, a]));
const REMOTE_BY_FOLDER = new Map();
for (const a of (D.remote && D.remote.apps) || [])
  for (const f of a.compared_with || []) {
    const key = String(f).replace(/\/+$/, "").split("/").pop();
    if (!REMOTE_BY_FOLDER.has(key)) REMOTE_BY_FOLDER.set(key, new Map());
    const m = REMOTE_BY_FOLDER.get(key);
    // EVERY APP, not the first: a prod and a staging app compared with one
    // folder each have their own verdict, and keeping only the first hid the other.
    for (const v of a.vars || []) {
      if (!m.has(v.name)) m.set(v.name, []);
      if (!m.get(v.name).some(x => x.app === a.app)) m.get(v.name).push({...v, app: a.app});
    }
  }
const VERDICT_ORDER = ["same_as_local", "local_only", "differs", "remote_only", "not_compared", "no_local_checkout"];
const VERDICT_RU = {
  same_as_local: ["то же, что локально", "danger"],
  differs: ["другое значение", "ok"],
  remote_only: ["только у прода", ""],
  local_only: ["только локально", "warn"],
  not_compared: ["не сравнивалось", ""],
  no_local_checkout: ["кода здесь нет", ""],
};

function renderHeroku() {
  const out = document.getElementById("out");
  if (!D.heroku) {
    // Never scanned is said as such, with the command that scans.
    out.innerHTML = `<p class="empty">Heroku не сканировался — ` +
      `<span class="mono">${E(cliCommand("heroku"))}</span></p>`;
    return;
  }
  const q = document.getElementById("q").value.trim().toLowerCase();
  const team = sel.value;
  const apps = APPS.filter(a => keepApp(a, q, team));
  if (!apps.length) { out.innerHTML = nothingFound(APPS.length); return; }
  const money = n => n == null || !Number.isFinite(Number(n)) ? "—" : "$" + Number(n).toLocaleString("en", {maximumFractionDigits: 2});
  sortInPlace(apps, {name: a => lower(a.name), cost: a => numOr(a.monthly_cost)});
  const groups = new Map();
  apps.forEach(a => { const key = SORT.key ? "Выбранные записи" : a.team; if (!groups.has(key)) groups.set(key, []); groups.get(key).push(a); });
  const cell = (label, html, cls) =>
    `<td data-label="${label}"${cls || html === NONE ? ` class="${
      [cls, html === NONE ? "e" : ""].filter(Boolean).join(" ")}"` : ""}>${html}</td>`;
  const appRow = a => {
    const dynos = (a.formation || []).filter(f => f.qty).map(f =>
      `<div class="st">${chip(`${E(f.type)}×${f.qty}`)}<span class="mono">${E(f.size)}</span></div>`).join("");
    const crashed = (a.crashed || []).length
      ? `<div class="tier">${chip("crashed: " + E(a.crashed.join(", ")), "danger")}</div>` : "";
    // Add-ons with their plan and monthly price.
    const planName = p => String(p || "").replace(/^heroku-/, "").replace(":", " ");
    const addons = (a.addons || []).length
      ? (a.addons || []).map(x => `<div class="st"><span>${E(planName(x.plan))}</span>` +
          (x.cents ? `<span class="mono">$${x.cents / 100}</span>` : "") + `</div>`).join("")
      : NONE;
    // An add-on attached from another app is shared, so changing it touches
    // that app too.
    const shared = (a.addons_attached || []).length
      ? `<div class="tier">${chip("общая с " + E(a.addons_attached.map(x => x.owner).join(", ")), "warn")}</div>` : "";
    const sha = a.deployed_commit && a.deployed_commit.sha
      ? `<div class="anchor mono" title="коммит из описания релиза v${E(a.deployed_commit.release)}">${E(a.deployed_commit.sha.slice(0, 8))}</div>` : "";
    const deploy = a.last_deploy_on
      ? E(a.last_deploy_on) + sha + (a.last_deploy_on < YEAR_AGO ? `<div class="tier">${chip("больше года", "warn")}</div>` : "")
      : `<span class="unlinked">${a.never_deployed ? "кода не было" : "не найден"}</span>`;
    // Why an app has no project: its source is outside, its folder is
    // unclaimed, or its source is unknown.
    const WHY_RU = { "external-repo": "источник вне нашего GitHub",
                     "folder-unclaimed": "папку не claim'ит ни один проект",
                     "no-source": "источник неизвестен" };
    const project = a.project
      ? `<a class="plink" href="#${E(a.project)}">${E(PROJ_NAME.get(a.project) || a.project)}</a>` +
        `<div class="anchor">${E(a.link_rule)}</div>`
      : `<span class="unlinked" title="${E(a.unlinked_reason || "")}">нет проекта</span>` +
        `<div class="anchor">${E(WHY_RU[a.unlinked_kind] || a.unlinked_kind || "")}</div>`;
    const folders = (a.local_folders || []).length
      ? (a.local_folders || []).map(p =>
          `<span class="folder">${E(p.replace(/^\/Users\/[^/]+\//, "~/"))}</span>`).join("")
      : `<span class="unlinked">нет папки</span>`;
    return `<tr id="a-${E(a.name)}">
      <td data-label="Приложение"><div class="name">${a.web_url
        ? `<a href="${E(a.web_url)}" target="_blank" rel="noopener">${E(a.name)}</a>`
        : E(a.name)}</div>
        <div class="anchor">${E(a.team || "аккаунт не указан")} · ${E(a.region)} · ${E(a.stack)}${a.stack_superseded ? " · стек снят с поддержки" : ""}</div></td>
      ${cell("Состояние", `<span class="st st-${E(a.state)}"><i></i>${E(STATE_RU[a.state] || a.state)}</span>` +
        (a.maintenance ? `<div class="tier">${chip("maintenance", "warn")}</div>` : "") + crashed)}
      ${cell("$/мес", money(a.monthly_cost), "num")}
      ${cell("Деплой кода", deploy, "num")}
      ${cell("Проект", project)}
      ${                                                                       
                                                                            ""}
      ${cell("Конфигурация", (() => {
        const r = REMOTE_BY_APP.get(a.name);
        if (!D.remote) return `<span class="unlinked">не сканировалось</span>`;
        if (!r) return `<span class="unlinked">нет в скане</span>`;
        if (r.error) return chip("не ответило", "warn");
        const c = r.counts || {};
        const n = (r.vars || []).length;
        if (!r.compared_with.length)
          return `<span class="mono">${n}</span><div class="anchor">переменных; кода здесь нет, сравнить не с чем</div>`;
        return `<span class="mono">${n}</span><div class="anchor">переменных</div>` +
          (c.same_as_local ? `<div class="tier">${chip(c.same_as_local + " как локально", "danger")}</div>` : "") +
          ((r.retired_in_use || []).length
            ? `<div class="tier">${chip((r.retired_in_use || []).length + " отставных", "danger")}</div>` : "") +
          `<div class="anchor">${c.differs || 0} отличается · ${c.remote_only || 0} только тут</div>`;
      })() + shared + `<details class="resource-detail"><summary>Ресурсы и папки</summary><b>Дино</b>${dynos || NONE}<b>Дополнения</b>${addons}<b>Код на машине</b>${folders}</details>`)}
      ${cell("Команда", `<div class="verbs">` +
        [["перезапуск", `heroku ps:restart -a ${a.name}`],
         ["логи", `heroku logs -t -a ${a.name}`],
         ...(a.state === "suspended" || a.state === "resources-only"
             ? [["что это", `heroku apps:info -a ${a.name}`]] : [])]
        .map(([label, cmd]) => `<button class="chip-btn" type="button"
              data-copy="${E(cmd)}" title="${E(cmd)}">Команда: ${E(label)}</button>`).join(" ")
        + `</div>`)}</tr>`;
  };
  const total = apps.reduce((n, a) => n + (Number(a.monthly_cost) || 0), 0);
  out.innerHTML = filterLine(apps.length, APPS.length, "приложений") +
    `<div class="list-summary"><b>${money(total)}/мес</b> · оценка выбранных приложений по прайс-листу, не счёт · измерено ${E(D.heroku.scanned_on || "—")}</div><div class="card"><table>
    <colgroup><col style="width:20%"><col style="width:10%"><col style="width:8%"><col style="width:12%"><col style="width:16%"><col style="width:22%"><col style="width:12%"></colgroup>
    <thead><tr>
      ${sortTh("Приложение", "name")}<th>Состояние</th>
      ${sortTh("$/мес", "cost")}<th>Деплой кода</th><th>Проект</th>
      <th>Конфигурация</th><th>Команда</th>
    </tr></thead>${[...groups].map(([team, as]) => `<tbody class="grp">
      ${grpHead(7, `${E(team)} <span class="n">${as.length}</span> <span class="n">${money(as.reduce((n, a) => n + a.monthly_cost, 0))}/мес</span>`, true)}
      ${as.map(appRow).join("")}</tbody>`).join("")}</table></div>
    <p class="dmeta">Показано ${apps.length} из ${APPS.length} · ${money(total)}/мес ·
      измерено ${E(D.heroku.scanned_on || "—")} ·
      цена по прайс-листу on-demand, не по счёту</p>`;
}

// A long repository list inside a cell folds after three; the button
// toggles it.
document.getElementById("out").addEventListener("click", e => {
  const b = e.target.closest(".more");
  if (!b) return;
  const list = b.previousElementSibling;
  const folded = list.classList.toggle("folded");
  b.textContent = folded ? `+${list.children.length - 3} ещё` : "свернуть";
});

// STICKY HEADERS. The table header sticks below the top bar and the
// controls, whose heights change with wrapping, so both are measured.
const bar = document.querySelector(".controls");
const topbar = document.getElementById("topbar");
const stick = () => {
  // Both offsets are CSS variables, set from the measured heights.
  const top = topbar ? topbar.offsetHeight : 0;
  document.documentElement.style.setProperty("--topbar", top + "px");
  document.documentElement.style.setProperty("--stick", (top + bar.offsetHeight) + "px");
};
new ResizeObserver(stick).observe(bar);
if (topbar) new ResizeObserver(stick).observe(topbar);
// THE REVIEW QUEUE, read-only: the newest proposals, each with the commands
// that accept or reject it. The decision itself is taken in a terminal.
(function renderQueue() {
  const host = document.getElementById("queue"), head = document.getElementById("queue-h");
  const q = D.queue || [];
  if (!q.length) {
    head.textContent = "Ждёт решения человека";
    host.innerHTML = `<p class="none">${D.store_degraded
      ? E(D.store_degraded) : "ничего не предложено — очередь пуста"}</p>`;
    return;
  }
  // The header says how many are shown of how many wait in total.
  const total = (D.health && D.health.proposed) || q.length;
  head.textContent = `Ждёт решения человека — ${q.length} из ${total}`;
  // One line above the rows: what waits, of which kinds, and what
  // retention erases first.
  const dg = D.digest || null;
  const digestLine = dg ? `<p class="dmeta" id="queue-digest">${dg.waiting} ждёт: ` +
    Object.entries(dg.by_kind || {}).map(([k, n]) => `${n} ${E(k)}`).join(", ") +
    ` · ретеншен стирает предложение через ${dg.horizon_days} дн` +
    (dg.erases_within_7d ? ` — <b>${dg.erases_within_7d}</b> уйдёт до ${E(dg.first_erase_on || "")}` : " — на этой неделе ничего не уйдёт") +
    ` · <button class="chip-btn" type="button" data-copy="${E(toolCommand("review.py", ["digest"]))}" title="скопировать команду">Команда: сводка очереди</button></p>` : "";
  host.innerHTML = digestLine + q.map(r => {
    const ok = toolCommand("review.py", ["promote", r.id, "--why", ""]);
    const no = toolCommand("review.py", ["reject", r.id, "--why", ""]);
    return `<div class="qrow" id="q-${E(r.id)}">
      <span class="qm">${E(r.at)}<br>${E(r.kind)}</span>
      <span>${E(r.statement)}${r.project
        ? ` <a class="plink" href="projects.html#${E(r.project)}">${E(String(r.project).split(":")[1])}</a>` : ""}
        <div class="anchor mono">${E(r.id)} r${E(r.rev)}</div>
        <div class="qacts"><button class="chip-btn" type="button" data-copy="${E(ok)}"
             title="скопировать команду принятия">Команда: принять</button>
          <button class="chip-btn" type="button" data-copy="${E(no)}"
             title="скопировать команду отклонения">Команда: отклонить</button></div></span>
    </div>`;
  }).join("") +
    `<p class="none">Кнопка кладёт команду в буфер — решение принимается в терминале
      (<span class="mono">${E(cliCommand("review"))}</span> для списка):
      запись без терминала отклоняется намеренно, и флага <span class="mono">--yes</span> нет.</p>`;
})();

(function renderFindings() {
  const F = D.findings, host = document.getElementById("findings");
  if (!F) {
    // Never built is said as such, with the command that builds it.
    host.innerHTML = `<div class="fh">находки <span class="when">не строились — ` +
      `${E(cliCommand("findings"))}</span></div>`;
    return;
  }
  const c = F.counts, when = E((F.built_at || "").slice(0, 16).replace("T", " "));
  const RU = { critical: ["критично", "danger"], warning: ["внимание", "warn"],
               info: ["к сведению", ""] };
  const openCount = (c.critical || 0) + (c.warning || 0) + (c.info || 0);
  host.innerHTML = (openCount === 0 ? '<p class="empty">Нет открытых находок.</p>' : '') +
    `<div class="fh">Находки <span class="when">${c.critical || 0} критично · ` +
    `${c.warning || 0} внимание · ${c.info || 0} к сведению` +
    // Silenced findings are counted in the header too, so what was
    // acknowledged away is never invisible.
    `${(F.silenced || []).length ? ` · ${F.silenced.length} заглушено` : ""}` +
    `${F.elsewhere ? ` · <a href="findings.html">подробности и ещё ${F.elsewhere} — на странице находок</a>` : ""}` +
    ` · без изменений с ${when}</span></div>` +
    // The findings page gets its own filter bar: severity chips, a type
    // selector with per-type counts, and a search box. Elsewhere, anything
    // below critical sits behind one "show more" control.
    (PAGE === "findings"
      ? `<div class="fbar" role="group" aria-label="Сужение находок">` +
        ["critical", "warning", "info"].map(s => `<button class="chip-btn" type="button" data-sev="${s}" aria-pressed="false">${RU[s][0]} <span class="n">${c[s] || 0}</span></button>`).join("") +
        `<select class="ftype" aria-label="Тип находки"><option value="">все типы</option>` +
        Object.entries(F.items.reduce((m, f) => (m[f.type] = (m[f.type] || 0) + 1, m), {})).sort()
          .map(([k, n]) => `<option value="${E(k)}">${E(k)} · ${n}</option>`).join("") +
        `</select><input type="search" class="fq" placeholder="Поиск по находкам" aria-label="Поиск по находкам">` +
        `<span class="fshown" role="status"></span></div>`
      : "") +
    `<div class="flist">` + F.items.map(f => {
      const [word, kind] = RU[f.severity] || [f.severity, ""];
      // Acknowledging is done in a terminal; the button copies that command.
      const cmd = toolCommand("ack.py", [f.id, "--why", ""]);
      const foldCls = ""; // Every selected finding is visible.
      // Each row has a stable anchor, so a link can point at one finding.
      const fid = "f-" + String(f.id).replace(/[^A-Za-z0-9_.:-]+/g, "-");
      const subj = subjectHref(f.subject);
      return `<div class="f${f.severity === "critical" ? "" : " f" + f.severity}${foldCls}" id="${E(fid)}" data-type="${E(f.type)}" data-sev="${E(f.severity)}">${chip(word, kind)}` +
        `<span class="t">${E(f.title)}` +
        (subj ? ` <a class="plink fsubj" href="${E(subj[0])}" title="открыть ${E(subj[1])}">→ ${E(subj[1])}</a>` : "") +
        (PAGE === "findings" ? ` <a class="fperma" href="#${E(fid)}" title="ссылка на эту строку">#</a>` : "") +
        `</span>` +
        (f.deadline ? `<span class="due">до ${E(f.deadline)}</span>` : "") +
        (PAGE === "index" ? `<a class="fdetail" href="findings.html#${E(fid)}">Разобрать →</a>` :
          `<details class="finding-body"><summary>Основание и действие</summary><p class="d">${E(f.detail)}</p>` +
          `<p class="act">${E(f.action)}</p>` +
          ` <button class="chip-btn ack" type="button" data-cmd="${E(cmd)}" title="скопировать команду заглушения">Команда: заглушить</button></details>`) + '</div>';
    }).join("") +
    `</div>` +
    // Silenced findings are listed with who silenced them, when and why,
    // and the command that brings each back.
    ((F.silenced || []).length ? `<details class="silenced"><summary>заглушено ${F.silenced.length} — ` +
      `на странице и в счётчиках их нет; здесь видно, кто, когда и почему</summary>` +
      F.silenced.map(s => `<div class="f fsilenced">${chip("заглушено")}<span class="t">${E(s.title)}</span>` +
        `<span class="d">${E(s.acked.why || "без причины")} — ${E(s.acked.by || "?")}` +
        `${s.acked.until ? `, до ${E(s.acked.until)}` : ""}</span>` +
        `<span class="act"><button class="chip-btn ack" type="button" data-cmd="${E(toolCommand("ack.py", ["--undo", s.id]))}">Команда: вернуть</button></span></div>`).join("") +
      `</details>` : "");
  // Copy buttons for acknowledge and undo, and per-type unfolding.
  host.querySelectorAll("button.ack").forEach(b => b.addEventListener("click", () => {
    const cmd = b.getAttribute("data-cmd"), label = b.textContent;
    copyText(cmd).then(ok => {
      toast(ok ? `скопировано: ${cmd.slice(0, 48)}…` : "буфер недоступен — скопируйте из подсказки");
      if (ok) { b.textContent = "скопировано"; setTimeout(() => { b.textContent = label; }, 1500); }
    });
  }));
  host.querySelectorAll("button.ftype").forEach(b => b.addEventListener("click", () => {
    const type = b.getAttribute("data-type");
    const rows = host.querySelectorAll(`.f.ftype-folded[data-type="${type.replace(/"/g, '\\"')}"]`);
    const open = b.getAttribute("aria-expanded") !== "true";
    rows.forEach(r => r.classList.toggle("ftype-open", open));
    b.setAttribute("aria-expanded", String(open));
    b.textContent = open ? `свернуть ${type}` : `ещё ${rows.length} типа ${type}`;
  }));
  if (PAGE === "findings") {
    const bar = host.querySelector(".fbar");
    const sevOn = new Set();
    const rows = [...host.querySelectorAll(".flist > .f")];
    const apply = () => {
      const type = bar.querySelector(".ftype").value;
      const q = bar.querySelector(".fq").value.trim().toLowerCase();
      let shown = 0;
      rows.forEach(r => {
        const ok = (!sevOn.size || sevOn.has(r.dataset.sev)) && (!type || r.dataset.type === type)
          && (!q || r.textContent.toLowerCase().includes(q));
        r.classList.toggle("fhide", !ok);
        if (ok) shown++;
      });
      // While anything narrows the list, per-type folding is set aside.
      host.querySelectorAll("button.ftype").forEach(b => { b.hidden = !!(sevOn.size || type || q); });
      if (sevOn.size || type || q) host.querySelectorAll(".f.ftype-folded").forEach(r => r.classList.add("ftype-open"));
      const what = [];
      if (sevOn.size) what.push([...sevOn].map(s => RU[s][0]).join(", "));
      if (type) what.push("тип " + type);
      if (q) what.push(`поиск «${q}»`);
      bar.querySelector(".fshown").innerHTML = `показано ${shown} из ${rows.length}` +
        (what.length ? ` · ${E(what.join(" · "))} <button class="chip-btn" type="button" data-fclear>сбросить</button>` : "");
      let none = host.querySelector(".fnone");
      if (!shown && what.length) {
        if (!none) { none = document.createElement("p"); none.className = "empty fnone"; host.querySelector(".flist").before(none); }
        none.innerHTML = `Ничего не найдено с этим сужением — ${E(what.join(" · "))}. <button class="chip-btn" type="button" data-fclear>сбросить</button>`;
      } else if (none) none.remove();
    };
    bar.querySelectorAll("[data-sev]").forEach(b => b.addEventListener("click", () => {
      const on = b.getAttribute("aria-pressed") === "true";
      b.setAttribute("aria-pressed", String(!on));
      on ? sevOn.delete(b.dataset.sev) : sevOn.add(b.dataset.sev);
      apply();
    }));
    bar.querySelector(".ftype").addEventListener("change", apply);
    bar.querySelector(".fq").addEventListener("input", apply);
    host.addEventListener("click", ev => {
      if (!(ev.target.closest && ev.target.closest("[data-fclear]"))) return;
      sevOn.clear();
      bar.querySelectorAll("[data-sev]").forEach(b => b.setAttribute("aria-pressed", "false"));
      bar.querySelector(".ftype").value = ""; bar.querySelector(".fq").value = "";
      apply();
    });
    // A finding named in the URL hash is unfolded and scrolled into view.
    const reveal = () => {
      const target = location.hash && location.hash.startsWith("#f-") && document.getElementById(location.hash.slice(1));
      if (target) {
        const body = target.querySelector(".finding-body"); if (body) body.open = true;
        sevOn.clear(); bar.querySelector(".ftype").value = ""; bar.querySelector(".fq").value = "";
        bar.querySelectorAll("[data-sev]").forEach(b => b.setAttribute("aria-pressed", "false"));
        apply(); target.scrollIntoView({block: "center"});
      }
    };
    reveal(); window.addEventListener("hashchange", reveal);
    apply();
  }
  const fold = document.getElementById("finfo");
  if (fold) fold.addEventListener("click", () => {
    const list = host.querySelector(".flist");
    const shown = list.classList.toggle("folded") === false;
    fold.setAttribute("aria-expanded", String(shown));
    const n = F.items.filter(f => f.severity !== "critical").length;
    fold.textContent = shown ? "свернуть" : `показать ещё ${n} (внимание и к сведению)`;
  });
})();

if (PAGE) {
  // A split page: mark the body with its name, so the CSS shows only this
  // page's parts, and turn the tab buttons into links between pages.
  const bodyEl = document.body || document.documentElement;
  if (bodyEl && bodyEl.setAttribute) bodyEl.setAttribute("data-page", PAGE);
  if (TABLE_PAGES.includes(PAGE)) { tab = PAGE; active = activeBy[tab] || new Set(); }
  for (const t of TABLE_PAGES) {
    const b = document.getElementById("tab-" + t);
    if (b) { b.onclick = () => { location.href = t + ".html"; };
             b.setAttribute("aria-selected", String(t === tab)); }
    const s = document.getElementById("seg-" + t);
    if (s) s.hidden = t !== tab;
  }
  // The selector is filled for this page's tab.
  if (typeof fillOwners === "function" && TABLE_PAGES.includes(PAGE)
      && typeof SEL_BY_TAB !== "undefined" && SEL_BY_TAB[tab]) fillOwners();
}
stick();
render();
// Finally, open whatever the URL hash names.
fromHash();
</script>
</body>
</html>
"""

TEMPLATE = TEMPLATE.replace("</style>", (Path(__file__).with_name("workspace.css").read_text(encoding="utf-8")) + "\n</style>")

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(OUT, build())
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    # The split pages, from the same payload: docs/dashboard/index.html is what
    # a person opens; the single page above is what the checks read.
    sizes = build_pages(build.last_payload)
    print(f"wrote {len(sizes)} page(s) under {paths.DASHBOARD_DIR}: "
          + ", ".join(f"{k} {v // 1024} KB" for k, v in sizes.items()))