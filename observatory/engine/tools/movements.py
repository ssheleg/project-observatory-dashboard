#!/usr/bin/env python3
"""Every movement of every key, read from the one journal that records them —
and the provider changes no journal names.

ONE READER FOR TWO SURFACES. `build_findings.py` needs the movements journal
to raise `secret.moved_unrecorded`, and the keys page needs to show it; reading
it inline in both places would copy the same logic into the dashboard build,
and two readers of one file is how one of them drifts. Both call here.

WHAT A MOVEMENT IS. A row in `<store>/projects/movements.jsonl` written by the
tools (`put`, `rotate`, `moved`, a door's `issue`/`rotate`/`disable`) — plus
the leak register's SETTLED rows, whose `how` names the release that replaced
a value, so a settlement is a movement on the record even from before the
journal existed. Names, places, dates, the `how`. Never a value.

WHAT UNRECORDED MEANS. Heroku's config trail (names only, `config_releases` in
the Heroku scan) shows a secret-shaped variable changing at the provider, and
no movement within two hours names that variable or its stem — and no
settlement or hand record names the release (`v1081`). The operator's rule:
every movement of every key is recorded by the agent that made it, in the same
turn; the tools do it themselves, a hand-made change is `vault.py moved`.
"""
from __future__ import annotations
import json
import pathlib
import re
from datetime import datetime, timedelta, timezone

#: A variable whose NAME says it holds a credential. The trail carries names
#: only, so the name is all there is to judge by.
SECRETISH = re.compile(r"(KEY|TOKEN|SECRET|PASS|DATABASE|DSN|CREDENTIAL|PRIVATE)", re.I)
#: A movement within this many hours of a release is that release's record.
WINDOW_HOURS = 2
#: How far back the trail is read.
DAYS = 7


def read_moves(leaks_path: pathlib.Path) -> list[dict]:
    """The journal beside the leak register, plus the register's settled rows.
    Unparseable lines are skipped: a half-written line is a crash somewhere
    else, and this reader is not the place to report it."""
    moves_file = leaks_path.parent / "movements.jsonl"
    out: list[dict] = []
    for mf in (moves_file, leaks_path):
        if not mf.is_file():
            continue
        try:
            text = mf.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if mf is leaks_path and row.get("event") != "settled":
                continue
            out.append(row)
    return out


def journal_tail(leaks_path: pathlib.Path, limit: int = 30) -> list[dict]:
    """The newest movements for a page: when, what, who, how, where — and
    nothing else, because a page is a thing people forward."""
    rows = sorted(read_moves(leaks_path), key=lambda r: r.get("at") or "", reverse=True)[:limit]
    keep = ("at", "event", "secret", "of", "by", "how", "at_provider", "to", "tool")
    return [{k: r.get(k) for k in keep if r.get(k) not in (None, "")} for r in rows]


def _when(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat((stamp or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def recorded(var: str, at: str, moves: list[dict], version=None) -> bool:
    """Does the journal own this change — by release number, or by name within
    the window?"""
    stem = var.split("_")[0].lower()
    if version is not None:
        for mv in moves:
            if f"v{version}" in json.dumps(mv, ensure_ascii=False):
                return True
    when = _when(at)
    if when is None:
        return False
    for mv in moves:
        mat = _when(mv.get("at") or "")
        if mat is None or abs((mat - when).total_seconds()) > WINDOW_HOURS * 3600:
            continue
        blob = json.dumps(mv, ensure_ascii=False).lower()
        if var.lower() in blob or f"/{stem}" in blob or f"{stem}_" in blob:
            return True
    return False


def unrecorded(hk_trail: dict[str, list], moves: list[dict],
               now: datetime | None = None, days: int = DAYS) -> list[dict]:
    """One row per release that moved a secret-shaped variable nobody recorded:
    app, version, when, the variables, who — structured, so a page can compose
    the `vault.py moved` that would settle it and a finding can list it."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[dict] = []
    for app, trail in sorted(hk_trail.items()):
        for rel in trail or []:
            if (rel.get("at") or "") < since:
                continue
            secretish = [v for v in (rel.get("vars") or []) if SECRETISH.search(v)]
            missing = [v for v in secretish if not recorded(v, rel.get("at") or "", moves, rel.get("version"))]
            if missing:
                out.append({"app": app, "version": rel.get("version"), "at": rel.get("at"),
                            "vars": missing, "by": rel.get("by")})
    return out


def describe(row: dict) -> str:
    """The one-line spelling the finding has always used."""
    return (f"{row['app']} v{row.get('version')} {(row.get('at') or '')[:16]}Z: "
            f"{', '.join(row['vars'])} ({row.get('by')})")
