"""`tools/verify_snapshot.py`: verify a graph another tool wrote, without gating it.

The team's own graphs are curated by `kg.py` in `group-kg/v1`, so `amg`'s write gate
does not protect them (decision `gate-boundary-bplus`). The bridge's promise is narrow:
adopt a copy, run the same report the health check runs, and never call a graph
"verified" when it is merely structurally sound. These tests pin that the bridge

1. does not write the source,
2. resolves `path:` evidence against the source graph's directory (an adopted copy in a
   temp dir has no evidence files, so hashing against the copy would report every real
   file as missing — a false alarm),
3. refuses to exit 0 when nothing could be verified, and
4. inherits the coverage/anchoring numbers instead of inventing its own green light.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "verify_snapshot.py")
ENV = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))


def run(*args):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True,
                          text=True, env=ENV)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def legacy_doc(evidence, rev=1):
    return {
        "schema": "group-kg/v1", "group": "t", "session": "", "goal": "g",
        "updatedAt": "2026-10-27T10:00:00+08:00", "rev": rev,
        "nodes": [{"id": "decision.b", "type": "decision", "label": "B",
                   "status": "done", "source": "group:legacy", "note": "",
                   "evidence": evidence,
                   "updatedAt": "2026-10-26T10:00:00+08:00"}],
        "edges": [],
        "changes": [{"at": "2026-10-25T10:00:00+08:00", "by": "x", "op": "add-node",
                     "target": "decision.b", "rev": 1, "note": ""}],
    }


class SnapshotBridgeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-bridge-")
        self.proof = os.path.join(self.dir, "proof.txt")
        with open(self.proof, "wb") as fh:
            fh.write(b"real bytes")
        self.src = os.path.join(self.dir, "graph.json")
        self.write(legacy_doc([{"locator": "path:proof.txt",
                                "content_sha256": sha(self.proof),
                                "captured_at": "2026-10-27T10:00:00+08:00"}]))

    def write(self, doc):
        with open(self.src, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)

    def test_verified_snapshot_passes_and_leaves_source_alone(self):
        before = sha(self.src)
        res = run(self.src)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("verdict: healthy", res.stdout)
        self.assertEqual(sha(self.src), before, "the source must never be written")

    def test_evidence_resolves_against_the_source_directory(self):
        # if it resolved against the adopted temp copy, this would be "missing"
        res = run(self.src, "--json")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        report = json.loads(res.stdout)["graphs"][0]
        self.assertEqual(report["evidence"]["verified"], 1)
        self.assertEqual(report["conclusions"]["verified"], 1)

    def test_tampered_evidence_is_a_problem(self):
        with open(self.proof, "ab") as fh:
            fh.write(b"tampered")
        res = run(self.src)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("do not match", res.stdout)

    def test_nothing_verified_is_exit_three_not_zero(self):
        self.write(legacy_doc(["docs/plan.md", "cmd:pytest -q"]))  # bare strings
        res = run(self.src)
        self.assertEqual(res.returncode, 3, res.stdout + res.stderr)
        self.assertIn("verdict: UNVERIFIED", res.stdout)
        self.assertIn("unanchored", res.stdout)

    def test_allow_unverified_relaxes_only_the_exit_code(self):
        self.write(legacy_doc(["docs/plan.md"]))
        accepted = json.loads(run(self.src, "--json", "--allow-unverified").stdout)
        report = accepted["graphs"][0]
        self.assertEqual(accepted["exit"], 0)
        self.assertEqual(report["verdict"], "unverified")
        self.assertTrue(report["unverified_accepted"])
        self.assertFalse(report["healthy"])

    def test_missing_input_is_usage_error(self):
        res = run(os.path.join(self.dir, "nope.json"))
        self.assertEqual(res.returncode, 2)

    def test_json_carries_the_anchoring_numbers(self):
        self.write(legacy_doc([{"locator": "path:proof.txt",
                                "content_sha256": sha(self.proof),
                                "captured_at": "2026-10-27T10:00:00+08:00"}]))
        doc = json.loads(run(self.src, "--json").stdout)
        report = doc["graphs"][0]
        for key in ("conclusions", "done", "evidence", "verdict", "strict_scope"):
            self.assertIn(key, report)
        self.assertIn("never", report["strict_scope"].replace("promotes nothing", "never promotes"))


if __name__ == "__main__":
    unittest.main()
