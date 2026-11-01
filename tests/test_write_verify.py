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


class LegacyEvidenceRepairTest(unittest.TestCase):
    """`status` must be able to run on a node whose evidence is bare strings.

    v0.38.0 shipped a crash: `set_status` computed the node's grade with
    `[e.get("grade", 5) for e in evidence]`, assuming every entry is a dict. A legacy node
    holding `["docs/x.md"]` raised `'str' object has no attribute 'get'` — so `status`,
    the one verb that can repair such a node, died on exactly the data it exists to fix.

    The tests below pin the repair and, just as importantly, pin what the repair cannot do.
    `--evidence` on `status` APPENDS. There is no verb in this schema that replaces or
    removes an evidence entry, so a legacy bare string stays on the node forever; the
    honest paths are to supersede the node or to record it in the baseline. Anyone reading
    "status can repair a node" should read these tests first.
    """

    def setUp(self):
        self.root = setup_root()
        # `TempGraph` in tests/helpers.py sets the CLASS attribute `Memory.evidence_root`
        # and never restores it, so whichever test file runs first decides the evidence
        # base for every test after it. Pin it here: these tests cite a file inside their
        # own throwaway root and must resolve against that root, not the repo.
        self._saved_evidence_root = Memory.evidence_root
        Memory.evidence_root = None

    def tearDown(self):
        Memory.evidence_root = self._saved_evidence_root

    def legacy_node(self, evidence):
        with open(os.path.join(self.root, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "schema": "amg/v1", "group": "t",
                "nodes": [{"id": "legacy", "type": "artifact", "label": "x", "status": "open",
                           "owner": "", "source": "cmd:t", "note": "", "evidence": evidence}],
                "edges": [], "changes": [],
            }, fh, ensure_ascii=False)
        return Memory.open(self.root)

    def test_status_survives_a_bare_string_evidence_entry(self):
        """MUTATION GUARD: drop `if isinstance(e, dict)` from the grade computation and this fails."""
        mem = self.legacy_node(["docs/x.md"])
        result = mem.set_status("legacy", "done", note="repair attempt",
                                evidence=[item("path:proof.md", real_digest(self.root))])
        self.assertEqual(result["to"], "done")
        node = [n for n in mem._doc["nodes"] if n["id"] == "legacy"][0]
        self.assertIn("docs/x.md", node["evidence"],
                      "the bare string must still be visible; nothing here may delete evidence")

    def test_a_node_of_only_bare_strings_can_still_change_status(self):
        """MUTATION GUARD: same, exercised with no dict entries at all."""
        mem = self.legacy_node(["docs/a.md", "docs/b.md"])
        mem.set_status("legacy", "in_progress", note="start")
        node = [n for n in mem._doc["nodes"] if n["id"] == "legacy"][0]
        self.assertEqual(node["status"], "in_progress")
        self.assertIsNone(node.get("evidence_grade"),
                          "no dict entry carries a grade, so the grade is unknown, not 5")

    def test_status_appends_and_cannot_replace(self):
        """The limitation, stated as a test so it cannot be discovered by surprise."""
        good = real_digest(self.root)
        mem = self.legacy_node([])
        mem.set_status("legacy", "done", note="first", evidence=[item("path:proof.md", good)])
        mem.set_status("legacy", "done", note="second", evidence=[item("path:proof.md", good)])
        node = [n for n in mem._doc["nodes"] if n["id"] == "legacy"][0]
        self.assertEqual(len(node["evidence"]), 2,
                         "--evidence on status appends; calling it twice adds twice")
        stamps = [(e["locator"], e["content_sha256"]) for e in node["evidence"]]
        self.assertEqual(stamps[0], stamps[1],
                         "and it does not deduplicate — the same entry twice is the caller's doing")
        self.assertNotEqual(node["evidence"][0]["graph_rev"], node["evidence"][1]["graph_rev"],
                            "each append is stamped with the rev it was written at")

    def test_supersede_does_not_clean_the_old_node(self):
        """The reason supersede is not a repair path: the debt stays on the graph."""
        mem = self.legacy_node(["docs/x.md"])
        mem.add_node(id="clean", type="artifact", label="x", source="cmd:t", status="done",
                     evidence=[item("path:proof.md", real_digest(self.root))])
        mem.supersede("legacy", "clean", note="evidence corrected")
        doc = mem._doc
        old = [n for n in doc["nodes"] if n["id"] == "legacy"][0]
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["evidence"], ["docs/x.md"],
                         "supersede keeps the old node's evidence verbatim — by design")
        from amg.protocol import check
        report = check(doc, strict=True)
        self.assertTrue(any("legacy" in e and "IR-4" in e for e in report["errors"]),
                        "so the IR-4 error survives the supersede; the baseline is what files it")

    def test_re_adding_the_same_id_is_refused(self):
        """The third road that is closed: you cannot overwrite a node by adding it again."""
        mem = self.legacy_node(["docs/x.md"])
        with self.assertRaises(ProtocolError) as ctx:
            mem.add_node(id="legacy", type="artifact", label="x", source="cmd:t", status="done",
                         evidence=[item("path:proof.md", real_digest(self.root))])
        self.assertEqual(ctx.exception.code, "E_DUP_ID")
