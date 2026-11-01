"""`amg check` verifies shape; `amg verify-evidence` verifies truth. They must not merge.

Measured on v0.38.1 before this file existed: a node declaring
`content_sha256 = 000…000` for a file that hashes to something else gets
`✓ check passed` from `amg check --strict`, and `E_EVIDENCE_MISMATCH` from
`amg verify-evidence`. Both are correct answers to different questions.

Why this is pinned rather than fixed: `check`'s job is "is this document well-formed".
Making it verify digests would be a different command with a different cost (it would
have to read every cited file), and would silently change what 58 decision pages and
the CI gate mean. What went wrong was never the code — it was that four tools were
called "check" and all their greens looked alike.

So the assertion is about the *distinction*, in both directions:

* test 1 fails if `check` starts verifying digests (the distinction collapses upward)
* test 2 fails if `verify-evidence` starts trusting declared digests (collapses downward)

Either mutation makes the two commands agree, and agreeing is exactly the failure.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

from helpers import write_fixture  # noqa: E402  (needs the src path inserted above)

CLI = [sys.executable, "-m", "amg.cli"]
FORGED = "0" * 64


def env():
    e = dict(os.environ)
    e["PYTHONPATH"] = os.path.join(ROOT, "src") + os.pathsep + e.get("PYTHONPATH", "")
    return e


def make_graph(forged=True):
    """A graph whose `done` node cites a real file but declares the wrong digest.

    Written straight to JSON on purpose: the write path refuses a forged digest
    (#39, `E_EVIDENCE_VERIFY_FAILED`), so the only way such a node exists is that
    someone edited the document. That is the situation `check` is being asked about.
    """
    root = tempfile.mkdtemp(prefix="amg-shapeonly-")
    proof = os.path.join(root, "proof.md")
    # v0.38.2 shipped this test with a bare `open(..., "w")` and a hard-coded
    # `sha256(b"the real bytes\n")`. On windows-latest the file holds `\r\n`, the digest
    # did not match, and the control case failed — the same mistake v0.37.4 fixed, made
    # again because the fix lived in one test file rather than in a shared helper.
    # `write_fixture` pins the newline and returns the digest it actually wrote.
    real = write_fixture(proof, "the real bytes\n")
    node = {
        "id": "claim", "type": "artifact", "label": "a claim", "status": "done",
        "owner": "t", "source": "cmd:test", "note": "",
        "evidence": [{
            "locator": "path:proof.md",
            "content_sha256": FORGED if forged else real,
            "captured_at": "2026-11-01T10:00:00+08:00",
        }],
    }
    doc = {"schema": "amg/v1", "group": "t", "rev": 1,
           "nodes": [node], "edges": [], "changes": []}
    with open(os.path.join(root, "graph.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    return root


def run(*args):
    return subprocess.run(CLI + list(args), capture_output=True, text=True,
                          env=env(), cwd=ROOT, timeout=60)


class CheckIsShapeOnlyTest(unittest.TestCase):
    def test_a_forged_digest_passes_check_strict(self):
        """MUTATION GUARD: wire verify_evidence into check and this fails."""
        root = make_graph(forged=True)
        res = run("check", root, "--strict")
        self.assertEqual(res.returncode, 0,
                         "check must not fail on a forged digest; it does not verify digests.\n"
                         + res.stdout + res.stderr)
        self.assertIn("check passed", res.stdout)

    def test_the_same_graph_is_caught_by_verify_evidence(self):
        """MUTATION GUARD: let verify-evidence trust the declared digest and this fails."""
        root = make_graph(forged=True)
        res = run("verify-evidence", root)
        self.assertNotEqual(res.returncode, 0,
                            "a forged digest must not pass the truth check\n"
                            + res.stdout + res.stderr)
        blob = res.stdout + res.stderr
        self.assertTrue("mismatch" in blob.lower() or "E_EVIDENCE_MISMATCH" in blob,
                        f"expected a mismatch verdict, got: {blob.strip()[:300]}")

    def test_with_a_correct_digest_the_two_commands_agree(self):
        """The control: the divergence above is caused by the digest, not by the fixture."""
        root = make_graph(forged=False)
        check = run("check", root, "--strict")
        verify = run("verify-evidence", root)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_the_two_commands_disagree_on_the_same_graph(self):
        """The whole point, stated once and directly: same graph, different verdicts."""
        root = make_graph(forged=True)
        check = run("check", root, "--strict")
        verify = run("verify-evidence", root)
        self.assertNotEqual(
            (check.returncode == 0), (verify.returncode == 0),
            "check and verify-evidence returned the same verdict on a forged digest — "
            "either check now verifies truth, or verify-evidence stopped doing so. "
            "Decision #58 requires them to stay different questions.",
        )


if __name__ == "__main__":
    unittest.main()
