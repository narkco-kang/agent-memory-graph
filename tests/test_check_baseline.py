"""The baseline excuses known debt and nothing else.

The property this file exists to hold, in one sentence: **a baseline may shrink or stay the
same, and everything that is not registered in it still fails.**

That sentence is easy to write and easy to break. The four ways it breaks, and the test that
catches each:

1. Registering by count instead of by node — "824 known errors" then excuses 824 of anything.
   `test_a_new_node_is_never_excused`
2. Registering by node but ignoring which errors — a node registered for one problem then
   silently covers a second one. `test_a_second_problem_on_a_registered_node_is_new`
3. Letting a re-run of --write-baseline sweep in whatever appeared since.
   `test_write_baseline_refuses_to_grow`
4. Document-level errors (schema mismatch, duplicate edges) being filed away per node, which
   would let a broken graph look like legacy debt. `test_document_level_errors_are_never_excused`

Each test names the mutation that must turn it red.
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

from amg import baseline as B  # noqa: E402

CLI = [sys.executable, "-m", "amg.cli"]


def env():
    e = dict(os.environ)
    e["PYTHONPATH"] = os.path.join(ROOT, "src") + os.pathsep + e.get("PYTHONPATH", "")
    return e


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def node(nid, evidence=None, status="done"):
    return {
        "id": nid, "type": "artifact", "label": nid, "status": status,
        "owner": "t", "source": "cmd:test", "note": "",
        "evidence": evidence if evidence is not None else [],
    }


def doc(*nodes):
    return {"schema": "amg/v1", "group": "t", "goal": "g", "rev": 1,
            "nodes": list(nodes), "edges": [], "changes": []}


class PartitionTest(unittest.TestCase):
    """Unit level: what counts as known, and what does not."""

    def test_a_registered_node_with_the_same_errors_is_known(self):
        errors = ["a: IR-4 conflict — done without evidence"]
        base = B.build(errors)
        known, new = B.partition(errors, base)
        self.assertEqual(known, errors)
        self.assertEqual(new, [])

    def test_a_new_node_is_never_excused(self):
        """MUTATION GUARD: register by count (a single "known: 1") and this fails."""
        base = B.build(["a: IR-4 conflict — done without evidence"])
        known, new = B.partition(
            ["a: IR-4 conflict — done without evidence",
             "b: IR-4 conflict — done without evidence"],
            base,
        )
        self.assertEqual(new, ["b: IR-4 conflict — done without evidence"],
                         "a node absent from the baseline must always be reported")

    def test_a_second_problem_on_a_registered_node_is_new(self):
        """MUTATION GUARD: match on node id alone and this fails.

        The whole node returns to the report rather than just the extra message: once a
        registered node has grown a problem the baseline never saw, everything on it is
        unreviewed again. Reporting only the new line would leave the old one excused by a
        registration that no longer describes the node.
        """
        base = B.build(["a: IR-4 conflict — done without evidence"])
        known, new = B.partition(
            ["a: IR-4 conflict — done without evidence", "a: IR-2 violated (missing or placeholder source)"],
            base,
        )
        self.assertEqual(known, [])
        self.assertEqual(new, ["a: IR-2 violated (missing or placeholder source)",
                               "a: IR-4 conflict — done without evidence"],
                         "being registered once must not cover a different problem")

    def test_document_level_errors_are_never_excused(self):
        """MUTATION GUARD: treat an empty node id as a normal key and this fails."""
        base = B.build(["schema mismatch: 'group-kg/v1' != 'amg/v1'"])
        self.assertEqual(base["nodes"], {},
                         "a document-level error belongs to no node and cannot be registered")
        _known, new = B.partition(["schema mismatch: 'group-kg/v1' != 'amg/v1'"], base)
        self.assertEqual(new, ["schema mismatch: 'group-kg/v1' != 'amg/v1'"])

    def test_a_fixed_node_shows_up_as_new_so_stale_registrations_are_visible(self):
        """A registered node whose errors changed is not silently 'known'."""
        base = B.build(["a: IR-4 conflict — done without evidence"])
        known, new = B.partition([], base)
        self.assertEqual((known, new), ([], []))


class CommandLineTest(unittest.TestCase):
    """End to end: the three states a reader must be able to tell apart."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-baseline-")

    def write(self, document):
        with open(os.path.join(self.dir, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(document, fh, ensure_ascii=False)

    def run_cli(self, *args):
        return subprocess.run(CLI + ["check", self.dir, "--strict", *args],
                              capture_output=True, text=True, env=env(), timeout=60)

    def test_the_three_states_are_distinguishable(self):
        self.write(doc(node("a")))
        base = os.path.join(self.dir, "baseline.json")

        plain = self.run_cli()
        self.assertEqual(plain.returncode, 1, "a red graph must be red without a baseline")

        written = self.run_cli("--baseline", base, "--write-baseline")
        self.assertEqual(written.returncode, 0, written.stderr)

        covered = self.run_cli("--baseline", base)
        self.assertEqual(covered.returncode, 0, covered.stdout + covered.stderr)
        self.assertIn("known", covered.stdout)
        self.assertIn("1", covered.stdout)

        self.write(doc(node("a"), node("b")))
        grew = self.run_cli("--baseline", base)
        self.assertEqual(grew.returncode, 1, "a new violating node must fail even with a baseline")
        self.assertIn("b: IR-4 conflict", grew.stdout)
        self.assertIn("1 new violation", grew.stdout)

    def test_write_baseline_refuses_to_grow(self):
        """MUTATION GUARD: drop the grown-set check and this passes when it must not."""
        self.write(doc(node("a")))
        base = os.path.join(self.dir, "baseline.json")
        self.run_cli("--baseline", base, "--write-baseline")
        before = read_json(base)

        self.write(doc(node("a"), node("b")))
        again = self.run_cli("--baseline", base, "--write-baseline")
        self.assertEqual(again.returncode, 1, again.stdout)
        self.assertIn("E_BASELINE_GROW", again.stderr)
        after = read_json(base)
        self.assertEqual(before, after, "a refused write must leave the baseline untouched")

    def test_prune_removes_silent_nodes_and_never_adds(self):
        self.write(doc(node("a"), node("b")))
        base = os.path.join(self.dir, "baseline.json")
        self.run_cli("--baseline", base, "--write-baseline")
        self.write(doc(node("a")))
        pruned = self.run_cli("--baseline", base, "--prune-baseline")
        self.assertEqual(pruned.returncode, 0, pruned.stderr)
        after = read_json(base)
        self.assertEqual(sorted(after["nodes"]), ["a"])
        self.assertEqual(after["total"], 1)


class ShrinkOnlyTest(unittest.TestCase):
    """The invariant stated as arithmetic: the baseline never gets larger on its own."""

    def test_repeated_checks_do_not_change_the_baseline(self):
        d = tempfile.mkdtemp(prefix="amg-baseline2-")
        with open(os.path.join(d, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(node("a")), fh, ensure_ascii=False)
        base = os.path.join(d, "baseline.json")
        subprocess.run(CLI + ["check", d, "--strict", "--baseline", base, "--write-baseline"],
                       capture_output=True, env=env(), timeout=60)
        first = read_text(base)
        for _ in range(3):
            subprocess.run(CLI + ["check", d, "--strict", "--baseline", base],
                           capture_output=True, env=env(), timeout=60)
        self.assertEqual(read_text(base), first,
                         "a plain check must never rewrite the baseline")


if __name__ == "__main__":
    unittest.main()
