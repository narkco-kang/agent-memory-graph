"""`memctl add --evidence` resolves locators against the workspace, not the graphs dir.

The bug this locks (2026-11-01, found by the CEO while accepting
`memctl add --evidence` as delivered):

    memctl never passed `--root`, so amg fell back to its default base — the GRAPH
    directory, `knowledge-graph/graphs/`. Every artefact this team cites lives under
    the workspace (`docs/`, `src/`, ...). So `--evidence` was accepted and then always
    rejected with "file does not exist": the flag looked implemented and could not
    write a single real digest.

That is the shape of the failure this project keeps finding — the mechanism runs, but
it runs against the wrong base. A test that only reads memctl's source text for
`--root` would pass on a version that passes the flag to the wrong verb, so these
tests drive the real `amg` binary end to end.

Skipped when no amg binary is available (set MEMCTL_AMG, or have amg on PATH).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMCTL = os.path.join(ROOT, "tools", "memctl")


def find_amg():
    cand = [os.environ.get("MEMCTL_AMG"), os.path.expanduser("~/.amg-venv/bin/amg")]
    cand += shutil.which("amg") and [shutil.which("amg")] or []
    for c in cand:
        if c and os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


AMG = find_amg()


@unittest.skipIf(AMG is None, "no amg binary (set MEMCTL_AMG)")
class EvidenceRootTest(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="amg-evroot-")
        graphs = os.path.join(self.ws, "knowledge-graph", "graphs")
        os.makedirs(graphs)
        os.makedirs(os.path.join(self.ws, "tools"))
        self.graph = os.path.join(graphs, "grp.json")
        with open(self.graph, "w", encoding="utf-8") as fh:
            json.dump({"schema": "amg/v1", "group": "grp", "nodes": [], "edges": [],
                       "changes": [], "rev": 0}, fh, ensure_ascii=False)
        self.tool = os.path.join(self.ws, "tools", "memctl")
        shutil.copy(MEMCTL, self.tool)
        self.conf = os.path.join(self.ws, "tools", ".memctl.json")
        with open(self.conf, "w", encoding="utf-8") as fh:
            json.dump({"backend": "amg"}, fh)
        # the artefact the evidence will point at: under the WORKSPACE, never under graphs/
        os.makedirs(os.path.join(self.ws, "docs"))
        self.doc = os.path.join(self.ws, "docs", "thing.md")
        with open(self.doc, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("evidence\n")
        with open(self.doc, "rb") as fh:
            self.sha = hashlib.sha256(fh.read()).hexdigest()

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def run_tool(self, *args):
        env = dict(os.environ)
        env["MEMCTL_CONF"] = self.conf
        env["MEMCTL_WORKSPACE"] = self.ws
        env["MEMCTL_AMG"] = AMG
        return subprocess.run([sys.executable, self.tool] + list(args),
                              cwd=self.ws, env=env, capture_output=True, text=True)

    def nodes(self):
        with open(self.graph, encoding="utf-8") as fh:
            return json.load(fh)["nodes"]

    def test_evidence_under_the_workspace_is_accepted(self):
        """The whole point: a locator relative to the workspace must resolve.

        Without `--root WORKSPACE`, amg resolves `path:docs/thing.md` against
        `knowledge-graph/graphs/` and raises `file does not exist`. This test fails
        in exactly that way — it does not inspect the command line.
        """
        res = self.run_tool("add", "grp", "--id", "n1", "--type", "artifact",
                            "--label", "N", "--status", "done", "--source", "test",
                            "--evidence", f"path:docs/thing.md|{self.sha}|2026-11-01T00:00:00Z")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        nodes = {n["id"]: n for n in self.nodes()}
        self.assertIn("n1", nodes)
        self.assertEqual(nodes["n1"]["evidence"][0]["content_sha256"], self.sha)

    def test_a_wrong_digest_is_still_rejected(self):
        """Guards the guard: passing the right root must not disable verification.

        If `--root` were satisfied by skipping the digest check, the test above would
        pass for the wrong reason.
        """
        bogus = "a" * 64
        res = self.run_tool("add", "grp", "--id", "n2", "--type", "artifact",
                            "--label", "N", "--status", "done", "--source", "test",
                            "--evidence", f"path:docs/thing.md|{bogus}|2026-11-01T00:00:00Z")
        self.assertNotEqual(res.returncode, 0)
        self.assertNotIn("n2", [n["id"] for n in self.nodes()])

    def test_a_path_outside_the_workspace_does_not_resolve(self):
        """The base must be the workspace, not "anywhere on disk".

        A root that accepts ../../etc/passwd is not a base, it is an oracle.
        """
        res = self.run_tool("add", "grp", "--id", "n3", "--type", "artifact",
                            "--label", "N", "--status", "done", "--source", "test",
                            "--evidence", f"path:../../etc/passwd|{self.sha}|2026-11-01T00:00:00Z")
        self.assertNotEqual(res.returncode, 0)
        self.assertNotIn("n3", [n["id"] for n in self.nodes()])


if __name__ == "__main__":
    unittest.main()
