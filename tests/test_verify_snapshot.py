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

    def test_evidence_root_is_explicit_and_reported(self):
        # Hermes: the same file answers 0/240 under graphs/, 113/240 under the workspace
        # root — so the base must be an input and must appear in the report.
        sub = os.path.join(self.dir, "graphs")
        os.makedirs(sub)
        moved = os.path.join(sub, "graph.json")
        with open(moved, "w", encoding="utf-8") as fh:
            json.dump(legacy_doc([{"locator": "path:proof.txt",
                                   "content_sha256": sha(self.proof),
                                   "captured_at": "2026-10-27T10:00:00+08:00"}]), fh)
        wrong = json.loads(run(moved, "--json").stdout)["graphs"][0]
        self.assertEqual(wrong["snapshot"]["resolve_root"], sub)
        self.assertEqual(wrong["snapshot"]["exists_rate"], 0.0)   # wrong base
        right = json.loads(run(moved, "--json", "--evidence-root", self.dir).stdout)
        graph = right["graphs"][0]
        self.assertEqual(graph["snapshot"]["resolve_root"], self.dir)
        self.assertEqual(graph["snapshot"]["exists_rate"], 1.0)
        self.assertEqual(right["exit"], 0)

    def test_legacy_hash_string_is_verified_not_guessed(self):
        digest = sha(self.proof)
        self.write(legacy_doc([f"path:proof.txt#sha256:{digest}", "docs/plan.md"]))
        res = run(self.src, "--json")
        report = json.loads(res.stdout)["graphs"][0]
        legacy = report["snapshot"]["legacy_strings"]
        self.assertEqual(legacy["checked"], 1)
        self.assertEqual(legacy["verified"], 1)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("1 with #sha256, 1 verified", run(self.src).stdout)

    def test_legacy_hash_mismatch_and_malformed_are_reported(self):
        self.write(legacy_doc([f"path:proof.txt#sha256:{'a' * 64}",
                               "path:proof.txt#sha256:nothex"]))
        report = json.loads(run(self.src, "--json").stdout)["graphs"][0]
        legacy = report["snapshot"]["legacy_strings"]
        self.assertEqual(len(legacy["mismatched"]), 1)
        self.assertEqual(len(legacy["malformed"]), 1)
        text = run(self.src).stdout
        self.assertIn("mismatched", text)

    def test_legacy_mismatch_is_a_problem_not_an_unverified_claim(self):
        # Glm仔 N4: a forged legacy sha exited 3 (same as "never claimed"), not 1
        self.write(legacy_doc([f"path:proof.txt#sha256:{'a' * 64}"]))
        res = run(self.src)          # no --strict: the violation itself must fail the run
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("does not match the file", res.stdout)
        self.assertIn("NEEDS ATTENTION", res.stdout)

    def test_done_and_conclusions_use_the_same_ruler(self):
        # Glm仔 N6: one node must not be "verified" above and "no evidence" below
        digest = sha(self.proof)
        nodes = [{"id": f"decision.d{i}", "type": "decision", "label": f"D{i}",
                  "status": "done", "source": "group:legacy", "note": "",
                  "evidence": [f"path:proof.txt#sha256:{digest}"],
                  "updatedAt": "2026-10-26T10:00:00+08:00"} for i in range(3)]
        doc = legacy_doc([])
        doc["nodes"] = nodes
        self.write(doc)
        out = run(self.src).stdout
        self.assertIn("conclusions: 3/3 verified (100%)", out)
        self.assertIn("done nodes: 3 total, 0 without evidence", out)

    def test_legacy_observations_count_toward_anchoring_not_just_the_verdict(self):
        # Glm仔 N3: the bridge printed "0/20 verified, 20 unanchored" and then healthy.
        # The numbers were the bug: a verified legacy string anchors the conclusion it
        # belongs to, so this graph is 1/20 (5%) anchored, warns, and fails --strict.
        nodes = [{"id": f"decision.d{i}", "type": "decision", "label": f"D{i}",
                  "status": "done", "source": "group:legacy", "note": "",
                  "evidence": ["cmd:pytest -q"],
                  "updatedAt": "2026-10-26T10:00:00+08:00"} for i in range(19)]
        nodes.append({"id": "decision.real", "type": "decision", "label": "real",
                      "status": "done", "source": "group:legacy", "note": "",
                      "evidence": [f"path:proof.txt#sha256:{sha(self.proof)}"],
                      "updatedAt": "2026-10-26T10:00:00+08:00"})
        doc = legacy_doc([])
        doc["nodes"] = nodes
        self.write(doc)
        res = run(self.src, "--json")
        report = json.loads(res.stdout)["graphs"][0]
        self.assertEqual(report["snapshot"]["observed_verified"], 1)
        self.assertEqual(report["conclusions"]["total"], 20)
        self.assertEqual(report["conclusions"]["verified"], 1)
        self.assertAlmostEqual(report["conclusions"]["anchor_coverage"], 0.05)
        self.assertEqual(report["conclusions"]["unobservable"], 19)
        self.assertTrue(any("cannot be observed" in w for w in report["warnings"]))
        # the bridge verifies, it does not own the store: 95% unanchored is not healthy
        self.assertEqual(report["verdict"], "partially_verified")
        self.assertEqual(run(self.src).returncode, 3)

    def test_strict_fails_on_debt_but_never_passes_a_broken_check(self):
        self.write(legacy_doc([{"locator": "path:proof.txt",
                                "content_sha256": sha(self.proof),
                                "captured_at": "2026-10-27T10:00:00+08:00"}]))
        self.assertEqual(run(self.src).returncode, 0)          # fully anchored
        with open(self.proof, "ab") as fh:
            fh.write(b"tampered")
        strict = run(self.src, "--strict")
        self.assertEqual(strict.returncode, 1, strict.stdout + strict.stderr)

    def test_zero_anchored_conclusions_are_partially_verified(self):
        # something verified, nothing anchored: the false green N3 actually described
        doc = legacy_doc(["cmd:pytest -q"])
        doc["nodes"].append({"id": "issue.note", "type": "issue", "label": "n",
                             "status": "done", "source": "group:legacy", "note": "",
                             "evidence": [f"path:proof.txt#sha256:{sha(self.proof)}"],
                             "updatedAt": "2026-10-26T10:00:00+08:00"})
        doc["nodes"][0]["evidence"] = []      # the conclusion carries nothing
        self.write(doc)
        res = run(self.src, "--json")
        report = json.loads(res.stdout)["graphs"][0]
        self.assertEqual(report["conclusions"]["anchor_coverage"], 0.0)
        self.assertEqual(report["verdict"], "partially_verified")
        self.assertEqual(res.returncode, 3, res.stdout + res.stderr)

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
