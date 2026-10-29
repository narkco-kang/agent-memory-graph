import unittest

from helpers import TempGraph, ev


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m
        self.m.add_node("task.hot", "task", "正在做的事", source="s", status="in_progress")
        self.m.add_node("task.block", "task", "被卡住的事", source="s", status="blocked")
        self.m.add_node("decision.d1", "decision", "一个结论" * 120, source="s",
                        status="done", evidence=[ev()])

    def tearDown(self):
        self.g.close()

    def test_digest_is_bounded(self):
        text = self.m.digest(max_bytes=250)
        self.assertLessEqual(len(text.encode("utf-8")), 250)
        self.assertIn("truncated", text)

    def test_priority_order(self):
        text = self.m.digest(max_bytes=65536)
        self.assertLess(text.index("task.hot"), text.index("task.block"))
        self.assertLess(text.index("task.block"), text.index("decision.d1"))

    def test_note_is_truncated_and_no_payload(self):
        text = self.m.digest()
        self.assertIn("…", text)
        self.assertNotIn("a" * 64, text)  # sha never copied into the digest

    def test_digest_points_at_ids(self):
        text = self.m.digest()
        for nid in ("task.hot", "task.block", "decision.d1"):
            self.assertIn(nid, text)


    def test_digest_excludes_superseded(self):
        """failures.md:118 — the digest is a live view; superseded facts stay in L2."""
        self.m.add_node("decision.old", "decision", "旧结论 限流 32", source="s old")
        self.m.add_node("decision.new", "decision", "新结论 限流 64", source="s new")
        self.m.supersede("decision.old", "decision.new", note="替换")
        text = self.m.digest(max_bytes=65536)
        self.assertNotIn("decision.old", text)
        self.assertIn("decision.new", text)
        self.assertIn("superseded excluded: 1", text)


if __name__ == "__main__":
    unittest.main()
