"""Edge traversal: neighbors, bounded paths, and cycle diagnostics.

Edges were write-only until v0.2 (stored, validated, counted, never walked).
This module is the only place that walks them, so the cost is visible and
testable in one spot.

Cycle policy: `depends_on` and `supersedes` edges must form a DAG — a cycle there
means the graph contradicts itself (a depends on b depends on a; v2 supersedes v1
supersedes v2). `relates_to`, `owned_by` and the rest may legitimately cycle, so
they are only counted as a hint.
"""
from collections import deque

from .const import EDGE_KINDS
from .errors import ProtocolError

ACYCLIC_KINDS = {"depends_on", "supersedes"}


def adjacency(doc: dict) -> dict:
    """id -> list of (edge, other_id, direction). Built once per query."""
    nodes = {n["id"] for n in doc.get("nodes") or []}
    adj = {nid: [] for nid in nodes}
    for e in doc.get("edges") or []:
        frm, to, kind = e.get("from"), e.get("to"), e.get("kind")
        if frm in adj:
            adj[frm].append((e, to, "out"))
        if to in adj:
            adj[to].append((e, frm, "in"))
    return adj


def related(doc: dict, node_id: str, depth: int = 1, kind: str = None) -> dict:
    if kind is not None and kind not in EDGE_KINDS:
        raise ProtocolError("E_BAD_EDGE", f"unknown edge kind: {kind}")
    if depth < 0 or depth > 5:
        raise ProtocolError("E_BAD_DEPTH", f"depth must be 0..5, got {depth}")
    nodes = {n["id"]: n for n in doc.get("nodes") or []}
    if node_id not in nodes:
        raise ProtocolError("E_NO_NODE", f"node not found: {node_id}")
    adj = adjacency(doc)
    seen = {node_id}
    frontier = deque([(node_id, 0)])
    found = []
    while frontier:
        current, level = frontier.popleft()
        if level >= depth:
            continue
        for edge, other, direction in adj.get(current, []):
            if kind is not None and edge.get("kind") != kind:
                continue
            if other == node_id:  # never report the origin as its own neighbor
                continue
            record = {
                "id": other,
                "label": (nodes.get(other) or {}).get("label"),
                "status": (nodes.get(other) or {}).get("status"),
                "type": (nodes.get(other) or {}).get("type"),
                "kind": edge.get("kind"),
                "direction": direction,
                "via": current,
                "depth": level + 1,
                "anchor_state": "present" if (nodes.get(other) or {}).get("evidence") else "none",
            }
            if other in seen:
                record["cycle"] = True
            else:
                seen.add(other)
                frontier.append((other, level + 1))
            found.append(record)
    found.sort(key=lambda r: (r["depth"], r["id"] or "", r["kind"] or ""))
    return {"id": node_id, "depth": depth, "kind": kind, "neighbors": found}


def _cycle_pairs(doc: dict):
    """Return cycles per edge kind family: (acyclic_cycles, tolerated_cycle_count)."""
    adj = {}
    kinds = {}
    for e in doc.get("edges") or []:
        frm, to, kind = e.get("from"), e.get("to"), e.get("kind")
        if kind not in ACYCLIC_KINDS:
            continue
        adj.setdefault(frm, []).append(to)
        kinds[(frm, to)] = kind
    state = {}
    cycles = []

    def visit(node, stack):
        state[node] = 1
        stack.append(node)
        for nxt in adj.get(node, []):
            if state.get(nxt) == 1:
                idx = stack.index(nxt)
                path = stack[idx:] + [nxt]
                cycles.append((node, nxt, kinds.get((node, nxt), "?"), path))
            elif state.get(nxt, 0) == 0:
                visit(nxt, stack)
        stack.pop()
        state[node] = 2

    for node in list(adj):
        if state.get(node, 0) == 0:
            visit(node, [])
    return cycles


def cycle_report(doc: dict) -> dict:
    cycles = _cycle_pairs(doc)
    tolerated = 0
    for comp in _weak_components(doc):
        if len(comp) > 1 and not _touches_acyclic(doc, comp):
            tolerated += 1
    return {"violations": [
        {"from": frm, "to": to, "kind": kind, "path": path}
        for frm, to, kind, path in cycles
    ], "tolerated_components": tolerated}


def _touches_acyclic(doc: dict, ids: set) -> bool:
    for e in doc.get("edges") or []:
        if e.get("kind") in ACYCLIC_KINDS and e.get("from") in ids and e.get("to") in ids:
            return True
    return False


def _weak_components(doc: dict):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for n in doc.get("nodes") or []:
        find(n["id"])
    for e in doc.get("edges") or []:
        union(e.get("from"), e.get("to"))
    groups = {}
    for x in list(parent):
        groups.setdefault(find(x), set()).add(x)
    return [g for g in groups.values() if len(g) > 1]
