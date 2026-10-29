"""Adopt a legacy `group-kg/v1` graph into `amg/v1` without fabricating anything.

Policy (DECISIONS.md #9):

- the source file is opened read-only and is never written; `src_sha256` is
  captured before and reported so the caller can prove nothing moved;
- legacy **bare-string evidence cannot become an evidence object**: we do not
  hold the cited artifact, so any `content_sha256` would be invented — exactly
  the lie the evidence gate exists to prevent. The strings are preserved
  verbatim in `legacy_evidence`, `evidence` stays `[]`, and the node is counted
  in the legacy ratio that `audit --pin` reports as a convergence metric;
- placeholder sources (`""` / `unknown` / `manual`) are replaced with explicit
  provenance `adopted:<src_schema>:<src_sha256[:12]>`; the old value is kept in
  `legacy_source`. The provenance says where the node came from, not that
  somebody vouched for it;
- `superseded_at` / `valid_until` are inferred from `updatedAt` only, flagged
  `superseded_at_inferred: true` and counted;
- `valid_from` is left `null` when unknown — never back-filled from
  `changes[].at` (transaction time is not validity time, DECISIONS #5) — and the
  node is stamped `valid_time_known: false` so TTL auto-expiry refuses it;
- duplicate ids, unknown enums and dangling edges are **refusals**, never
  silent drops. `--drop-dangling` is the one explicit, counted exception.
"""
import hashlib
import json
import os

from . import migrate as migrate_mod
from . import protocol
from .audit import legacy_stats
from .const import CONCLUSION_TYPES, EDGE_KINDS, NODE_TYPES, SCHEMA, STATUSES, now
from .errors import ProtocolError
from .gate import validate_evidence
from .store import Store

LEGACY_SCHEMAS = {"group-kg/v1"}
# Adoption-only fields are documented in docs/API.md (docs must equal code).
NODE_FIELDS = ("id", "type", "label", "status", "owner", "source", "note",
               "evidence", "legacy_evidence", "conclusion", "evidence_grade",
               "valid_from", "valid_until", "valid_time_known",
               "recorded_at", "superseded_at", "updatedAt", "legacy_source")
MAX_LISTED = 5


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_placeholder_source(value) -> bool:
    if not isinstance(value, str):
        return True
    text = value.strip()
    return text == "" or text in {"unknown", "manual"}


def _keep_evidence_object(item) -> "dict | None":
    """Only an already-valid object survives; everything else is legacy text."""
    if not isinstance(item, dict):
        return None
    try:
        return validate_evidence([item], 0)[0]
    except ProtocolError:
        return None


def _list(items) -> str:
    head = ", ".join(items[:MAX_LISTED])
    return head + (" …" if len(items) > MAX_LISTED else "")


