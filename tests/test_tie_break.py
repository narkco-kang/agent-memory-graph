"""Ranking ties: the order is deterministic, the tie-break is the id, and the surface is measured.

The project ships a rule (`retrieval.rank_key`): the score rounded to three decimals, then
anchored-ness (v0.36.0 — it used to be first, which made it a gate rather than a preference),
then the node id reversed. That makes runs reproducible, but it also means a boundary tie
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

    def test_anchor_decides_only_an_exact_tie(self):
        """v0.36.0: anchoring is a tie-breaker, not a gate (DECISIONS #3, amended by #55).

        The old rule ranked anchored hits above any score, so an unanchored node could not
        beat a stray anchored one at 0.1 against 9.9. On the team's own graph that made an
        unanchored node unreachable for its own label: 0/40 against 40/40 for anchored ones.
        Now the score decides, and anchoring only breaks a tie in its favour.
        """
        self.assertGreater(retrieval.rank_key(9.9, False, "z"),
                           retrieval.rank_key(0.1, True, "a"),
                           "a much higher score must beat a low-score anchored hit")
        self.assertGreater(retrieval.rank_key(1.0, True, "a"),
                           retrieval.rank_key(1.0, False, "z"),
                           "at an exact tie the anchored hit still comes first")

    def test_anchored_hit_wins_an_exact_tie_against_unanchored(self):
        """Preserved property, NOT the regression guard for #55.

        At an exact score tie the anchored hit still comes first: the tie-break survived the
        demotion. This passes under the old key too, so it cannot catch a regression of #55.
        The guards that do fail under the old order are `test_anchor_decides_only_an_exact_tie`
        and `test_key_prefers_score_over_anchoring`.
        """
        tied_unanchored = [node(f"u{i:03d}", evidence=False) for i in range(10)]
        document = doc(tied_unanchored + [node("a001", evidence=True),
                                          node("a002", evidence=True)])
        hit_ids = [hit["id"] for hit in retrieval.search(document, "alpha beta", layer="L3", k=5)]
        self.assertEqual(hit_ids[:2], ["a002", "a001"],
                         "anchored hits must not be pushed out of top-k at equal scores")

    def test_key_prefers_score_over_anchoring(self):
        """Judgement-form guard on the measured pair: 1.313 anchored vs 3.527 unanchored.

        Glm measured that pair on the real graph. Under the old key `(anchor, score, id)` both
        comparisons below were false — anchoring beat any score, so a 3.5-point correct answer
        lost to a 1.3-point anchored stray. Keep the measured numbers; they are not arbitrary.
        """
        self.assertGreater(retrieval.rank_key(3.527, False, "z999"),
                           retrieval.rank_key(1.313, True, "a001"),
                           "score must outrank anchoring, not the other way round")
        self.assertGreater(retrieval.rank_key(0.0, False, "a"),
                           retrieval.rank_key(-1.0, True, "z"),
                           "even a tiny score lead must beat anchoring")

    def test_unanchored_target_beats_partly_matching_anchored_noise(self):
        """A5: the regression that motivated #55 — an unanchored node could not find itself.

        The noise is deliberately NOT zero-match: 20 anchored nodes that partly match the query
        also score, so under the old key they filled top-k ahead of the correct unanchored node.
        Zero-match noise ("unrelated filler text") passes under any ordering and proves nothing —
        that was Glm's finding in issue.mem-arch-v036-new-tests-do-not-catch-mutation.
        """
        noise = [node(f"z{i:03d}", label="quantum filler padding text", evidence=True)
                 for i in range(20)]
        target = node("target",
                      label="quantum widgets quantum widgets quantum widgets",
                      evidence=False)
        document = doc(noise + [target])
        hits = retrieval.search(document, target["label"], layer="L3", k=5)
        self.assertEqual(len(hits), 5, "the fixture must fill top-k with real candidates")
        self.assertEqual(hits[0]["id"], "target",
                         "the correct answer must rank first whatever its anchor state")
        self.assertEqual(hits[0]["anchor_state"], "none")

    def test_strict_still_returns_anchored_hits_only(self):
        """The change moves the anchor out of the ordering key; it must not touch the filter."""
        document = doc([node("plain", evidence=False), node("withproof", evidence=True)])
        strict_ids = [hit["id"] for hit in
                      retrieval.search(document, "alpha beta", layer="L3", k=10, strict=True)]
        self.assertEqual(strict_ids, ["withproof"])

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
