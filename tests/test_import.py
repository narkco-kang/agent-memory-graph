import json
import os
import subprocess
import sys
import tempfile
import unittest

from amg import Memory, ProtocolError
from helpers import TempGraph, ev

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHA = "d" * 64


def node(i, **kw):
    base = {"id": f"task.i{i}", "type": "task", "label": f"imported {i}", "source": "batch 2026-10-30"}
    base.update(kw)
    return base


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m

    def tearDown(self):
        self.g.close()

    def _bytes(self):
        with open(os.path.join(self.g.dir, "graph.json"), "rb") as fh:
            return fh.read()

    def test_batch_writes_all_nodes_and_keeps_rev_monotonic(self):
        res = self.m.add_many([node(1), node(2), node(3)])
        self.assertEqual(res["nodes"], 3)
        ids = [n["id"] for n in self.m.doc["nodes"]]
        self.assertEqual(ids, ["task.i1", "task.i2", "task.i3"])
        revs = [c["rev"] for c in self.m.doc["changes"]]
        self.assertEqual(revs, sorted(revs))
        self.assertTrue(self.m.check()["ok"])

    def test_all_or_nothing_on_invalid_node(self):
        before = self._bytes()
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_many([node(1), {"id": "task.bad", "type": "task", "label": "x", "source": ""}])
        self.assertEqual(ctx.exception.code, "E_NO_SOURCE")
        self.assertEqual(self._bytes(), before)  # nothing written
        self.assertEqual(Memory.open(self.g.dir).doc["nodes"], [])

    def test_duplicate_inside_batch_rejects_everything(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_many([node(1), node(1)])
        self.assertEqual(ctx.exception.code, "E_DUP_ID")
        self.assertEqual(self.m.doc["nodes"], [])

    def test_duplicate_against_existing_rejects(self):
        self.m.add_node("task.i1", "task", "one", source="s")
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_many([node(1), node(2)])
        self.assertEqual(ctx.exception.code, "E_DUP_ID")
        self.assertEqual(len(Memory.open(self.g.dir).doc["nodes"]), 1)

    def test_edge_endpoint_must_exist_and_edges_written(self):
        self.m.add_many([node(1), node(2)], edges=[{"from": "task.i1", "to": "task.i2", "kind": "relates_to"}])
        self.assertEqual(len(self.m.doc["edges"]), 1)
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_many([node(3)], edges=[{"from": "task.i3", "to": "ghost", "kind": "relates_to"}])
        self.assertEqual(ctx.exception.code, "E_NO_NODE")
        self.assertEqual(len(self.m.doc["nodes"]), 2)

    def test_conclusion_gate_applies_in_batch(self):
        bad = node(1, type="decision", status="done")  # no evidence
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_many([bad])
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_MISSING")
        ok = node(1, type="decision", status="done", evidence=[ev()])
        self.assertEqual(self.m.add_many([ok])["nodes"], 1)

    def test_batch_is_faster_than_one_by_one(self):
        import time
        many = [node(i) for i in range(500)]
        t0 = time.perf_counter()
        self.m.add_many(many)
        batch = time.perf_counter() - t0
        self.assertLess(batch, 1.5, f"batch of 500 took {batch:.2f}s")


class ImportCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-import-")

    def cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        return subprocess.run([sys.executable, "-m", "amg.cli", *args],
                              capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)

    def _batch_file(self, payload):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return path

    def test_cli_import_success_and_exit_codes(self):
        self.cli("init", self.dir, "--group", "t")
        good = self._batch_file({"nodes": [node(1), node(2)], "edges": []})
        res = self.cli("import", self.dir, "--from", good)
        self.assertEqual(res.returncode, 0, res.stderr)
        bad = self._batch_file({"nodes": [{"id": "x", "type": "task", "label": "x", "source": ""}]})
        self.assertEqual(self.cli("import", self.dir, "--from", bad).returncode, 1)  # protocol
        self.assertEqual(self.cli("import", self.dir, "--from", "/nonexistent.json").returncode, 2)
        broken = self._batch_file(["not-an-object"])
        self.assertEqual(self.cli("import", self.dir, "--from", broken).returncode, 2)


if __name__ == "__main__":
    unittest.main()
