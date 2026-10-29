import unittest

from helpers import TempGraph, ev


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m
        self.m.add_node("task.anchored", "task", "并发 打满 限流", source="s 1",
                        note="已打满，证据齐全", evidence=[ev(grade=1)])
        self.m.add_node("task.bare", "task", "并发 打满 观察", source="s 2",
                        note="只有观察，无证据")
        self.m.add_node("rule.limit", "rule", "限流规则 并发<=32", source="s 3",
                        applies="global", expires_when=None)

    def tearDown(self):
        self.g.close()

    def test_anchored_ranks_before_unanchored(self):
        hits = self.m.search("并发 打满")
        self.assertGreaterEqual(len(hits), 2)
        self.assertEqual(hits[0]["id"], "task.anchored")
        self.assertEqual(hits[0]["anchor_state"], "present")
        self.assertEqual(hits[1]["anchor_state"], "none")

    def test_default_keeps_degraded_results(self):
        hits = self.m.search("并发 打满")
        self.assertTrue(any(h["anchor_state"] == "none" for h in hits))

    def test_strict_filters_unanchored(self):
        hits = self.m.search("并发 打满", strict=True)
        self.assertEqual([h["id"] for h in hits], ["task.anchored"])

    def test_l1_and_l4_layers(self):
        self.m.set_status("task.bare", "done", note="closed")
        l1 = self.m.search("并发", layer="L1")
        self.assertNotIn("task.bare", [h["id"] for h in l1])
        l4 = self.m.search("限流", layer="L4")
        self.assertEqual([h["id"] for h in l4], ["rule.limit"])

    def test_l2_searches_changes(self):
        hits = self.m.search("add-node", layer="L2")
        self.assertTrue(hits)
        self.assertTrue(all(h["type"] == "change" for h in hits))


    def test_search_never_returns_superseded(self):
        """failures.md:118 — retrieval hard-filters superseded (not negotiable)."""
        self.m.add_node("decision.v1", "decision", "限流阈值 旧版", source="s v1")
        self.m.add_node("decision.v2", "decision", "限流阈值 新版", source="s v2")
        self.m.supersede("decision.v1", "decision.v2", note="v2 替换 v1")
        for layer in ("L1", "L3"):
            ids = [h["id"] for h in self.m.search("限流", layer=layer)]
            self.assertNotIn("decision.v1", ids, f"{layer} returned a superseded node")
            self.assertIn("decision.v2", ids, layer)
        self.m.add_node("rule.old", "rule", "限流规则 旧", source="s r1",
                        applies="global", expires_when=None)
        self.m.add_node("rule.new", "rule", "限流规则 新", source="s r2",
                        applies="global", expires_when=None)
        self.m.supersede("rule.old", "rule.new", note="新规则替换")
        l4 = [h["id"] for h in self.m.search("限流", layer="L4")]
        self.assertNotIn("rule.old", l4, "L4 returned a superseded rule")
        self.assertIn("rule.new", l4)

    def test_history_stays_in_l2_after_supersede(self):
        """Filtering superseded must not erase history: L2 keeps the change log."""
        self.m.add_node("decision.v1", "decision", "限流阈值 旧版", source="s v1")
        self.m.add_node("decision.v2", "decision", "限流阈值 新版", source="s v2")
        self.m.supersede("decision.v1", "decision.v2", note="v2 替换 v1")
        hits = self.m.search("supersede", layer="L2")
        self.assertTrue(hits, "L2 lost the supersede event")
        self.assertTrue(all(h["type"] == "change" for h in hits))


if __name__ == "__main__":
    unittest.main()
