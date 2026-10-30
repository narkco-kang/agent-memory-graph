import json
import os
import unittest

from amg import Memory
from helpers import TempGraph


class MigrateTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m
        self.m.add_node("task.a", "task", "A", source="s")
        self.m.add_node("task.b", "task", "B", source="s")

    def tearDown(self):
        self.g.close()

    def _inject_legacy_shapes(self):
        with self.m.store.transaction() as (doc, commit):
            doc["changes"].append({"at": "2026-10-29T10:00:00+08:00", "by": "x",
                                   "op": "fix-edge", "detail": "no target, no rev"})
            doc["changes"].append({"at": "2026-10-29T10:01:00+08:00", "by": "x",
                                   "op": "fix-edge", "target": "task.a", "note": "no rev"})
            commit()
        self.m = Memory.open(self.g.dir)

    def test_migrate_normalizes_three_shapes_without_faking_rev(self):
        self._inject_legacy_shapes()
        stats = self.m.migrate()
        self.assertGreaterEqual(stats["filled_target"], 1)
        self.assertGreaterEqual(stats["filled_rev"], 2)
        legacy = [c for c in self.m.doc["changes"] if c.get("by") == "x"]
        for c in legacy:
            self.assertIn("target", c)
            self.assertIn("rev", c)
            self.assertIsNone(c["rev"])  # never invented
        self.assertTrue(all(len(k) > 0 for k in stats["shapes_after"]))

    def test_detail_is_folded_into_note_not_dropped_and_shapes_become_canonical(self):
        self._inject_legacy_shapes()
        stats = self.m.migrate()
        self.assertEqual(stats["folded_detail"], 1)
        self.assertEqual(stats["non_canonical_shapes"], {},
                         f"shapes after migrate: {stats['shapes_after']}")
        legacy = [c for c in self.m.doc["changes"] if c.get("by") == "x"]
        filled = [c for c in legacy if c.get("op") == "fix-edge" and c.get("note")]
        self.assertTrue(any("no target, no rev" in c["note"] for c in filled),
                        "the only copy of `detail` must survive in `note`")
        for c in legacy:
            self.assertNotIn("detail", c)

    def test_check_does_not_advise_migrating_twice(self):
        self._inject_legacy_shapes()
        before = self.m.check()
        self.assertTrue(any("run `amg migrate`" in h for h in before["hints"]))
        self.m.migrate()
        after = Memory.open(self.g.dir).check()
        text = " ".join(after["hints"])
        self.assertNotIn("run `amg migrate`", text,
                         "after migrate a null rev is unknown, not an un-migrated record")
        self.assertIn("rev unknown", text)

    def test_migrate_is_idempotent(self):
        self._inject_legacy_shapes()
        self.m.migrate()
        again = Memory.open(self.g.dir).migrate()
        self.assertEqual(again["changed"], 0)
        self.assertEqual(again["filled_target"], 0)
        self.assertEqual(again["folded_detail"], 0)


if __name__ == "__main__":
    unittest.main()
