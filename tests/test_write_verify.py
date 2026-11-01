"""Write-time evidence verification: a digest is proved, not merely well-formed.

Measured before this guard: `validate_evidence` accepted any 64 lowercase hex string,
so `aaaa…` was stored as a `done` node. The forgery surfaced only on the READ side,
where `audit --verify` and `search` called it `missing` — but by then the memory was
already written and retrievable. A claim that is checked only when someone reads it
has already been trusted by everyone who did not.

Rules enforced at write time (each is a way the check could otherwise be useless):

* the declared digest must equal the digest of the bytes;
* a `path:` locator must stay inside the evidence root — refusing to skip an escaping
  locator is what stops the check from becoming its own bypass;
* the file must exist; a missing file is a failed claim, not an unverifiable one.
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg.errors import ProtocolError  # noqa: E402
from amg.gate import verify_evidence_on_write  # noqa: E402
from amg.memory import Memory  # noqa: E402

CLI = [sys.executable, "-m", "amg.cli"]
FORGED = "a" * 64


def setup_root():
    root = tempfile.mkdtemp(prefix="amg-wv-")
    with open(os.path.join(root, "proof.md"), "w", encoding="utf-8") as fh:
        fh.write("proof content\n")
    with open(os.path.join(root, "graph.json"), "w", encoding="utf-8") as fh:
        json.dump({"schema": "amg/v1", "group": "t", "nodes": [], "edges": [], "changes": []}, fh)
    return root


def item(locator, digest, captured="2026-11-01T00:00:00Z"):
    return {"locator": locator, "content_sha256": digest, "captured_at": captured}


def real_digest(root, name="proof.md"):
    return hashlib.sha256(pathlib.Path(os.path.join(root, name)).read_bytes()).hexdigest()


class GateLevelTest(unittest.TestCase):
    def setUp(self):
        self.root = setup_root()

    def test_a_forged_digest_is_refused(self):
        with self.assertRaises(ProtocolError) as ctx:
            verify_evidence_on_write([item("path:proof.md", FORGED)], self.root, "n1")
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_VERIFY_FAILED")
        self.assertIn("hashes to", str(ctx.exception))

    def test_the_real_digest_passes(self):
        verify_evidence_on_write([item("path:proof.md", real_digest(self.root))], self.root)

    def test_a_missing_file_is_refused(self):
        with self.assertRaises(ProtocolError) as ctx:
            verify_evidence_on_write([item("path:gone.md", FORGED)], self.root)
        self.assertIn("does not exist", str(ctx.exception))

    def test_an_escaping_locator_is_refused_not_skipped(self):
        """Skipping it would make the check itself the bypass."""
        with self.assertRaises(ProtocolError) as ctx:
            verify_evidence_on_write([item("path:../outside.md", real_digest(self.root))], self.root)
        self.assertIn("escapes", str(ctx.exception))

    def test_non_path_locators_are_allowed_but_do_not_count(self):
        verify_evidence_on_write([item("cmd:python3 -m amg check", FORGED)], self.root)


class WritePathTest(unittest.TestCase):
    """The guard has to be on the write, not only callable."""

    def setUp(self):
        self.root = setup_root()
        # The evidence base is a property of the graph, not of the process; say it
        # explicitly so a leftover class attribute from another test cannot leak in.
        Memory.evidence_root = self.root
        self.mem = Memory.open(self.root)

    def tearDown(self):
        Memory.evidence_root = None

    def test_add_node_done_with_a_forged_digest_is_refused(self):
        """MUTATION GUARD: drop the add_node call and this fails."""
        with self.assertRaises(ProtocolError) as ctx:
            self.mem.add_node(id="f", type="artifact", label="x", source="t", status="done",
                              evidence=[item("path:proof.md", FORGED)])
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_VERIFY_FAILED")
        self.assertNotIn("f", [n["id"] for n in Memory.open(self.root).doc["nodes"]],
                         "a refused write must not land")

    def test_add_node_done_with_the_real_digest_is_accepted(self):
        node = self.mem.add_node(id="ok", type="artifact", label="x", source="t", status="done",
                                 evidence=[item("path:proof.md", real_digest(self.root))])
        self.assertEqual(node["status"], "done")

    def test_open_nodes_are_not_gated(self):
        """Evidence is a constraint on concluding, not on recording."""
        self.mem.add_node(id="open1", type="artifact", label="x", source="t", status="open",
                          evidence=[item("path:proof.md", FORGED)])

    def test_status_to_done_with_a_forged_digest_is_refused(self):
        """MUTATION GUARD: drop the set_status call and this fails."""
        self.mem.add_node(id="s1", type="artifact", label="x", source="t", status="open",
                          evidence=[item("path:proof.md", FORGED)], conclusion=False)
        with self.assertRaises(ProtocolError) as ctx:
            self.mem.set_status("s1", "done", note="promoting")
        self.assertEqual(ctx.exception.code, "E_EVIDENCE_VERIFY_FAILED")
        self.assertEqual(Memory.open(self.root)._node(
            Memory.open(self.root).doc, "s1")["status"], "open")


class CliExitCodeTest(unittest.TestCase):
    def test_the_new_code_is_classified(self):
        """An unclassified code raises at exit; the exit-code table must name it."""
        root = setup_root()
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        res = subprocess.run(
            CLI + ["add", root, "--id", "f", "--type", "artifact", "--label", "x",
                   "--source", "t", "--status", "done",
                   "--evidence", f"path:proof.md|{FORGED}|2026-11-01T00:00:00Z"],
            capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT, timeout=60)
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn("E_EVIDENCE_VERIFY_FAILED", res.stderr)


if __name__ == "__main__":
    unittest.main()
