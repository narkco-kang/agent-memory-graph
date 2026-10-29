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


if __name__ == "__main__":
    unittest.main()
