"""The coverage-rerank experiment must reproduce the shipped scorer at alpha = 0.

Why this test exists: the first version of the harness broke ties by id, which moved n1
recall@5 from 0.865 to 0.827 without any signal being involved — a 10k corpus has many equal
scores, so the tie-break was doing the work. A reranker that cannot reproduce its baseline at
alpha = 0 measures its own tie-break, not the feature. The committed result records the check
(`alpha0_metrics_equal_shipped`) and this asserts it stayed true, so a rejected experiment
cannot be re-read months later as evidence for something the harness never measured.
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT = os.path.join(ROOT, "experiments", "retrieval_beyond_df", "result.json")
PREREG = os.path.join(ROOT, "experiments", "retrieval_beyond_df", "PREREGISTRATION.md")


class CoverageRerankResultTests(unittest.TestCase):
    def setUp(self):
        with open(RESULT, encoding="utf-8") as fh:
            self.result = json.load(fh)

    def test_alpha_zero_reproduces_the_shipped_metrics_on_every_corpus(self):
        for name, corpus in self.result["corpora"].items():
            self.assertTrue(corpus["alpha0_metrics_equal_shipped"],
                            f"{name}: alpha=0 no longer matches the shipped scorer")

    def test_alpha_zero_metrics_equal_shipped_metrics(self):
        for name, corpus in self.result["corpora"].items():
            control = corpus["arms"]["0"]
            shipped = corpus["arms"]["shipped"]
            for metric in ("recall@1", "recall@5", "recall@10", "mrr@10"):
                self.assertAlmostEqual(control[metric], shipped[metric], places=3,
                                       msg=f"{name}: {metric} differs at alpha=0")

    def test_the_verdict_is_recorded_as_rejected_with_a_reason(self):
        verdicts = self.result["verdicts"]
        self.assertFalse(verdicts["ship"], "the experiment recorded a ship; check the result")
        self.assertLess(verdicts["n2_gain"], 0.0, "the recorded N2 gain should be the measured one")
        with open(PREREG, encoding="utf-8") as fh:
            prereg = fh.read()
        self.assertIn("C2 the target moves", prereg, "the pre-registered criteria must stay readable")
        # the pre-registration is written before the run; the outcome lives in README.md
        self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(PREREG), "README.md")))


if __name__ == "__main__":
    unittest.main()
