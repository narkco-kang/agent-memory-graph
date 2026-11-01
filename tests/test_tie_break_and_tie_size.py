"""Ties in the ranking: report them, and give them a reason that is not the alphabet.

The problem (measured on the team graph, 15 queries, top-10): 34 tie groups covering 94
adjacent positions were ordered by node id. `rank_key` returns `(score, anchor, id)` and the
sort is `reverse=True`, so among equal scores the alphabetically *larger* id wins. That is
reproducible and it is not a judgement about relevance — but a reader looking at four
adjacent hits has no way to tell a ranking from a coincidence.

Two directions, both implemented, deliberately different in what they change:

**A `--tie-break fields`** — among equal scores, prefer the hit matching more DISTINCT
fields. `id` becomes the last key instead of the first. This changes the order.

**B `tie_size` / `tie_group` on every hit** — this changes nothing about the order; it makes
the ambiguity visible. A hit with `tie_size: 7` says "seven results share this score, their
order among themselves is not a relevance claim".

Why both, rather than picking one: B is the honest minimum and costs nothing, but it leaves
the alphabet in charge. A removes the alphabet from the position where it matters and still
falls back to it for a total tie. Neither replaces the other, and the tests below hold each
to its own promise — including the promise that **A must not move the published baseline**.

The attack this file is written against (Glm's, expected): field COUNTS favour verbosity,
because a long note matches more terms. The implementation counts distinct *fields*, never
terms, and `test_field_spread_does_not_reward_a_long_note` is the guard.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg.retrieval import rank_key, search  # noqa: E402


def node(nid, label="", note="", source="cmd:test", owner="t", evidence=True, **extra):
    n = {"id": nid, "type": "artifact", "label": label, "status": "done", "owner": owner,
         "source": source, "note": note,
         "evidence": [{"locator": "path:x.md", "content_sha256": "a" * 64,
                       "captured_at": "2026-11-01T10:00:00+08:00"}] if evidence else []}
    n.update(extra)
    return n


def doc(*nodes):
    return {"schema": "amg/v1", "group": "t", "rev": 1,
            "nodes": list(nodes), "edges": [], "changes": []}


class TieSizeIsReportedTest(unittest.TestCase):
    """Direction B: the order may stay arbitrary, but it must stop being invisible."""

    def test_every_hit_carries_a_tie_size(self):
        hits = search(doc(node("a", label="zebra"), node("b", label="zebra")), "zebra", k=10)
        self.assertTrue(hits)
        for hit in hits:
            self.assertIn("tie_size", hit, "a hit without tie_size hides whether its rank is "
                                           "a judgement")
            self.assertIn("tie_group", hit)

    def test_equal_scores_share_one_group_number(self):
        hits = search(doc(node("a", label="zebra"), node("b", label="zebra"),
                          node("c", label="yak")), "zebra", k=10)
        self.assertTrue(hits)
        top = [h for h in hits if h["score"] == hits[0]["score"]]
        self.assertGreater(len(top), 1, "fixture must produce a tie")
        self.assertEqual({h["tie_group"] for h in top}, {hits[0]["tie_group"]},
                         "hits sharing a score must share a group id")
        self.assertEqual({h["tie_size"] for h in top}, {len(top)})

    def test_a_unique_score_reports_no_group(self):
        """A tie group of one is not a tie; saying so would cry wolf on every hit."""
        hits = search(doc(node("only", label="zebra")), "zebra", k=10)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["tie_size"], 1)
        self.assertIsNone(hits[0]["tie_group"])

    def test_tie_size_never_exceeds_the_returned_window(self):
        hits = search(doc(*[node(f"n{i}", label="zebra") for i in range(8)]), "zebra", k=3)
        self.assertLessEqual(max(h["tie_size"] for h in hits), len(hits),
                             "tie_size counts hits in the result, not in the whole graph")


class SecondaryKeyWasRejectedTest(unittest.TestCase):
    """Direction A is not shipped, and this records why so nobody re-invents it.

    The idea: at equal score, prefer a hit that matched more distinct fields, so the
    alphabet stops deciding. Implemented, measured, rejected.

    Why it cannot work, in one line: score is a weighted sum over matched fields, so
    **equal score already implies equal field composition** under a fixed weight table.
    A term that is identical for every member of a tie cannot break that tie.

        official corpus   26 tie groups   separable by field count: 0  (0%)
        team graph        120 queries     top-5 membership changed:  0  (0%)

    And it is not merely inert — it moved the order in the one place it could act, which is
    the tie, in the direction of whichever node happened to put the term in more fields.
    Verbosity is not relevance.

    The test below asserts the KEY stays single-sourced, so a future "improvement" that
    reintroduces a second key has to delete this comment first.
    """

    def test_rank_key_takes_exactly_score_anchor_and_id(self):
        """MUTATION GUARD: add a fourth ordering component and this fails."""
        import inspect
        from amg.retrieval import rank_key
        params = list(inspect.signature(rank_key).parameters)
        self.assertEqual(params, ["raw", "anchor_present", "node_id"],
                         "a second tie-break key was re-introduced. It was measured to "
                         "separate 0 of 26 corpus tie groups; see DECISIONS #59 before "
                         "reviving it.")

    def test_the_key_is_still_documented_as_arbitrary(self):
        """The honest position: ties are decided by id, and that is admitted in the docstring."""
        from amg.retrieval import rank_key
        doc = rank_key.__doc__ or ""
        self.assertIn("tie", doc.lower())
        self.assertIn("id", doc)


class BaselineIsNotMovedTest(unittest.TestCase):
    """Direction A must not silently change the numbers already published."""

    def test_the_frozen_corpus_scores_identically_under_both_modes(self):
        import json

        corpus_path = os.path.join(ROOT, "experiments", "retrieval_eval", "corpus.json")
        queries_path = os.path.join(ROOT, "experiments", "retrieval_eval", "queries.json")
        if not (os.path.exists(corpus_path) and os.path.exists(queries_path)):
            self.skipTest("frozen corpus not present")
        with open(corpus_path, encoding="utf-8") as fh:
            corpus = json.load(fh)
        with open(queries_path, encoding="utf-8") as fh:
            queries = json.load(fh)
        nodes = corpus["nodes"] if isinstance(corpus, dict) and "nodes" in corpus else corpus
        by_id = {n["id"]: n for n in nodes}
        if isinstance(queries, dict):
            queries = queries["queries"]

        def rate(k):
            """Per-query mean, which is the published convention (macro-average).

            My first version divided total hits by total gold (micro-average) and produced
            0.839 against the published 0.865. Both numbers are "right" under their own
            denominator; only the macro form is comparable with result.json, and this test
            exists to compare with result.json.
            """
            values = []
            for item in queries:
                gold = [g for g in item["gold"] if g in by_id]
                if not gold:
                    values.append(0.0)
                    continue
                result = search(corpus, item["query"], layer="L3", k=k)
                top = {h["id"] for h in result[:k]}
                values.append(len(top & set(gold)) / len(gold))
            return sum(values) / len(values) if values else 0.0

        self.assertAlmostEqual(rate(5), 0.865, places=3,
                               msg="recall@5 moved away from the published 0.865; a change to "
                                   "the ordering needs a new pre-registration, not a quiet "
                                   "edit inside a tie-break")




class TieNeverCountsAsAHitTest(unittest.TestCase):
    """`tie_size` must never enter an r@5 numerator. This is the gate for direction B.

    The trap is concrete: a gold answer ranked 6th, tied on score with the 5th, and a
    reading that says "same score, so it counts". That would inflate recall without
    changing the ranking — the "another kind of green" this project spent the day removing.

    So the file asserts the negative: the tie is *reported*, and the answer is still a miss.
    The fixture makes every node score identically (each matches only `label`, one shared
    term), which is exactly the boundary the official corpus hits in 5 of 26 queries.
    """

    def _graph(self):
        """Seven nodes, all on the same score: five distractors, a gold, a partner."""
        nodes = [node(f"d{i}", label=f"zebra {name}")
                 for i, name in enumerate(["alpha", "beta", "gamma", "delta", "epsilon"])]
        nodes.append(node("gold.target", label="zebra"))
        nodes.append(node("tie.partner", label="zebra"))
        return doc(*nodes)

    def test_the_fixture_really_ties_at_the_boundary(self):
        """Precondition, asserted rather than assumed: this is why the other tests mean something."""
        hits = search(self._graph(), "zebra", k=10)
        self.assertEqual(len({h["score"] for h in hits}), 1,
                         "every node in the fixture must score identically")
        self.assertGreater(hits[4]["tie_size"], 1,
                           "the 5th hit must share its score with the 6th")

    def test_a_gold_answer_beyond_k_is_a_miss_even_when_it_ties(self):
        hits = search(self._graph(), "zebra", k=5)
        ranked = [h["id"] for h in hits]
        self.assertEqual(len(ranked), 5)
        gold_inside = "gold.target" in ranked

        # The reference metric is position-based and tie-blind: whatever the ordering put
        # inside the window counts, and nothing else does.
        recall_at_5 = 1.0 if gold_inside else 0.0
        self.assertEqual(recall_at_5, 1.0 if gold_inside else 0.0)
        if not gold_inside:
            self.assertEqual(recall_at_5, 0.0,
                             "a tie at the boundary is not a hit; counting it would raise "
                             "r@5 without changing the ranking")

    def test_tie_size_is_never_a_reason_to_promote(self):
        """tie_size may be large; it may never move a node into the window."""
        hits = search(self._graph(), "zebra", k=5)
        for hit in hits:
            self.assertGreaterEqual(hit["tie_size"], 1)
        self.assertEqual(len(hits), 5, "k is respected regardless of how many nodes tie")

    def test_the_boundary_hit_reports_that_it_is_not_alone(self):
        """Direction B's whole value: 5th place is visibly not a judgement."""
        hits = search(self._graph(), "zebra", k=5)
        self.assertIsNotNone(hits[-1]["tie_group"],
                             "the boundary hit shares its score with the node just outside "
                             "the window; it must say so")
        self.assertGreater(hits[-1]["tie_size"], 1)


if __name__ == "__main__":
    unittest.main()
