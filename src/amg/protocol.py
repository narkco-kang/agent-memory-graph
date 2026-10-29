"""Structural invariants (IR-1..IR-4) as machine-checkable rules."""

from .const import EDGE_KINDS, NODE_TYPES, SCHEMA, STATUSES, is_conclusion, parse_ts
from .gate import SHA256_RE


def _parse_ts(value):
    return parse_ts(value)


def check(doc: dict, strict: bool = False) -> dict:
    errors, conflicts, hints = [], [], []
    nodes = doc.get("nodes") or []
    edges = doc.get("edges") or []
    changes = doc.get("changes") or []

    if doc.get("schema") != SCHEMA:
        errors.append(f"schema mismatch: {doc.get('schema')!r} != {SCHEMA!r}")
    if not doc.get("group"):
        errors.append("group is required")

    ids = set()
    for n in nodes:
        nid = n.get("id")
        if not nid:
            errors.append("node without id")
            continue
        if nid in ids:
            errors.append(f"duplicate node id: {nid}")
        ids.add(nid)
        if n.get("type") not in NODE_TYPES:
            errors.append(f"{nid}: bad type {n.get('type')!r}")
        if n.get("status") not in STATUSES:
            errors.append(f"{nid}: bad status {n.get('status')!r}")
        src = n.get("source")
        if not src or src in {"unknown", "manual"}:  # IR-2
            errors.append(f"{nid}: IR-2 violated (missing or placeholder source)")
        for i, ev in enumerate(n.get("evidence") or []):
            if not isinstance(ev, dict):
                errors.append(f"{nid}: evidence[{i}] is not an object (IR-4 format)")
                continue
            if not str(ev.get("locator", "")).startswith(("path:", "cmd:", "url:", "sha256:")):
                errors.append(f"{nid}: evidence[{i}].locator has no known prefix")
            if not SHA256_RE.match(str(ev.get("content_sha256", ""))):
                errors.append(f"{nid}: evidence[{i}].content_sha256 invalid")
        if n.get("status") == "done" and not (n.get("evidence") or []):
            msg = f"{nid}: IR-4 conflict — done without evidence"
            (errors if strict else hints).append(msg)
        if n.get("type") == "rule":
            if not n.get("applies"):
                errors.append(f"{nid}: rule node without applies")
            if "expires_when" not in n:
                errors.append(f"{nid}: rule node must declare expires_when explicitly (null = never)")
        if n.get("status") == "superseded" and not n.get("superseded_at"):
            errors.append(f"{nid}: superseded without superseded_at")
        vf, vu = _parse_ts(n.get("valid_from")), _parse_ts(n.get("valid_until"))
        if vf and vu and vu < vf:
            errors.append(f"{nid}: valid_until earlier than valid_from")
        if is_conclusion(n) and n.get("status") == "done" and not (n.get("evidence") or []):
            pass  # already covered by IR-4 above

    seen_edges = set()
    for e in edges:
        if e.get("kind") not in EDGE_KINDS:
            errors.append(f"edge bad kind {e.get('kind')!r}")
        if e.get("from") not in ids:
            errors.append(f"edge dangling from: {e.get('from')!r}")
        if e.get("to") not in ids:
            errors.append(f"edge dangling to: {e.get('to')!r}")
        key = (e.get("from"), e.get("to"), e.get("kind"))
        if key in seen_edges:
            errors.append(f"duplicate edge {key}")
        seen_edges.add(key)

    last_rev = -1
    for i, c in enumerate(changes):
        if not c.get("op"):
            errors.append(f"changes[{i}]: missing op")
        rev = c.get("rev")
        if rev is None:
            hints.append(f"changes[{i}]: missing rev (run `amg migrate`)")
        elif isinstance(rev, int):
            if rev < last_rev:
                errors.append(f"changes[{i}]: rev went backwards ({rev} < {last_rev}) — IR-1")
            last_rev = rev

    return {
        "ok": not errors,
        "errors": errors,
        "conflicts": conflicts,
        "hints": hints,
        "counts": {"nodes": len(nodes), "edges": len(edges), "changes": len(changes),
                   "rev": doc.get("rev", 0)},
    }
