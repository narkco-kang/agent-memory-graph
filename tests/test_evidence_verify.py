"""`amg verify-evidence`: the observation mechanism for declared evidence hashes.

`issue.mem-arch-evidence-sha-forgeable` reproduced an attack: any 64-hex string passed
the shape gate, so a fabricated `content_sha256` produced `anchor_state: "present"` and
won the retrieval sort key. v0.20.0 answers with disclosure plus an explicit verifier —
these tests pin both halves, including the limitation that stays.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import gate  # noqa: E402

CLI = [sys.executable, "-m", "amg.cli"]
ENV = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))


def cli(*args, cwd=None):
    return subprocess.run(CLI + list(args), capture_output=True, text=True,
                          env=ENV, cwd=cwd or ROOT)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VerifyEvidenceUnitTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-evidence-")
        self.path = os.path.join(self.dir, "note.txt")
        with open(self.path, "wb") as fh:
            fh.write(b"the bytes")

    def test_path_locator_matching_bytes_is_ok(self):
        rows = gate.verify_evidence(
            [{"locator": "path:note.txt", "content_sha256": sha(b"the bytes")}], self.dir)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[0]["actual"], sha(b"the bytes"))

    def test_path_locator_with_other_bytes_is_a_mismatch(self):
        rows = gate.verify_evidence(
            [{"locator": "path:note.txt", "content_sha256": "0" * 64}], self.dir)
        self.assertEqual(rows[0]["status"], "mismatch")

    def test_absolute_path_outside_the_root_is_not_read(self):
        outside = tempfile.mkdtemp(prefix="amg-outside-")
        path = os.path.join(outside, "secret.txt")
        with open(path, "wb") as fh:
            fh.write(b"outside bytes")
        rows = gate.verify_evidence([{"locator": "path:" + path,
                                      "content_sha256": sha(b"outside bytes")}], self.dir)
        self.assertEqual(rows[0]["status"], "outside_root")
        self.assertIsNone(rows[0]["actual"], "an outside file must never be hashed")

    def test_traversal_and_symlink_escape_are_outside_root(self):
        outside = tempfile.mkdtemp(prefix="amg-outside-")
        with open(os.path.join(outside, "x.txt"), "wb") as fh:
            fh.write(b"x")
        link = os.path.join(self.dir, "link.txt")
        try:
            os.symlink(os.path.join(outside, "x.txt"), link)
        except (OSError, NotImplementedError):  # pragma: no cover - sandboxed hosts
            link = None
        locators = [{"locator": "path:../" + os.path.basename(outside) + "/x.txt",
                     "content_sha256": sha(b"x")}]
        if link:
            locators.append({"locator": "path:link.txt", "content_sha256": sha(b"x")})
        rows = gate.verify_evidence(locators, self.dir)
        self.assertEqual([r["status"] for r in rows], ["outside_root"] * len(locators))

    def test_directory_is_not_a_file(self):
        os.makedirs(os.path.join(self.dir, "subdir"), exist_ok=True)
        rows = gate.verify_evidence([{"locator": "path:subdir",
                                      "content_sha256": sha(b"")}], self.dir)
        self.assertEqual(rows[0]["status"], "not_a_file")

    def test_unreadable_file_is_reported_not_crashed(self):
        path = os.path.join(self.dir, "locked.txt")
        with open(path, "wb") as fh:
            fh.write(b"locked")
        os.chmod(path, 0o000)
        try:
            if os.access(path, os.R_OK):  # running as root: cannot be tested here
                self.skipTest("permissions are not enforced for this user")
            rows = gate.verify_evidence([{"locator": "path:locked.txt",
                                          "content_sha256": sha(b"locked")}], self.dir)
        finally:
            os.chmod(path, 0o600)
        self.assertEqual(rows[0]["status"], "unreadable")

    def test_missing_and_unverifiable_are_never_ok(self):
        rows = gate.verify_evidence([{"locator": "path:absent.txt",
                                      "content_sha256": "0" * 64},
                                     {"locator": "url:https://example.test/x",
                                      "content_sha256": "1" * 64},
                                     {"locator": "cmd:echo hi",
                                      "content_sha256": "2" * 64},
                                     {"locator": "sha256:" + "3" * 64,
                                      "content_sha256": "3" * 64}], self.dir)
        self.assertEqual([r["status"] for r in rows],
                         ["missing", "unverifiable", "unverifiable", "unverifiable"])

    def test_absolute_path_inside_the_root_is_allowed(self):
        rows = gate.verify_evidence([{"locator": "path:" + self.path,
                                      "content_sha256": sha(b"the bytes")}], self.dir)
        self.assertEqual(rows[0]["status"], "ok")


class VerifyEvidenceCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-evidence-cli-")
        with open(os.path.join(self.dir, "note.txt"), "wb") as fh:
            fh.write(b"the bytes")
        self.assertEqual(cli("init", self.dir, "--group", "t").returncode, 0)

    def add(self, node_id, locator, digest, status="done"):
        res = cli("add", self.dir, "--id", node_id, "--type", "decision",
                  "--label", "a claim", "--source", "group:t", "--status", status,
                  "--evidence", f"{locator}|{digest}|2026-10-31T00:00:00+08:00")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_matching_evidence_exits_zero(self):
        self.add("decision.ok", "path:note.txt", sha(b"the bytes"))
        res = cli("verify-evidence", self.dir, "--json")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        report = json.loads(res.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["counts"], {"ok": 1})

    def test_fabricated_sha_exits_one_and_names_the_item(self):
        self.add("decision.fake", "path:note.txt", "0" * 64)
        res = cli("verify-evidence", self.dir)
        self.assertEqual(res.returncode, 1)
        self.assertIn("E_EVIDENCE_MISMATCH", res.stderr)
        report = json.loads(cli("verify-evidence", self.dir, "--json").stdout)
        self.assertEqual(report["mismatched"][0]["node"], "decision.fake")
        self.assertEqual(report["mismatched"][0]["actual"], sha(b"the bytes"))

    def test_missing_path_reports_but_strict_fails(self):
        self.add("decision.gone", "path:absent.txt", "0" * 64)
        self.assertEqual(cli("verify-evidence", self.dir).returncode, 0)
        strict = cli("verify-evidence", self.dir, "--strict", "--json")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("E_EVIDENCE_UNVERIFIED", strict.stderr)
        report = json.loads(strict.stdout)
        self.assertFalse(report["ok"], "a failing strict run must not report ok=true")
        self.assertFalse(report["all_verified"])

    def test_strict_rejects_unverifiable_evidence(self):
        self.add("decision.url", "url:https://example.test/report", "1" * 64)
        self.assertEqual(cli("verify-evidence", self.dir).returncode, 0)
        strict = cli("verify-evidence", self.dir, "--strict")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("E_EVIDENCE_UNVERIFIED", strict.stderr)
        report = json.loads(cli("verify-evidence", self.dir, "--strict", "--json").stdout)
        self.assertFalse(report["ok"])

    def test_outside_root_exits_one_even_without_strict(self):
        res = cli("add", self.dir, "--id", "decision.out", "--type", "decision",
                  "--label", "a claim", "--source", "group:t", "--status", "done",
                  "--evidence", f"path:/etc/hosts|{'0' * 64}|2026-10-31T00:00:00+08:00")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        res = cli("verify-evidence", self.dir, "--json")
        self.assertEqual(res.returncode, 1)
        self.assertIn("E_EVIDENCE_OUTSIDE_ROOT", res.stderr)
        report = json.loads(res.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["outside_root"][0]["locator"], "path:/etc/hosts")

    def test_empty_graph_is_not_a_strict_pass(self):
        self.assertEqual(cli("verify-evidence", self.dir).returncode, 0)
        strict = cli("verify-evidence", self.dir, "--strict", "--json")
        self.assertEqual(strict.returncode, 1)
        report = json.loads(strict.stdout)
        self.assertEqual(report["checked"], 0)
        self.assertFalse(report["ok"])
        self.assertFalse(report["all_verified"])

    def test_unverifiable_is_counted_but_never_passes_silently(self):
        self.add("decision.url", "url:https://example.test/report", "1" * 64)
        res = cli("verify-evidence", self.dir, "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        self.assertEqual(report["counts"], {"unverifiable": 1})
        self.assertEqual(report["mismatched"], [])

    def test_id_filter_checks_one_node(self):
        self.add("decision.ok", "path:note.txt", sha(b"the bytes"))
        self.add("decision.fake", "path:note.txt", "0" * 64)
        res = cli("verify-evidence", self.dir, "--id", "decision.ok", "--json")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(json.loads(res.stdout)["counts"], {"ok": 1})


class DisclosedLimitationTests(unittest.TestCase):
    """The part v0.20.0 does NOT fix, kept as an executable statement."""

    def test_shape_gate_still_accepts_a_fabricated_hash(self):
        accepted = gate.validate_evidence(
            [{"locator": "path:nope.txt", "content_sha256": "f" * 64,
              "captured_at": "2026-10-31T00:00:00+08:00"}], graph_rev=1)
        self.assertEqual(accepted[0]["content_sha256"], "f" * 64)

    def test_search_still_calls_declared_evidence_present(self):
        from amg import retrieval
        doc = {"nodes": [{"id": "decision.fake", "type": "decision",
                          "status": "done", "label": "zebra", "note": "",
                          "source": "t",
                          "evidence": [{"locator": "path:gone.txt",
                                        "content_sha256": "f" * 64,
                                        "captured_at": "2026-10-31T00:00:00+08:00",
                                        "graph_rev": 1}]}],
               "edges": [], "changes": []}
        hits = retrieval.search(doc, "zebra", k=1)
        self.assertEqual(hits[0]["anchor_state"], "present")


if __name__ == "__main__":
    unittest.main()