def adopt(src: str, dst: str, group: str = None, drop_dangling: bool = False,
          pin_out: str = None, dry_run: bool = False) -> dict:
    src_file = os.path.join(src, "graph.json") if os.path.isdir(src) else src
    if not os.path.isfile(src_file):
        raise ProtocolError("E_NO_GRAPH", f"no legacy graph at {src_file}")
    with open(src_file, "rb") as fh:
        raw = fh.read()
    src_sha = _sha256_bytes(raw)
    doc = json.loads(raw.decode("utf-8"))
    schema_before = doc.get("schema")
    if schema_before == SCHEMA:
        raise ProtocolError("E_ALREADY_AMG",
                            f"{src_file} is already {SCHEMA}; adopt only reads legacy graphs")

    nodes = doc.get("nodes") or []
    edges = doc.get("edges") or []
    changes_before = doc.get("changes") or []

    # ---- refusals first: nothing is dropped silently -------------------------
    problems, seen, dups = [], set(), []
    for n in nodes:
        nid = n.get("id")
        if not nid:
            problems.append("node without id")
            continue
        if nid in seen:
            dups.append(str(nid))
        seen.add(nid)
        if n.get("type") not in NODE_TYPES:
            problems.append(f"{nid}: unknown type {n.get('type')!r}")
        if n.get("status") not in STATUSES:
            problems.append(f"{nid}: unknown status {n.get('status')!r}")
    if dups:
        problems.append(f"duplicate node ids: {_list(dups)}")
    bad_kind, dangling = [], []
    for e in edges:
        if e.get("kind") not in EDGE_KINDS:
            bad_kind.append(f"{e.get('from')} -{e.get('kind')}-> {e.get('to')}")
        if e.get("from") not in seen or e.get("to") not in seen:
            dangling.append(f"{e.get('from')} -{e.get('kind')}-> {e.get('to')}")
    if problems or bad_kind:
        details = list(problems)
        if bad_kind:
            details.append(f"bad edge kind: {_list(bad_kind)}")
        raise ProtocolError("E_ADOPT_UNSUPPORTED",
                            "source graph has unsupported data: " + "; ".join(details))
    if dangling and not drop_dangling:
        raise ProtocolError(
            "E_ADOPT_DANGLING",
            f"{len(dangling)} edge(s) point at missing nodes: {_list(dangling)}; "
            "pass --drop-dangling to drop them explicitly (they are counted, never hidden)")

    stamp = now()
    provenance = f"adopted:{schema_before or 'unknown'}:{src_sha[:12]}"
    stats = {"source_backfilled": 0, "evidence_legacy_strings": 0, "evidence_objects_kept": 0,
             "evidence_objects_rejected": 0, "superseded_completed": 0,
             "valid_from_unknown": 0, "valid_time_unknown": 0}
    out_nodes = []
    for n in nodes:
        updated = n.get("updatedAt") or n.get("recorded_at") or stamp
        node = {field: None for field in NODE_FIELDS}
        node["id"] = n["id"]
        node["type"] = n["type"]
        node["label"] = n.get("label") or str(n["id"])
        node["status"] = n["status"]
        node["owner"] = n.get("owner")
        if _is_placeholder_source(n.get("source")):
            node["source"] = provenance
            node["legacy_source"] = n.get("source")
            stats["source_backfilled"] += 1
        else:
            node["source"] = n["source"]
            node["legacy_source"] = None
        node["note"] = "" if n.get("note") is None else str(n.get("note"))

        kept, legacy = [], []
        for item in (n.get("evidence") or []):
            if isinstance(item, dict):
                valid = _keep_evidence_object(item)
                if valid is not None:
                    kept.append(valid)
                    continue
                legacy.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
                stats["evidence_objects_rejected"] += 1
            else:
                legacy.append(str(item))
                stats["evidence_legacy_strings"] += 1
        node["evidence"] = kept
        node["legacy_evidence"] = legacy
        if kept:
            stats["evidence_objects_kept"] += 1
        node["conclusion"] = n.get("type") in CONCLUSION_TYPES
        node["evidence_grade"] = min([e.get("grade", 5) for e in kept], default=None) if kept else None
        node["valid_from"] = n.get("valid_from")
        if node["valid_from"] is None:
            stats["valid_from_unknown"] += 1
        # Validity time is a separate axis from transaction time. Legacy data has
        # no validity window, so migrated nodes must declare that explicitly:
        # TTL auto-expiry refuses them rather than deleting facts we never dated.
        node["valid_time_known"] = bool(n.get("valid_from"))
        if not node["valid_time_known"]:
            stats["valid_time_unknown"] += 1
        node["valid_until"] = n.get("valid_until")
        node["recorded_at"] = n.get("recorded_at") or updated
        node["superseded_at"] = n.get("superseded_at")
        if n["status"] == "superseded" and not node["superseded_at"]:
            node["superseded_at"] = updated
            node["superseded_at_inferred"] = True
            if not node["valid_until"]:
                node["valid_until"] = updated
            stats["superseded_completed"] += 1
        node["updatedAt"] = updated
        out_nodes.append(node)

    # Identical triples carry no extra information and `check` rejects them as
    # duplicates, so identity-level merging is lossless — but it is counted and
    # reported, never silent.
    out_edges, edge_seen, duplicate_edges = [], set(), 0
    for e in edges:
        if e.get("kind") not in EDGE_KINDS or e.get("from") not in seen or e.get("to") not in seen:
            continue
        triple = (e["from"], e["to"], e["kind"])
        if triple in edge_seen:
            duplicate_edges += 1
            continue
        edge_seen.add(triple)
        out_edges.append({"from": triple[0], "to": triple[1], "kind": triple[2]})

    revs = [c.get("rev") for c in changes_before if isinstance(c.get("rev"), int)]
    legacy_rev = doc.get("rev")
    rev = legacy_rev if isinstance(legacy_rev, int) else (max(revs) if revs else len(changes_before))

    out_doc = {
        "schema": SCHEMA,
        "group": group or doc.get("group") or "adopted",
        "session": "",
        "goal": doc.get("goal") or "",
        "adopted_from": {"path": os.path.abspath(src_file), "schema": schema_before,
                         "sha256": src_sha, "at": stamp},
        "updatedAt": stamp,
        "rev": rev,
        "nodes": out_nodes,
        "edges": out_edges,
        "changes": [dict(c) for c in changes_before],
    }
    stats["changes"] = migrate_mod.normalize(out_doc)
    out_doc["changes"].append({
        "at": stamp, "by": "amg adopt", "op": "adopt", "target": "graph",
        "rev": rev + 1,
        "note": f"from {schema_before or 'unknown'} sha256:{src_sha[:12]} "
                f"nodes={len(out_nodes)} edges={len(out_edges)}",
    })
    out_doc["rev"] = rev + 1

    report_check = protocol.check(out_doc)
    report = {
        "src": os.path.abspath(src_file),
        "src_schema": schema_before,
        "src_sha256": src_sha,
        "dst": None if dry_run else os.path.abspath(dst),
        "dry_run": dry_run,
        "counts": {"nodes": len(out_nodes), "edges": len(out_edges),
                   "changes": len(out_doc["changes"]),
                   "nodes_before": len(nodes), "edges_before": len(edges),
                   "changes_before": len(changes_before),
                   "duplicate_edges_merged": duplicate_edges,
                   "dangling_dropped": len(dangling)},
        "mapped": stats,
        "rev": out_doc["rev"],
        "check": report_check,
        "legacy": {k: v for k, v in legacy_stats(out_doc).items() if not k.startswith("_")},
        "pin": None,
    }

    if not dry_run:
        store = Store(dst)
        if store.exists():
            raise ProtocolError("E_EXISTS", f"destination already has a graph: {store.file}")
        os.makedirs(store.dir, exist_ok=True)
        with store.locked():
            store._atomic_write(out_doc)
        if pin_out:
            pin = {"schema": "amg-pin/v1", "adopted_from_sha256": src_sha, "at": stamp,
                   "done_no_evidence_sha256": report["legacy"]["done_no_evidence_sha256"],
                   "no_evidence_sha256": report["legacy"]["no_evidence_sha256"]}
            with open(pin_out, "w", encoding="utf-8") as fh:
                json.dump(pin, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            report["pin"] = os.path.abspath(pin_out)
    return report
