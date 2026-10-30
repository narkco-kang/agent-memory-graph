"""Bounded, labelled scores: the two properties v0.19.0 added (issues R1/R2).

R1: a score must not grow without limit as the graph grows, and must stay within the
weighted-evidence bound. R2: a consumer must be able to tell an IDF score from a
constant recency score and from an expansion stub, so the three are never merged.

The stronger invariant — that the normalization changes no rank at all — is checked
against the frozen v0.18.0 scorer in `experiments/score_scale/` and pinned by the
numbers in `tests/test_retrieval_eval.py`.
"""
import unittest

from amg import retrieval

FIELD_WEIGHT_SUM = sum(retrieval.WEIGHTS.values())  # 7.0: a term matched in every field


def node(node_id, label="", note="", source="manual", type_="task", status="open"):
    return {"id": node_id, "type": type_, "status": status, "label": label,
            "note": note, "source": source, "evidence": []}


def doc(nodes, edges=None, changes=None):
    return {"schema": "amg/v1", "group": "t", "nodes": nodes,
            "edges": edges or [], "changes": changes or []}


class BoundedScoreTests(unittest.TestCase):
    def test_a_term_matching_every_field_stays_inside_the_bound(self):
        n = node("zebra", label="zebra", note="zebra", source="zebra")
        n["owner"] = "zebra"
        hits = retrieval.search(doc([n]), "zebra", k=1)
        self.assertEqual(len(hits), 1)
        self.assertGreater(hits[0]["score"], 0)
        self.assertLessEqual(hits[0]["score"], FIELD_WEIGHT_SUM + 1e-9)

    def test_score_does_not_grow_with_unrelated_nodes(self):
        query = "zebra"
        gold = node("task.zebra", label="zebra")
        small = doc([gold] + [node(f"task.n{i}", label="parser queue") for i in range(20)])
        large = doc([gold] + [node(f"task.n{i}", label="parser queue") for i in range(500)])
        first = retrieval.search(small, query, k=1)[0]["score"]
        second = retrieval.search(large, query, k=1)[0]["score"]
        self.assertLessEqual(second, FIELD_WEIGHT_SUM)
        # Bounded drift: the saturating ln ratio can lift this, but never toward
        # the old unbounded behaviour (which multiplied with N).
        self.assertLess(second, first * 1.5)

    def test_larger_graph_does_not_reorder_the_gold_above_a_competitor(self):
        gold = node("task.zebra", label="zebra crossing")
        rival = node("task.rival", label="zebra")
        base = doc([gold, rival])
        scaled = doc([gold, rival] + [node(f"task.n{i}", label="unrelated words")
                                      for i in range(300)])
        self.assertEqual([h["id"] for h in retrieval.search(base, "zebra crossing", k=5)],
                         [h["id"] for h in retrieval.search(scaled, "zebra crossing", k=5)])


class ScoreKindTests(unittest.TestCase):
    def test_l3_hits_are_idf_scored(self):
        hits = retrieval.search(doc([node("task.a", label="zebra")]), "zebra", k=3)
        self.assertTrue(hits)
        self.assertTrue(all(h["score_kind"] == "idf" for h in hits))

    def test_l2_hits_are_recency_scored_and_never_claim_idf(self):
        changes = [{"op": "add", "target": "task.a", "note": "zebra", "rev": 1,
                    "at": "2026-10-31T00:00:00+08:00"}]
        hits = retrieval.search(doc([node("task.a", label="zebra")], changes=changes),
                                "zebra", layer="L2", k=3)
        self.assertTrue(hits)
        self.assertTrue(all(h["score_kind"] == "recency" for h in hits))

    def test_expanded_neighbours_are_marked_as_expansion(self):
        nodes = [node("task.a", label="zebra"), node("task.b", label="neighbour")]
        edges = [{"from": "task.a", "to": "task.b", "kind": "relates_to"}]
        hits = retrieval.search(doc(nodes, edges=edges), "zebra", k=5, expand=True)
        kinds = {h["id"]: h["score_kind"] for h in hits}
        self.assertEqual(kinds["task.a"], "idf")
        self.assertEqual(kinds["task.b"], "expansion")

    def test_archived_l2_hits_are_recency_scored(self):
        archived = [{"file": "archive/changes-0001.json", "record": {
            "op": "add", "target": "task.a", "note": "zebra", "rev": 1,
            "at": "2026-10-30T00:00:00+08:00"}}]
        hits = retrieval.search(doc([node("task.a")]), "zebra", layer="L2", k=3,
                                archived=archived)
        self.assertTrue(hits[0].get("archived"))
        self.assertEqual(hits[0]["score_kind"], "recency")


if __name__ == "__main__":
    unittest.main()
