"""Ranking ties: the order is deterministic, the tie-break is the id, and the surface is measured.

The project ships a rule (`retrieval.rank_key`): anchored first, then the score rounded to three
decimals, then the node id reversed. That makes runs reproducible, but it also means a boundary tie
is resolved by an identifier rather than by relevance — and more than half of the real-text queries
end on such a tie. These tests pin the rule and the measurement, so a future weight change cannot
quietly "gain" a query by flipping a tie.
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys

sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import retrieval  # noqa: E402

ART = os.path.join(ROOT, "experiments", "retrieval_noise_realtext")


def node(nid, label="alpha beta", note="gamma delta", evidence=False):
    payload = {"id": nid, "label": label, "note": note, "type": "task",
               "status": "active", "source": "fixture"}
    if evidence:
        payload["evidence"] = [{"locator": "path:fixture.txt",
                                "content_sha256": "0" * 64,
                                "captured_at": "2026-01-01T00:00:00Z"}]
    return payload


def doc(nodes):
    return {"schema": "amg/v1", "group": "tie-fixture", "nodes": nodes, "edges": [], "changes": []}


class RankKeyTest(unittest.TestCase):
    def test_id_breaks_an_exact_tie_descending(self):
        self.assertGreater(retrieval.rank_key(1.0, False, "n003"),
                           retrieval.rank_key(1.0, False, "n002"))
        self.assertGreater(retrieval.rank_key(1.0, False, "n002"),
                           retrieval.rank_key(1.0, False, "n001"))

    def test_anchor_outranks_any_score(self):
        self.assertGreater(retrieval.rank_key(0.1, True, "a"),
                           retrieval.rank_key(9.9, False, "z"))

    def test_scores_equal_after_rounding_tie(self):
        """The ordering score is rounded to the displayed precision, so 0.0004 apart is a tie."""
        self.assertEqual(retrieval.rank_key(1.0004, False, "a"),
                         retrieval.rank_key(1.0001, False, "a"))

    def test_search_returns_a_tie_in_id_order_and_is_deterministic(self):
        document = doc([node("n001"), node("n002"), node("n003"), node("a999", evidence=True)])
        first = [(hit["id"], hit["score"]) for hit in
                 retrieval.search(document, "alpha beta", layer="L3", k=10)]
        second = [(hit["id"], hit["score"]) for hit in
                  retrieval.search(document, "alpha beta", layer="L3", k=10)]
        self.assertEqual(first, second)
        self.assertEqual([nid for nid, _score in first], ["a999", "n003", "n002", "n001"])
        self.assertEqual(len({score for _nid, score in first}), 1,
                         "the fixture must produce one exact tie to test the tie-break")


class TieSurfaceTest(unittest.TestCase):
    #: Measured at the pinned corpus; a change here means the evaluation surface moved.
    EXPECTED_K5 = {"realtext": 10, "n2": 10, "control": 5}

    def setUp(self):
        with open(os.path.join(ART, "result.json"), encoding="utf-8") as fh:
            self.result = json.load(fh)
        with open(os.path.join(ART, "ledger.json"), encoding="utf-8") as fh:
            self.ledger = json.load(fh)

    def test_every_arm_reports_its_tie_surface(self):
        for name, arm in self.result["arms"].items():
            surface = arm["tie_surface"]
            for cutoff in ("k5", "k10"):
                self.assertEqual(surface[cutoff]["queries"], len(surface[cutoff]["ids"]),
                                 f"{name}: {cutoff} count and id list disagree")
                self.assertLessEqual(surface[cutoff]["queries"], 26)

    def test_pinned_tie_surface_is_unchanged(self):
        for name, expected in self.EXPECTED_K5.items():
            self.assertEqual(self.result["arms"][name]["tie_surface"]["k5"]["queries"], expected,
                             f"{name}: boundary-tie count moved; re-review every quoted number")

    def test_ledger_rows_agree_with_the_arm_surface(self):
        tied = [row["id"] for row in self.ledger["rows"] if row["boundary_tie_at_5"]]
        self.assertEqual(tied, self.result["arms"]["realtext"]["tie_surface"]["k5"]["ids"])
        self.assertGreaterEqual(len(tied), 10,
                                "the real-text boundary-tie surface moved; re-review the sweep")


if __name__ == "__main__":
    unittest.main()
