"""The lexical-signal round must publish the numbers it measured, including the wrong predictions.

DECISIONS #49 closes the lexical rerank family for query-vocabulary noise. The risk this test
guards is the one the project keeps hitting: a document and a result file drifting apart, and a
pre-registration whose failed predictions quietly disappear while the release note quotes only what
survived.

Checks:
1. `result.json` says no arm improves N2, `ship` is false, and alpha = 0 reproduces the shipped
   metrics on all four corpora (a harness that cannot reproduce the baseline measures itself);
2. the decision page quotes those same numbers (0.538 shipped, 0.481 best arm, 0.846 ceiling);
3. the pre-registration still carries all four predictions and marks three of them wrong;
4. the failing-half AUCs in the page match `diagnostic_by_solved.json`.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments", "retrieval_lexical_ceiling")
PAGE = os.path.join(ROOT, "docs", "decisions", "49-lexical-rerank-closed.md")
PREREG = os.path.join(EXP, "PREREGISTRATION.md")


def load_json(name):
    with open(os.path.join(EXP, name), encoding="utf-8") as fh:
        return json.load(fh)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class LexicalCeilingTests(unittest.TestCase):
    def setUp(self):
        self.result = load_json("result.json")
        self.diag = load_json("diagnostic_by_solved.json")
        self.page = read(PAGE)
        self.prereg = read(PREREG)

    def test_alpha_zero_reproduces_the_shipped_scorer(self):
        for corpus, block in self.result["corpora"].items():
            self.assertTrue(block["alpha0_metrics_equal_shipped"],
                            f"{corpus}: alpha=0 disagrees with the shipped scorer")

    def test_no_arm_improves_the_target(self):
        verdicts = self.result["verdicts"]
        self.assertFalse(verdicts["ship"], "the experiment shipped something; update #49 too")
        self.assertTrue(verdicts["all_arms_fail_C2"])
        self.assertLess(verdicts["n2_gain"], 0.0, "an arm gained recall; #49 says none did")
        shipped = self.result["criteria"] and self.result["verdicts"]["shipped_r5"]["n2"]
        for arm, block in self.result["corpora"]["n2"]["arms"].items():
            if arm in ("shipped", "0"):
                continue
            self.assertLessEqual(block["recall@5"], shipped,
                                 f"n2 {arm} beat the shipped 0.538: #49 is outdated")

    def test_decision_page_quotes_the_measured_numbers(self):
        n2 = self.result["corpora"]["n2"]["arms"]
        best = max(block["recall@5"] for arm, block in n2.items()
                   if arm not in ("shipped", "0"))
        ceiling = self.result["corpora"]["n2"]["diagnostics"]["candidate_ceiling"]
        for number in (f"{n2['shipped']['recall@5']:.3f}", f"{best:.3f}", f"{ceiling:.3f}"):
            self.assertIn(number, self.page, f"the page does not quote {number}")
        self.assertIn("#48", self.page, "the page must name the direction it closes")

    def test_failing_half_aucs_match_the_diagnostic(self):
        failing = self.diag["mean_auc_failing"]
        for signal, value in failing.items():
            self.assertIn(f"{value:.3f}", self.page,
                          f"the page does not quote the {signal} failing-half AUC {value:.3f}")
        self.assertEqual(self.diag["queries"], len(self.diag["rows"]))
        self.assertEqual(self.diag["solved_gold_in_top5"] + self.diag["failing_gold_outside_top5"],
                         self.diag["queries"])

    def test_failed_predictions_stay_visible(self):
        self.assertIn("### Predictions scored", self.prereg)
        wrong = len(re.findall(r"\*\*wrong\*\*", self.prereg))
        self.assertEqual(wrong, 3, f"expected three failed predictions kept on record, saw {wrong}")
        self.assertIn("**correct**", self.prereg)
        for claim in ("0.846", "4 of 26", "at or below chance"):
            self.assertIn(claim, self.prereg, f"the outcome lost its evidence: {claim}")


if __name__ == "__main__":
    unittest.main()
