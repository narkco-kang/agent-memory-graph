import json
import os
import unittest

from amg import Memory, ProtocolError
from amg.const import now
from helpers import SHA, TempGraph, ev


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m

    def tearDown(self):
        self.g.close()

    def test_init_never_overwrites(self):
        with self.assertRaises(ProtocolError) as ctx:
            Memory.init(self.g.dir, "t")
        self.assertEqual(ctx.exception.code, "E_EXISTS")

    def test_ir1_append_only_rev_monotonic(self):
        n = self.m.add_node("task.a", "task", "A", source="group:t 2026-10-29 10:00")
        self.assertEqual(self.m.doc["rev"], 1)
        self.m.set_status("task.a", "done", note="pytest green")
        self.assertEqual(self.m.doc["rev"], 2)
        revs = [c["rev"] for c in self.m.doc["changes"]]
        self.assertEqual(revs, sorted(revs))
        self.assertEqual(len(self.m.doc["nodes"]), 1)  # no delete API touched it

    def test_ir2_source_required(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("task.b", "task", "B", source="")
        self.assertEqual(ctx.exception.code, "E_NO_SOURCE")
        with self.assertRaises(ProtocolError):
            self.m.add_node("task.c", "task", "C", source="unknown")
        self.assertNotIn("task.b", [n["id"] for n in self.m.doc["nodes"]])

    def test_ir4_conclusion_done_requires_evidence(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("decision.x", "decision", "X", source="s", status="done")
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_MISSING")
        self.m.add_node("decision.x", "decision", "X", source="s")
        with self.assertRaises(ProtocolError) as ctx:
            self.m.set_status("decision.x", "done", note="done but no evidence")
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_MISSING")
        self.m.set_status("decision.x", "done", note="evidence attached", evidence=[ev()])
        self.assertEqual(len(self.m.doc["nodes"][0]["evidence"]), 1)

    def test_non_conclusion_done_allowed_without_evidence(self):
        self.m.add_node("task.y", "task", "Y", source="s", status="done")
        self.assertEqual(self.m.doc["nodes"][0]["status"], "done")

    def test_bare_string_evidence_rejected(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("decision.z", "decision", "Z", source="s", evidence=["path:README.md"])
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_FORMAT")

    def test_evidence_sha_must_be_hex64(self):
        bad = dict(ev())
        bad["content_sha256"] = "deadbeef"
        with self.assertRaises(ProtocolError):
            self.m.add_node("decision.q", "decision", "Q", source="s", evidence=[bad])

    def test_status_requires_note(self):
        self.m.add_node("task.n", "task", "N", source="s")
        with self.assertRaises(ProtocolError) as ctx:
            self.m.set_status("task.n", "done", note="  ")
        self.assertEqual(ctx.exception.code, "E_NOTE_REQUIRED")

    def test_supersede_keeps_old_node_and_stamps_validity(self):
        self.m.add_node("decision.v1", "decision", "V1", source="s", status="done", evidence=[ev()])
        self.m.add_node("decision.v2", "decision", "V2", source="s", status="done", evidence=[ev()])
        res = self.m.supersede("decision.v1", "decision.v2", note="v2 corrects v1")
        self.assertTrue(res["valid_until"])
        old = [n for n in self.m.doc["nodes"] if n["id"] == "decision.v1"][0]
        self.assertEqual(old["status"], "superseded")
        self.assertIsNotNone(old["superseded_at"])
        self.assertTrue(any(e["kind"] == "supersedes" for e in self.m.doc["edges"]))
        with self.assertRaises(ProtocolError) as ctx:
            self.m.set_status("decision.v1", "done", note="nope")
        self.assertEqual(ctx.exception.code, "E_IMMUTABLE")

    def test_duplicate_id_and_dangling_edge(self):
        self.m.add_node("task.d", "task", "D", source="s")
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("task.d", "task", "D2", source="s")
        self.assertEqual(ctx.exception.code, "E_DUP_ID")
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_edge("task.d", "task.missing", "relates_to")
        self.assertEqual(ctx.exception.code, "E_NO_NODE")

    def test_check_flags_rev_backwards(self):
        self.m.add_node("task.r1", "task", "R1", source="s")
        self.m.add_node("task.r2", "task", "R2", source="s")
        doc = self.m.doc
        doc["changes"][1]["rev"] = 0
        rep = self.m.check()
        self.assertFalse(rep["ok"])
        self.assertTrue(any("IR-1" in e for e in rep["errors"]))

    def test_atomic_write_leaves_no_tmp(self):
        self.m.add_node("task.t", "task", "T", source="s")
        leftovers = [f for f in os.listdir(self.g.dir) if f.startswith(".graph.") and f.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        with open(os.path.join(self.g.dir, "graph.json"), encoding="utf-8") as fh:
            loaded = json.load(fh)
        self.assertEqual(loaded["nodes"][0]["id"], "task.t")


if __name__ == "__main__":
    unittest.main()


class RuleFieldTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m

    def tearDown(self):
        self.g.close()

    def test_rule_requires_applies(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("rule.a", "rule", "A", source="s", expires_when=None)
        self.assertEqual(ctx.exception.code, "E_RULE_APPLIES")

    def test_rule_requires_explicit_lifetime(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("rule.b", "rule", "B", source="s", applies="global")
        self.assertEqual(ctx.exception.code, "E_RULE_EXPIRES")

    def test_rule_with_explicit_never_is_valid(self):
        self.m.add_node("rule.c", "rule", "C", source="s", applies="global", expires_when=None)
        node = self.m.doc["nodes"][0]
        self.assertEqual(node["applies"], "global")
        self.assertIn("expires_when", node)
        self.assertIsNone(node["expires_when"])
        self.assertTrue(self.m.check()["ok"])


class GradeTypeTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m

    def tearDown(self):
        self.g.close()

    def test_boolean_grade_is_rejected(self):
        bad = ev()
        bad["grade"] = True
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("decision.g", "decision", "G", source="s", evidence=[bad])
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_FORMAT")

    def test_integer_grade_is_stored(self):
        good = ev(grade=2)
        self.m.add_node("decision.h", "decision", "H", source="s", evidence=[good])
        self.assertEqual(self.m.doc["nodes"][0]["evidence"][0]["grade"], 2)
        self.assertIs(type(self.m.doc["nodes"][0]["evidence"][0]["grade"]), int)


if __name__ == "__main__":
    unittest.main()
