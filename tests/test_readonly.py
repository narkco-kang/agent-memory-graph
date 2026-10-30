"""Read-only mode: the write path is refused in code, not just in the docs.

Two layers are tested separately because they fail differently:

- `Memory.open(..., read_only=True)` is the *backstop*: every mutation funnels
  through `Memory._commit`, so a read-only instance refuses to commit no matter
  which method (or future method) reaches it.
- the MCP server additionally *advertises* no write tools and *refuses* them if
  a client calls one anyway. Hiding a tool is not enforcement; both are tested.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory, ProtocolError  # noqa: E402
from amg import mcp as mcp_mod  # noqa: E402

SHA = "e" * 64
EVIDENCE = [{"locator": "path:README.md", "content_sha256": SHA,
             "captured_at": "2026-10-30T10:00:00+08:00"}]


def digest(path):
    with open(os.path.join(path, "graph.json"), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def frame(**kw):
    return json.dumps(kw, ensure_ascii=False)


class ReadOnlyMemoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(tempfile.mkdtemp(prefix="amg-ro-"), "mem")
        Memory.init(self.dir, group="t")

    def test_read_only_refuses_every_mutation(self):
        # Seed with a writable instance so each call below would otherwise succeed
        # and reach the commit choke point.
        w = Memory.open(self.dir)
        w.add_node(id="task.a", type="task", label="a", source="test", note="n", by="test")
        w.add_node(id="task.old", type="task", label="old", source="test", note="n",
                   valid_from="2019-01-01T00:00:00+08:00",
                   valid_until="2020-01-01T00:00:00+08:00", by="test")
        w.add_node(id="task.new", type="task", label="new", source="test", note="n", by="test")
        before = digest(self.dir)
        m = Memory.open(self.dir, read_only=True)
        calls = [
            lambda: m.add_node(id="task.b", type="task", label="b", source="test",
                               note="n", by="test"),
            lambda: m.set_status("task.a", "done", note="n", by="test"),
            lambda: m.supersede("task.old", "task.new", note="n", by="test"),
            lambda: m.expire(apply=True, by="test"),
        ]
        for call in calls:
            with self.assertRaises(ProtocolError) as ctx:
                call()
            self.assertEqual(ctx.exception.code, "E_READ_ONLY")
        self.assertEqual(digest(self.dir), before, "read-only instance wrote bytes")

    def test_read_only_does_not_short_circuit_validation(self):
        # Content errors are still reported as content errors; read-only is a
        # write guard, not a validation bypass.
        m = Memory.open(self.dir, read_only=True)
        with self.assertRaises(ProtocolError) as ctx:
            m.add_node(id="x", type="nope", label="x", source="test", note="n", by="test")
        self.assertEqual(ctx.exception.code, "E_BAD_TYPE")

    def test_read_only_allows_reads(self):
        w = Memory.open(self.dir)
        w.add_node(id="task.a", type="task", label="alpha", source="test", note="n", by="test")
        m = Memory.open(self.dir, read_only=True)
        self.assertEqual(m.search("alpha")[0]["id"], "task.a")
        self.assertTrue(m.check()["ok"])
        self.assertEqual(m.related("task.a")["id"], "task.a")
        self.assertTrue(m.digest())
        self.assertEqual(m.audit()["counts"]["nodes"], 1)

    def test_read_only_on_missing_graph_is_no_graph(self):
        missing = os.path.join(tempfile.mkdtemp(prefix="amg-ro-miss-"), "nope")
        with self.assertRaises(ProtocolError) as ctx:
            Memory.open(missing, read_only=True)
        self.assertEqual(ctx.exception.code, "E_NO_GRAPH")
        self.assertFalse(os.path.isdir(missing), "read-only open must not create the dir")

    def test_writable_default_is_unchanged(self):
        m = Memory.open(self.dir)
        m.add_node(id="task.a", type="task", label="alpha", source="test", note="n", by="test")
        self.assertIn("task.a", [n["id"] for n in m.doc["nodes"]])


class ToolClassificationTests(unittest.TestCase):
    def test_partition_is_complete_and_disjoint(self):
        advertised = {t["name"] for t in mcp_mod.TOOLS}
        read, write = mcp_mod.READ_TOOLS, mcp_mod.WRITE_TOOLS
        self.assertEqual(read & write, set(), "a tool cannot be both read and write")
        self.assertEqual(read | write, advertised,
                         "every advertised tool must be classified; new tools cannot slip through")

    def test_write_tools_are_exactly_the_mutators(self):
        # Deliberate: the classification is asserted literally, so adding a
        # mutating tool requires updating this test (review point, not a default).
        self.assertEqual(mcp_mod.WRITE_TOOLS,
                         {"memory_add", "memory_status", "memory_supersede"})
        self.assertEqual(mcp_mod.READ_TOOLS,
                         {"memory_search", "memory_related", "memory_check",
                          "memory_audit", "memory_digest"})


class McpReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(tempfile.mkdtemp(prefix="amg-mcp-ro-"), "mem")
        Memory.init(self.dir, group="t")

    def speak(self, messages, read_only):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        cmd = [sys.executable, "-m", "amg.cli", "mcp", self.dir]
        if read_only:
            cmd.append("--read-only")
        res = subprocess.run(cmd, input="\n".join(messages) + "\n", capture_output=True,
                            text=True, encoding="utf-8", env=env, cwd=ROOT, timeout=60)
        lines = [l for l in res.stdout.splitlines() if l.strip()]
        return [json.loads(l) for l in lines], res

    def test_read_only_lists_no_write_tools(self):
        replies, _ = self.speak([frame(jsonrpc="2.0", id=1, method="tools/list")], True)
        names = {t["name"] for t in replies[0]["result"]["tools"]}
        self.assertEqual(names, set(mcp_mod.READ_TOOLS))
        self.assertNotIn("memory_add", names)

    def test_read_only_refuses_write_tool_calls_even_if_hidden(self):
        before = digest(self.dir)
        replies, res = self.speak([
            frame(jsonrpc="2.0", id=1, method="tools/call", params={
                "name": "memory_add", "arguments": {
                    "id": "decision.x", "type": "decision", "label": "x",
                    "source": "test", "status": "done", "evidence": EVIDENCE}}),
            frame(jsonrpc="2.0", id=2, method="tools/call", params={
                "name": "memory_status", "arguments": {"id": "a", "status": "done", "note": "n"}}),
            frame(jsonrpc="2.0", id=3, method="tools/call", params={
                "name": "memory_supersede", "arguments": {"old_id": "a", "new_id": "b", "note": "n"}}),
        ], True)
        for reply in replies:
            self.assertTrue(reply["result"]["isError"])
            self.assertIn("E_READ_ONLY", reply["result"]["content"][0]["text"])
        self.assertEqual(digest(self.dir), before, "read-only server wrote bytes")
        self.assertEqual(res.stdout.count('"jsonrpc"'), len(replies))

    def test_read_only_still_serves_reads(self):
        Memory.open(self.dir).add_node(id="task.a", type="task", label="alpha",
                                       source="test", note="n", by="test")
        replies, _ = self.speak([frame(jsonrpc="2.0", id=1, method="tools/call", params={
            "name": "memory_search", "arguments": {"query": "alpha"}})], True)
        self.assertFalse(replies[0]["result"]["isError"])
        hits = json.loads(replies[0]["result"]["content"][0]["text"])
        self.assertEqual(hits[0]["id"], "task.a")

    def test_read_only_initialize_says_so(self):
        replies, _ = self.speak([frame(jsonrpc="2.0", id=1, method="initialize", params={})], True)
        instructions = replies[0]["result"].get("instructions", "")
        self.assertIn("read-only", instructions.lower())

    def test_writable_server_still_writes(self):
        replies, _ = self.speak([frame(jsonrpc="2.0", id=1, method="tools/call", params={
            "name": "memory_add", "arguments": {
                "id": "decision.x", "type": "decision", "label": "x", "source": "test",
                "status": "done", "evidence": EVIDENCE}})], False)
        self.assertFalse(replies[0]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
