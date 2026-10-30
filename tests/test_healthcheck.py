"""`tools/healthcheck.py`: the operator's one-page "is my store okay?".

The report is deliberately split into problems (exit 1) and debt (warnings): a stale
task must not page an operator, a mismatched evidence file must.
"""
import hashlib
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "healthcheck.py")
sys.path.insert(0, os.path.join(ROOT, "tests"))
from helpers import TempGraph  # noqa: E402

ENV = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))


def run(*args):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True,
                          text=True, env=ENV)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class HealthcheckTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.proof = os.path.join(self.g.dir, "proof.txt")
        with open(self.proof, "wb") as fh:
            fh.write(b"proof bytes")
        self.g.m.add_node("decision.claim", "decision", "a claim", source="group:t",
                          status="done",
                          evidence=[{"locator": "path:proof.txt",
                                     "content_sha256": sha(self.proof),
                                     "captured_at": "2026-10-31T00:00:00+08:00"}])

    def tearDown(self):
        self.g.close()

    def test_healthy_graph_exits_zero(self):
        res = run(self.g.dir)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("verdict: healthy", res.stdout)

    def test_tampered_evidence_is_a_problem(self):
        with open(self.proof, "ab") as fh:
            fh.write(b"tampered")
        res = run(self.g.dir)
        self.assertEqual(res.returncode, 1)
        self.assertIn("do not match", res.stdout)

    def test_outside_root_evidence_is_a_problem(self):
        self.g.m.add_node("decision.out", "decision", "outside", source="group:t",
                          status="done",
                          evidence=[{"locator": "path:/etc/hosts",
                                     "content_sha256": "0" * 64,
                                     "captured_at": "2026-10-31T00:00:00+08:00"}])
        res = run(self.g.dir)
        self.assertEqual(res.returncode, 1)
        self.assertIn("leave the graph directory", res.stdout)

    def test_structural_error_is_a_problem(self):
        path = os.path.join(self.g.dir, "graph.json")
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["edges"].append({"from": "decision.claim", "to": "ghost.node",
                             "kind": "relates_to"})
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        res = run(self.g.dir)
        self.assertEqual(res.returncode, 1)
        self.assertIn("structural error(s)", res.stdout)

    def test_audit_conflict_is_debt_not_a_failure_unless_strict(self):
        path = os.path.join(self.g.dir, "graph.json")
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["nodes"].append({"id": "task.stale", "type": "task", "status": "in_progress",
                             "label": "stale", "source": "group:t", "note": "",
                             "evidence": [], "updatedAt": "2026-10-01T00:00:00+08:00",
                             "recorded_at": "2026-10-01T00:00:00+08:00"})
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        self.assertEqual(run(self.g.dir).returncode, 0)
        strict = run(self.g.dir, "--strict")
        self.assertEqual(strict.returncode, 1, strict.stdout + strict.stderr)

    def test_json_report_has_the_documented_shape(self):
        res = run(self.g.dir, "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        for key in ("path", "store", "check", "audit", "evidence", "archive",
                    "problems", "warnings", "healthy"):
            self.assertIn(key, report)
        self.assertEqual(report["store"]["nodes"], 1)

    def test_windows_code_page_does_not_swallow_the_verdict(self):
        # v0.23.0 printed "✗"/"—", which raised UnicodeEncodeError on a cp1252 console
        # and silently dropped the problems/verdict lines while exiting 1.
        with open(self.proof, "ab") as fh:
            fh.write(b"tampered")
        res = subprocess.run([sys.executable, TOOL, self.g.dir], capture_output=True,
                             text=True, env=dict(ENV, PYTHONIOENCODING="cp1252"))
        self.assertEqual(res.returncode, 1)
        self.assertIn("do not match", res.stdout)
        self.assertIn("verdict: NEEDS ATTENTION", res.stdout)

    def test_missing_graph_is_usage_error(self):
        self.assertEqual(run(os.path.join(self.g.dir, "nope")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
