import json
import os
import subprocess
import sys
import tempfile
import unittest

from amg import Memory
from amg import readaudit
from helpers import TempGraph, ev

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ReadAuditTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m
        self.m.add_node("decision.limit", "decision", "limit is 32", source="s",
                        status="done", evidence=[ev()])
        self.m.add_node("rule.scope", "rule", "scope rule", source="s",
                        applies="global", expires_when=None)
        self.m.add_node("task.old", "task", "old task", source="s", status="done")
        self.m.add_node("task.new", "task", "new task", source="s", status="done")
        self.m.supersede("task.old", "task.new", note="replaced")

    def tearDown(self):
        self.g.close()

    def _log_path(self):
        return os.path.join(self.g.dir, "reads.jsonl")

    def test_no_file_when_disabled(self):
        self.m.search("limit is 32", layer="L4")
        self.assertFalse(os.path.exists(self._log_path()))

    def test_low_risk_read_not_logged_even_when_enabled(self):
        self.m.search("new task", audit_read=True)
        self.assertFalse(os.path.exists(self._log_path()))

    def test_strict_query_is_logged(self):
        before = open(os.path.join(self.g.dir, "graph.json"), "rb").read()
        self.m.search("limit is 32", strict=True, audit_read=True)
        self.assertTrue(os.path.exists(self._log_path()))
        event = json.loads(open(self._log_path(), encoding="utf-8").readline())
        self.assertEqual(event["op"], "search")
        self.assertTrue(event["strict"])
        self.assertEqual(open(os.path.join(self.g.dir, "graph.json"), "rb").read(), before)

    def test_l4_read_is_logged(self):
        self.m.search("scope rule", layer="L4", audit_read=True)
        event = json.loads(open(self._log_path(), encoding="utf-8").readline())
        self.assertEqual(event["layer"], "L4")

    def test_superseded_history_read_is_logged(self):
        self.m.search("task.old", layer="L2", audit_read=True)
        self.assertTrue(os.path.exists(self._log_path()))

    def test_rotation_keeps_log_bounded(self):
        old = readaudit.MAX_BYTES
        readaudit.MAX_BYTES = 400
        try:
            for i in range(20):
                readaudit.log_read(self.g.dir, op="search", query=f"q{i}", strict=True)
            self.assertTrue(os.path.exists(self._log_path() + ".1"))
            self.assertLessEqual(os.path.getsize(self._log_path()), 400)
        finally:
            readaudit.MAX_BYTES = old

    def test_stats_reports_segments(self):
        self.m.search("limit is 32", strict=True, audit_read=True)
        stats = readaudit.stats(self.g.dir)
        self.assertGreaterEqual(len(stats["segments"]), 1)
        self.assertGreater(stats["total_bytes"], 0)


class ReadAuditCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-rda-")

    def cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        return subprocess.run([sys.executable, "-m", "amg.cli", *args],
                              capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)

    def test_cli_audit_read(self):
        self.cli("init", self.dir, "--group", "t")
        self.cli("add", self.dir, "--id", "decision.d", "--type", "decision", "--label",
                 "a decision", "--source", "s", "--status", "done",
                 "--evidence", "path:README.md|" + "a" * 64 + "|2026-10-30T09:00:00+08:00")
        self.assertEqual(self.cli("search", self.dir, "a decision", "--strict", "--audit-read").returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "reads.jsonl")))
        self.assertEqual(self.cli("search", self.dir, "a decision").returncode, 0)
        self.assertEqual(len(open(os.path.join(self.dir, "reads.jsonl"), encoding="utf-8").readlines()), 1)


if __name__ == "__main__":
    unittest.main()
