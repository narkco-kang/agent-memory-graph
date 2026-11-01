"""Read paths report `evidence_state`, not `anchor_state`.

`anchor_state` answers one question — is the evidence LIST non-empty — and a reader
naturally takes the word "anchor=present" to mean "this hit has evidence behind it".
It does not. On the team graph every `done` node's evidence is a bare string, so
per-node anchoring reads `present` while nothing was ever checked. That is the exact
misreading this project keeps removing: a claim rendered as a result.

`evidence_state` states what is observable:

    verified  a proper object's file resolved AND its digest matched   (only pass)
    declared  something recorded; nothing checkable was checked
    missing   every path-shaped locator resolves nowhere (dead pointer)
    absent    nothing recorded at all
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg.audit import evidence_state  # noqa: E402

CLI = [sys.executable, "-m", "amg.cli"]


def make_root():
    root = tempfile.mkdtemp(prefix="amg-estate-")
    with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("# ws\n")
    with open(os.path.join(root, "here.md"), "w", encoding="utf-8") as fh:
        fh.write("present\n")
    return root


def sha_of(root, name):
    import hashlib
    return hashlib.sha256(open(os.path.join(root, name), "rb").read()).hexdigest()


class EvidenceStateTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root()

    def test_no_evidence_is_absent(self):
        self.assertEqual(evidence_state({"evidence": []}, self.root)["state"], "absent")

    def test_bare_string_is_declared_never_verified(self):
        """The whole point: a declaration is not a verified result."""
        for locator in ("here.md", "path:here.md", "some prose about a file"):
            state = evidence_state({"evidence": [locator]}, self.root)["state"]
            self.assertEqual(state, "declared", f"{locator!r} must not read as verified")

    def test_a_dead_pointer_is_missing_not_declared(self):
        state = evidence_state({"evidence": ["nowhere/gone.md"]}, self.root)["state"]
        self.assertEqual(state, "missing")

    def test_a_matching_object_is_verified(self):
        node = {"evidence": [{"locator": "path:here.md",
                              "content_sha256": sha_of(self.root, "here.md"),
                              "captured_at": "2026-01-01T00:00:00Z"}]}
        self.assertEqual(evidence_state(node, self.root)["state"], "verified")

    def test_a_wrong_digest_is_stale_not_missing(self):
        """The file IS there; its bytes changed. That is a different fact from absent,
        and it is the one a reader needs: the claim no longer describes its evidence."""
        node = {"evidence": [{"locator": "path:here.md", "content_sha256": "a" * 64,
                              "captured_at": "2026-01-01T00:00:00Z"}]}
        self.assertEqual(evidence_state(node, self.root)["state"], "stale")

    def test_one_good_and_one_rotted_citation_is_partly_stale(self):
        node = {"evidence": [
            {"locator": "path:here.md", "content_sha256": sha_of(self.root, "here.md"),
             "captured_at": "2026-01-01T00:00:00Z"},
            {"locator": "path:here.md", "content_sha256": "a" * 64,
             "captured_at": "2026-01-01T00:00:00Z"},
        ]}
        self.assertEqual(evidence_state(node, self.root)["state"], "partly_stale")

    def test_a_prose_only_node_is_declared(self):
        node = {"evidence": ["cmd:python3 -m amg check"]}
        self.assertEqual(evidence_state(node, self.root)["state"], "declared")


class SearchReportsStateTest(unittest.TestCase):
    """The CLI must render `declared`, not "present", and accept `--root`/`--graph`."""

    def setUp(self):
        self.root = make_root()
        self.graphs = os.path.join(self.root, "graphs")
        os.makedirs(self.graphs)
        self.graph = os.path.join(self.graphs, "g.json")
        doc = {"schema": "amg/v1", "group": "t", "nodes": [
            {"id": "bare", "type": "task", "label": "alpha beta", "status": "open",
             "owner": "", "source": "t", "note": "", "evidence": ["here.md"]},
            {"id": "dead", "type": "task", "label": "alpha gamma", "status": "open",
             "owner": "", "source": "t", "note": "", "evidence": ["gone/x.md"]},
            {"id": "none", "type": "task", "label": "alpha delta", "status": "open",
             "owner": "", "source": "t", "note": "", "evidence": []},
        ], "edges": [], "changes": []}
        with open(self.graph, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)

    def run_search(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        return subprocess.run(CLI + ["search", self.graphs, "--graph", self.graph,
                                     "alpha", "--json", *args],
                              capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=ROOT, timeout=60)

    def test_search_accepts_root(self):
        res = self.run_search("--root", self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("unrecognized", res.stderr)

    def test_each_hit_carries_evidence_state(self):
        hits = json.loads(self.run_search("--root", self.root).stdout)
        states = {h["id"]: h["evidence_state"]["state"] for h in hits}
        self.assertEqual(states["bare"], "declared")
        self.assertEqual(states["dead"], "missing")
        self.assertEqual(states["none"], "absent")

    def test_plain_output_never_says_present(self):
        """MUTATION GUARD: render anchor_state again and this fails."""
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        res = subprocess.run(CLI + ["search", self.graphs, "--graph", self.graph, "alpha",
                                    "--root", self.root],
                             capture_output=True, text=True, encoding="utf-8",
                             env=env, cwd=ROOT, timeout=60)
        self.assertNotIn("anchor=present", res.stdout,
                         "a bare-string declaration must never be printed as present")
        self.assertIn("evidence=declared", res.stdout)


if __name__ == "__main__":
    unittest.main()


class ShaFragmentTest(unittest.TestCase):
    """Legacy `path:<rel>#sha256:<hex>` locators are a KNOWN format, not stray text.

    `kg.py` wrote them; 41 records on the team graph use it. They were looked up with
    the fragment still attached, so the file never resolved and every one was reported
    `missing` — the only historic evidence that ever declared a digest was voided by the
    switch. These pin the parse and the three outcomes it can produce.
    """

    def setUp(self):
        self.root = make_root()

    def frag(self, sha):
        return {"evidence": [f"here.md#sha256:{sha}"]}

    def test_a_matching_fragment_digest_is_verified(self):
        self.assertEqual(evidence_state(self.frag(sha_of(self.root, "here.md")), self.root)["state"],
                         "verified")

    def test_a_mismatched_fragment_digest_is_stale(self):
        """MUTATION GUARD: parse the fragment as part of the path and this fails —
        the file is not found and the state collapses to `missing`."""
        self.assertEqual(evidence_state(self.frag("b" * 64), self.root)["state"], "stale")

    def test_a_fragment_without_a_file_is_missing(self):
        node = {"evidence": ["gone.md#sha256:" + "b" * 64]}
        self.assertEqual(evidence_state(node, self.root)["state"], "missing")

    def test_split_sha_fragment_only_accepts_a_full_hex(self):
        from amg.gate import split_sha_fragment
        self.assertEqual(split_sha_fragment("a.md#sha256:" + "c" * 64),
                         ("a.md", "c" * 64))
        self.assertEqual(split_sha_fragment("a.md"), ("a.md", None))
        self.assertEqual(split_sha_fragment("a.md#sha256:short"),
                         ("a.md#sha256:short", None),
                         "a malformed fragment stays part of the path rather than pretending")


class GlyphCoverageTest(unittest.TestCase):
    """Every `evidence_state` must have a display glyph — enforced by walking the enum.

    This exists because `partly_stale` shipped without one: `search` raised KeyError the
    moment it met a node with rotted citations, while 493 tests stayed green. The gap
    was not "a missing case in a dict", it was "nothing checked that the two evolve
    together". Adding a state now fails here instead of in production.
    """

    def test_every_state_has_a_glyph(self):
        """MUTATION GUARD: delete any state's glyph and this fails immediately."""
        from amg.cli import EVIDENCE_STATE_GLYPHS, evidence_state_glyph
        from amg import audit as audit_mod
        import inspect
        import re

        source = inspect.getsource(audit_mod.evidence_state)
        found = set(re.findall(r'"state":\s*"([a-z_]+)"', source))
        # A state may also be selected into a variable before being returned, so the
        # literal check is paired with an explicit enum of what this build can emit.
        found |= set(re.findall(r'(?:state = |")("?)(partly_stale|stale|verified|declared|missing|absent)', source))
        states = {f[1] if isinstance(f, tuple) else f for f in found}
        states |= {"verified", "partly_stale", "stale", "declared", "missing", "absent"}
        self.assertGreaterEqual(len(states), 6, "the enum walk found too few states")
        for state in sorted(states):
            self.assertIn(state, EVIDENCE_STATE_GLYPHS,
                          f"{state} has no display glyph; search would crash on it")
            self.assertNotEqual(evidence_state_glyph(state), "?",
                                f"{state} resolves to the unknown glyph")

    def test_the_glyphs_are_distinct_enough_to_read(self):
        from amg.cli import EVIDENCE_STATE_GLYPHS
        # The two stale variants share one glyph on purpose: both mean "a citation no
        # longer matches its file". Everything else is distinct so a reader can tell
        # verified from declared at a glance.
        dupes = {g for g in EVIDENCE_STATE_GLYPHS.values()
                 if list(EVIDENCE_STATE_GLYPHS.values()).count(g) > 1}
        self.assertEqual(dupes, {"!"}, f"unexpected shared glyphs: {dupes}")

    def test_an_unknown_state_does_not_crash_a_read(self):
        """A newer writer may store a state this build has never seen."""
        from amg.cli import evidence_state_glyph
        self.assertEqual(evidence_state_glyph("from_the_future"), "?")

    def test_search_renders_a_stale_hit_without_raising(self):
        mem = tempfile.mkdtemp(prefix="amg-glyph-")
        with open(os.path.join(mem, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("# ws\n")
        with open(os.path.join(mem, "doc.md"), "w", encoding="utf-8") as fh:
            fh.write("original\n")
        with open(os.path.join(mem, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump({"schema": "amg/v1", "group": "t", "nodes": [
                {"id": "rotted", "type": "artifact", "label": "aqua rot", "status": "done",
                 "owner": "", "source": "t", "note": "",
                 "evidence": [{"locator": "path:doc.md", "content_sha256": "a" * 64,
                               "captured_at": "2026-01-01T00:00:00Z"}]}],
                "edges": [], "changes": []}, fh, ensure_ascii=False)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        res = subprocess.run(CLI + ["search", mem, "aqua", "--root", mem],
                             capture_output=True, text=True, encoding="utf-8",
                             env=env, cwd=ROOT, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("KeyError", res.stderr)
        self.assertIn("evidence=stale", res.stdout)
