import copy
import datetime
import os
import unittest
import unittest.mock

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

    def test_stale_threshold_defaults_to_three_days(self):
        self.m.add_node("task.two", "task", "two days", source="s", status="in_progress")
        self._backdate("task.two", 2)
        self.assertFalse(any("untouched" in c for c in self.m.audit()["conflicts"]))
        self._backdate("task.two", 4)
        self.assertTrue(any("untouched" in c for c in self.m.audit()["conflicts"]))

    def test_stale_days_argument_overrides_the_rule(self):
        self.m.add_node("task.ten", "task", "ten days", source="s", status="in_progress")
        self._backdate("task.ten", 10)
        self.assertTrue(any("untouched" in c for c in self.m.audit()["conflicts"]))
        relaxed = self.m.audit(stale_days=30)
        self.assertFalse(any("untouched" in c for c in relaxed["conflicts"]))

    def test_stale_days_env_is_used_and_nonsense_falls_back(self):
        self.m.add_node("task.ten", "task", "ten days", source="s", status="in_progress")
        self._backdate("task.ten", 10)
        with unittest.mock.patch.dict(os.environ, {"AMG_STALE_DAYS": "30"}):
            self.assertFalse(any("untouched" in c for c in self.m.audit()["conflicts"]))
        for bad in ("soon", "-1", "0", "100000"):
            with unittest.mock.patch.dict(os.environ, {"AMG_STALE_DAYS": bad}):
                rep = self.m.audit()
                self.assertTrue(any("untouched" in c for c in rep["conflicts"]),
                                f"bad value {bad!r} should fall back to the default")

    def test_findings_mirror_conflicts_and_hints(self):
        """`findings` is the structured form of the same list. It must not drift:
        every human string has exactly one entry, in order, with the right severity."""
        self.m.add_node("task.legacy", "task", "old", source="s", status="done")
        self.m.add_node("task.old", "task", "stale", source="s", status="in_progress",
                        owner="someone")
        self._backdate("task.old", 10)
        self.m.doc["edges"].append({"from": "task.ghost", "to": "task.old", "kind": "relates_to"})
        rep = self.m.audit()
        conflicts = [f for f in rep["findings"] if f["severity"] == "conflict"]
        hints = [f for f in rep["findings"] if f["severity"] == "hint"]
        self.assertEqual([f["detail"] for f in conflicts], rep["conflicts"])
        self.assertEqual([f["detail"] for f in hints], rep["hints"])

    def test_stale_finding_carries_who_and_how_long(self):
        self.m.add_node("task.old", "task", "stale", source="s", status="in_progress",
                        owner="kimi")
        self._backdate("task.old", 10)
        finding = next(f for f in self.m.audit()["findings"]
                       if f["kind"] == "stale_work_item")
        self.assertEqual(finding["node"], "task.old")
        self.assertEqual(finding["owner"], "kimi")
        self.assertEqual(finding["age_days"], 10)
        self.assertEqual(finding["limit_days"], 3)
        self.assertEqual(finding["status"], "in_progress")

    def test_done_without_evidence_finding_has_node(self):
        self.m.add_node("task.legacy", "task", "old", source="s", status="done")
        finding = next(f for f in self.m.audit()["findings"]
                       if f["kind"] == "done_without_evidence")
        self.assertEqual(finding["node"], "task.legacy")
        self.assertEqual(finding["type"], "task")
        self.assertIsNone(finding["owner"])

    def test_dangling_edge_finding_has_both_endpoints(self):
        self.m.add_node("task.a", "task", "a", source="s")
        self.m.doc["edges"].append({"from": "task.ghost", "to": "task.a", "kind": "relates_to"})
        finding = next(f for f in self.m.audit()["findings"]
                       if f["kind"] == "dangling_edge")
        self.assertEqual(finding["edge"], {"from": "task.ghost", "to": "task.a",
                                           "kind": "relates_to"})

    def test_hint_findings_are_marked_as_hints(self):
        self.m.add_node("decision.d", "decision", "D", source="s", status="done",
                        evidence=[ev()])
        # Strip the evidence after the gate accepted it, to reach a state adoption can
        # produce: a conclusion recorded `done` with no evidence object at all.
        self.m.doc["nodes"][0]["evidence"] = []
        finding = next(f for f in self.m.audit()["findings"]
                       if f["kind"] == "conclusion_without_grade")
        self.assertEqual(finding["severity"], "hint")

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
