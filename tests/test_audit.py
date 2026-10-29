import copy
import unittest

from amg.audit import expiry_eligible, legacy_stats
from helpers import TempGraph, ev


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m

    def tearDown(self):
        self.g.close()

    def test_done_without_evidence_is_conflict(self):
        self.m.add_node("task.legacy", "task", "old", source="s", status="done")
        rep = self.m.audit()
        self.assertFalse(rep["ok"])
        self.assertTrue(any("IR-4" in c for c in rep["conflicts"]))

    def test_pin_match_exempts_legacy_only(self):
        self.m.add_node("task.legacy", "task", "old", source="s", status="done")
        pin = {k: v for k, v in legacy_stats(self.m.doc).items()
               if k.endswith("sha256")}
        rep = self.m.audit(pin=pin)
        self.assertTrue(rep["ok"])
        self.assertTrue(rep["pin"]["match"])

    def test_new_write_cannot_hide_behind_pin(self):
        self.m.add_node("task.legacy", "task", "old", source="s", status="done")
        pin = {k: v for k, v in legacy_stats(self.m.doc).items() if k.endswith("sha256")}
        self.m.add_node("task.new", "task", "new", source="s", status="done")
        rep = self.m.audit(pin=pin)
        self.assertFalse(rep["pin"]["match"])
        self.assertTrue(any("pin changed" in c for c in rep["conflicts"]))

    def test_expired_but_active_is_conflict(self):
        self.m.add_node("decision.e", "decision", "E", source="s", status="done", evidence=[ev()])
        node = self.m.doc["nodes"][0]
        node["valid_until"] = "2020-01-01T00:00:00+08:00"
        rep = self.m.audit()
        self.assertTrue(any("valid_until passed" in c for c in rep["conflicts"]))

    def test_changes_key_shapes_reported(self):
        self.m.add_node("task.a", "task", "A", source="s")
        doc = self.m.doc
        doc["changes"].append({"at": "2026-10-29T10:00:00+08:00", "by": "x", "op": "fix-edge",
                               "detail": "no target, no rev"})
        rep = self.m.audit()
        self.assertTrue(any("key shapes" in h for h in rep["hints"]))


    def test_expired_with_unknown_validity_is_hint_not_conflict(self):
        """Adopted validity time is unknown: expiring it would delete a fact we
        never dated (maintainer ruling 2026-10-29)."""
        self.m.add_node("decision.e", "decision", "E", source="s", status="done", evidence=[ev()])
        node = self.m.doc["nodes"][0]
        node["valid_until"] = "2020-01-01T00:00:00+08:00"
        node["valid_time_known"] = False
        rep = self.m.audit()
        self.assertFalse(any("valid_until passed" in c for c in rep["conflicts"]))
        self.assertTrue(any("validity time is unknown" in h for h in rep["hints"]))
        self.assertTrue(rep["ok"])

    def test_ttl_auto_expiry_refuses_unknown_validity(self):
        self.assertFalse(expiry_eligible({"valid_time_known": False}))
        self.assertTrue(expiry_eligible({}))                    # absent = known (normal nodes)
        self.assertTrue(expiry_eligible({"valid_time_known": True}))
        self.m.add_node("task.a", "task", "A", source="s")
        self.m.doc["nodes"][0]["valid_time_known"] = False
        rep = self.m.audit()
        self.assertTrue(any("TTL auto-expiry refuses" in h for h in rep["hints"]))


if __name__ == "__main__":
    unittest.main()
