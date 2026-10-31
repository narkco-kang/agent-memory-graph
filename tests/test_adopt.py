"""Adoption of legacy `group-kg/v1` graphs — the boundary behaviour is the product.

Each test pins one promise from docs/DECISIONS.md #9: nothing is fabricated,
nothing is silently dropped, the source is never touched, and adoption does not
weaken the gate for new writes.
"""
import json
import os
import re
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from amg import Memory, ProtocolError
from amg import cli as cli_mod
from amg.const import EXIT_ERROR, EXIT_OK, EXIT_USAGE

SHA_A = "a" * 64


def legacy_doc():
    return {
        "schema": "group-kg/v1",
        "group": "legacy-team",
        "session": "",
        "goal": "old goal",
        "updatedAt": "2026-10-27T10:00:00+08:00",
        "rev": 41,
        "nodes": [
            {"id": "task.a", "type": "task", "label": "A", "status": "done",
             "source": "group:legacy 2026-10-25", "note": "did the thing",
             "evidence": ["docs/plan.md", "cmd:pytest -q (exit 0)"],
             "createdAt": "2026-10-25T10:00:00+08:00",
             "updatedAt": "2026-10-25T10:00:00+08:00"},
            {"id": "decision.b", "type": "decision", "label": "B", "status": "in_progress",
             "source": "manual", "note": "",
             "updatedAt": "2026-10-26T10:00:00+08:00"},
            {"id": "artifact.c", "type": "artifact", "label": "C", "status": "superseded",
             "source": "", "note": "replaced",
             "updatedAt": "2026-10-27T10:00:00+08:00"},
            {"id": "env.d", "type": "env", "label": "D", "status": "open",
             "source": "group:legacy 2026-10-27",
             "evidence": [{"locator": "path:docs/x.md", "content_sha256": SHA_A,
                           "captured_at": "2026-10-27T10:00:00+08:00"}],
             "updatedAt": "2026-10-27T10:00:00+08:00"},
        ],
        "edges": [
            {"from": "task.a", "to": "decision.b", "kind": "relates_to"},
            {"from": "decision.b", "to": "artifact.c", "kind": "supersedes"},
        ],
        "changes": [
            {"at": "2026-10-25T10:00:00+08:00", "by": "x", "op": "add-node",
             "target": "task.a", "rev": 40, "note": ""},
            {"at": "2026-10-26T10:00:00+08:00", "by": "x", "op": "set-status",
             "rev": 41, "note": "no target"},
            {"at": "2026-10-27T10:00:00+08:00", "by": "x", "op": "fix-edge",
             "detail": "no target no rev"},
        ],
    }


class AdoptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="amg-adopt-")
        self.legacy = os.path.join(self.tmp, "legacy")
        self.dst = os.path.join(self.tmp, "dst")
        os.makedirs(self.legacy, exist_ok=True)
        self.legacy_file = os.path.join(self.legacy, "graph.json")
        self._write_doc(self.legacy_file, legacy_doc())
        self._old_now = os.environ.get("AMG_NOW")
        os.environ["AMG_NOW"] = "2026-10-29T20:00:00+08:00"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self._old_now is None:
            os.environ.pop("AMG_NOW", None)
        else:
            os.environ["AMG_NOW"] = self._old_now

    # ---------- helpers ----------
    def _write_doc(self, path, doc):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)

    def _node(self, graph_dir, node_id):
        m = Memory.open(graph_dir)
        return next(n for n in m.doc["nodes"] if n["id"] == node_id)

    def _adopt(self, **kwargs):
        return Memory.adopt(self.legacy, self.dst, **kwargs)

    # ---------- core transform ----------
    def test_adopt_creates_check_clean_amg_graph(self):
        rep = self._adopt()
        self.assertEqual(rep["src_schema"], "group-kg/v1")
        self.assertTrue(rep["check"]["ok"], rep["check"]["errors"])
        m = Memory.open(self.dst)
        self.assertEqual(m.doc["schema"], "amg/v1")
        self.assertEqual(m.doc["group"], "legacy-team")
        self.assertEqual(len(m.doc["nodes"]), 4)
        self.assertEqual(len(m.doc["edges"]), 2)
        self.assertEqual(rep["counts"]["changes"], 4)  # 3 legacy + 1 adopt record
        self.assertTrue(rep["check"]["ok"])
        self.assertEqual(m.check()["errors"], [])

    def test_never_fabricates_evidence_from_legacy_strings(self):
        rep = self._adopt()
        node = self._node(self.dst, "task.a")
        self.assertEqual(node["evidence"], [])
        self.assertEqual(node["legacy_evidence"], ["docs/plan.md", "cmd:pytest -q (exit 0)"])
        self.assertIsNone(node["evidence_grade"])
        self.assertEqual(rep["mapped"]["evidence_legacy_strings"], 2)
        # the legacy ratio is reported, not hidden: audit still sees it as legacy debt
        self.assertEqual(rep["legacy"]["done_no_evidence_ratio"], "1/1")

    def test_source_placeholder_backfilled_with_provenance(self):
        rep = self._adopt()
        prov = "adopted:group-kg/v1:" + rep["src_sha256"][:12]
        for node_id, old in (("decision.b", "manual"), ("artifact.c", "")):
            node = self._node(self.dst, node_id)
            self.assertEqual(node["source"], prov)
            self.assertEqual(node["legacy_source"], old)
        self.assertEqual(rep["mapped"]["source_backfilled"], 2)
        # real sources are preserved verbatim, not overwritten by provenance
        self.assertEqual(self._node(self.dst, "task.a")["source"], "group:legacy 2026-10-25")

    def test_superseded_timestamps_inferred_and_flagged(self):
        rep = self._adopt()
        node = self._node(self.dst, "artifact.c")
        self.assertEqual(node["superseded_at"], "2026-10-27T10:00:00+08:00")
        self.assertTrue(node["superseded_at_inferred"])
        self.assertEqual(node["valid_until"], "2026-10-27T10:00:00+08:00")
        self.assertEqual(rep["mapped"]["superseded_completed"], 1)

    def test_valid_from_is_not_invented(self):
        rep = self._adopt()
        self.assertIsNone(self._node(self.dst, "task.a")["valid_from"])
        self.assertEqual(rep["mapped"]["valid_from_unknown"], 4)

    def test_existing_valid_evidence_object_is_kept(self):
        rep = self._adopt()
        node = self._node(self.dst, "env.d")
        self.assertEqual(len(node["evidence"]), 1)
        self.assertEqual(node["evidence"][0]["locator"], "path:docs/x.md")
        self.assertEqual(node["legacy_evidence"], [])
        self.assertEqual(rep["mapped"]["evidence_objects_kept"], 1)

    # ---------- refusals: nothing dropped silently ----------
    def test_dangling_edge_is_refused_by_default(self):
        doc = legacy_doc()
        doc["edges"].append({"from": "task.a", "to": "ghost.z", "kind": "relates_to"})
        self._write_doc(self.legacy_file, doc)
        with self.assertRaises(ProtocolError) as ctx:
            self._adopt()
        self.assertEqual(ctx.exception.code, "E_ADOPT_DANGLING")
        self.assertFalse(os.path.exists(os.path.join(self.dst, "graph.json")))

    def test_drop_dangling_is_explicit_and_counted(self):
        doc = legacy_doc()
        doc["edges"].append({"from": "task.a", "to": "ghost.z", "kind": "relates_to"})
        self._write_doc(self.legacy_file, doc)
        rep = self._adopt(drop_dangling=True)
        self.assertEqual(rep["counts"]["dangling_dropped"], 1)
        self.assertEqual(len(Memory.open(self.dst).doc["edges"]), 2)

    def test_duplicate_id_is_refused(self):
        doc = legacy_doc()
        doc["nodes"].append(dict(doc["nodes"][0]))
        self._write_doc(self.legacy_file, doc)
        with self.assertRaises(ProtocolError) as ctx:
            self._adopt()
        self.assertEqual(ctx.exception.code, "E_ADOPT_UNSUPPORTED")

    def test_unknown_type_is_refused(self):
        doc = legacy_doc()
        doc["nodes"].append({"id": "weird.e", "type": "telemetry", "label": "E",
                             "status": "open", "source": "x"})
        self._write_doc(self.legacy_file, doc)
        with self.assertRaises(ProtocolError) as ctx:
            self._adopt()
        self.assertEqual(ctx.exception.code, "E_ADOPT_UNSUPPORTED")

    def test_duplicate_identical_edges_are_merged_and_counted(self):
        doc = legacy_doc()
        doc["edges"].append(dict(doc["edges"][0]))
        self._write_doc(self.legacy_file, doc)
        rep = self._adopt()
        self.assertEqual(rep["counts"]["duplicate_edges_merged"], 1)
        self.assertEqual(len(Memory.open(self.dst).doc["edges"]), 2)
        self.assertTrue(rep["check"]["ok"])

    # ---------- safety ----------
    def test_source_file_is_never_modified(self):
        with open(self.legacy_file, "rb") as fh:
            before = fh.read()
        self._adopt()
        with open(self.legacy_file, "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_destination_must_not_exist(self):
        self._adopt()
        with self.assertRaises(ProtocolError) as ctx:
            self._adopt()
        self.assertEqual(ctx.exception.code, "E_EXISTS")

    def test_refuses_already_adopted_graph(self):
        self._adopt()
        with self.assertRaises(ProtocolError) as ctx:
            Memory.adopt(self.dst, os.path.join(self.tmp, "dst2"))
        self.assertEqual(ctx.exception.code, "E_ALREADY_AMG")

    def test_dry_run_writes_nothing(self):
        rep = self._adopt(dry_run=True)
        self.assertTrue(rep["dry_run"])
        self.assertIsNone(rep["dst"])
        self.assertFalse(os.path.exists(os.path.join(self.dst, "graph.json")))
        self.assertTrue(rep["check"]["ok"])

    def test_adoption_is_deterministic(self):
        other = os.path.join(self.tmp, "dst2")
        self._adopt()
        Memory.adopt(self.legacy, other)
        with open(os.path.join(self.dst, "graph.json"), "rb") as fh:
            a = fh.read()
        with open(os.path.join(other, "graph.json"), "rb") as fh:
            b = fh.read()
        self.assertEqual(a, b)

    def test_pin_out_makes_legacy_conflicts_disappear(self):
        doc = {"schema": "group-kg/v1", "group": "g", "rev": 2, "updatedAt": "2026-10-29T12:00:00+08:00",
               "nodes": [
                   {"id": "task.done_no_ev", "type": "task", "label": "A", "status": "done",
                    "source": "s", "updatedAt": "2026-10-29T12:00:00+08:00"},
                   {"id": "task.open", "type": "task", "label": "B", "status": "open",
                    "source": "s", "updatedAt": "2026-10-29T12:00:00+08:00"},
               ], "edges": [], "changes": []}
        self._write_doc(self.legacy_file, doc)
        pin_path = os.path.join(self.tmp, "pin.json")
        self._adopt(pin_out=pin_path)
        m = Memory.open(self.dst)
        without = m.audit()
        self.assertFalse(without["ok"])          # legacy debt is visible, not erased
        with open(pin_path, encoding="utf-8") as fh:
            pin = json.load(fh)
        with_pin = m.audit(pin=pin)
        self.assertTrue(with_pin["ok"], with_pin["conflicts"])
        self.assertTrue(with_pin["pin"]["match"])

    def test_gate_stays_content_typed_after_adoption(self):
        """Adoption must not weaken the gate for new writes, and the gate still
        triggers on conclusion-typed content (DECISIONS #2), not on status."""
        self._adopt()
        m = Memory.open(self.dst)
        m.add_node("task.new", "task", "new work", source="standup 2026-10-29")
        m.set_status("task.new", "done", note="plain task: not a conclusion, no evidence required")
        m.add_node("decision.new", "decision", "new fact", source="standup 2026-10-29",
                   status="in_progress")
        with self.assertRaises(ProtocolError) as ctx:
            m.set_status("decision.new", "done", note="no evidence")
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_MISSING")
        self.assertTrue(m.check()["ok"])

    # ---------- CLI contract ----------
    def test_cli_exit_codes(self):
        self.assertEqual(cli_mod.main(["adopt", self.legacy, self.dst]), EXIT_OK)
        self.assertEqual(cli_mod.main(["adopt", self.legacy, self.dst]), EXIT_USAGE)  # dst exists
        self.assertEqual(cli_mod.main(["adopt", self.dst, os.path.join(self.tmp, "x")]), EXIT_USAGE)
        bad = legacy_doc()
        bad["edges"].append({"from": "task.a", "to": "ghost.z", "kind": "relates_to"})
        self._write_doc(self.legacy_file, bad)
        self.assertEqual(cli_mod.main(["adopt", self.legacy, os.path.join(self.tmp, "y")]), EXIT_ERROR)


    def test_adopted_nodes_declare_unknown_validity(self):
        rep = self._adopt()
        m = Memory.open(self.dst)
        self.assertTrue(all(n["valid_time_known"] is False for n in m.doc["nodes"]))
        self.assertEqual(rep["mapped"]["valid_time_unknown"], 4)
        node = next(n for n in m.doc["nodes"] if n["id"] == "decision.b")
        node["valid_until"] = "2020-01-01T00:00:00+08:00"
        audit = m.audit()
        self.assertFalse(any("valid_until passed" in c for c in audit["conflicts"]))
        self.assertTrue(any("validity time is unknown" in h for h in audit["hints"]))


class AdoptionSuccessCriteriaDocTests(unittest.TestCase):
    """`docs/ADOPTION.md` defines "successful adoption" — the definition is the contract.

    `issue.mem-arch-dod5-criterion-rewrite`: "audit --pin exits 0" must never be the
    criterion, because a real graph carries genuine stale work and requiring exit 0
    pushes an operator to silence it. The six observable criteria live in the owning
    document; this test fails if that section disappears or loses a criterion.
    """

    def setUp(self):
        path = os.path.join(ROOT, "docs", "ADOPTION.md")
        with open(path, encoding="utf-8") as fh:
            self.text = fh.read()

    def section(self):
        start = self.text.find("## What counts as a successful adoption")
        self.assertNotEqual(start, -1, "ADOPTION.md lost the success-criteria section")
        end = self.text.find("\n## ", start + 1)
        return self.text[start:end if end != -1 else None]

    def test_six_criteria_are_numbered(self):
        section = self.section()
        numbered = re.findall(r"^\d\. ", section, flags=re.MULTILINE)
        self.assertEqual(len(numbered), 6, section)

    def test_each_criterion_is_named(self):
        section = self.section().lower()
        for needle in ("check` errors are `0", "counts the tool printed add up",
                       "no fabricated evidence", "pin is self-consistent",
                       "forward-only", "byte-identical"):
            self.assertIn(needle, section)

    def test_the_exit_code_is_not_the_criterion(self):
        section = self.section()
        self.assertIn("Do not use `audit --pin`'s exit code as the success criterion",
                      section)
        self.assertIn("pin.match: true", section)


if __name__ == "__main__":
    unittest.main()
