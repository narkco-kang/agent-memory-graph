"""Consolidation digest: pointers only, bounded bytes, priority-ordered.

M4 mechanism: never copies evidence payloads, never becomes a second store.
Everything trimmed is counted, never silently dropped.

Superseded nodes are excluded (failures.md:118): the digest is a live view, and
expired facts belong to L2 history. The excluded count is printed in the header
so a shrinking graph is visible, not mysterious.
"""
from .const import CONCLUSION_TYPES

NOTE_LIMIT = 200
LABEL_LIMIT = 80
PRIORITY = [
    ("in_progress", lambda n: n.get("status") == "in_progress"),
    ("blocked", lambda n: n.get("status") == "blocked"),
    ("open", lambda n: n.get("status") == "open"),
    ("decision", lambda n: n.get("type") in CONCLUSION_TYPES and n.get("status") != "done"),
    ("rest", lambda n: True),
]


def _line(n: dict) -> str:
    note = (n.get("note") or "").replace("\n", " ").strip()
    if len(note) > NOTE_LIMIT:
        note = note[:NOTE_LIMIT] + "…"
    label = (n.get("label") or "").replace("\n", " ").strip()
    if len(label) > LABEL_LIMIT:
        label = label[:LABEL_LIMIT] + "…"
    ev = n.get("evidence") or []
    tail = f" ev×{len(ev)}" if ev else ""
    owner = f" @{n['owner']}" if n.get("owner") else ""
    suffix = f" | {note}" if note else ""
    return f"- [{n.get('status')}] {n.get('id')} — {label}{owner}{tail}{suffix}"


def build(doc: dict, max_bytes: int = 65536) -> str:
    all_nodes = list(doc.get("nodes") or [])
    nodes = [n for n in all_nodes if n.get("status") != "superseded"]
    superseded_excluded = len(all_nodes) - len(nodes)
    used = set()
    ordered = []
    for _, pred in PRIORITY:
        for n in nodes:
            if id(n) in used:
                continue
            if pred(n):
                used.add(id(n))
                ordered.append(n)

    header = (f"# {doc.get('group', 'memory')} · digest\n"
              f"> rev {doc.get('rev', 0)} | nodes {len(all_nodes)} "
              f"(superseded excluded: {superseded_excluded}) | "
              f"edges {len(doc.get('edges') or [])}\n\n")
    reserve = len(b"[truncated 9999 items]\n")  # kept free so the marker cannot overflow
    budget = max_bytes - len(header.encode("utf-8")) - reserve
    out, dropped = [], 0
    for n in ordered:
        line = _line(n) + "\n"
        size = len(line.encode("utf-8"))
        if size > budget:
            dropped += 1
            continue
        budget -= size
        out.append(line)
    text = header + "".join(out)
    if dropped:
        text += f"[truncated {dropped} items]\n"
    return text
