"""Provider accounts as entities, and the `in_account` edges that point at them.

Contract: docs/design/DEPLOYMENTS.md, rule 3 and slice PB-004a (PB-127).

- An account id is `account:<provider>/<the provider's own account id>`. The
  label (a team name, an account name the operator chose) is display only, so
  renaming a team does not change the id.
- A resource gets an `in_account` edge only when its provider stated the
  account. A Heroku app names its team (`team.id`), or, for a personal app, its
  owner (`owner.id`); a Cloudflare zone names its account (`account.id`). A
  resource whose account was not stated has no edge and is listed under
  `unattributed` with the reason. It is never attached to the only account in
  sight.
- No e-mail address becomes an id. A Heroku owner is identified by its user
  id; its e-mail stays where the scan already kept it.

Written by collectors/emit_registry.py as `registry/accounts.json`; edges go
into relations.json with a `rule` (validate_registry refuses a derived edge
without one).
"""
from __future__ import annotations

HEROKU_SRC = ["SRC-0013"]      # Heroku Platform API (emit_registry SOURCES)
ZONES_SRC = ["SRC-0016"]       # Cloudflare zone listings


def heroku_account(app: dict) -> tuple[str, str, str] | None:
    """(account id, label, rule) for one Heroku scan row, or None when not stated."""
    team_id = app.get("team_id")
    if team_id:
        return f"account:heroku/{team_id}", app.get("team") or team_id, "heroku-team"
    owner_id = app.get("owner_id")
    if owner_id and (app.get("team") in (None, "", "personal")):
        return f"account:heroku/{owner_id}", "personal", "heroku-owner"
    return None


def cloudflare_account(zone: dict) -> tuple[str, str, str] | None:
    """(account id, label, rule) for one zone registry row, or None when not stated."""
    account_id = zone.get("account_id")
    if not account_id:
        return None
    label = zone.get("account_label") or zone.get("account") or account_id
    return f"account:cloudflare/{account_id}", label, "cloudflare-zone-account"


def build(heroku_scan_apps: list[dict], zone_rows: list[dict], obs_date: str,
          heroku_scanned: bool, zones_scanned: bool) -> tuple[dict, list[dict]]:
    """(accounts.json document, in_account edges)."""
    accounts: dict[str, dict] = {}
    edges: list[dict] = []
    unattributed: list[dict] = []
    degraded: list[dict] = []

    def attach(resource: str, found, why_missing: str, src: list[str]) -> None:
        if not found:
            unattributed.append({"resource": resource, "why": why_missing})
            return
        aid, label, rule = found
        provider = aid.split(":", 1)[1].split("/", 1)[0]
        acc = accounts.setdefault(aid, {"id": aid, "provider": provider, "label": label, "resources": 0})
        acc["resources"] += 1
        edges.append({"id": f"relation:{resource}:in-account:{aid.split(':', 1)[1]}",
                      "type": "in_account", "from": resource, "to": aid, "rule": rule,
                      "source_refs": src})

    ids_missing = [a for a in heroku_scan_apps if "team_id" not in a and "owner_id" not in a]
    if heroku_scan_apps and ids_missing:
        # A scan written before 0.3.3 recorded team names only. Its apps are
        # unattributed until the next Heroku scan, not guessed from the name.
        degraded.append({"source": "heroku", "reason": f"{len(ids_missing)} app(s) come from a scan that "
                         "predates account ids; the next Heroku scan attributes them"})
    for a in sorted(heroku_scan_apps, key=lambda x: x["name"]):
        attach("heroku:" + a["name"], heroku_account(a),
               "the scan predates account ids" if a in ids_missing else "Heroku stated no team and no owner", HEROKU_SRC)
    for z in sorted(zone_rows, key=lambda x: x["id"]):
        attach(z["id"], cloudflare_account(z), "Cloudflare stated no account for this zone", ZONES_SRC)
    if not heroku_scanned:
        degraded.append({"source": "heroku", "reason": "no Heroku scan; Heroku accounts are not listed"})
    if not zones_scanned:
        degraded.append({"source": "cloudflare", "reason": "no zone scan; Cloudflare accounts are not listed"})
    doc = {
        "schema_version": 1, "updated_on": obs_date,
        "note": ("Provider accounts as entities (docs/design/DEPLOYMENTS.md). An id is the provider's own "
                 "account id; the label is display only. A resource is attached only when its provider "
                 "stated the account; the rest are listed under `unattributed`."),
        "accounts": sorted(accounts.values(), key=lambda a: a["id"]),
        "unattributed": unattributed,
        "totals": {"accounts": len(accounts), "attributed": len(edges), "unattributed": len(unattributed)},
        "degraded": degraded,
        "source_refs": (HEROKU_SRC if heroku_scanned else []) + (ZONES_SRC if zones_scanned else []),
    }
    return doc, edges
