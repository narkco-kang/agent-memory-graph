import json
import os
import subprocess
import sys
import tempfile
import unittest

from amg import Memory, ProtocolError
from helpers import SHA, TempGraph, ev

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RelationTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m
        for nid in ("task.a", "task.b", "task.c", "decision.d"):
            self.m.add_node(nid, "decision" if nid.startswith("decision") else "task",
                            f"label {nid}", source="s", evidence=[ev()] if nid == "decision.d" else None,
                            status="done" if nid == "decision.d" else "open")

    def tearDown(self):
        self.g.close()

    def test_one_hop_both_directions(self):
        self.m.add_edge("task.a", "task.b", "relates_to")
        self.m.add_edge("task.c", "task.a", "relates_to")
        res = self.m.related("task.a")
        ids = {n["id"]: n for n in res["neighbors"]}
        self.assertEqual(set(ids), {"task.b", "task.c"})
        self.assertEqual(ids["task.b"]["direction"], "out")
        self.assertEqual(ids["task.c"]["direction"], "in")

    def test_depth_two(self):
        self.m.add_edge("task.a", "task.b", "relates_to")
        self.m.add_edge("task.b", "task.c", "relates_to")
        one = self.m.related("task.a", depth=1)
        two = self.m.related("task.a", depth=2)
        self.assertEqual({n["id"] for n in one["neighbors"]}, {"task.b"})
        self.assertEqual({n["id"] for n in two["neighbors"]}, {"task.b", "task.c"})

    def test_kind_filter(self):
        self.m.add_edge("task.a", "task.b", "relates_to")
        self.m.add_edge("task.a", "task.c", "depends_on")
        res = self.m.related("task.a", kind="depends_on")
        self.assertEqual([n["id"] for n in res["neighbors"]], ["task.c"])

    def test_unknown_node_and_bad_depth(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.related("ghost")
        self.assertEqual(ctx.exception.code, "E_NO_NODE")
        with self.assertRaises(ProtocolError) as ctx:
            self.m.related("task.a", depth=99)
        self.assertEqual(ctx.exception.code, "E_BAD_DEPTH")

    def test_no_neighbors_returns_empty(self):
        self.assertEqual(self.m.related("task.a")["neighbors"], [])

    def test_search_expand_marks_source(self):
        self.m.add_node("task.widget", "task", "widget queue", source="s", evidence=[ev()])
        self.m.add_node("task.spoke", "task", "spoke node", source="s")
        self.m.add_edge("task.widget", "task.spoke", "relates_to")
        hits = self.m.search("widget", expand=False)
        self.assertEqual([h["id"] for h in hits], ["task.widget"])
        expanded = self.m.search("widget", expand=True)
        pullers = [h for h in expanded if h.get("expanded_from")]
        self.assertEqual([h["id"] for h in pullers], ["task.spoke"])
        self.assertEqual(pullers[0]["expanded_from"], "task.widget")

    def test_expand_strict_drops_unanchored_neighbors(self):
        self.m.add_node("decision.root", "decision", "root widget", source="s",
                        status="done", evidence=[ev()])
        self.m.add_node("task.bare", "task", "bare spoke", source="s")
        self.m.add_edge("decision.root", "task.bare", "relates_to")
        expanded = self.m.search("root widget", expand=True, strict=True)
        self.assertFalse([h for h in expanded if h.get("expanded_from")])

    def test_acyclic_kinds_reject_cycles(self):
        self.m.add_edge("task.a", "task.b", "depends_on")
        self.m.add_edge("task.b", "task.a", "depends_on")
        rep = self.m.check()
        self.assertFalse(rep["ok"])
        self.assertTrue(any("cycle on depends_on" in e for e in rep["errors"]))

    def test_relates_cycles_are_tolerated_hint(self):
        self.m.add_edge("task.a", "task.b", "relates_to")
        self.m.add_edge("task.b", "task.a", "relates_to")
        rep = self.m.check()
        self.assertTrue(rep["ok"])
        self.assertTrue(any("cyclic component" in h for h in rep["hints"]))


class RelatedCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-rel-")

    def cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        return subprocess.run([sys.executable, "-m", "amg.cli", *args],
                              capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)

    def test_cli_related(self):
        self.cli("init", self.dir, "--group", "t")
        self.cli("add", self.dir, "--id", "task.a", "--type", "task", "--label", "A", "--source", "s")
        self.cli("add", self.dir, "--id", "task.b", "--type", "task", "--label", "B", "--source", "s")
        self.cli("link", self.dir, "--from", "task.a", "--to", "task.b", "--kind", "relates_to")
        res = self.cli("related", self.dir, "task.a", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["neighbors"][0]["id"], "task.b")
        self.assertEqual(self.cli("related", self.dir, "ghost").returncode, 1)
        self.assertEqual(self.cli("related", self.dir, "task.a", "--depth", "9").returncode, 2)


if __name__ == "__main__":
    unittest.main()
