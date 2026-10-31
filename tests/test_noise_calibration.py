"""The noise-calibration failure must stay published with its numbers (DECISIONS #51).

The risk this guards: a rejected corpus quietly becoming a result ("0.654 with a better noise model"),
or the probe ladder being deleted because it failed.

Checks:
1. `result.json` records Q2 as failed and Q1 as not met, and its rejected-run recall is kept;
2. the decision page quotes the same coverage numbers as `result.json` and the probe values as
   `probes.json`, and does not present 0.654 as an accepted result;
3. the probe ladder is monotone-ish (no mix reaches the target) and the conclusion string says
   selection effect;
4. the pre-registration keeps its failed predictions and its stated deviation.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments", "retrieval_noise_representativeness")
PAGE = os.path.join(ROOT, "docs", "decisions", "51-calibrate-what-competes.md")
PREREG = os.path.join(EXP, "PREREGISTRATION.md")


def load_json(name):
    with open(os.path.join(EXP, name), encoding="utf-8") as fh:
        return json.load(fh)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class NoiseCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.result = load_json("result.json")
        self.probes = load_json("probes.json")
        self.page = read(PAGE)
        self.prereg = read(PREREG)

    def test_calibration_was_rejected_not_blessed(self):
        verdicts = self.result["verdicts"]
        self.assertFalse(verdicts["Q2_calibration_within_tolerance"],
                         "Q2 passed; #51 says it failed")
        self.assertFalse(verdicts["Q1_n2cal_r5_at_least_0.75"])
        self.assertTrue(verdicts["Q3_ordering_preserved"])
        self.assertEqual(verdicts["n2cal_r5"], self.result["arms"]["n2cal"]["recall@5"])

    def test_page_quotes_measured_coverage(self):
        coverage = self.result["coverage"]
        for name in ("control", "n2", "n2cal"):
            value = coverage[name]["share_ge_0.25"]
            self.assertIn(f"{value:.3f}", self.page, f"the page omits {name} share {value:.3f}")
        self.assertIn(f"{self.result['arms']['n2cal']['recall@5']:.3f}", self.page)
        self.assertIn("rejected-run diagnostic", self.page,
                      "the rejected corpus's recall must be labelled, not quoted as a result")

    def test_probe_ladder_is_recorded_and_fails(self):
        target = self.probes["target_share"]
        tolerance = self.probes["tolerance"]
        self.assertEqual(len(self.probes["rows"]), 3)
        for row in self.probes["rows"]:
            self.assertGreater(abs(row["share_ge_0.25"] - target), tolerance,
                               f"{row['mix']} is within tolerance; #51 says no mix reaches it")
            self.assertIn(f"{row['share_ge_0.25']:.3f}", self.page,
                          f"the page omits the probe {row['mix']}")
        self.assertIn("selection effect", self.probes["conclusion"])

    def test_failed_predictions_and_deviation_stay_visible(self):
        self.assertIn("### Predictions scored", self.prereg)
        self.assertIn("**Deviation, recorded:**", self.prereg)
        self.assertIn("**wrong**", self.prereg)
        self.assertIn("Still unmeasured", self.prereg)


if __name__ == "__main__":
    unittest.main()
