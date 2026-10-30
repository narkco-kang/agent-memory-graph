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
candidates = run_eval.candidate_mod

REQUIRED_KEYS = {"id", "label", "type", "status", "score", "matched_fields",
                 "anchor_state", "evidence_count", "conclusion"}


def usable_candidates(doc):
    """Candidates that can actually run here: model-backed ones need a daemon."""
    out = {}
    for name, cand in candidates.CANDIDATES.items():
        if getattr(cand, "COST", "none") == "optional-model":
            try:
                cand.search(doc, "probe", k=1)
            except Exception:  # no daemon / no model on this host (e.g. CI)
                continue
        out[name] = cand
    return out

# v0.14.0 moved these on purpose (word-boundary + inflection matching, identifier
# lookups; DECISIONS #25). Previous values, kept for audit rather than overwritten:
#   overall  r@1 0.654  r@5 0.865  r@10 0.904  mrr 0.744
#   keyword  r@1 0.812  r@5 0.938  r@10 1.000
#   paraphrase r@1 0.400 r@5 0.750 r@10 0.750
# The per-query analysis of what moved and why is in
# experiments/retrieval_precision/PREREGISTRATION.md.
BASELINE = {
    "overall": {"recall@1": 0.654, "recall@5": 0.808, "recall@10": 0.865, "mrr@10": 0.763},
    "keyword": {"recall@1": 0.875, "recall@5": 0.969, "recall@10": 0.969},
    "paraphrase": {"recall@1": 0.3, "recall@5": 0.55, "recall@10": 0.7},
    "paraphrase-H1": {"recall@5": 0.5},
    "paraphrase-H2": {"recall@5": 0.6},
    "keyword-H1": {"recall@5": 0.938},
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


class CandidateTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(EVAL_DIR, "corpus.json"), encoding="utf-8") as fh:
            self.doc = json.load(fh)

    def test_every_candidate_returns_the_shared_shape(self):
        cands = usable_candidates(self.doc)
        self.assertTrue({"bm25", "hashed-vec"} <= set(cands))
        for name, cand in cands.items():
            hits = cand.search(self.doc, "atomic replace", k=3)
            self.assertTrue(hits, f"{name} returned nothing for a keyword query")
            self.assertLessEqual(len(hits), 3)
            for hit in hits:
                self.assertTrue(REQUIRED_KEYS <= set(hit), f"{name} shape drifted")
                self.assertIn(hit["anchor_state"], {"present", "none"})

    def test_every_candidate_applies_the_hard_filters(self):
        doc = {"nodes": [
            {"id": "task.live", "type": "task", "status": "open", "label": "zebra",
             "note": "zebra stripes", "source": "test"},
            {"id": "task.dead", "type": "task", "status": "superseded", "label": "zebra",
             "note": "zebra stripes", "source": "test"},
            {"id": "task.future", "type": "task", "status": "open", "label": "zebra",
             "note": "zebra stripes", "source": "test",
             "valid_from": "2999-01-01T00:00:00+00:00"},
        ], "edges": [], "changes": []}
        for name, cand in usable_candidates(doc).items():
            ids = [h["id"] for h in cand.search(doc, "zebra", k=10)]
            self.assertIn("task.live", ids, name)
            self.assertNotIn("task.dead", ids, f"{name} returned a superseded node")
            self.assertNotIn("task.future", ids, f"{name} returned a not-yet-valid node")

    def test_verdict_rejects_a_regression_and_accepts_a_clean_gain(self):
        baseline = {"paraphrase-H1": {"recall@5": 0.7}, "paraphrase-H2": {"recall@5": 0.8},
                    "keyword-H1": {"recall@5": 0.938}, "keyword-H2": {"recall@5": 1.0}}
        worse = {"paraphrase-H1": {"recall@5": 0.3}, "paraphrase-H2": {"recall@5": 0.6},
                 "keyword-H1": {"recall@5": 0.938}, "keyword-H2": {"recall@5": 0.9}}
        decision = run_eval.verdict(baseline, worse, cost="none")
        self.assertFalse(decision["adopted"])
        self.assertIn("C1 paraphrase-H1", decision["failed"])
        self.assertIn("C2 keyword-H2", decision["failed"])

        better = {"paraphrase-H1": {"recall@5": 0.9}, "paraphrase-H2": {"recall@5": 1.0},
                  "keyword-H1": {"recall@5": 0.938}, "keyword-H2": {"recall@5": 1.0}}
        self.assertTrue(run_eval.verdict(baseline, better, cost="none")["adopted"])
        # A model download may not become the default path.
        self.assertFalse(run_eval.verdict(baseline, better, cost="optional-model")["adopted"])

    def test_measured_candidates_are_not_adopted(self):
        # Both candidates lost to the baseline. If this ever flips, the experiment
        # README must be updated with the new numbers in the same commit.
        with open(os.path.join(EVAL_DIR, "corpus.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        with open(os.path.join(EVAL_DIR, "queries.json"), encoding="utf-8") as fh:
            queries = json.load(fh)["queries"]
        nodes_by_id = {n["id"]: n for n in doc["nodes"]}
        base = run_eval.stratified_halves(
            run_eval.evaluate(run_eval.retrieval.search, doc, queries, nodes_by_id))
        base_groups = {k: run_eval.aggregate(v) for k, v in run_eval.group_rows(base).items()}
        for name in ("bm25", "hashed-vec"):
            rows = run_eval.stratified_halves(
                run_eval.evaluate(candidates.CANDIDATES[name].search, doc, queries, nodes_by_id))
            groups = {k: run_eval.aggregate(v) for k, v in run_eval.group_rows(rows).items()}
            decision = run_eval.verdict(base_groups, groups,
                                        cost=candidates.CANDIDATES[name].COST)
            self.assertFalse(decision["adopted"], f"{name} now passes; update the README")
            self.assertIn("C1 paraphrase-H1", decision["failed"])


class LocalEmbeddingCandidateTests(unittest.TestCase):
    """Skipped unless a local embedding model is reachable; CI has none."""

    def setUp(self):
        cand = candidates.CANDIDATES.get("local-embed")
        if cand is None:
            self.skipTest("local-embed candidate not registered")
        with open(os.path.join(EVAL_DIR, "corpus.json"), encoding="utf-8") as fh:
            self.doc = json.load(fh)
        try:
            cand.search(self.doc, "atomic replace", k=1)
        except Exception as exc:  # daemon absent, model missing, network blocked
            self.skipTest(f"local embedding model unavailable: {type(exc).__name__}")
        self.cand = cand

    def test_it_is_still_not_adopted_but_is_measurably_better(self):
        with open(os.path.join(EVAL_DIR, "queries.json"), encoding="utf-8") as fh:
            queries = json.load(fh)["queries"]
        nodes_by_id = {n["id"]: n for n in self.doc["nodes"]}
        base = run_eval.stratified_halves(
            run_eval.evaluate(run_eval.retrieval.search, self.doc, queries, nodes_by_id))
        rows = run_eval.stratified_halves(
            run_eval.evaluate(self.cand.search, self.doc, queries, nodes_by_id))
        base_groups = {k: run_eval.aggregate(v) for k, v in run_eval.group_rows(base).items()}
        groups = {k: run_eval.aggregate(v) for k, v in run_eval.group_rows(rows).items()}

        # The measurement: a real embedding model roughly closes the paraphrase gap.
        self.assertGreaterEqual(groups["paraphrase"]["recall@5"],
                                base_groups["paraphrase"]["recall@5"] + 0.15)
        # The decision: it still may not be the default path (C3: 274 MB model).
        decision = run_eval.verdict(base_groups, groups, cost=self.cand.COST)
        self.assertFalse(decision["adopted"], "update the experiment README if this flips")
        self.assertIn("C3 cost", decision["failed"])
