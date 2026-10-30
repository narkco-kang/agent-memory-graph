import copy
import datetime
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
        node["valid_time_known"] = True  # v0.2: expiry needs a known validity window
        rep = self.m.audit()
        self.assertTrue(any("valid_until passed" in c for c in rep["conflicts"]))

    def _backdate(self, node_id, days):
        """Age a node without sleeping: staleness is about updatedAt, not the clock."""
        node = next(n for n in self.m.doc["nodes"] if n["id"] == node_id)
        node["updatedAt"] = (datetime.datetime.now(datetime.timezone.utc)
                             - datetime.timedelta(days=days)).isoformat()

    def test_work_item_untouched_is_still_a_conflict(self):
        self.m.add_node("task.old", "task", "old work", source="s",
                        status="in_progress", owner="someone")
        self._backdate("task.old", 10)
        rep = self.m.audit()
        self.assertTrue(any("task.old" in c and "untouched" in c for c in rep["conflicts"]),
                        rep["conflicts"])

    def test_unknown_type_defaults_to_the_staleness_check(self):
        """Exemptions are explicit: a new node type is still checked, so abandoning a
        thing of that type cannot become invisible."""
        self.m.add_node("question.old", "question", "something else", source="s",
                        status="in_progress")
        self._backdate("question.old", 10)
        rep = self.m.audit()
        self.assertTrue(any("question.old" in c and "untouched" in c for c in rep["conflicts"]),
                        rep["conflicts"])

    def test_registry_types_are_not_reported_stale(self):
        """`group`, `env` and `member` register something long-lived; a group marked
        in_progress is active, not abandoned, and its updatedAt does not move when its
        children change. Flagging them was noise, not a finding (REAL-WORLD.md)."""
        for node_type in ("group", "env", "member"):
            node_id = f"{node_type}.self"
            self.m.add_node(node_id, node_type, node_type, source="s", status="in_progress")
            self._backdate(node_id, 30)
        rep = self.m.audit()
        flagged = [c for c in rep["conflicts"] if "untouched" in c]
        self.assertEqual(flagged, [], f"registry types reported stale: {flagged}")

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
