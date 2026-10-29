"""`amg expire` — opt-in TTL expiry with a dry-run default.

Pre-registered acceptance criteria (fixed before implementation):
1. dry-run unless `--apply`; a dry-run must not change one byte on disk;
2. only nodes whose validity window is KNOWN and whose `valid_until` has passed
   and that are not already superseded;
3. the action is status -> superseded + change-log trace; no node is ever deleted;
4. idempotent: a second `--apply` changes nothing;
5. after `--apply`, audit has zero "expired but still active" conflicts, and
   unrelated staleness conflicts are NOT cleaned up as a side effect;
6. unknown validity (`valid_time_known: false`) is skipped and counted;
7. nothing in a migrated graph is eligible (all migrated nodes have unknown
   validity) — so adoption can never trigger mass expiry.
"""
import contextlib
import io
import os
import unittest

from amg import Memory
from amg import cli as cli_mod
from helpers import TempGraph


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


def expired(node_id="task.expired", label="expired fact"):
    return dict(id=node_id, type="task", label=label, source="s",
                valid_from="2019-01-01T00:00:00+08:00",
                valid_until="2020-01-01T00:00:00+08:00")


class ExpireTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m
        self.m.add_node(**expired())
        self.m.add_node(id="task.active", type="task", label="active fact", source="s",
                        valid_from="2019-01-01T00:00:00+08:00",
                        valid_until="2999-01-01T00:00:00+08:00")
        # known end, unknown start => unknown validity window
        self.m.add_node(id="task.unknown", type="task", label="unknown window", source="s",
                        valid_until="2020-01-01T00:00:00+08:00")
        self.m = Memory.open(self.g.dir)

    def tearDown(self):
        self.g.close()

    def _graph_bytes(self):
        with open(os.path.join(self.g.dir, "graph.json"), "rb") as fh:
            return fh.read()

    # 1 -------------------------------------------------------------------
    def test_dry_run_is_the_default_and_writes_nothing(self):
        before = self._graph_bytes()
        report = self.m.expire()
        self.assertTrue(report["dry_run"])
        self.assertIn("task.expired", report["eligible"])
        self.assertEqual(report["applied"], 0)
        self.assertEqual(self._graph_bytes(), before)
        self.assertEqual(Memory.open(self.g.dir).doc["nodes"][0]["status"], "open")

    # 2 + 3 ---------------------------------------------------------------
    def test_apply_supersedes_with_trace_and_never_deletes(self):
        before_count = len(Memory.open(self.g.dir).doc["nodes"])
        report = self.m.expire(apply=True)
        doc = Memory.open(self.g.dir).doc
        self.assertEqual(report["applied"], 1)
        self.assertEqual(len(doc["nodes"]), before_count)          # nothing deleted
        node = next(n for n in doc["nodes"] if n["id"] == "task.expired")
        self.assertEqual(node["status"], "superseded")
        self.assertIsNotNone(node["superseded_at"])
        self.assertEqual(node["valid_until"], "2020-01-01T00:00:00+08:00")  # window preserved
        trace = [c for c in doc["changes"] if c.get("op") == "expire"]
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["target"], "task.expired")

    def test_unknown_validity_is_skipped_and_counted(self):
        report = self.m.expire(apply=True)
        doc = Memory.open(self.g.dir).doc
        unknown = next(n for n in doc["nodes"] if n["id"] == "task.unknown")
        self.assertEqual(unknown["status"], "open")                # untouched
        self.assertEqual(report["skipped_unknown_validity"], 1)
        self.assertNotIn("task.unknown", report["eligible"])

    def test_active_and_future_windows_are_not_eligible(self):
        report = self.m.expire(apply=True)
        doc = Memory.open(self.g.dir).doc
        active = next(n for n in doc["nodes"] if n["id"] == "task.active")
        self.assertEqual(active["status"], "open")
        self.assertNotIn("task.active", report["eligible"])

    # 4 -------------------------------------------------------------------
    def test_second_apply_is_a_no_op(self):
        self.m.expire(apply=True)
        after_first = self._graph_bytes()
        report = Memory.open(self.g.dir).expire(apply=True)
        self.assertEqual(report["applied"], 0)
        self.assertEqual(self._graph_bytes(), after_first)

    # 5 -------------------------------------------------------------------
    def test_audit_shows_no_expiry_conflict_after_apply(self):
        before = self.m.audit()
        self.assertTrue(any("task.expired" in c and "valid_until passed" in c
                            for c in before["conflicts"]))
        Memory.open(self.g.dir).expire(apply=True)
        after = Memory.open(self.g.dir).audit()
        self.assertFalse(any("valid_until passed" in c for c in after["conflicts"]))

    def test_unrelated_staleness_conflict_survives_expiry(self):
        with self.m.store.transaction() as (doc, commit):
            stale = next(n for n in doc["nodes"] if n["id"] == "task.active")
            stale["status"] = "in_progress"
            stale["updatedAt"] = "2026-10-01T00:00:00+08:00"
            commit()
        Memory.open(self.g.dir).expire(apply=True)
        after = Memory.open(self.g.dir).audit()
        self.assertTrue(any("untouched for" in c for c in after["conflicts"]))

    # 7 -------------------------------------------------------------------
    def test_migrated_graph_has_nothing_eligible(self):
        self.m.add_node(id="task.adopted", type="task", label="adopted", source="adopted:x:y")
        with self.m.store.transaction() as (doc, commit):
            node = next(n for n in doc["nodes"] if n["id"] == "task.adopted")
            node["valid_time_known"] = False
            node["valid_until"] = "2020-01-01T00:00:00+08:00"
            commit()
        report = Memory.open(self.g.dir).expire(apply=True)
        self.assertEqual(report["applied"], 1)                     # only the known-window node
        self.assertEqual(report["eligible"], ["task.expired"])
        self.assertEqual(report["skipped_unknown_validity"], 2)


class ExpireCliTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.g.m.add_node(**expired())

    def tearDown(self):
        self.g.close()

    def _bytes(self):
        with open(os.path.join(self.g.dir, "graph.json"), "rb") as fh:
            return fh.read()

    def test_cli_default_is_dry_run(self):
        before = self._bytes()
        self.assertEqual(quiet(cli_mod.main, ["expire", self.g.dir]), 0)
        self.assertEqual(self._bytes(), before)

    def test_cli_apply_supersedes(self):
        self.assertEqual(quiet(cli_mod.main, ["expire", self.g.dir, "--apply"]), 0)
        node = Memory.open(self.g.dir).doc["nodes"][0]
        self.assertEqual(node["status"], "superseded")

    def test_cli_json_report(self):
        self.assertEqual(quiet(cli_mod.main, ["expire", self.g.dir, "--json"]), 0)


if __name__ == "__main__":
    unittest.main()
