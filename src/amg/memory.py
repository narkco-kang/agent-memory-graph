"""Memory — the single public entry point (library face, 5 core methods)."""
import json

from . import audit as audit_mod
from . import digest as digest_mod
from . import migrate as migrate_mod
from . import protocol
from . import relations
from . import retrieval
from .const import EDGE_KINDS, NODE_TYPES, SCHEMA, STATUSES, now, parse_ts
from .errors import ProtocolError
from .audit import expiry_eligible
from .gate import enforce_conclusion, validate_evidence
from .store import Store

_UNSET = object()


def _empty(group: str, goal: str = "") -> dict:
    return {
        "schema": SCHEMA,
        "group": group,
        "session": "",
        "goal": goal,
        "updatedAt": now(),
        "rev": 0,
        "nodes": [],
        "edges": [],
        "changes": [],
    }


def _validity_ended(node: dict, at) -> bool:
    """True when a parseable `valid_until` is at or before `at`."""
    end = parse_ts(node.get("valid_until"))
    return end is not None and end <= at


class Memory:
    def __init__(self, store: Store, doc: dict):
        self.store = store
        self._doc = doc

    # ---------- lifecycle ----------
    @classmethod
    def init(cls, path: str, group: str, goal: str = "") -> "Memory":
        store = Store(path)
        if store.exists():
            raise ProtocolError("E_EXISTS", f"graph already exists: {store.file} (init never overwrites)")
        store.dir and __import__("os").makedirs(store.dir, exist_ok=True)
        doc = _empty(group, goal)
        store._atomic_write(doc)
        return cls(store, doc)

    @classmethod
    def open(cls, path: str) -> "Memory":
        store = Store(path)
        return cls(store, store.read())

    @classmethod
    def adopt(cls, src: str, dst: str, group: str = None, drop_dangling: bool = False,
              pin_out: str = None, dry_run: bool = False) -> dict:
        """Turn a legacy (`group-kg/v1`) graph into a new `amg/v1` directory.

        Never writes to `src`, never overwrites `dst`, and never fabricates
        evidence: legacy locator strings are preserved in `legacy_evidence`
        (see DECISIONS.md #9). Returns the adoption report.
        """
        from . import adopt as adopt_mod
        return adopt_mod.adopt(src, dst, group=group, drop_dangling=drop_dangling,
                               pin_out=pin_out, dry_run=dry_run)

    @property
    def doc(self) -> dict:
        return self._doc

    def _node(self, doc: dict, node_id: str) -> dict:
        """Always resolve inside the transaction's doc, never the cached one."""
        for n in doc["nodes"]:
            if n["id"] == node_id:
                return n
        raise ProtocolError("E_NO_NODE", f"node not found: {node_id}")

    def _log(self, doc: dict, op: str, target: str, note: str, by: str) -> dict:
        change = {"at": now(), "by": by, "op": op, "target": target,
                  "rev": int(doc.get("rev", 0)) + 1, "note": note}
        doc["changes"].append(change)
        return change

    def _commit(self, doc: dict, commit) -> None:
        commit()
        self._doc = doc

    # ---------- writes ----------
    def _log_rev(self, doc: dict, rev: int, op: str, target: str, note: str, by: str) -> dict:
        change = {"at": now(), "by": by, "op": op, "target": target, "rev": rev, "note": note}
        doc["changes"].append(change)
        return change

    def _make_node(self, rev: int, id: str, type: str, label: str, source: str,
                   status: str = "open", owner=None, note: str = "",
                   evidence=None, conclusion=None, applies=None,
                   expires_when=_UNSET, valid_from: str = None,
                   valid_until: str = None) -> dict:
        """Validate one node and build the stored record. Never touches the doc."""
        if not id or not isinstance(id, str):
            raise ProtocolError("E_BAD_ID", "id must be a non-empty string")
        if type not in NODE_TYPES:
            raise ProtocolError("E_BAD_TYPE", f"unknown node type: {type}")
        if status not in STATUSES:
            raise ProtocolError("E_BAD_STATUS", f"unknown status: {status}")
        if not source or not isinstance(source, str) or source in {"unknown", "manual"}:
            raise ProtocolError("E_NO_SOURCE", "IR-2: every node needs a real source (not 'unknown'/'manual')")
        # Validity time is supplied by the caller or stays unknown. It is never
        # defaulted to the write time: `changes[].at` is transaction time, and
        # treating it as fact time is measurably wrong (see experiments/).
        if valid_from is not None and parse_ts(valid_from) is None:
            raise ProtocolError("E_BAD_VALID_TIME",
                                f"{id}: valid_from is not ISO-8601: {valid_from!r}")
        if valid_until is not None and parse_ts(valid_until) is None:
            raise ProtocolError("E_BAD_VALID_TIME",
                                f"{id}: valid_until is not ISO-8601: {valid_until!r}")
        if (valid_from is not None and valid_until is not None
                and parse_ts(valid_until) < parse_ts(valid_from)):
            raise ProtocolError("E_BAD_VALID_RANGE",
                                f"{id}: valid_until {valid_until} is earlier than valid_from {valid_from}")
        ev = validate_evidence(evidence, rev)
        if type == "rule":
            # L4 rules must declare their scope and lifetime explicitly:
            # an applicable rule with no scope cannot be machine-checked.
            if not applies:
                raise ProtocolError("E_RULE_APPLIES", f"{id}: rule nodes require applies")
            if expires_when is _UNSET:
                raise ProtocolError("E_RULE_EXPIRES",
                                    f"{id}: rule nodes must declare expires_when (use None for never)")
        stamp = now()
        node = {
            "id": id, "type": type, "label": label, "status": status,
            "owner": owner, "source": source, "note": note,
            "evidence": ev,
            "conclusion": bool(conclusion) if conclusion is not None else type in {"decision", "artifact"},
            "evidence_grade": min([e.get("grade", 5) for e in ev], default=None),
            "valid_from": valid_from, "valid_until": valid_until,
            "valid_time_known": valid_from is not None,
            "recorded_at": stamp, "superseded_at": None,
            "updatedAt": stamp,
        }
        if type == "rule":
            node["applies"] = applies
            node["expires_when"] = expires_when
        enforce_conclusion(node, ev)
        return node

    def add_node(self, id: str, type: str, label: str, source: str,
                 status: str = "open", owner=None, note: str = "",
                 evidence=None, conclusion=None, applies=None,
                 expires_when=_UNSET, valid_from: str = None, valid_until: str = None,
                 by: str = "amg") -> dict:
        with self.store.transaction() as (doc, commit):
            if any(n["id"] == id for n in doc["nodes"]):
                raise ProtocolError("E_DUP_ID", f"node id already exists: {id}")
            rev = int(doc.get("rev", 0)) + 1
            node = self._make_node(rev, id, type, label, source, status=status,
                                   owner=owner, note=note, evidence=evidence,
                                   conclusion=conclusion, applies=applies,
                                   expires_when=expires_when, valid_from=valid_from,
                                   valid_until=valid_until)
            doc["nodes"].append(node)
            self._log_rev(doc, rev, "add-node", id, f"type={type} status={status}", by)
            self._commit(doc, commit)
            return {k: v for k, v in node.items()}

    def add_many(self, nodes, edges=None, by: str = "amg") -> dict:
        """Batch write: validate everything first, then append all and write once.

        All-or-nothing by construction: the document is mutated only after every
        node and edge has passed the same gates a single write uses. One load,
        N appends, one atomic replace — this is what makes bulk ingest linear
        instead of quadratic (see docs/BENCHMARKS.md).
        """
        if not nodes:
            raise ProtocolError("E_BAD_BATCH", "empty batch")
        if not isinstance(nodes, (list, tuple)):
            raise ProtocolError("E_BAD_BATCH", "nodes must be a list")
        edges = list(edges or [])
        with self.store.transaction() as (doc, commit):
            existing = {n["id"] for n in doc["nodes"]}
            seen = set()
            built = []
            base = int(doc.get("rev", 0)) + 1
            for i, raw in enumerate(nodes):
                if not isinstance(raw, dict):
                    raise ProtocolError("E_BAD_BATCH", f"nodes[{i}] must be an object")
                nid = raw.get("id")
                if nid in existing:
                    raise ProtocolError("E_DUP_ID", f"node id already exists: {nid}")
                if nid in seen:
                    raise ProtocolError("E_DUP_ID", f"node id repeated in batch: {nid}")
                seen.add(nid)
                built.append(self._make_node(
                    base + i,
                    id=nid,
                    type=raw.get("type"),
                    label=raw.get("label"),
                    source=raw.get("source"),
                    status=raw.get("status", "open"),
                    owner=raw.get("owner"),
                    note=raw.get("note", ""),
                    evidence=raw.get("evidence"),
                    conclusion=raw.get("conclusion"),
                    applies=raw.get("applies"),
                    expires_when=raw.get("expires_when", _UNSET),
                    valid_from=raw.get("valid_from"),
                    valid_until=raw.get("valid_until"),
                ))
            known = existing | seen
            existing_edges = {(e["from"], e["to"], e["kind"]) for e in doc["edges"]}
            built_edges = []
            for i, raw in enumerate(edges):
                if not isinstance(raw, dict):
                    raise ProtocolError("E_BAD_BATCH", f"edges[{i}] must be an object")
                frm, to, kind = raw.get("from"), raw.get("to"), raw.get("kind")
                if kind not in EDGE_KINDS:
                    raise ProtocolError("E_BAD_EDGE", f"edges[{i}]: unknown edge kind: {kind}")
                if frm not in known or to not in known:
                    raise ProtocolError("E_NO_NODE", f"edges[{i}]: endpoint missing ({frm} -> {to})")
                key = (frm, to, kind)
                if key in existing_edges or key in {(e["from"], e["to"], e["kind"]) for e in built_edges}:
                    raise ProtocolError("E_DUP_EDGE", f"edges[{i}]: duplicate edge {key}")
                built_edges.append({"from": frm, "to": to, "kind": kind})
            for i, node in enumerate(built):
                doc["nodes"].append(node)
                self._log_rev(doc, base + i, "import-node", node["id"],
                              f"type={node['type']} status={node['status']}", by)
            doc["edges"].extend(built_edges)
            doc["rev"] = base + len(built) - 1
            self._commit(doc, commit)
            return {"nodes": len(built), "edges": len(built_edges),
                    "rev": int(doc.get("rev", 0))}

    def set_status(self, node_id: str, new_status: str, note: str,
                   evidence=None, by: str = "amg") -> dict:
        if new_status not in STATUSES:
            raise ProtocolError("E_BAD_STATUS", f"unknown status: {new_status}")
        if not note or not str(note).strip():
            raise ProtocolError("E_NOTE_REQUIRED", "IR-4: status change requires a note")
        if new_status == "superseded":
            raise ProtocolError("E_USE_SUPERSEDE", "use Memory.supersede() to supersede a node")

        with self.store.transaction() as (doc, commit):
            node = self._node(doc, node_id)
            old = node["status"]
            if old == "superseded":
                raise ProtocolError("E_IMMUTABLE", f"{node_id} is superseded; supersede a new node instead")
            if evidence is not None:
                node["evidence"] = node.get("evidence", []) + validate_evidence(
                    evidence, int(doc.get("rev", 0)) + 1)
            node["status"] = new_status
            node["updatedAt"] = now()
            node["evidence_grade"] = min([e.get("grade", 5) for e in node.get("evidence", [])], default=None)
            enforce_conclusion(node, node.get("evidence", []))
            self._log(doc, "set-status", node_id, f"{old}->{new_status}: {note}", by)
            self._commit(doc, commit)
            return {"id": node_id, "from": old, "to": new_status}

    def add_edge(self, from_id: str, to_id: str, kind: str, by: str = "amg") -> dict:
        if kind not in EDGE_KINDS:
            raise ProtocolError("E_BAD_EDGE", f"unknown edge kind: {kind}")
        with self.store.transaction() as (doc, commit):
            self._node(doc, from_id)
            self._node(doc, to_id)
            for e in doc["edges"]:
                if e["from"] == from_id and e["to"] == to_id and e["kind"] == kind:
                    raise ProtocolError("E_DUP_EDGE", f"edge already exists: {from_id} -{kind}-> {to_id}")
            doc["edges"].append({"from": from_id, "to": to_id, "kind": kind})
            self._log(doc, "add-edge", f"{from_id}->{to_id}", kind, by)
            self._commit(doc, commit)
            return {"from": from_id, "to": to_id, "kind": kind}

    def supersede(self, old_id: str, new_id: str, note: str = "", by: str = "amg") -> dict:
        if not note or not str(note).strip():
            raise ProtocolError("E_NOTE_REQUIRED", "supersede requires a note (which fact changed, and why)")
        with self.store.transaction() as (doc, commit):
            old = self._node(doc, old_id)
            self._node(doc, new_id)
            if old_id == new_id:
                raise ProtocolError("E_BAD_SUPERSEDE", "cannot supersede a node with itself")
            stamp = now()
            old["status"] = "superseded"
            old["valid_until"] = stamp
            old["superseded_at"] = stamp
            old["updatedAt"] = stamp
            doc["edges"].append({"from": new_id, "to": old_id, "kind": "supersedes"})
            self._log(doc, "supersede", old_id, f"superseded by {new_id}: {note}", by)
            self._commit(doc, commit)
            return {"old": old_id, "new": new_id, "valid_until": stamp}

    def expire(self, apply: bool = False, by: str = "amg expire") -> dict:
        """Supersede nodes whose *known* validity window has ended.

        Dry-run by default: nothing is written unless `apply=True`. Expiry never
        deletes a node — it sets `status="superseded"`, stamps `superseded_at`
        and appends one `expire` change record per node, so the action is
        visible in L2 history. Nodes whose validity window is unknown
        (`valid_time_known: false`, e.g. everything `amg adopt` migrated) are
        skipped and counted: an undated fact can never be auto-expired.

        Idempotent: a second `apply=True` run finds nothing eligible.
        """
        with self.store.transaction() as (doc, commit):
            stamp = now()
            at = parse_ts(stamp)
            eligible, skipped_unknown, already = [], 0, 0
            for node in doc["nodes"]:
                if node.get("status") == "superseded":
                    already += 1
                    continue
                ended = _validity_ended(node, at)
                if not expiry_eligible(node):
                    if ended:
                        skipped_unknown += 1
                    continue
                if ended:
                    eligible.append(node["id"])
            report = {
                "dry_run": not apply,
                "eligible": eligible,
                "applied": 0,
                "skipped_unknown_validity": skipped_unknown,
                "already_superseded": already,
                "rev": int(doc.get("rev", 0)),
            }
            if not apply or not eligible:
                self._doc = doc
                return report
            new_rev = int(doc.get("rev", 0)) + 1
            for node_id in eligible:
                node = self._node(doc, node_id)
                node["status"] = "superseded"
                node["superseded_at"] = stamp
                node["updatedAt"] = stamp
                doc["changes"].append({
                    "at": stamp, "by": by, "op": "expire", "target": node_id,
                    "rev": new_rev,
                    "note": f"valid_until {node.get('valid_until')} passed (auto-expiry)",
                })
            self._commit(doc, commit)
            report["applied"] = len(eligible)
            report["rev"] = new_rev
            return report

    # ---------- reads ----------
    def search(self, query: str, layer: str = "L3", k: int = 10, strict: bool = False,
               expand: bool = False):
        return retrieval.search(self._doc, query, layer=layer, k=k, strict=strict,
                                expand=expand)

    def related(self, node_id: str, depth: int = 1, kind: str = None) -> dict:
        """Walk edges around one node. This is the only traversal entry point."""
        return relations.related(self._doc, node_id, depth=depth, kind=kind)

    def check(self, strict: bool = False):
        return protocol.check(self._doc, strict=strict)

    def audit(self, pin=None):
        return audit_mod.audit(self._doc, pin=pin)

    def digest(self, max_bytes: int = 65536) -> str:
        return digest_mod.build(self._doc, max_bytes=max_bytes)

    def migrate(self) -> dict:
        with self.store.transaction() as (doc, commit):
            stats = migrate_mod.normalize(doc)
            if stats["changed"]:
                self._log(doc, "migrate", "changes", json.dumps(stats, ensure_ascii=False), "amg")
                self._commit(doc, commit)
            else:
                self._doc = doc
            return stats

    def export(self, fmt: str = "json") -> str:
        if fmt == "json":
            return json.dumps(self._doc, ensure_ascii=False, indent=2)
        if fmt == "jsonl":
            lines = [json.dumps(n, ensure_ascii=False) for n in self._doc["nodes"]]
            return "\n".join(lines) + "\n"
        raise ProtocolError("E_BAD_FORMAT", f"unknown export format: {fmt}")
