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
import re
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


def sha256_bytes(data: bytes) -> str:
    return __import__("hashlib").sha256(data).hexdigest()


#: Fixture files are written with an explicit newline so the bytes on disk are the bytes
#: the digest is computed from. Why this is not paranoia (v0.37.4, Windows CI red):
#:
#: `open(path, "w", encoding="utf-8")` translates `\n` to `\r\n` on Windows. The fixture
#: then held `present\r\n` while the test declared `sha256(b"present\n")`, so the digest
#: did not match, the node landed in `evidence_unverifiable` as `mismatch`, and
#: `evidence_resolvable` came back empty. Two tests failed on windows-latest and passed
#: everywhere else — not because the code differs by platform, but because the fixture
#: silently changed what it wrote.
#:
#: The first guess was drive letters and case sensitivity in `_resolve_inside`. It was
#: wrong: `_resolve_inside` was never reached, because the file it named did exist and
#: resolved fine. The bytes had changed underneath the declaration — which is the exact
#: failure this project exists to report, arriving here as a test bug.
FIXTURE_NEWLINE = "\n"


def write_fixture(path, text):
    """Write fixture text with LF endings on every platform, then return its real digest.

    The digest is read back from disk rather than assumed, so a fixture that ever again
    grows a newline translation fails loudly here instead of silently emptying a bucket.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=FIXTURE_NEWLINE) as fh:
        fh.write(text)
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def make_root(with_sub_base=True):
    """A graph root with one resolvable file, one missing file and an optional repo/ sub-base.

    The digest of every fixture written here is registered in `FIXTURE_DIGESTS`, keyed by
    the root, so a test declares `digest_of(self.root, "here.md")` instead of hashing a
    hard-coded string it only hopes is what landed on disk.
    """
    root = tempfile.mkdtemp(prefix="amg-buckets-")
    digests = {"here.md": write_fixture(os.path.join(root, "here.md"), "present\n")}
    # a structure anchor, so this temporary root is not refused as "not the work tree"
    digests["README.md"] = write_fixture(os.path.join(root, "README.md"), "# fixture root\n")
    if with_sub_base:
        digests["agent-memory-graph/src/adopt.py"] = write_fixture(
            os.path.join(root, "agent-memory-graph", "src", "adopt.py"), "# adopt\n")
    FIXTURE_DIGESTS[root] = digests
    return root


#: root -> {fixture relative path: digest of the bytes actually on disk}
FIXTURE_DIGESTS = {}


def digest_of(root, rel):
    """The digest of the bytes `make_root` actually wrote for `rel` under `root`."""
    return FIXTURE_DIGESTS[root][rel]


def node(nid, evidence, status="done"):
    return {"id": nid, "type": "artifact", "label": nid, "status": status,
            "owner": "", "source": "t", "note": "", "evidence": evidence}


def doc(*nodes):
    return {"schema": "amg/v1", "group": "t", "nodes": list(nodes), "edges": [], "changes": []}


CLI = [sys.executable, "-m", "amg.cli"]


class BucketTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root()
        self.sha = digest_of(self.root, "here.md")

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
        sha = digest_of(root, "agent-memory-graph/src/adopt.py")
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


class FixtureBytesTest(unittest.TestCase):
    """The fixture must declare the digest of the bytes it actually wrote.

    v0.37.4 shipped four releases whose CI was red before anyone looked. One of them was
    this suite: `open(path, "w")` writes `\\r\\n` on Windows, so the fixture held
    `present\\r\\n` while the test declared `sha256(b"present\\n")`. The digest did not
    match, the node landed in `evidence_unverifiable` as `mismatch`, and
    `evidence_resolvable` came back empty — two errors on windows-latest, green
    everywhere else.

    The first diagnosis was drive letters and case sensitivity in `_resolve_inside`. That
    was wrong: the path resolved fine and the file was there. What had changed was the
    content, underneath a declaration that assumed it had not.

    These tests run on any platform. They cannot reproduce the Windows byte, but they can
    hold the property that made the bug possible: no digest here may be a hard-coded
    assumption about what a writer produced.
    """

    def test_the_declared_digest_is_the_digest_on_disk(self):
        root = make_root()
        for rel in ("here.md", "README.md", "agent-memory-graph/src/adopt.py"):
            path = os.path.join(root, *rel.split("/"))
            with open(path, "rb") as fh:
                on_disk = sha256_bytes(fh.read())
            self.assertEqual(
                digest_of(root, rel), on_disk,
                f"{rel}: the registered digest is not the digest of the bytes on disk",
            )

    def test_fixture_writing_is_pinned_to_lf(self):
        """The pin is what makes the bytes platform-independent; assert it is still there."""
        self.assertEqual(FIXTURE_NEWLINE, "\n",
                         "FIXTURE_NEWLINE must stay '\\n'; None re-enables the platform "
                         "translation that made the Windows digest disagree")
        root = make_root()
        with open(os.path.join(root, "here.md"), "rb") as fh:
            raw = fh.read()
        self.assertNotIn(b"\r\n", raw,
                         "the fixture file grew a CRLF; a digest computed from the "
                         "source text would no longer describe it")
        self.assertEqual(raw, b"present\n")

    def test_the_writer_actually_passes_the_newline_pin(self):
        """MUTATION GUARD: drop `newline=` from write_fixture's open() and this fails.

        Asserting the constant is not enough: the constant can stay while the `open()`
        call stops passing it. On POSIX that mutation is invisible — `open(..., "w")` and
        `open(..., "w", newline="\\n")` write identical bytes — so no runtime assertion
        available on this machine can tell them apart. The call itself has to be checked.
        """
        source = pathlib.Path(__file__).read_text(encoding="utf-8")
        writer = source.split("def write_fixture(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("newline=FIXTURE_NEWLINE", writer,
                      "write_fixture no longer passes the newline pin to open(); on "
                      "Windows it will write CRLF and every digest in this module becomes "
                      "a guess again")

    def test_no_test_in_this_module_hashes_a_string_literal(self):
        """A digest must never be `sha256(b"...")` — that is the assumption, not a fact.

        Parsed with `ast` rather than matched line by line: a line-based scan caught this
        test's own docstring and its pattern, and then the docstring's continuation lines
        as well. Only a real call node whose argument is a bytes literal counts.
        """
        import ast

        tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name != "sha256":
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, bytes):
                    offenders.append(f"line {node.lineno}: sha256({arg.value!r})")
        self.assertEqual(
            offenders, [],
            "these calls declare a digest from a string literal instead of from the "
            f"bytes on disk: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
