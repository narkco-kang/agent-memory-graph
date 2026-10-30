import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHA = "e" * 64


def frame(**kw):
    return json.dumps(kw, ensure_ascii=False)


class McpTests(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(tempfile.mkdtemp(prefix="amg-mcp-"), "mem")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        subprocess.run([sys.executable, "-m", "amg.cli", "init", self.dir, "--group", "t"],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)

    def speak(self, messages):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        payload = "\n".join(messages) + "\n"
        res = subprocess.run([sys.executable, "-m", "amg.cli", "mcp", self.dir],
                             input=payload, capture_output=True, text=True,
                             encoding="utf-8", env=env, cwd=ROOT, timeout=60)
        lines = [l for l in res.stdout.splitlines() if l.strip()]
        return [json.loads(l) for l in lines], res

    def test_initialize_and_tools_list(self):
        replies, res = self.speak([frame(jsonrpc="2.0", id=1, method="initialize", params={}),
                                   frame(jsonrpc="2.0", method="notifications/initialized"),
                                   frame(jsonrpc="2.0", id=2, method="tools/list")])
        self.assertEqual(replies[0]["id"], 1)
        self.assertIn("tools", replies[0]["result"]["capabilities"])
        names = [t["name"] for t in replies[1]["result"]["tools"]]
        self.assertIn("memory_search", names)
        self.assertIn("memory_add", names)
        # stdout must be protocol-only
        self.assertEqual(res.stdout.count('"jsonrpc"'), len(replies))

    def test_search_schema_advertises_include_archive(self):
        replies, _ = self.speak([frame(jsonrpc="2.0", id=1, method="initialize", params={}),
                                 frame(jsonrpc="2.0", method="notifications/initialized"),
                                 frame(jsonrpc="2.0", id=2, method="tools/list")])
        tools = {t["name"]: t for t in replies[1]["result"]["tools"]}
        props = tools["memory_search"]["inputSchema"]["properties"]
        self.assertIn("include_archive", props)
        self.assertEqual(props["include_archive"]["type"], "boolean")
        # The tool list stays at eight: the archive is a search option, not a new tool.
        self.assertEqual(len(tools), 8)

    def test_add_then_search_roundtrip(self):
        evidence = [{"locator": "path:README.md", "content_sha256": SHA,
                     "captured_at": "2026-10-30T10:00:00+08:00"}]
        replies, _ = self.speak([
            frame(jsonrpc="2.0", id=1, method="tools/call", params={
                "name": "memory_add", "arguments": {
                    "id": "decision.limit", "type": "decision", "label": "limit is 32",
                    "source": "mcp test", "status": "done", "evidence": evidence}}),
            frame(jsonrpc="2.0", id=2, method="tools/call", params={
                "name": "memory_search", "arguments": {"query": "limit is 32"}}),
        ])
        self.assertFalse(replies[0]["result"]["isError"])
        hits = json.loads(replies[1]["result"]["content"][0]["text"])
        self.assertEqual(hits[0]["id"], "decision.limit")
        self.assertEqual(hits[0]["anchor_state"], "present")

    def _old_graph(self):
        """A graph whose whole ledger is old enough to archive, built with AMG_NOW."""
        self.dir = os.path.join(tempfile.mkdtemp(prefix="amg-mcp-old-"), "mem")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        env["AMG_NOW"] = "2026-08-01T10:00:00+08:00"
        for args in (["init", self.dir, "--group", "t"],
                     ["add", self.dir, "--id", "task.alpha", "--type", "task",
                      "--label", "alpha", "--source", "cmd:x"]):
            subprocess.run([sys.executable, "-m", "amg.cli", *args], check=True,
                           capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
        env.pop("AMG_NOW")
        subprocess.run([sys.executable, "-m", "amg.cli", "archive", self.dir,
                        "--older-than-days", "1", "--apply"], check=True,
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)

    def test_search_can_include_the_cold_archive(self):
        self._old_graph()
        replies, _ = self.speak([
            frame(jsonrpc="2.0", id=1, method="tools/call", params={
                "name": "memory_search",
                "arguments": {"query": "task.alpha", "layer": "L2",
                              "include_archive": True}}),
        ])
        hits = json.loads(replies[0]["result"]["content"][0]["text"])
        self.assertTrue(any(h.get("archived") for h in hits), hits)
        self.assertTrue(all("archive_file" in h for h in hits if h.get("archived")))

    def test_include_archive_is_refused_on_node_layers_over_mcp(self):
        replies, _ = self.speak([
            frame(jsonrpc="2.0", id=1, method="tools/call", params={
                "name": "memory_search",
                "arguments": {"query": "x", "layer": "L3", "include_archive": True}}),
        ])
        self.assertTrue(replies[0]["result"]["isError"])
        self.assertIn("E_ARCHIVE_LAYER", replies[0]["result"]["content"][0]["text"])

    def test_gate_rejects_through_mcp(self):
        replies, _ = self.speak([frame(jsonrpc="2.0", id=1, method="tools/call", params={
            "name": "memory_add", "arguments": {
                "id": "decision.bad", "type": "decision", "label": "no evidence",
                "source": "mcp", "status": "done"}})])
        self.assertTrue(replies[0]["result"]["isError"])
        self.assertIn("E_EVIDENCE_MISSING", replies[0]["result"]["content"][0]["text"])

    def test_unknown_method_and_tool(self):
        replies, _ = self.speak([
            frame(jsonrpc="2.0", id=1, method="does/not/exist"),
            frame(jsonrpc="2.0", id=2, method="tools/call", params={"name": "nope", "arguments": {}}),
        ])
        self.assertEqual(replies[0]["error"]["code"], -32601)
        self.assertTrue(replies[1]["result"]["isError"])
        self.assertIn("unknown tool", replies[1]["result"]["content"][0]["text"])

    def test_check_and_digest_tools(self):
        replies, _ = self.speak([
            frame(jsonrpc="2.0", id=1, method="tools/call", params={"name": "memory_check", "arguments": {}}),
            frame(jsonrpc="2.0", id=2, method="tools/call", params={"name": "memory_digest", "arguments": {"max_bytes": 2048}}),
        ])
        report = json.loads(replies[0]["result"]["content"][0]["text"])
        self.assertTrue(report["ok"])
        digest = json.loads(replies[1]["result"]["content"][0]["text"])["digest"]
        self.assertLessEqual(len(digest.encode()), 2048)


if __name__ == "__main__":
    unittest.main()
