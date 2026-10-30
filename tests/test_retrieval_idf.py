"""IDF term weights: the properties the v0.18.0 ranking change promises.

The point of the change (DECISIONS #28) is that a word which is everywhere must not
outvote the term that answers. These tests pin the mechanism, not a corpus number —
the corpus numbers live in `experiments/retrieval_idf/` and are asserted in
`test_retrieval_eval.py`.
"""
import unittest

from amg import retrieval


def doc_with(nodes):
    return {"schema": "amg/v1", "group": "t", "nodes": nodes, "edges": [], "changes": []}


def node(node_id, label, note="", source="manual", type_="task"):
    return {"id": node_id, "type": type_, "status": "open", "label": label,
            "note": note, "source": source, "evidence": []}


class IdfRankingTests(unittest.TestCase):
    def test_a_rare_word_beats_many_common_ones(self):
        nodes = [node(f"task.noise{i}", "the graph file", "the graph file is here")
                 for i in range(20)]
        nodes.append(node("task.zebra", "The graph file", "a zebra crossing"))
        hits = retrieval.search(doc_with(nodes), "graph zebra", k=3)
        self.assertEqual(hits[0]["id"], "task.zebra",
                         "the node with the rare term must outrank common-word matches")

    def test_common_word_only_corpus_still_returns_matches(self):
        # IDF is positive for every finite df, so "in every node" never means "no hit".
        nodes = [node(f"task.c{i}", "the graph", "the graph") for i in range(5)]
        hits = retrieval.search(doc_with(nodes), "graph", k=10)
        self.assertEqual(len(hits), 5)
        self.assertTrue(all(h["score"] > 0 for h in hits))

    def test_repeating_a_query_word_does_not_inflate_the_score(self):
        nodes = [node("task.a", "zebra"), node("task.b", "giraffe zebra")]
        once = retrieval.search(doc_with(nodes), "zebra", k=2)
        twice = retrieval.search(doc_with(nodes), "zebra zebra", k=2)
        self.assertEqual([h["id"] for h in once], [h["id"] for h in twice])
        self.assertEqual(once[0]["score"], twice[0]["score"])

    def test_single_term_lookup_ranking_is_field_order_then_id(self):
        # With one term every hit gets the same idf, so the order must stay exactly
        # what constant weights produced: field weight first, then id.
        nodes = [node("task.b", "other", "zebra here"),
                 node("task.a", "zebra", "nothing"),
                 node("task.c", "other", "nothing")]
        hits = retrieval.search(doc_with(nodes), "zebra", k=3)
        self.assertEqual([h["id"] for h in hits], ["task.a", "task.b"])

    def test_scores_are_positive_sorted_and_deterministic(self):
        nodes = [node(f"task.n{i}", "graph queue parser", "synthetic note") for i in range(6)]
        nodes.append(node("task.read", "Log reads", "reads.jsonl rotated at one megabyte"))
        first = retrieval.search(doc_with(nodes), "reads.jsonl rotation", k=5)
        second = retrieval.search(doc_with(nodes), "reads.jsonl rotation", k=5)
        self.assertEqual([h["id"] for h in first], [h["id"] for h in second])
        self.assertEqual([h["score"] for h in first], [h["score"] for h in second])
        scores = [h["score"] for h in first]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(s > 0 for s in scores))

    def test_idf_counts_only_visible_nodes(self):
        # A superseded node must not dilute the rarity of a term: it is not searched,
        # so it is not part of N either.
        live = [node("task.live", "zebra")]
        dead = [dict(node("task.dead", "zebra"), status="superseded")]
        doc = doc_with(live + dead)
        self.assertEqual([h["id"] for h in retrieval.search(doc, "zebra", k=5)],
                         ["task.live"])


if __name__ == "__main__":
    unittest.main()
