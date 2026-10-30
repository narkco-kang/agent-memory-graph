"""Opt-in read-side audit.

Writes are logged in `changes[]`; reads are not — until they matter. This module
records only *high-risk* reads (L4 rule access, superseded history, strict
queries) into a separate, bounded, rotated JSONL file. Deliberate choices:

- not in `changes[]`: read events would drown the write ledger and change its
  meaning (and `changes[]` is append-only, so it could never be rotated);
- bounded + rotated: an unbounded read log is a second storage that grows without
  anyone auditing it — the exact failure this project warns about;
- opt-in per call: the default stays zero-cost, and the fact that reads are not
  audited by default is stated in the docs.
"""
import json
import os
from datetime import datetime, timezone

MAX_BYTES = 1 << 20  # 1 MiB per segment
KEEP_SEGMENTS = 1    # reads.jsonl + reads.jsonl.1


def _path(graph_dir: str) -> str:
    return os.path.join(os.path.abspath(graph_dir), "reads.jsonl")


def _rotate(path: str) -> None:
    """Shift segments by one and start a fresh file. Bounded by KEEP_SEGMENTS."""
    oldest = f"{path}.{KEEP_SEGMENTS}"
    if os.path.exists(oldest):
        os.unlink(oldest)
    for i in range(KEEP_SEGMENTS - 1, 0, -1):
        src, dst = f"{path}.{i}", f"{path}.{i + 1}"
        if os.path.exists(src):
            os.replace(src, dst)
    os.replace(path, f"{path}.1")


def is_high_risk(layer: str = None, strict: bool = False, statuses=()) -> bool:
    if strict or layer == "L4":
        return True
    return any(s == "superseded" for s in statuses)


def log_read(graph_dir: str, *, op: str, query: str = None, node_id: str = None,
             layer: str = None, strict: bool = False, hits: int = 0,
             by: str = "cli") -> dict:
    """Append one read event. Returns {'logged': bool, 'rotated': bool, 'bytes': int}."""
    os.makedirs(graph_dir, exist_ok=True)
    path = _path(graph_dir)
    event = {
        "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "by": by, "op": op, "layer": layer, "strict": bool(strict),
        "hits": hits, "query": query, "node": node_id,
    }
    line = json.dumps(event, ensure_ascii=False) + "\n"
    rotated = False
    if os.path.exists(path) and os.path.getsize(path) + len(line.encode()) > MAX_BYTES:
        _rotate(path)
        rotated = True
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
    return {"logged": True, "rotated": rotated, "bytes": os.path.getsize(path)}


def stats(graph_dir: str) -> dict:
    path = _path(graph_dir)
    out = {"segments": [], "total_bytes": 0}
    for name in (path, f"{path}.1"):
        if os.path.exists(name):
            size = os.path.getsize(name)
            out["segments"].append({"path": name, "bytes": size})
            out["total_bytes"] += size
    return out
