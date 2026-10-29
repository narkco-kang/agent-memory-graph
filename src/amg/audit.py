"""Audit: legacy coverage, staleness, expiry, integrity. Exit 1 on conflicts."""
import datetime
import hashlib

from .const import is_conclusion

STALE_DAYS = 3


def _parse(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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


def audit(doc: dict, pin: dict = None, now: datetime.datetime = None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
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
        if n.get("status") in {"in_progress", "blocked"}:
            ts = _parse(n.get("updatedAt"))
            if ts and (now - ts).days >= STALE_DAYS:
                conflicts.append(f"{nid}: {n.get('status')} untouched for {(now - ts).days}d (limit {STALE_DAYS}d)")
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
