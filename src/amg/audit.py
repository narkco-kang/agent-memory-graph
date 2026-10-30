"""Audit: legacy coverage, staleness, expiry, integrity. Exit 1 on conflicts."""
import datetime
import hashlib
import os

from .const import is_conclusion, not_yet_valid, parse_ts

# How long a work item may sit in `in_progress`/`blocked` before audit calls it
# stale. Default 3 days, overridable per call (`audit(..., stale_days=N)`) or by the
# `AMG_STALE_DAYS` environment variable — because the right threshold is a property
# of the team's cadence, not of the tool (DECISIONS #21).
DEFAULT_STALE_DAYS = 3
MAX_STALE_DAYS = 365


def stale_days_from_env(default: int = DEFAULT_STALE_DAYS) -> int:
    """Read AMG_STALE_DAYS. Nonsense or out-of-range values fall back to the default.

    Silent fallback is deliberate, like AMG_LOCK_TIMEOUT: a typo must not silently
    disable (0) or effectively disable (huge) the check.
    """
    raw = os.environ.get("AMG_STALE_DAYS")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if not 0 < value <= MAX_STALE_DAYS:
        return default
    return value

# Types that register something long-lived rather than a work item. A group marked
# `in_progress` is active, not abandoned, and its `updatedAt` does not move when its
# children change — so the staleness rule, which assumes short-lived work, reported
# noise (docs/REAL-WORLD.md). Exemptions are explicit on purpose: an unknown type is
# still checked, so abandoning a new kind of work cannot become invisible by omission.
LONG_LIVED_TYPES = frozenset({"group", "env", "member"})


def _parse(value):
    return parse_ts(value)


def expiry_eligible(node: dict) -> bool:
    """TTL auto-expiry must never process a node whose validity time is unknown.

    Expiring an adopted node would delete a fact on the strength of a timestamp
    we never had; leaving it alive is the safe direction (maintainer ruling 2026-10-29).
    Absent field = known, so only `valid_time_known: false` is refused.
    """
    return node.get("valid_time_known") is not False


def _sorted_sha(ids) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def legacy_stats(doc: dict) -> dict:
    nodes = doc.get("nodes") or []
    done_no_ev = [n["id"] for n in nodes if n.get("status") == "done" and not (n.get("evidence") or [])]
    all_no_ev = [n["id"] for n in nodes if not (n.get("evidence") or [])]
    done = [n["id"] for n in nodes if n.get("status") == "done"]
    return {
        "done": len(done),
        "nodes": len(nodes),
        "done_no_evidence": len(done_no_ev),
        "no_evidence": len(all_no_ev),
        "done_no_evidence_ratio": f"{len(done_no_ev)}/{len(done)}",
        "no_evidence_ratio": f"{len(all_no_ev)}/{len(nodes)}",
        "done_no_evidence_sha256": _sorted_sha(done_no_ev),
        "no_evidence_sha256": _sorted_sha(all_no_ev),
        "_ids": set(done_no_ev),
    }


def audit(doc: dict, pin: dict = None, now: datetime.datetime = None,
          stale_days: int = None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if stale_days is None:
        stale_days = stale_days_from_env()
    nodes = doc.get("nodes") or []
    edges = doc.get("edges") or []
    changes = doc.get("changes") or []
    conflicts, hints = [], []

    legacy = legacy_stats(doc)
    pinned = set()
    pin_report = None
    if pin:
        expected_done = pin.get("done_no_evidence_sha256")
        expected_all = pin.get("no_evidence_sha256")
        match = (expected_done in (None, legacy["done_no_evidence_sha256"]) and
                 expected_all in (None, legacy["no_evidence_sha256"]))
        pin_report = {
            "expected": {"done_no_evidence_sha256": expected_done,
                         "no_evidence_sha256": expected_all},
            "actual": {"done_no_evidence_sha256": legacy["done_no_evidence_sha256"],
                       "no_evidence_sha256": legacy["no_evidence_sha256"]},
            "match": match,
        }
        if not match:
            conflicts.append("legacy exemption pin changed without an explicit explanation "
                            "(new exemptions or backfill) — only forward writes may add exemptions")
        else:
            pinned = legacy["_ids"]

    ids = {n.get("id") for n in nodes}
    for n in nodes:
        nid = n.get("id")
        if n.get("status") == "done" and not (n.get("evidence") or []) and nid not in pinned:
            conflicts.append(f"{nid}: done without evidence (IR-4)")
        if (n.get("status") in {"in_progress", "blocked"}
                and n.get("type") not in LONG_LIVED_TYPES):
            ts = _parse(n.get("updatedAt"))
            if ts and (now - ts).days >= stale_days:
                conflicts.append(f"{nid}: {n.get('status')} untouched for {(now - ts).days}d (limit {stale_days}d)")
        if not_yet_valid(n, now):
            hints.append(f"{nid}: not yet valid (valid_from {n.get('valid_from')} is in the "
                         f"future) — treated as not yet in effect by retrieval and expiry")
        vu = _parse(n.get("valid_until"))
        if vu and vu <= now and n.get("status") != "superseded":
            if expiry_eligible(n):
                conflicts.append(f"{nid}: valid_until passed but status={n.get('status')} (not superseded)")
            else:
                hints.append(f"{nid}: valid_until passed but validity time is unknown "
                             f"(valid_time_known=false) — cannot auto-expire, manual review")
        if is_conclusion(n) and n.get("status") == "done" and not (n.get("evidence") or []):
            hints.append(f"{nid}: conclusion without evidence grade")

    for e in edges:
        if e.get("from") not in ids or e.get("to") not in ids:
            conflicts.append(f"dangling edge {e.get('from')} -{e.get('kind')}-> {e.get('to')}")

    shapes = {}
    missing_target = missing_rev = 0
    for c in changes:
        key = ",".join(sorted(c.keys()))
        shapes[key] = shapes.get(key, 0) + 1
        if "target" not in c:
            missing_target += 1
        if "rev" not in c:
            missing_rev += 1
    unknown_validity = sum(1 for n in nodes if n.get("valid_time_known") is False)
    if unknown_validity:
        hints.append(f"valid_time_known=false on {unknown_validity} node(s): "
                     f"TTL auto-expiry refuses them (migrated validity time is unknown)")

    if missing_target or missing_rev:
        hints.append(f"changes key shapes: {len(shapes)} variants, missing target={missing_target}, "
                     f"missing rev={missing_rev} (run `amg migrate` before any public release)")

    return {
        "ok": not conflicts,
        "conflicts": conflicts,
        "hints": hints,
        "legacy": {k: v for k, v in legacy.items() if not k.startswith("_")},
        "pin": pin_report,
        "counts": {"nodes": len(nodes), "edges": len(edges), "changes": len(changes),
                   "rev": doc.get("rev", 0)},
    }
