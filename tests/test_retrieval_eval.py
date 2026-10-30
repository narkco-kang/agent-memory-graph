"""Lock the retrieval baseline so a ranking change cannot land unnoticed.

The numbers below are the pre-registered baseline (experiments/retrieval_eval).
If a change to `amg.retrieval` alters them, either the change is an improvement
that must be recorded in the experiment README, or it is a regression — in both
cases the test failing is the point.
"""
import importlib.util
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, "experiments", "retrieval_eval")
spec = importlib.util.spec_from_file_location("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)

BASELINE = {
    "overall": {"recall@1": 0.654, "recall@5": 0.865, "recall@10": 0.904, "mrr@10": 0.744},
    "keyword": {"recall@1": 0.812, "recall@5": 0.938, "recall@10": 1.0},
    "paraphrase": {"recall@1": 0.4, "recall@5": 0.75, "recall@10": 0.75},
    "paraphrase-H1": {"recall@5": 0.7},
    "paraphrase-H2": {"recall@5": 0.8},
    "keyword-H1": {"recall@5": 0.875},
    "keyword-H2": {"recall@5": 1.0},
}


def load():
    with open(os.path.join(EVAL_DIR, "corpus.json"), encoding="utf-8") as fh:
        doc = json.load(fh)
    with open(os.path.join(EVAL_DIR, "queries.json"), encoding="utf-8") as fh:
        queries = json.load(fh)["queries"]
    nodes_by_id = {n["id"]: n for n in doc["nodes"]}
    rows = run_eval.stratified_halves(
        run_eval.evaluate(run_eval.retrieval.search, doc, queries, nodes_by_id))
    return doc, queries, rows


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.doc, self.queries, self.rows = load()

    def group(self, rows):
        return {k: run_eval.aggregate(v) for k, v in {
            "overall": rows,
            "keyword": [r for r in rows if r["bucket"] == "keyword"],
            "paraphrase": [r for r in rows if r["bucket"] == "paraphrase"],
            "paraphrase-H1": [r for r in rows if r.get("half") == "paraphrase-H1"],
            "paraphrase-H2": [r for r in rows if r.get("half") == "paraphrase-H2"],
            "keyword-H1": [r for r in rows if r.get("half") == "keyword-H1"],
            "keyword-H2": [r for r in rows if r.get("half") == "keyword-H2"],
        }.items()}

    def test_baseline_numbers_are_unchanged(self):
        groups = self.group(self.rows)
        for name, expected in BASELINE.items():
            for metric, value in expected.items():
                self.assertAlmostEqual(groups[name][metric], value, places=3,
                                       msg=f"{name} {metric} drifted")

    def test_buckets_are_measured_not_intended(self):
        for item in self.queries:
            self.assertNotIn("bucket", item, "queries.json must not declare buckets")
        for row in self.rows:
            if row["bucket"] == "paraphrase":
                self.assertLess(row["overlap"], run_eval.PARAPHRASE_OVERLAP)
            else:
                self.assertGreaterEqual(row["overlap"], run_eval.PARAPHRASE_OVERLAP)

    def test_halves_are_balanced_and_deterministic(self):
        sizes = {}
        for row in self.rows:
            sizes[row["half"]] = sizes.get(row["half"], 0) + 1
        self.assertEqual(sizes["paraphrase-H1"], 5)
        self.assertEqual(sizes["paraphrase-H2"], 5)
        self.assertEqual(sizes["keyword-H1"], 8)
        self.assertEqual(sizes["keyword-H2"], 8)
        rows_again = run_eval.stratified_halves(
            run_eval.evaluate(run_eval.retrieval.search, self.doc, self.queries,
                              {n["id"]: n for n in self.doc["nodes"]}))
        self.assertEqual([r["ranked"] for r in self.rows],
                         [r["ranked"] for r in rows_again])

    def test_recall_is_monotone_in_k(self):
        for row in self.rows:
            self.assertLessEqual(row["recall@1"], row["recall@5"] + 1e-9)
            self.assertLessEqual(row["recall@5"], row["recall@10"] + 1e-9)

    def test_every_gold_id_exists_in_corpus(self):
        ids = {n["id"] for n in self.doc["nodes"]}
        for item in self.queries:
            for gold in item["gold"]:
                self.assertIn(gold, ids, f"{item['id']}: gold id not in corpus")


if __name__ == "__main__":
    unittest.main()
