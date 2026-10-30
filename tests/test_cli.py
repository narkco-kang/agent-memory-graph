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
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=cwd or ROOT)


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

    def test_audit_stale_days_flag_and_env(self):
        self.assertEqual(run("init", self.dir, "--group", "t").returncode, 0)
        self.assertEqual(run("add", self.dir, "--id", "task.old", "--type", "task",
                             "--label", "old", "--source", "s",
                             "--status", "in_progress").returncode, 0)
        # Age it in place: the CLI has no flag for that, and sleeping 10 days is not
        # an option in a test suite.
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        subprocess.run([sys.executable, "-c", f"""
import datetime, json, sys
path = {os.path.join(self.dir, "graph.json")!r}
with open(path, encoding="utf-8") as fh:
    doc = json.load(fh)
old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)).isoformat()
for node in doc["nodes"]:
    if node["id"] == "task.old":
        node["updatedAt"] = old
with open(path, "w", encoding="utf-8") as fh:
    json.dump(doc, fh)
"""], check=True, env=env)
        self.assertEqual(run("audit", self.dir).returncode, 1)
        self.assertEqual(run("audit", self.dir, "--stale-days", "30").returncode, 0)
        relaxed = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"),
                       AMG_STALE_DAYS="30")
        res = subprocess.run([sys.executable, "-m", "amg.cli", "audit", self.dir],
                             capture_output=True, text=True, env=relaxed)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

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


class SupersedeCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-sup-")

    def _seed(self):
        run("init", self.dir, "--group", "t")
        ev = f"path:README.md|{SHA}|2026-10-30T09:00:00+08:00"
        run("add", self.dir, "--id", "decision.a", "--type", "decision", "--label", "A",
            "--source", "s", "--status", "done", "--evidence", ev)
        run("add", self.dir, "--id", "decision.b", "--type", "decision", "--label", "B",
            "--source", "s", "--status", "done", "--evidence", ev)

    def test_supersede_keeps_old_node(self):
        self._seed()
        res = run("supersede", self.dir, "decision.a", "decision.b", "--note", "b replaces a")
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(self.dir, "graph.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        old = [n for n in doc["nodes"] if n["id"] == "decision.a"][0]
        self.assertEqual(old["status"], "superseded")
        self.assertTrue(old["valid_until"] and old["superseded_at"])
        self.assertEqual(len(doc["nodes"]), 2)

    def test_supersede_exit_codes(self):
        self._seed()
        self.assertEqual(run("supersede", self.dir, "decision.a", "ghost", "--note", "x").returncode, 1)
        self.assertEqual(run("supersede", self.dir, "decision.a", "decision.a", "--note", "x").returncode, 2)
