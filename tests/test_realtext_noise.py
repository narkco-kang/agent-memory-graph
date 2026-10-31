"""Real-prose noise must keep its calibration-first evidence (DECISIONS #52).

Checks:
1. the calibration number is reported and is below N2's 0.918 (the corpus is accepted as "real text");
2. the recall number on that corpus is below the published 0.70 target, and the page says so — this is
   the whole point of #52: realistic noise does not rescue the target;
3. the post-hoc length sweep is present and shows the pre-registered length reproduces the
   pre-registered number (determinism), and that longer, more realistic text does not raise recall@5;
4. the page keeps both the wrong prediction and the correction of #50's suspicion.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments", "retrieval_noise_realtext")
PAGE = os.path.join(ROOT, "docs", "decisions", "52-real-noise-also-misses.md")
PREREG = os.path.join(EXP, "PREREGISTRATION.md")


def load_json(name):
    with open(os.path.join(EXP, name), encoding="utf-8") as fh:
        return json.load(fh)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class RealTextNoiseTests(unittest.TestCase):
    def setUp(self):
        self.result = load_json("result.json")
        self.sensitivity = load_json("sensitivity_window.json")
        self.page = read(PAGE)
        self.prereg = read(PREREG)

    def test_calibration_passes_and_is_reported_first(self):
        verdicts = self.result["verdicts"]
        self.assertTrue(verdicts["Q2_calibration_below_n2"])
        share = self.result["coverage"]["realtext"]["share_ge_0.25"]
        self.assertLess(share, self.result["coverage"]["n2_reference_share_ge_0.25"])
        self.assertIn(f"{share:.3f}", self.page, "the page must quote the competing share")

    def test_real_noise_still_misses_the_target(self):
        r5 = self.result["arms"]["realtext"]["recall@5"]
        self.assertLess(r5, 0.70, "real text reached 0.70; #52 says it did not")
        self.assertIn(f"{r5:.3f}", self.page)
        self.assertIn("0.70", self.page)
        self.assertIn("unmet", self.page.lower())
        self.assertTrue(self.result["verdicts"]["Q3_ordering_n2_lt_realtext_lt_control"])

    def test_length_sweep_is_recorded_and_does_not_rescue_recall(self):
        rows = {str(row["window"]): row for row in self.sensitivity["rows"]}
        self.assertEqual(len(rows), 3)
        pre = self.result["arms"]["realtext"]["recall@5"]
        self.assertAlmostEqual(rows["8"]["recall@5"], pre, places=4,
                               msg="the pre-registered length must reproduce the pre-registered number")
        longest = rows["whole paragraph"]["recall@5"]
        self.assertLessEqual(longest, pre + 1e-9,
                             "longer real text raised recall@5; #52 says it does not")
        self.assertIn(f"{longest:.3f}", self.page)

    def test_wrong_prediction_and_correction_stay_visible(self):
        self.assertIn("### Predictions scored", self.prereg)
        self.assertEqual(len(re.findall(r"\*\*wrong\*\*", self.prereg)), 2)
        self.assertIn("**wrong**", self.page, "the page must record that #50's suspicion was wrong")


if __name__ == "__main__":
    unittest.main()
