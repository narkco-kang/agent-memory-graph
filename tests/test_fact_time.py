"""v0.2 fact-time input (signed scope, seven rules).

Rules pinned here:
1. explicit `valid_from` is persisted verbatim;
2. the default is "unknown", never the write time;
3. a future `valid_from` is accepted, audited as "not yet valid", and treated as
   not-yet-in-effect by retrieval, digest and expiry;
4. `valid_until < valid_from` is rejected;
5. expiry still requires a *known* validity window (conservative direction);
6. `amg adopt` keeps refusing to infer validity (covered in test_adopt.py).
"""
import contextlib
import io
import os
import shutil
import tempfile
import unittest

from amg import Memory, ProtocolError
from helpers import TempGraph, ev

from amg import cli as cli_mod
from amg.audit import expiry_eligible


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


class FactTimeTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m

    def tearDown(self):
        self.g.close()

    # 1 -------------------------------------------------------------------
    def test_explicit_valid_from_is_persisted_verbatim(self):
        raw = "2026-01-15T09:30:00+08:00"
        self.m.add_node("task.explicit", "task", "explicit fact time", source="s",
                        valid_from=raw)
        node = self.m.doc["nodes"][0]
        self.assertEqual(node["valid_from"], raw)          # verbatim, not re-formatted
        self.assertIsNone(node["valid_until"])
        self.assertTrue(node["valid_time_known"])

    # 2 -------------------------------------------------------------------
    def test_default_is_unknown_not_the_write_time(self):
        self.m.add_node("task.default", "task", "no fact time given", source="s")
        node = self.m.doc["nodes"][0]
        self.assertIsNone(node["valid_from"])
        self.assertFalse(node["valid_time_known"])
        self.assertNotEqual(node.get("valid_from"), node.get("recorded_at"))
        self.assertIsNotNone(node.get("recorded_at"))      # transaction time still recorded

    # 3 -------------------------------------------------------------------
    def test_future_valid_from_is_hint_and_not_an_answer(self):
        self.m.add_node("task.future", "task", "限流 未来生效", source="s",
                        valid_from="2999-01-01T00:00:00+08:00")
        self.m.add_node("task.now", "task", "限流 当前生效", source="s",
                        valid_from="2026-01-01T00:00:00+08:00")
        audit = self.m.audit()
        self.assertFalse(any("not yet valid" in c for c in audit["conflicts"]))
        self.assertTrue(any("not yet valid" in h for h in audit["hints"]))
        ids = [h["id"] for h in self.m.search("限流")]
        self.assertNotIn("task.future", ids)               # not-yet-effective is not an answer
        self.assertIn("task.now", ids)
        text = self.m.digest(max_bytes=65536)
        self.assertNotIn("task.future", text)
        self.assertIn("task.now", text)

    # 4 -------------------------------------------------------------------
    def test_inverted_validity_range_is_rejected(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("task.bad", "task", "inverted", source="s",
                            valid_from="2026-05-01T00:00:00+08:00",
                            valid_until="2026-04-01T00:00:00+08:00")
        self.assertEqual(ctx.exception.code, "E_BAD_VALID_RANGE")
        self.assertEqual(len(self.m.doc["nodes"]), 0)      # nothing was written

    def test_unparseable_fact_time_is_rejected(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.add_node("task.bad2", "task", "not a time", source="s",
                            valid_from="yesterday-ish")
        self.assertEqual(ctx.exception.code, "E_BAD_VALID_TIME")

    # 5 -------------------------------------------------------------------
    def test_expiry_still_requires_a_known_validity_window(self):
        self.m.add_node("task.unknown", "task", "unknown validity", source="s",
                        valid_until="2020-01-01T00:00:00+08:00")
        node = self.m.doc["nodes"][0]
        self.assertFalse(node["valid_time_known"])
        self.assertFalse(expiry_eligible(node))
        audit = self.m.audit()
        self.assertFalse(any("valid_until passed" in c for c in audit["conflicts"]))
        self.assertTrue(any("validity time is unknown" in h for h in audit["hints"]))

        self.m.add_node("task.known", "task", "known validity", source="s",
                        valid_from="2019-01-01T00:00:00+08:00",
                        valid_until="2020-01-01T00:00:00+08:00")
        known = next(n for n in self.m.doc["nodes"] if n["id"] == "task.known")
        self.assertTrue(expiry_eligible(known))
        audit2 = self.m.audit()
        self.assertTrue(any("task.known" in c and "valid_until passed" in c
                            for c in audit2["conflicts"]))

    # 6 (adopt promise re-asserted at the API level) -----------------------
    def test_adopt_is_not_touched_by_fact_time_input(self):
        self.m.add_node("task.a", "task", "A", source="s")
        self.assertIsNone(self.m.doc["nodes"][0]["valid_from"])
        self.assertFalse(self.m.doc["nodes"][0]["valid_time_known"])


class FactTimeCliTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()

    def tearDown(self):
        self.g.close()

    def _cli(self, *args):
        return quiet(cli_mod.main, list(args))

    def test_cli_accepts_valid_from_and_persists_it(self):
        raw = "2026-02-03T04:05:06+08:00"
        self.assertEqual(self._cli("add", self.g.dir, "--id", "task.cli",
                                   "--type", "task", "--label", "L", "--source", "s",
                                   "--valid-from", raw), 0)
        node = Memory.open(self.g.dir).doc["nodes"][0]
        self.assertEqual(node["valid_from"], raw)
        self.assertTrue(node["valid_time_known"])

    def test_cli_default_valid_from_stays_unknown(self):
        self.assertEqual(self._cli("add", self.g.dir, "--id", "task.cli2",
                                   "--type", "task", "--label", "L", "--source", "s"), 0)
        node = Memory.open(self.g.dir).doc["nodes"][0]
        self.assertIsNone(node["valid_from"])
        self.assertFalse(node["valid_time_known"])

    def test_cli_rejects_inverted_and_unparseable_ranges(self):
        self.assertEqual(self._cli("add", self.g.dir, "--id", "task.bad", "--type", "task",
                                   "--label", "L", "--source", "s",
                                   "--valid-from", "2026-05-01T00:00:00+08:00",
                                   "--valid-until", "2026-04-01T00:00:00+08:00"), 2)
        self.assertEqual(self._cli("add", self.g.dir, "--id", "task.bad2", "--type", "task",
                                   "--label", "L", "--source", "s",
                                   "--valid-from", "not-a-time"), 2)


if __name__ == "__main__":
    unittest.main()
