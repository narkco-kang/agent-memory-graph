import os
import subprocess
import sys
import tempfile
import unittest

from amg import Memory, ProtocolError
from helpers import TempGraph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = """## Where we are
- did: adopted the legacy graph, audit pin in place
- next: run the concurrency burst on the real graph
- blocked: nothing
- pointers: docs/REAL-WORLD.md, docs/CONCURRENCY.md
"""


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.m = self.g.m

    def tearDown(self):
        self.g.close()

    def test_write_then_read(self):
        card = self.m.write_handoff(CARD, by="kimi", owner="mini")
        self.assertEqual(card["bytes"], len(CARD.strip().encode()))
        read = self.m.handoff()
        self.assertEqual(read["note"], CARD.strip())
        self.assertEqual(read["by"], "kimi")
        self.assertEqual(read["owner"], "mini")
        self.assertEqual(read["max_bytes"], 4096)
        self.assertTrue(read["id"].startswith("handoff."))

    def test_writing_again_supersedes_the_previous_card(self):
        first = self.m.write_handoff(CARD, by="kimi")
        second = self.m.write_handoff("## Where we are\n- did: shipped 0.9.0", by="mini")
        self.assertEqual(second["superseded"], first["id"])
        old = next(n for n in self.m.doc["nodes"] if n["id"] == first["id"])
        self.assertEqual(old["status"], "superseded")
        self.assertTrue(old["valid_until"] and old["superseded_at"])
        self.assertEqual(self.m.handoff()["id"], second["id"])
        self.assertTrue(self.m.check()["ok"])

    def test_empty_card_is_refused(self):
        with self.assertRaises(ProtocolError) as ctx:
            self.m.write_handoff("   \n ", by="kimi")
        self.assertEqual(ctx.exception.code, "E_BAD_HANDOFF")

    def test_over_budget_card_is_refused_and_writes_nothing(self):
        path = os.path.join(self.g.dir, "graph.json")
        with open(path, "rb") as fh:
            before = fh.read()
        with self.assertRaises(ProtocolError) as ctx:
            self.m.write_handoff("x" * 4097, by="kimi")
        self.assertEqual(ctx.exception.code, "E_HANDOFF_TOO_LARGE")
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), before, "a rejected handoff must not touch the file")

    def test_audit_flags_a_card_over_budget(self):
        """The CLI refuses oversized cards, but a hand-edited graph can still hold
        one; audit is what catches that, so the limit is not merely advisory."""
        self.m.write_handoff(CARD, by="kimi")
        node = next(n for n in self.m.doc["nodes"] if n["type"] == "handoff")
        node["note"] = "y" * 5000
        rep = self.m.audit()
        finding = next(f for f in rep["findings"] if f["kind"] == "handoff_over_budget")
        self.assertEqual(finding["severity"], "conflict")
        self.assertEqual(finding["bytes"], 5000)
        self.assertEqual(finding["limit_bytes"], 4096)

    def test_audit_flags_two_active_cards(self):
        self.m.write_handoff(CARD, by="kimi")
        card = next(n for n in self.m.doc["nodes"] if n["type"] == "handoff")
        duplicate = dict(card)
        duplicate["id"] = "handoff.duplicate"
        self.m.doc["nodes"].append(duplicate)
        rep = self.m.audit()
        finding = next(f for f in rep["findings"] if f["kind"] == "multiple_active_handoffs")
        self.assertEqual(finding["count"], 2)

    def test_handoff_node_is_not_treated_as_stale_work(self):
        """A handoff card is a registration, not a task: it must not age into a
        staleness conflict the way an abandoned task does."""
        import datetime
        self.m.write_handoff(CARD, by="kimi")
        node = next(n for n in self.m.doc["nodes"] if n["type"] == "handoff")
        node["status"] = "in_progress"
        node["updatedAt"] = (datetime.datetime.now(datetime.timezone.utc)
                             - datetime.timedelta(days=30)).isoformat()
        rep = self.m.audit()
        self.assertFalse(any("untouched" in c for c in rep["conflicts"]), rep["conflicts"])


class HandoffCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-handoff-cli-")
        self.cli("init", self.dir, "--group", "t")

    def cli(self, *args, stdin=None):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        return subprocess.run([sys.executable, "-m", "amg.cli", *args],
                              capture_output=True, text=True, encoding="utf-8",
                              env=env, input=stdin)

    def test_write_read_and_budget(self):
        wrote = self.cli("handoff", self.dir, "--by", "kimi", "--note", "where we are")
        self.assertEqual(wrote.returncode, 0, wrote.stderr)
        read = self.cli("handoff", self.dir, "--json")
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertIn("where we are", read.stdout)
        self.assertIn('"by": "kimi"', read.stdout)
        too_big = self.cli("handoff", self.dir, "--by", "kimi", "--note", "z" * 5000)
        self.assertEqual(too_big.returncode, 2)
        self.assertIn("E_HANDOFF_TOO_LARGE", too_big.stderr)

    def test_reading_without_a_card_is_a_usage_error(self):
        res = self.cli("handoff", self.dir)
        self.assertEqual(res.returncode, 2)
        self.assertIn("no handoff card", res.stderr)

    def test_note_can_come_from_stdin(self):
        res = self.cli("handoff", self.dir, "--by", "mini", "--note", "-",
                       stdin="## Where we are\n- next: ship")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ship", self.cli("handoff", self.dir).stdout)


if __name__ == "__main__":
    unittest.main()
