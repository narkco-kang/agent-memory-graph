"""Fingerprints: what they detect, what they cannot, and what they never write."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory, ProtocolError  # noqa: E402
from amg import fingerprint as fp_mod  # noqa: E402

SHA = "e" * 64
EVIDENCE = [{"locator": "path:README.md", "content_sha256": SHA,
             "captured_at": "2026-10-30T12:00:00+08:00"}]


def raw(path):
    with open(os.path.join(path, "graph.json"), "rb") as fh:
        return fh.read()


def cli(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    return subprocess.run([sys.executable, "-m", "amg.cli", *args], capture_output=True,
                          text=True, encoding="utf-8", env=env, cwd=ROOT, timeout=60)


class FingerprintShapeTests(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(tempfile.mkdtemp(prefix="amg-fp-"), "mem")
        self.m = Memory.init(self.dir, group="t")
        self.m.add_node(id="task.a", type="task", label="alpha", source="test", note="n", by="test")

    def test_fingerprint_is_stable_and_order_independent(self):
        first = self.m.fingerprint()
        self.assertEqual(len(first["state_sha256"]), 64)
        self.assertEqual(len(first["history_sha256"]), 64)
        shuffled = json.loads(json.dumps(self.m.doc))
        shuffled["nodes"].reverse()
        shuffled["edges"].reverse()
        self.assertEqual(fp_mod.state_digest(shuffled), first["state_sha256"])
        self.assertEqual(self.m.fingerprint(), first, "fingerprint must be deterministic")

    def test_state_and_history_answer_different_questions(self):
        doc = json.loads(json.dumps(self.m.doc))
        before = self.m.fingerprint()
        doc["nodes"][0]["label"] = "edited directly"
        edited = fp_mod.fingerprint(doc)
        self.assertNotEqual(edited["state_sha256"], before["state_sha256"])
        self.assertEqual(edited["history_sha256"], before["history_sha256"])
        doc2 = json.loads(json.dumps(self.m.doc))
        doc2["changes"].append({"at": "2026-10-30T12:00:00+08:00", "by": "test",
                                "op": "fake", "target": "task.a", "rev": 99, "note": "n"})
        appended = fp_mod.fingerprint(doc2)
        self.assertEqual(appended["state_sha256"], before["state_sha256"])
        self.assertNotEqual(appended["history_sha256"], before["history_sha256"])

    def test_fingerprint_writes_nothing(self):
        before = raw(self.dir)
        current = self.m.fingerprint()
        self.m.verify_fingerprint({"state_sha256": current["state_sha256"]})
        self.assertEqual(raw(self.dir), before, "fingerprint/verify must not write")

    def test_verify_rejects_an_empty_expectation(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.verify_fingerprint({})
        self.assertEqual(ctx.exception.code, "E_NO_EXPECTATION")
        with self.assertRaises(ProtocolError) as ctx:
            self.m.verify_fingerprint("nope")
        self.assertEqual(ctx.exception.code, "E_BAD_FINGERPRINT")


class FingerprintCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(tempfile.mkdtemp(prefix="amg-fpcli-"), "mem")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        subprocess.run([sys.executable, "-m", "amg.cli", "init", self.dir, "--group", "t"],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
        m = Memory.open(self.dir)
        m.add_node(id="task.a", type="task", label="alpha", source="test", note="n", by="test")
        self.fp_file = os.path.join(tempfile.mkdtemp(prefix="amg-fpjson-"), "fp.json")

    def test_round_trip_then_detect_a_silent_edit(self):
        res = cli("fingerprint", self.dir, "--out", self.fp_file)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(cli("verify", self.dir, "--expect", self.fp_file).returncode, 0)

        # Edit the file directly: no change record, no lock, no API.
        path = os.path.join(self.dir, "graph.json")
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["nodes"][0]["label"] = "tampered"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)

        res = cli("verify", self.dir, "--expect", self.fp_file, "--json")
        self.assertEqual(res.returncode, 1)
        report = json.loads(res.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["mismatched"], ["state_sha256"],
                         "history was untouched, so only state may mismatch")

    def test_usage_errors_exit_two(self):
        self.assertEqual(cli("verify", self.dir).returncode, 2)                    # no expectation
        self.assertEqual(cli("verify", self.dir, "--expect", "/nope/none.json").returncode, 2)

    def test_verify_does_not_modify_the_graph(self):
        cli("fingerprint", self.dir, "--out", self.fp_file)
        before = raw(self.dir)
        cli("verify", self.dir, "--expect", self.fp_file)
        self.assertEqual(raw(self.dir), before)

    def test_fingerprint_of_missing_graph_is_usage_error(self):
        self.assertEqual(cli("fingerprint", os.path.join(self.dir, "absent")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
