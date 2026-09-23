#!/usr/bin/env python3
"""host -> project_id, from what the registry already knows.

The one thing this estate has that a raw analytics export does not: it knows
WHOSE each host is. Traffic sources speak hostnames (a Cloudflare zone, a GSC
property, a GA4 stream); the registry's projects claim sites and the domain
registry claims apexes. This helper is that join, written once — every
analytics plugin maps through it, so a host that changes owners changes owner
everywhere at the next emit.

Resolution order, most specific first:

  1. a project's own `sites[].host`     (the project claimed the host)
  2. the apex of such a site            (`www.x.com` -> the project of `x.com`)
  3. a `public_domain_of` relation      (domain -> project edge)

A host nothing claims resolves to None, and the CALLER must report it rather
than drop it: an unmapped host with traffic is a finding about the registry,
not noise (the caller decides which; this module only answers).
"""
from __future__ import annotations
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import paths                                                        # noqa: E402


def _load(name: str) -> dict:
    return json.loads((paths.REGISTRY / name).read_text(encoding="utf-8"))


def build() -> dict[str, str]:
    """The whole map, lowercase host -> project_id."""
    out: dict[str, str] = {}
    rel = _load("relations.json")["relations"]
    for r in rel:
        if r["type"] == "public_domain_of":
            host = r["from"].split(":", 1)[1].lower()
            out.setdefault(host, r["to"])
    # Sites OVERRIDE relations: a site on the project row is the more specific
    # claim, and the loop runs second so its writes win. Between two projects
    # claiming one host the EVIDENCE decides — the operator's word, then a
    # config in a local checkout, then GitHub, then Bitbucket, then a wiki
    # mention (`estate_surfaces.EVIDENCE_RANK`, the operator's own order).
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "collectors"))
    import estate_surfaces
    rank: dict[str, int] = {}
    for p in _load("projects.json")["projects"]:
        for s in p.get("sites") or []:
            host = (s.get("host") or "").lower()
            if not host:
                continue
            r = estate_surfaces.evidence_rank(s.get("evidence") or [])
            if host not in rank or r < rank[host]:
                out[host] = p["id"]
                rank[host] = r
    return out


def resolve(host: str, table: dict[str, str] | None = None) -> str | None:
    """One host to one project, or None — never a guess.

    `www.` and a single leading label fall back to the apex, because a zone is
    registered at the apex while a site may be claimed with or without `www`.
    Deeper subdomains fall back only to a claimed apex, not to each other.
    """
    t = table if table is not None else build()
    h = (host or "").lower().strip().rstrip(".")
    if not h:
        return None
    if h in t:
        return t[h]
    if h.startswith("www.") and h[4:] in t:
        return t[h[4:]]
    parts = h.split(".")
    if len(parts) > 2:
        apex = ".".join(parts[-2:])
        if apex in t:
            return t[apex]
    return None


if __name__ == "__main__":                                  # a quick look
    t = build()
    print(f"{len(t)} host(s) mapped; e.g.")
    for h in sorted(t)[:8]:
        print(f"  {h} -> {t[h]}")
