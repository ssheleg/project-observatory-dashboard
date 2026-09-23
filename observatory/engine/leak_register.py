"""One rule for when a leak-register row closes a recorded exposure.

Up to 0.2.0, ``vault.py rotate`` appended ``{"event": "settled", "by":
"rotation"}`` after replacing a local slot. A local replacement proves neither
provider revocation nor consumer rollout, so such a row does not close the
exposure; the leak reads as open again and is labelled ``legacy_rotation``.
Manual ``settle`` rows (with ``how``) and 0.2.1+ attested rows still close it.
"""
from __future__ import annotations


def is_legacy_rotation(row: dict) -> bool:
    return (row.get("event") == "settled" and row.get("by") == "rotation"
            and "verification" not in row)


def settles(row: dict) -> bool:
    """True when this row closes the leak named by its ``of``."""
    return row.get("event") == "settled" and bool(row.get("of")) and not is_legacy_rotation(row)


def settled_ids(rows) -> set:
    return {r.get("of") for r in rows if settles(r)}


def legacy_rotation_ids(rows) -> set:
    return {r.get("of") for r in rows if is_legacy_rotation(r)}
