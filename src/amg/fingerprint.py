"""Canonical fingerprints of graph state and of the change log.

Two separate digests, because they answer different questions:

- `state_sha256` — what the graph says right now (nodes and edges), order
  independent, so re-ordering the file does not change it.
- `history_sha256` — the change records, in order, so any edit is visible.

Splitting them is what makes a silent edit detectable: rewriting a node without
recording a change moves `state_sha256` while leaving `history_sha256` alone, and
that mismatch is a fact about the file, not an accusation.

What this can and cannot prove is written down in docs/THREAT-MODEL.md. In short:
a fingerprint kept **inside** the same file proves nothing against someone who
can write the file, because they can recompute it. Its value comes from storing
the digest somewhere else — a git commit, a CI log, a ticket.
"""
import hashlib
import json


def _canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def state_digest(doc: dict) -> str:
    nodes = sorted((doc.get("nodes") or []), key=lambda n: str(n.get("id") or ""))
    edges = sorted((doc.get("edges") or []),
                   key=lambda e: (str(e.get("from") or ""), str(e.get("to") or ""),
                                  str(e.get("kind") or "")))
    return _sha(_canonical({"nodes": nodes, "edges": edges}))


def history_digest(doc: dict) -> str:
    return _sha(_canonical(doc.get("changes") or []))


def fingerprint(doc: dict) -> dict:
    return {
        "schema": doc.get("schema"),
        "group": doc.get("group"),
        "rev": doc.get("rev", 0),
        "nodes": len(doc.get("nodes") or []),
        "edges": len(doc.get("edges") or []),
        "changes": len(doc.get("changes") or []),
        "state_sha256": state_digest(doc),
        "history_sha256": history_digest(doc),
    }


def compare(current: dict, expected: dict) -> dict:
    """Compare two fingerprints. Only the fields present in `expected` are checked."""
    checks = {}
    for field in ("state_sha256", "history_sha256"):
        want = expected.get(field)
        if not want:
            continue
        checks[field] = {"expected": want, "actual": current[field],
                         "match": current[field] == want}
    mismatched = [name for name, data in checks.items() if not data["match"]]
    return {"ok": not mismatched, "checked": sorted(checks), "mismatched": mismatched,
            "checks": checks, "current": current}
