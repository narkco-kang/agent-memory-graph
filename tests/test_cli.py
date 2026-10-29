import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHA = "c" * 64


def run(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    return subprocess.run([sys.executable, "-m", "amg.cli", *args],
                          capture_output=True, text=True, env=env, cwd=cwd or ROOT)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-cli-")

    def test_exit_codes_contract(self):
        self.assertEqual(run("init", self.dir, "--group", "t").returncode, 0)
        # 2 = usage error
        self.assertEqual(run("add", self.dir, "--id", "x").returncode, 2)
        # 1 = protocol violation (duplicate id)
        self.assertEqual(run("add", self.dir, "--id", "task.a", "--type", "task",
                             "--label", "A", "--source", "s").returncode, 0)
        self.assertEqual(run("add", self.dir, "--id", "task.a", "--type", "task",
                             "--label", "A", "--source", "s").returncode, 1)
        # 0 = clean check
        self.assertEqual(run("check", self.dir).returncode, 0)

    def test_conclusion_gate_via_cli(self):
        run("init", self.dir, "--group", "t")
        bad = run("add", self.dir, "--id", "decision.d", "--type", "decision",
                  "--label", "D", "--source", "s", "--status", "done")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("E_EVIDENCE_MISSING", bad.stderr)
        ok = run("add", self.dir, "--id", "decision.d", "--type", "decision",
                 "--label", "D", "--source", "s", "--status", "done",
                 "--evidence", f"path:README.md|{SHA}|2026-10-29T10:00:00+08:00")
        self.assertEqual(ok.returncode, 0)

    def test_search_json_and_digest(self):
        run("init", self.dir, "--group", "t")
        run("add", self.dir, "--id", "task.hot", "--type", "task", "--label",
            "并发 限流", "--source", "s")
        out = run("search", self.dir, "限流", "--json")
        self.assertEqual(out.returncode, 0)
        hits = json.loads(out.stdout)
        self.assertEqual(hits[0]["id"], "task.hot")
        self.assertEqual(hits[0]["anchor_state"], "none")
        d = run("digest", self.dir, "--max-bytes", "4096")
        self.assertEqual(d.returncode, 0)
        graph_md = os.path.join(self.dir, "graph.md")
        self.assertTrue(os.path.isfile(graph_md))
        self.assertLessEqual(os.path.getsize(graph_md), 4096 + 200)

    def test_audit_exit_1_on_legacy_conflict(self):
        run("init", self.dir, "--group", "t")
        run("add", self.dir, "--id", "task.old", "--type", "task", "--label",
            "old", "--source", "s", "--status", "done")
        self.assertEqual(run("audit", self.dir).returncode, 1)


    def test_missing_graph_is_a_usage_error(self):
        """Contract: missing graph -> exit 2 (usage), not 1 (protocol violation)."""
        missing = os.path.join(self.dir, "does-not-exist")
        cases = [("check", missing), ("audit", missing), ("search", missing, "x"),
                 ("digest", missing), ("export", missing)]
        for args in cases:
            res = run(*args)
            self.assertEqual(res.returncode, 2, (args, res.returncode, res.stderr))


if __name__ == "__main__":
    unittest.main()
