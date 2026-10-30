"""Pinned precision semantics of the lexical matcher (v0.14.0, DECISIONS #25).

The recall experiment (`experiments/retrieval_eval/`) says how many gold answers are
found; these tests say what must **not** be found, which is the half a recall number
cannot see. Criteria were pre-registered in
`experiments/retrieval_precision/PREREGISTRATION.md`.
"""
import unittest

from helpers import TempGraph


class MatcherPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m
        self.m.add_node("task.read-audit", "task", "high-risk reads are logged",
                        source="s 1", note="query text is appended to reads.jsonl")
        self.m.add_node("decision.two-key-ranking", "decision", "ranking is two-key",
                        source="s 2", note="nodes with evidence come first")
        self.m.add_node("task.并发", "task", "并发 打满 限流", source="s 3")
        self.m.add_node("task.plain", "task", "unrelated note", source="s 4")

    def tearDown(self):
        self.g.close()

    def test_single_letter_query_returns_nothing(self):
        for query in ("a", "e", "i", "x"):
            self.assertEqual(self.m.search(query, layer="L3"), [], query)
            self.assertEqual(self.m.search(query, layer="L2"), [], query)

    def test_identifier_lookup_returns_the_node_first(self):
        hits = self.m.search("task.read-audit", layer="L3")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "task.read-audit")

    def test_identifier_for_missing_node_returns_nothing(self):
        for query in ("task.a", "issue.zzz", "missing.node"):
            self.assertEqual(self.m.search(query, layer="L3"), [], query)

    def test_identifier_inside_a_sentence_is_still_one_token(self):
        hits = self.m.search("reads.jsonl rotation", layer="L3")
        self.assertEqual([h["id"] for h in hits], ["task.read-audit"])

    def test_regular_inflections_match(self):
        # "rank" must find "ranking": the eval measured the recall this costs otherwise.
        self.assertEqual([h["id"] for h in self.m.search("rank", layer="L3")],
                         ["decision.two-key-ranking"])
        self.assertEqual([h["id"] for h in self.m.search("ranked", layer="L3")],
                         ["decision.two-key-ranking"])

    def test_words_are_not_matched_inside_other_words(self):
        # "read" must not match "reads.jsonl"? it does, as a word start with a suffix —
        # but "hea" (no such word) must match nothing even though it is inside "high".
        self.assertEqual(self.m.search("hea", layer="L3"), [])
        self.assertEqual(self.m.search("nked", layer="L3"), [])

    def test_cjk_still_matches_as_substring(self):
        self.assertEqual([h["id"] for h in self.m.search("限流", layer="L3")], ["task.并发"])
        self.assertEqual([h["id"] for h in self.m.search("并", layer="L3")], ["task.并发"])

    def test_partial_identifier_matches_by_design(self):
        # `-`, `.`, `_` and `/` are word separators, so typing a prefix of an id is a
        # useful lookup; typing a fragment from the middle is not (asserted above).
        # Documented rather than accidental: see docs/API.md "Retrieval rules".
        hits = self.m.search("task.read", layer="L3")
        self.assertIn("task.read-audit", [h["id"] for h in hits])
        self.assertEqual(self.m.search("read.audit", layer="L3"), [])


if __name__ == "__main__":
    unittest.main()
