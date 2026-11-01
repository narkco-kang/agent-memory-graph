"""Test order must not change the answer.

The defect: `Memory.evidence_root` is a class attribute (decision #56 makes the evidence
base a process-wide choice, not a per-node one). `TempGraph` set it to the repo root and
never restored it. So whichever test file ran first decided the evidence base for every
test after it — each file green alone, the suite red, and no single test to blame.

That is the same shape as four other failures today (the `search` crash, a stale `dist/`,
an `egg-info` false negative, a fixture digest computed from source text instead of from
the bytes): **the object being measured was changed by something else in the middle of the
measurement.** The only assertion that catches this shape is one that runs the same work in
a different order and compares.

These tests do exactly that, plus a direct guard on the leak itself.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

from amg import Memory  # noqa: E402
import helpers  # noqa: E402


class EvidenceRootDoesNotLeakTest(unittest.TestCase):
    """MUTATION GUARD: drop the save/restore in TempGraph and both tests below fail."""

    def setUp(self):
        self._saved = Memory.evidence_root
        Memory.evidence_root = None

    def tearDown(self):
        Memory.evidence_root = self._saved

    def test_tem_graph_restores_the_evidence_base(self):
        self.assertIsNone(Memory.evidence_root, "precondition")
        graph = helpers.TempGraph()
        self.assertEqual(Memory.evidence_root, helpers.ROOT,
                         "inside its lifetime the helper sets the repo root")
        graph.close()
        self.assertIsNone(Memory.evidence_root,
                          "after close() the evidence base must be back where it started")

    def test_a_failing_use_still_restores(self):
        """`close()` alone is not enough: a test that raises before close() would leak."""
        graph = helpers.TempGraph()
        graph.restore()
        self.assertIsNone(Memory.evidence_root)
        graph.close()

    def test_the_helper_can_scope_the_base_to_its_own_directory(self):
        graph = helpers.TempGraph(evidence_root=None)
        try:
            self.assertIsNone(Memory.evidence_root,
                              "passing None means 'resolve against the graph dir'")
            self.assertEqual(graph.m._evidence_base(), os.path.abspath(graph.dir))
        finally:
            graph.close()

    def test_restore_returns_to_the_previous_non_none_base(self):
        """MUTATION GUARD: hard-code the saved value to None and this fails.

        The other tests all start from `None`, so a restore that always writes `None`
        passes them by coincidence — it only looks correct because nothing else was set.
        Start from a real base to remove the coincidence.
        """
        marker = os.path.join(ROOT, "docs")
        Memory.evidence_root = marker
        try:
            graph = helpers.TempGraph()
            self.assertEqual(Memory.evidence_root, helpers.ROOT)
            graph.close()
            self.assertEqual(Memory.evidence_root, marker,
                             "restore must put back the value it found, not a hard-coded None")
        finally:
            Memory.evidence_root = None

    def test_two_helpers_in_a_row_do_not_compound(self):
        first = helpers.TempGraph()
        first.close()
        second = helpers.TempGraph()
        second.close()
        self.assertIsNone(Memory.evidence_root,
                          "the second helper must restore to None, not to the first's ROOT")


class OrderIndependenceTest(unittest.TestCase):
    """The assertion that actually catches order dependence: run it both ways."""

    def _both_orders(self, first, second):
        """Run `first` then `second`; and `second` then `first`. Both must pass."""
        from unittest import TestLoader, TextTestRunner

        first = first[0] if isinstance(first, tuple) else first
        second = second[0] if isinstance(second, tuple) else second
        loader = TestLoader()
        outcomes = {}
        for label, names in (("forward", [first, second]), ("reverse", [second, first])):
            suite = loader.loadTestsFromNames(names)
            with open(os.devnull, "w") as sink:
                result = TextTestRunner(verbosity=0, stream=sink).run(suite)
            outcomes[label] = (result.wasSuccessful(), result.testsRun,
                               list(result.errors) + list(result.failures))
        return outcomes

    def test_helpers_and_the_repair_tests_agree_in_both_orders(self):
        """The exact pair that failed: a TempGraph file, then the legacy-repair tests."""
        outcomes = self._both_orders(
            ("test_digest",),
            ("test_write_verify.LegacyEvidenceRepairTest",),
        )
        for label, (ok, ran, problems) in outcomes.items():
            self.assertTrue(ok, f"{label} order failed with {len(problems)} problem(s): "
                                f"{[name for name, _ in problems]}")
            self.assertGreater(ran, 0, f"{label} order ran nothing; the test selection is wrong")
        self.assertEqual(outcomes["forward"][1], outcomes["reverse"][1],
                         "the same number of tests must run in both orders")

    def test_a_temp_graph_file_and_the_baseline_tests_agree_in_both_orders(self):
        outcomes = self._both_orders(
            ("test_digest",),
            ("test_check_baseline",),
        )
        for label, (ok, _ran, problems) in outcomes.items():
            self.assertTrue(ok, f"{label} order failed: {[name for name, _ in problems]}")

    def test_the_evidence_base_is_the_same_before_and_after_a_temp_graph(self):
        """The direct form of the invariant, independent of which test files exist.

        `TempGraph` must be a scope, not a global switch: entering and leaving it has to
        leave `Memory.evidence_root` exactly as it found it. If this holds, no ordering of
        test files can make one test's evidence base depend on another's.
        """
        import amg.memory

        before = amg.memory.Memory.evidence_root
        graph = helpers.TempGraph()
        inside = amg.memory.Memory.evidence_root
        graph.close()
        after = amg.memory.Memory.evidence_root
        self.assertNotEqual(inside, before,
                            "precondition: the helper does set a base while open")
        self.assertEqual(after, before,
                         "TempGraph leaked its evidence base; every later test inherits it")

if __name__ == "__main__":
    unittest.main()
