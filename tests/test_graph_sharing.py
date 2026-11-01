"""`--graph <file>`: share one physical FILE with a writer that owns the layout.

Why this exists (measured, not designed):

* the team writes group graphs with `kg.py`, at `graphs/<group>.json`, and that tool
  decides the filename itself;
* this tool wanted `<dir>/graph.json`;
* bridging the two with a symlink SPLIT THE GRAPH on the first write:
  `os.replace` swaps the link rather than writing through it, so `amg add` reported
  success while the real file kept its old content and a second, ordinary file
  appeared beside it with the new node inside.

So neither "move the other tool's file" nor "bridge with a symlink" is acceptable:
the two tools must open the same physical file. `--graph` does that, and the lock is
taken next to that file so both writers contend on the same lock.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg.memory import Memory  # noqa: E402
from amg.store import Store  # noqa: E402

CLI = [sys.executable, "-m", "amg.cli"]


def make_graph(group="t", nodes=()):
    return {"schema": "group-kg/v1", "group": group, "session": "", "goal": "",
            "updatedAt": "2026-11-01T00:00:00+08:00", "rev": 0,
            "nodes": list(nodes), "edges": [], "changes": []}


class StoreGraphFileTest(unittest.TestCase):
    def test_store_opens_the_exact_file_when_given(self):
        d = tempfile.mkdtemp(prefix="amg-share-")
        named = os.path.join(d, "测试群.json")
        with open(named, "w", encoding="utf-8") as fh:
            json.dump(make_graph(), fh, ensure_ascii=False)
        store = Store(d, graph_file=named)
        self.assertEqual(store.file, os.path.abspath(named))
        self.assertEqual(store.dir, os.path.abspath(d))

    def test_the_lock_lives_next_to_the_shared_file(self):
        """Both writers must contend on one lock, so it cannot follow `<dir>`."""
        d = tempfile.mkdtemp(prefix="amg-share-")
        named = os.path.join(d, "group.json")
        with open(named, "w", encoding="utf-8") as fh:
            json.dump(make_graph(), fh, ensure_ascii=False)
        store = Store(d, graph_file=named)
        self.assertEqual(store.lockfile, os.path.join(os.path.abspath(d), ".lock"))

    def test_without_graph_file_the_old_layout_is_unchanged(self):
        d = tempfile.mkdtemp(prefix="amg-share-")
        self.assertEqual(Store(d).file, os.path.join(os.path.abspath(d), "graph.json"))

    def test_a_write_through_graph_file_lands_in_that_file(self):
        d = tempfile.mkdtemp(prefix="amg-share-")
        named = os.path.join(d, "测试群.json")
        with open(named, "w", encoding="utf-8") as fh:
            json.dump(make_graph(), fh, ensure_ascii=False)
        m = Memory.open(d, graph_file=named)
        m.add_node(id="n1", type="task", label="x", source="fixture", note="")
        with open(named, encoding="utf-8") as fh:
            after = json.load(fh)
        self.assertEqual([n["id"] for n in after["nodes"]], ["n1"])
        # and no stray <dir>/graph.json was created beside it
        self.assertFalse(os.path.exists(os.path.join(d, "graph.json")))


class GraphFlagTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="amg-flag-")
        self.graphs = os.path.join(self.root, "knowledge-graph", "graphs")
        os.makedirs(self.graphs, exist_ok=True)
        self.named = os.path.join(self.graphs, "g.json")
        with open(self.named, "w", encoding="utf-8") as fh:
            json.dump(make_graph(), fh, ensure_ascii=False)

    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        return subprocess.run(CLI + list(args), capture_output=True, text=True,
                              encoding="utf-8", env=env, cwd=ROOT, timeout=60)

    def test_add_writes_the_shared_file(self):
        """MUTATION GUARD: drop `--graph` (back to `<dir>/graph.json`) and this fails."""
        res = self.run_cli("add", self.graphs, "--graph", self.named,
                           "--id", "shared", "--type", "task", "--label", "shared write",
                           "--source", "fixture", "--status", "open")
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(self.named, encoding="utf-8") as fh:
            after = json.load(fh)
        self.assertIn("shared", [n["id"] for n in after["nodes"]])
        self.assertFalse(os.path.exists(os.path.join(self.graphs, "graph.json")),
                         "nothing may be written beside the shared file")

    def test_search_reads_the_shared_file(self):
        res = self.run_cli("search", self.graphs, "--graph", self.named, "anything",
                           "--root", self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("E_NO_GRAPH", res.stderr)

    def test_every_dir_taking_subcommand_accepts_graph(self):
        """A new sub-command must not be able to silently lack the flag."""
        for name in ("add", "status", "search", "check", "audit", "digest",
                     "related", "export", "verify-evidence", "mcp"):
            res = self.run_cli(name, "--help")
            self.assertIn("--graph", res.stdout, f"{name} is missing --graph")

    def test_rev_stays_contiguous_across_repeated_shared_writes(self):
        for i in range(3):
            res = self.run_cli("add", self.graphs, "--graph", self.named,
                               "--id", f"n{i}", "--type", "task", "--label", f"n{i}",
                               "--source", "fixture", "--status", "open")
            self.assertEqual(res.returncode, 0, res.stderr)
        with open(self.named, encoding="utf-8") as fh:
            after = json.load(fh)
        self.assertEqual([c["rev"] for c in after["changes"]], [1, 2, 3])
        self.assertEqual(after["rev"], 3)


if __name__ == "__main__":
    unittest.main()
