"""`audit --verify`: one mixed count becomes three named buckets.

The defect this fixes (DECISIONS #57): `legacy_stats` reports a single
`done_no_evidence`, so a reader cannot tell "there is no evidence" from "there is a
declaration this build cannot check". Both are real, neither is the other, and a
single number makes them indistinguishable — the same failure as reporting
`ValidationSuspended` as `ValidationFailed`.

What a mutation must break, and why the tests are shaped this way:

* deleting the `--verify` wiring collapses the buckets back into one key, so
  `test_verify_flag_is_required_for_buckets` fails;
* resolving only against the graph root loses the sub-base bucket, so
  `test_sub_base_resolution_is_reported` fails — that bucket is the visible
  evidence of the locator-base bug, not a convenience.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg.audit import evidence_buckets  # noqa: E402
from amg.gate import resolve_evidence_path  # noqa: E402
import pathlib

SHA = "a" * 64


def make_root(with_sub_base=True):
    """A graph root with one resolvable file, one missing file and an optional repo/ sub-base."""
    root = tempfile.mkdtemp(prefix="amg-buckets-")
    with open(os.path.join(root, "here.md"), "w", encoding="utf-8") as fh:
        fh.write("present\n")
    # a structure anchor, so this temporary root is not refused as "not the work tree"
    with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("# fixture root\n")
    if with_sub_base:
        os.makedirs(os.path.join(root, "agent-memory-graph", "src"), exist_ok=True)
        with open(os.path.join(root, "agent-memory-graph", "src", "adopt.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("# adopt\n")
    return root


def node(nid, evidence, status="done"):
    return {"id": nid, "type": "artifact", "label": nid, "status": status,
            "owner": "", "source": "t", "note": "", "evidence": evidence}


def doc(*nodes):
    return {"schema": "amg/v1", "group": "t", "nodes": list(nodes), "edges": [], "changes": []}


CLI = [sys.executable, "-m", "amg.cli"]


class BucketTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root()
        self.sha = __import__("hashlib").sha256(b"present\n").hexdigest()

    def write(self, document):
        with open(os.path.join(self.root, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(document, fh, ensure_ascii=False)

    def buckets(self):
        return evidence_buckets(doc(
            node("absent", []),
            node("verified", [{"locator": "path:here.md", "content_sha256": self.sha,
                               "captured_at": "2026-01-01T00:00:00Z"}]),
            node("mismatch", [{"locator": "path:here.md", "content_sha256": SHA,
                               "captured_at": "2026-01-01T00:00:00Z"}]),
            node("gone", [{"locator": "path:nope.md", "content_sha256": SHA,
                           "captured_at": "2026-01-01T00:00:00Z"}]),
            node("not_done", [], status="open"),
        ), self.root)

    def test_the_four_outcomes_are_separate_keys(self):
        b = self.buckets()
        self.assertEqual(b["evidence_absent"]["ids"], ["absent"])
        self.assertEqual(b["evidence_resolvable"]["count"], 1)
        self.assertEqual([n["id"] for n in b["evidence_unverifiable"]["nodes"]], ["gone", "mismatch"])

    def test_open_nodes_never_land_in_a_bucket(self):
        b = self.buckets()
        landed = (b["evidence_absent"]["ids"]
                  + [n["id"] for n in b["evidence_unverifiable"]["nodes"]]
                  + [n["id"] for n in b["evidence_resolvable"]["nodes"]]
                  + [n["id"] for n in b["evidence_declared_uncheckable"]["nodes"]])
        self.assertNotIn("not_done", landed)

    def test_known_limitation_is_an_empty_reserved_key(self):
        b = self.buckets()
        self.assertEqual(b["known_limitation"]["count"], 0)
        self.assertIn("P1", b["known_limitation"]["note"])

    def test_a_legacy_bare_string_is_not_counted_as_verified(self):
        """A bare string declares no digest; calling it resolvable would overclaim."""
        root = make_root()
        b = evidence_buckets(doc(node("legacy", ["here.md"])), root)
        self.assertEqual(b["evidence_resolvable"]["count"], 0)
        self.assertEqual(b["evidence_declared_uncheckable"]["count"], 1)
        self.assertEqual(b["evidence_declared_uncheckable"]["nodes"][0]["bases"], ["root"])

    def test_sub_base_resolution_is_reported(self):
        """The locator-base bug must stay visible: a sub-base hit names its base."""
        root = make_root()
        b = evidence_buckets(doc(node("legacy", ["src/adopt.py"])), root)
        row = b["evidence_declared_uncheckable"]["nodes"][0]
        self.assertIn("agent-memory-graph", row["bases"],
                      "a locator written against the repo root must report that base")

    def test_resolvable_reports_which_base_matched(self):
        root = make_root()
        sha = __import__("hashlib").sha256(b"# adopt\n").hexdigest()
        b = evidence_buckets(doc(node("v", [{"locator": "path:src/adopt.py",
                                             "content_sha256": sha,
                                             "captured_at": "2026-01-01T00:00:00Z"}])), root)
        row = b["evidence_resolvable"]["nodes"][0]
        self.assertEqual(row["base"], "agent-memory-graph")
        self.assertTrue(row["via_sub_base"])
        self.assertEqual(b["evidence_resolvable"]["via_base"]["agent-memory-graph"], 1)

    def test_root_is_tried_before_the_sub_base(self):
        """A file present at the root wins; the sub-base is only a fallback."""
        root = make_root()
        with open(os.path.join(root, "src_dup.md"), "w", encoding="utf-8") as fh:
            fh.write("root copy\n")
        path, base = resolve_evidence_path(root, "src_dup.md")
        self.assertEqual(base, "root")

    def test_a_dotdot_escape_is_still_refused(self):
        root = make_root()
        with open(os.path.join(root, "..", "outside.md"), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        path, reason = resolve_evidence_path(root, "../outside.md")
        self.assertIsNone(path)
        self.assertEqual(reason, "outside_root")


class VerifyFlagTest(unittest.TestCase):
    """The flag has to be what turns the buckets on; without it they must be absent."""

    def setUp(self):
        self.root = make_root()
        self.write_doc()

    def write_doc(self):
        with open(os.path.join(self.root, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(node("absent", [])), fh, ensure_ascii=False)

    def run_audit(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        res = subprocess.run(CLI + ["audit", self.root, "--json", *args],
                             capture_output=True, text=True, encoding="utf-8",
                             env=env, cwd=ROOT, timeout=60)
        return json.loads(res.stdout)

    def run_audit(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        res = subprocess.run(CLI + ["audit", self.root, "--json", "--root", self.root, *args],
                             capture_output=True, text=True, encoding="utf-8",
                             env=env, cwd=ROOT, timeout=60)
        return json.loads(res.stdout)

    def test_verify_flag_is_required_for_buckets(self):
        """MUTATION GUARD: remove the --verify wiring and this fails."""
        without = self.run_audit()
        self.assertNotIn("evidence_buckets", without,
                         "buckets must not appear unless --verify is passed")
        with_flag = self.run_audit("--verify")
        self.assertIn("evidence_buckets", with_flag,
                      "--verify is what splits the single mixed count")

    def test_without_the_flag_the_old_mixed_count_is_untouched(self):
        rep = self.run_audit()
        self.assertIn("legacy", rep)
        self.assertIn("done_no_evidence", rep["legacy"])

    def test_buckets_sum_to_the_done_node_count(self):
        rep = self.run_audit("--verify")
        b = rep["evidence_buckets"]
        total = sum(b[k]["count"] for k in (
            "evidence_absent", "evidence_unverifiable",
            "evidence_resolvable", "evidence_declared_uncheckable"))
        done = sum(1 for n in json.loads(pathlib.Path(os.path.join(self.root, "graph.json")).read_text(encoding="utf-8"))["nodes"]
                   if n.get("status") == "done")
        self.assertEqual(total, done)


class DeadPointerIsNotADeclarationTest(unittest.TestCase):
    """A bare pointer that resolves nowhere is `unverifiable`, not `declared`.

    Reported defect (CEO, on the live view): one run printed
    `evidence_unverifiable 0` while the same run listed `missing=272`. Both lines
    came from one code path that put every bare-string node into `declared`
    regardless of whether its pointer could be observed. A reader who trusts the
    first line concludes nothing is broken; the second line says 272 things are.
    """

    def test_a_bare_string_that_resolves_nowhere_is_unverifiable(self):
        root = make_root()
        b = evidence_buckets(doc(node("dead", ["nope/missing.md"])), root)
        self.assertEqual(b["evidence_unverifiable"]["count"], 1)
        self.assertEqual(b["evidence_declared_uncheckable"]["count"], 0)
        self.assertEqual(b["evidence_unverifiable"]["nodes"][0]["id"], "dead")

    def test_a_bare_string_that_resolves_is_still_declared(self):
        """Existence is all a bare string can show, so it stays out of `resolvable`."""
        root = make_root()
        b = evidence_buckets(doc(node("alive", ["here.md"])), root)
        self.assertEqual(b["evidence_declared_uncheckable"]["count"], 1)
        self.assertEqual(b["evidence_unverifiable"]["count"], 0)

    def test_the_two_buckets_can_never_both_read_zero_for_a_dead_pointer(self):
        """The contradiction guard: these were 272 and 0 in the same report."""
        root = make_root()
        nodes = [node(f"dead{i}", [f"gone/none{i}.md"]) for i in range(5)]
        b = evidence_buckets(doc(*nodes), root)
        self.assertGreater(b["evidence_unverifiable"]["count"], 0,
                           "dead pointers must land in unverifiable")
        self.assertEqual(b["evidence_declared_uncheckable"]["count"], 0)


class EvidenceRootTest(unittest.TestCase):
    """The evidence base is explicit, checked, and always named in the report."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="amg-evroot-")
        with open(os.path.join(self.root, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("# workspace\n")
        with open(os.path.join(self.root, "here.md"), "w", encoding="utf-8") as fh:
            fh.write("present\n")
        self.graph_dir = os.path.join(self.root, "knowledge-graph", "live")
        os.makedirs(self.graph_dir, exist_ok=True)
        with open(os.path.join(self.graph_dir, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(node("n", ["here.md"])), fh, ensure_ascii=False)

    def run_raw(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        return subprocess.run(CLI + ["audit", self.graph_dir, "--json", "--verify", *args],
                              capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=ROOT, timeout=60)

    def run_audit(self, *args):
        return json.loads(self.run_raw(*args).stdout)

    def test_missing_root_is_refused_rather_than_guessed(self):
        """MUTATION GUARD: restore "default to dir" and this fails. 232 vs 24."""
        res = self.run_raw()
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("E_EVIDENCE_ROOT_REQUIRED", res.stderr)
        self.assertEqual(res.stdout.strip(), "", "no report when the base is unknown")

    def test_a_base_without_structure_anchors_is_refused(self):
        """MUTATION GUARD: make the anchor check always pass and this fails."""
        res = self.run_raw("--root", self.graph_dir)
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("E_EVIDENCE_ROOT_SUSPECT", res.stderr)
        self.assertEqual(res.stdout.strip(), "")

    def test_force_root_reports_anyway_and_leaves_a_trace(self):
        rep = self.run_audit("--root", self.graph_dir, "--force-root")
        self.assertTrue(rep["evidence_root"]["anchors"]["suspect"],
                        "forcing must not make a suspect base look healthy")

    def test_root_decouples_the_evidence_base(self):
        rep = self.run_audit("--root", self.root)
        self.assertEqual(rep["evidence_root"]["source"], "--root")
        self.assertEqual(rep["evidence_root"]["path"], os.path.abspath(self.root))
        self.assertEqual(rep["evidence_buckets"]["evidence_unverifiable"]["count"], 0)

    def test_the_report_carries_a_physical_identity(self):
        """(dev, ino) identifies a directory where a path string cannot.

        Reported, not enforced: whoever picks the root can pick one that passes.
        """
        rep = self.run_audit("--root", self.root)
        ident = rep["evidence_root"]["identity"]
        st = os.stat(self.root)
        self.assertEqual((ident["dev"], ident["ino"]), (st.st_dev, st.st_ino))


if __name__ == "__main__":
    unittest.main()
