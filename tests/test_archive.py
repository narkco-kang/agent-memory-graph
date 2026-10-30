"""`amg archive` — move cold ledger records out, and prove the move lost nothing.

Pre-registered acceptance criteria (fixed before implementation):

1. a dry-run writes **not one byte** and creates no `archive/` directory;
2. only a *prefix* of time-ordered ledger records older than the cutoff moves —
   an old record sitting behind a newer one is counted, never taken out of order;
   an undated record stops the prefix (unknown time is never a reason to move);
3. the graph's nodes and edges are untouched: `state_sha256` is identical before
   and after (checked, not assumed);
4. the move is proven immediately: the archive file as re-read from disk must
   reproduce the moved records, and the live ledger must be remainder + one pointer;
5. if the proof fails, the snapshot is written back and the command fails
   (`E_ARCHIVE_VERIFY`) — no half-true success;
6. `--verify` recomputes every payload digest from disk and requires rev numbers to
   appear exactly once and stay contiguous across archive and live ledger;
7. idempotent: a second run finds nothing old enough and writes nothing.
"""
import contextlib
import io
import json
import os
import unittest
from unittest import mock

from amg import Memory, ProtocolError
from amg import archive as archive_mod
from amg.const import now
from amg import cli as cli_mod
from helpers import TempGraph

OLD = "2026-08-01T10:00:00+08:00"
NOW = "2026-10-31T01:00:00+08:00"


