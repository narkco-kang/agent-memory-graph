"""The valid_from measurement is reproducible, and its documented numbers hold.

If someone ever "fixes" adoption by back-filling valid_from from the change log,
these assertions fail — that is the point: the experiment is the guard rail for
DECISIONS #5, not just a one-off chart.
"""
import importlib.util
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERIMENT = os.path.join(ROOT, "experiments", "valid_from_bias", "run_experiment.py")


def _load_experiment():
    spec = importlib.util.spec_from_file_location("valid_from_bias_experiment", EXPERIMENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # __name__ != "__main__", so main() does not run
    return module


class ValidFromBiasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp = _load_experiment()
        cls.tmp = tempfile.mkdtemp(prefix="valid-from-bias-test-")
        doc, cls.truth = cls.exp.build_fixture()
        fixture_path = os.path.join(cls.tmp, "fixture_legacy.json")
        import json
        with open(fixture_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        from amg import Memory
        cls.report = Memory.adopt(fixture_path, os.path.join(cls.tmp, "adopted"),
                                  group="valid-from-bias-fixture")
        cls.adopted = Memory.open(os.path.join(cls.tmp, "adopted")).doc
        cls.summary = cls.exp.summarize(cls.exp.measure(cls.adopted, cls.truth))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fixture_shape_matches_preregistration(self):
        self.assertEqual(len(self.truth), 30)
        self.assertEqual(self.summary["lagged"]["n"], 20)
        self.assertEqual(self.summary["control"]["n"], 10)

    def test_proxy_deviation_is_exactly_the_write_lag(self):
        for bucket, lag in (("3d", 3), ("10d", 10), ("30d", 30)):
            info = self.summary["by_bucket"][bucket]
            self.assertEqual(info["min_deviation_days"], float(lag), bucket)
            self.assertEqual(info["max_deviation_days"], float(lag), bucket)

    def test_decision_threshold_met_on_lagged_facts(self):
        self.assertEqual(self.summary["lagged"]["exceeding"], 20)
        self.assertEqual(self.summary["lagged"]["ratio"], 1.0)
        self.assertGreaterEqual(self.summary["lagged"]["ratio"],
                                self.exp.DECISION_THRESHOLD)
        self.assertIn("MUST add an explicit fact-time input", self.summary["verdict"])

    def test_control_group_shows_the_proxy_is_not_always_wrong(self):
        self.assertEqual(self.summary["control"]["exceeding"], 0)
        self.assertEqual(self.summary["all_facts"]["ratio"], round(20 / 30, 3))

    def test_adoption_still_refuses_to_invent_valid_from(self):
        self.assertTrue(self.summary["adopted_valid_from_is_null"])
        self.assertTrue(self.summary["adopted_valid_time_known_false"])
        self.assertTrue(self.report["check"]["ok"], self.report["check"]["errors"])


if __name__ == "__main__":
    unittest.main()
