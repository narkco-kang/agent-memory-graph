"""Hygiene checks: the project's only boundary is file permissions, so test it."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402
from amg import security  # noqa: E402

POSIX_ONLY = unittest.skipIf(os.name == "nt", "POSIX permission bits only")


def cli(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    return subprocess.run([sys.executable, "-m", "amg.cli", *args], capture_output=True,
                          text=True, encoding="utf-8", env=env, cwd=ROOT, timeout=60)


class HygieneTests(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(tempfile.mkdtemp(prefix="amg-sec-"), "mem")
        self.graph_dir = tempfile.mkdtemp(prefix="amg-sec-root-")
        self.dir = os.path.join(self.graph_dir, "mem")
        Memory.init(self.dir, group="t")
        os.chmod(self.dir, 0o700)
        os.chmod(os.path.join(self.dir, "graph.json"), 0o600)
        self.m = Memory.open(self.dir)

    def test_private_graph_has_no_findings(self):
        self.assertEqual(self.m.security_findings(), [])
        self.assertEqual(security.worst([]), "ok")

    @POSIX_ONLY
    def test_world_writable_graph_is_reported(self):
        os.chmod(os.path.join(self.dir, "graph.json"), 0o666)
        found = self.m.security_findings()
        self.assertIn("SEC_WORLD_WRITABLE", {f["code"] for f in found})
        self.assertEqual(security.worst(found), "warn")

    @POSIX_ONLY
    def test_world_writable_directory_is_reported(self):
        os.chmod(self.dir, 0o777)
        codes = {f["code"] for f in self.m.security_findings()}
        self.assertIn("SEC_WORLD_WRITABLE", codes)

    @POSIX_ONLY
    def test_group_writable_is_info_not_warn(self):
        os.chmod(os.path.join(self.dir, "graph.json"), 0o660)
        found = self.m.security_findings()
        self.assertEqual([f["severity"] for f in found if f["code"] == "SEC_GROUP_WRITABLE"], ["info"])

    def test_symlinked_graph_is_reported(self):
        target = os.path.join(self.graph_dir, "elsewhere.json")
        source = os.path.join(self.dir, "graph.json")
        os.replace(source, target)
        try:
            os.symlink(target, source)
        except (OSError, NotImplementedError):  # pragma: no cover - platform limit
            self.skipTest("symlinks not permitted here")
        self.assertIn("SEC_GRAPH_SYMLINK", {f["code"] for f in self.m.security_findings()})

    def test_missing_graph_is_an_error_finding(self):
        empty = tempfile.mkdtemp(prefix="amg-sec-empty-")
        self.assertEqual([f["severity"] for f in security.findings(empty)], ["error"])

    @POSIX_ONLY
    def test_doctor_strict_fails_on_world_writable(self):
        self.assertEqual(cli("doctor", self.dir, "--strict").returncode, 0)
        os.chmod(os.path.join(self.dir, "graph.json"), 0o666)
        res = cli("doctor", self.dir, "--strict")
        self.assertEqual(res.returncode, 1)
        self.assertIn("E_INSECURE_GRAPH", res.stderr)

    @POSIX_ONLY
    def test_doctor_json_reports_findings_without_strict(self):
        os.chmod(os.path.join(self.dir, "graph.json"), 0o666)
        res = cli("doctor", self.dir, "--json")
        self.assertEqual(res.returncode, 0, "non-strict doctor still succeeds")
        info = json.loads(res.stdout)
        self.assertEqual(info["security_worst"], "warn")
        self.assertTrue(info["security"])

    @POSIX_ONLY
    def test_mcp_warns_on_startup_but_still_serves(self):
        os.chmod(os.path.join(self.dir, "graph.json"), 0o666)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        res = subprocess.run([sys.executable, "-m", "amg.cli", "mcp", self.dir, "--read-only"],
                             input=payload, capture_output=True, text=True, encoding="utf-8",
                             env=env, cwd=ROOT, timeout=60)
        self.assertIn("SEC_WORLD_WRITABLE", res.stderr)
        self.assertEqual(res.returncode, 0)
        self.assertIn('"tools"', res.stdout, "warnings must not corrupt the protocol stream")


class NetworkPathTests(unittest.TestCase):
    def test_network_prefixes_are_detected(self):
        for path in ("/Volumes/share/mem", "/net/host/mem", "//server/share/mem"):
            normalised = path
            hit = any(p in normalised for p in security.NETWORK_PATH_PREFIXES)
            self.assertTrue(hit, path)


if __name__ == "__main__":
    unittest.main()
