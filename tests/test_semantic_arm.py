"""The semantic arm's published numbers must be the measured ones (DECISIONS #50).

Checks:
1. `result.json` says all three arms miss C2 and pass the regression gates, `ship` is false, and the
   model digest is the one the page quotes;
2. the decision page quotes the four per-corpus numbers and the unchanged N2 ceiling;
3. the pre-registration keeps all four predictions and marks three of them wrong;
4. the churn list in the page matches the post-hoc diagnostic — the aggregate alone (three arms all
   at 0.577) would hide six queries crossing the top-5 boundary in opposite directions.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments", "retrieval_semantic")
PAGE = os.path.join(ROOT, "docs", "decisions", "50-similarity-family-closed.md")
PREREG = os.path.join(EXP, "PREREGISTRATION.md")


def load_json(name):
    with open(os.path.join(EXP, name), encoding="utf-8") as fh:
        return json.load(fh)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class SemanticArmTests(unittest.TestCase):
    def setUp(self):
        self.result = load_json("result.json")
        self.diag = load_json("diagnostic_moved_queries.json")
        self.page = read(PAGE)
        self.prereg = read(PREREG)

    def test_no_arm_passes_the_increment_and_none_ships(self):
        verdicts = self.result["verdicts"]
        self.assertFalse(verdicts["ship"])
        self.assertEqual(verdicts["model"]["digest"],
                         "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f")
        for arm, block in verdicts["arms"].items():
            self.assertFalse(block["passes_all"], f"{arm} passed the gates; #50 says none did")
            self.assertFalse(block["C2_n2_gain_at_least_0.05"], arm)
            for gate in ("C1_control_no_regression", "C3_n1_unchanged", "C4_n3_not_harmed"):
                self.assertTrue(block[gate], f"{arm} broke a regression gate")

    def test_page_quotes_the_measured_table(self):
        corpora = self.result["corpora"]
        for corpus, arm in (("control", "B_semantic"), ("n2", "B_semantic"),
                            ("n2", "shipped"), ("n3", "C_hybrid")):
            value = corpora[corpus]["arms"][arm]["recall@5"]
            self.assertIn(f"{value:.3f}", self.page,
                          f"the page does not quote {corpus}/{arm} = {value:.3f}")
        ceiling = corpora["n2"]["ceilings"]["B_semantic"]
        self.assertIn(f"{ceiling:.3f}", self.page, "the page must quote the unchanged N2 ceiling")
        self.assertIn("#49", self.page, "the page must name the round it continues")

    def test_failed_predictions_stay_visible(self):
        self.assertIn("### Predictions scored", self.prereg)
        self.assertEqual(len(re.findall(r"\*\*wrong\*\*", self.prereg)), 3)
        self.assertEqual(len(re.findall(r"\*\*correct\*\*", self.prereg)), 1)

    def test_churn_list_matches_the_diagnostic(self):
        moved = set(self.diag["moved_across_top5"])
        self.assertEqual(len(moved), 6, f"expected six boundary crossings, saw {sorted(moved)}")
        for query in sorted(moved):
            self.assertIn(f"`{query}`", self.page, f"the page omits the moved query {query}")
        self.assertEqual(self.diag["caption"].split(":")[0], "post-hoc")
        # The three arms tie at recall@5 while behaving differently: that is the point of the table.
        self.assertEqual(len(set(self.diag["per_arm_top5"].values())), 2)


if __name__ == "__main__":
    unittest.main()