@contextlib.contextmanager
def at(stamp):
    old = os.environ.get("AMG_NOW")
    os.environ["AMG_NOW"] = stamp
    try:
        yield stamp
    finally:
        if old is None:
            os.environ.pop("AMG_NOW", None)
        else:
            os.environ["AMG_NOW"] = old


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        with at(OLD):
            self.g = TempGraph()
            self.m = self.g.m
            for i in range(10):
                self.m.add_node(id=f"task.{i}", type="rule", label=f"t{i}", source="cmd:test",
                                applies="any", expires_when=None, by="t")
            self.m.add_edge("task.0", "task.1", "relates_to")
        self.graph = os.path.join(self.g.dir, "graph.json")

    def tearDown(self):
        self.g.close()

    def bytes(self):
        with open(self.graph, "rb") as fh:
            return fh.read()

    def test_dry_run_writes_nothing(self):
        before = self.bytes()
        with at(NOW):
            rep = self.m.archive(days=30)
        self.assertTrue(rep["dry_run"])
        self.assertEqual(rep["eligible"], 11)
        self.assertEqual(rep["archived"], 0)
        self.assertEqual(self.bytes(), before)
        self.assertFalse(os.path.exists(os.path.join(self.g.dir, "archive")))

    def test_apply_moves_records_and_proves_it(self):
        before = self.bytes()
        with at(NOW):
            rep = Memory.open(self.g.dir).archive(days=30, apply=True)
        v = rep["verify"]
        self.assertTrue(v["ok"], v["reasons"])
        self.assertEqual(rep["archived"], 11)
        self.assertTrue(v["archive_payload_match"])
        self.assertTrue(v["live_ledger_match"])
        self.assertTrue(v["state_unchanged"])
        self.assertTrue(v["check_ok"])
        self.assertTrue(v["rev_contiguous"])
        self.assertLess(rep["bytes_after"], len(before))
        self.assertTrue(os.path.getsize(os.path.join(self.g.dir, rep["snapshot"]["file"])) > 0)
        live = Memory.open(self.g.dir)
        self.assertEqual(len(live.doc["changes"]), 1)
        self.assertEqual(live.doc["changes"][0]["op"], "archive")
        self.assertTrue(live.check()["ok"])
        live_changes = live.doc["changes"][0]["note"]
        self.assertIn("change record(s)", live_changes)

    def test_nodes_and_edges_are_untouched(self):
        with at(NOW):
            first = Memory.open(self.g.dir).fingerprint()
            Memory.open(self.g.dir).archive(days=30, apply=True)
            second = Memory.open(self.g.dir).fingerprint()
        self.assertEqual(first["state_sha256"], second["state_sha256"])
        self.assertEqual(second["nodes"], first["nodes"])
        self.assertEqual(second["edges"], first["edges"])
        self.assertNotEqual(first["history_sha256"], second["history_sha256"])

    def test_recent_records_are_not_archived(self):
        with at(NOW):
            rep = self.m.archive(days=30, apply=True)
        self.assertEqual(rep["archived"], 11)
        with at(NOW):
            again = Memory.open(self.g.dir).archive(days=30, apply=True)
        self.assertEqual(again["eligible"], 0)
        self.assertEqual(again["archived"], 0)

    def test_undated_record_stops_the_prefix(self):
        # An undated record at the head: unknown time is never a reason to move
        # history, so the whole ledger stays even though 11 records are old.
        doc = json.loads(self.bytes())
        doc["changes"].insert(0, {"op": "manual", "rev": 0})
        with open(self.graph, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        with at(NOW):
            rep = self.m.archive(days=30)
        self.assertEqual(rep["eligible"], 0)
        self.assertEqual(rep["unknown_time_after_prefix"], 1)
        self.assertEqual(rep["deferred_behind_newer"], 11)

    def test_old_record_behind_a_newer_one_is_deferred_not_moved(self):
        doc = json.loads(self.bytes())
        doc["changes"].append({"at": now(), "by": "t", "op": "add-node", "target": "fresh",
                               "rev": 12, "note": "fresh"})
        doc["changes"].append({"at": OLD, "by": "t", "op": "add-node", "target": "late",
                               "rev": 13, "note": "old but behind a newer record"})
        doc["rev"] = 13
        with open(self.graph, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        with at(NOW):
            rep = self.m.archive(days=30, apply=True)
        self.assertEqual(rep["eligible"], 11)
        self.assertEqual(rep["archived"], 11)
        self.assertEqual(rep["deferred_behind_newer"], 1)
        live = Memory.open(self.g.dir)
        self.assertEqual([c.get("target") for c in live.doc["changes"]],
                         ["fresh", "late", live.doc["changes"][-1].get("target")])

    def test_failed_proof_restores_the_snapshot(self):
        before = self.bytes()
        broken = {"ok": False, "reasons": ["simulated"], "archived": 0, "live": 0}
        with at(NOW):
            with mock.patch.object(archive_mod, "_verify_roundtrip", return_value=broken):
                with self.assertRaises(ProtocolError) as ctx:
                    Memory.open(self.g.dir).archive(days=30, apply=True)
        self.assertEqual(ctx.exception.code, "E_ARCHIVE_VERIFY")
        self.assertEqual(self.bytes(), before)
        live = Memory.open(self.g.dir)
        self.assertEqual(len(live.doc["changes"]), 11)
        self.assertTrue(live.check()["ok"])

    def test_verify_reports_a_tampered_archive(self):
        with at(NOW):
            rep = Memory.open(self.g.dir).archive(days=30, apply=True)
            path = os.path.join(self.g.dir, rep["archive"]["file"])
            head = read_json(path)
            head["changes"][0]["note"] = "quietly rewritten"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(head, fh)
            out = Memory.open(self.g.dir).archive_verify()
        self.assertFalse(out["ok"])
        self.assertTrue(any("payload digest" in reason for reason in out["reasons"]))

    def test_verify_reports_a_rev_gap(self):
        with at(NOW):
            Memory.open(self.g.dir).archive(days=30, apply=True)
            doc = json.loads(self.bytes())
            doc["changes"][0]["rev"] = 13  # skip 12: a hole between archive and live
            with open(self.graph, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            out = Memory.open(self.g.dir).archive_verify()
        self.assertFalse(out["ok"])
        self.assertEqual(out["gaps"], [12])

    def test_verify_reports_duplicate_revs(self):
        with at(NOW):
            Memory.open(self.g.dir).archive(days=30, apply=True)
            doc = json.loads(self.bytes())
            doc["changes"][0]["rev"] = 3  # collides with an archived record
            with open(self.graph, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            out = Memory.open(self.g.dir).archive_verify()
        self.assertFalse(out["ok"])
        self.assertEqual(out["duplicates"], [3])

    def test_unnumbered_record_is_unknown_not_a_failure(self):
        # Graphs written before `amg migrate` can carry records without `rev`.
        # Contiguity is then unknowable: report unknown, do not refuse the move.
        doc = json.loads(self.bytes())
        doc["changes"][-1].pop("rev", None)
        with open(self.graph, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        with at(NOW):
            rep = Memory.open(self.g.dir).archive(days=30, apply=True)
            out = Memory.open(self.g.dir).archive_verify()
        self.assertTrue(rep["verify"]["ok"], rep["verify"]["reasons"])
        self.assertIsNone(rep["verify"]["rev_contiguous"])
        self.assertEqual(rep["verify"]["rev_unnumbered"], 1)
        self.assertEqual(rep["archived"], 11)
        self.assertTrue(out["ok"], out["reasons"])
        self.assertIsNone(out["rev_continuity"])
        self.assertEqual(out["records_without_rev"], 1)

    def test_verify_on_a_graph_without_archives(self):
        with at(NOW):
            out = Memory.open(self.g.dir).archive_verify()
        self.assertTrue(out["ok"], out["reasons"])
        self.assertEqual(out["archived_records"], 0)
        self.assertEqual(out["live_records"], 11)


class ArchivePolicyTests(unittest.TestCase):
    def test_env_days_falls_back_to_the_default(self):
        for value in ("", "abc", "0", "-5", "99999"):
            os.environ["AMG_ARCHIVE_DAYS"] = value
            try:
                self.assertEqual(archive_mod.resolve_days(), archive_mod.DEFAULT_DAYS, value)
            finally:
                os.environ.pop("AMG_ARCHIVE_DAYS", None)

    def test_env_days_is_used_when_sane(self):
        os.environ["AMG_ARCHIVE_DAYS"] = "7"
        try:
            self.assertEqual(archive_mod.resolve_days(), 7)
            self.assertEqual(archive_mod.resolve_days(3), 3)
        finally:
            os.environ.pop("AMG_ARCHIVE_DAYS", None)


class ArchiveCliTests(unittest.TestCase):
    def setUp(self):
        with at(OLD):
            self.g = TempGraph()
            self.m = self.g.m
            self.m.add_node(id="task.x", type="rule", label="x", source="cmd:test",
                            applies="any", expires_when=None, by="t")

    def tearDown(self):
        self.g.close()

    def test_dry_run_then_apply_then_verify(self):
        with at(NOW):
            self.assertEqual(quiet(cli_mod.main, ["archive", self.g.dir, "--json"]), 0)
            self.assertFalse(os.path.exists(os.path.join(self.g.dir, "archive")))
            self.assertEqual(quiet(cli_mod.main, ["archive", self.g.dir, "--apply"]), 0)
            self.assertEqual(quiet(cli_mod.main, ["archive", self.g.dir, "--verify"]), 0)

    def test_tampered_archive_exits_one(self):
        with at(NOW):
            quiet(cli_mod.main, ["archive", self.g.dir, "--apply"])
            archive_dir = os.path.join(self.g.dir, "archive")
            name = sorted(n for n in os.listdir(archive_dir) if n.startswith("changes-"))[0]
            path = os.path.join(archive_dir, name)
            head = read_json(path)
            head["count"] = 99
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(head, fh)
            self.assertEqual(quiet(cli_mod.main, ["archive", self.g.dir, "--verify"]), 1)

    def test_missing_graph_is_usage_error(self):
        self.assertEqual(quiet(cli_mod.main, ["archive", "/nonexistent-amg-dir", "--json"]), 2)


if __name__ == "__main__":
    unittest.main()
