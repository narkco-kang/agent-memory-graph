"""Cold history stays reachable: `amg search --layer L2 --include-archive`.

Moving the ledger out (`amg archive`) must not silently change what a default search
returns, and the history that was moved must not become unsearchable either. The two
claims are tested separately, because either one alone is easy to satisfy badly.

Pre-registered criteria:
1. default L2 search returns what it returned before archiving (nothing hidden, nothing
   invented);
2. `include_archive=True` finds the moved record and marks it `archived` with the
   archive file it came from — a reader can always tell old history from live history;
3. the limit `k` applies across live and archived records together, newest first, and
   from `k >= 5` the archive keeps a reserved share — otherwise `--include-archive`
   returns nothing whenever live records fill `k` (`issue.mem-arch-archive-k-starve`,
   v0.21.0); a per-file first pass means no archive file with a match is invisible;
4. the flag is refused on node layers (`E_ARCHIVE_LAYER`, exit 2) rather than quietly
   ignored;
5. archived hits keep their original `at` and `rev`.
"""
import contextlib
import io
import json
import os
import unittest

from amg import Memory, ProtocolError
from amg import cli as cli_mod
from helpers import TempGraph

OLD = "2026-08-01T10:00:00+08:00"
NOW = "2026-10-31T02:30:00+08:00"


@contextlib.contextmanager
def at(stamp):
    previous = os.environ.get("AMG_NOW")
    os.environ["AMG_NOW"] = stamp
    try:
        yield stamp
    finally:
        if previous is None:
            os.environ.pop("AMG_NOW", None)
        else:
            os.environ["AMG_NOW"] = previous


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


class ArchiveReservationTests(unittest.TestCase):
    """The reservation that keeps `--include-archive` from being a no-op."""

    def _doc(self):
        return {"nodes": [], "edges": [], "changes": [
            {"op": "add", "target": f"task.l{i}", "note": "needle",
             "at": f"2026-10-31T00:0{i}:00+08:00", "rev": 100 + i} for i in range(12)]}

    def _archived(self):
        return [{"file": f"archive/changes-000{file_index}.json",
                 "record": {"op": "add", "target": f"task.a{file_index}{i}",
                            "note": "needle", "rev": i,
                            "at": f"2026-10-0{file_index}T00:0{i}:00+08:00"}}
                for file_index in (1, 2) for i in range(6)]

    def test_live_hits_cannot_starve_the_archive(self):
        from amg import retrieval
        hits = retrieval.search(self._doc(), "needle", layer="L2", k=10,
                                archived=self._archived())
        self.assertEqual(len(hits), 10)
        archived = [h for h in hits if h.get("archived")]
        self.assertGreaterEqual(len(archived), 2)
        self.assertEqual({h["archive_file"] for h in archived},
                         {"archive/changes-0001.json", "archive/changes-0002.json"},
                         "every archive file with a match must be visible at k=10")

    def test_small_k_keeps_recency_order(self):
        from amg import retrieval
        for k in (1, 3):
            hits = retrieval.search(self._doc(), "needle", layer="L2", k=k,
                                    archived=self._archived())
            self.assertEqual(len(hits), k)
            self.assertFalse(any(h.get("archived") for h in hits),
                             "below k=5 the newest live record still wins, as before")

    def test_spare_capacity_is_filled_with_history(self):
        from amg import retrieval
        hits = retrieval.search(self._doc(), "needle", layer="L2", k=24,
                                archived=self._archived())
        self.assertEqual(sum(1 for h in hits if h.get("archived")), 12)


class ArchiveSearchTests(unittest.TestCase):
    def setUp(self):
        with at(OLD):
            self.g = TempGraph()
            self.g.m.add_node(id="task.alpha", type="task", label="alpha parser", source="cmd:x")
            self.g.m.add_node(id="task.beta", type="task", label="beta linter", source="cmd:x")
        with at(NOW):
            self.m = Memory.open(self.g.dir)
            self.before = [h["id"] for h in self.m.search("alpha", layer="L2")]
            self.report = self.m.archive(days=30, apply=True)

    def tearDown(self):
        self.g.close()

    def test_default_l2_is_unchanged_by_archiving(self):
        self.assertEqual(self.before, ["task.alpha"])
        self.assertEqual(self.report["archived"], 2)
        with at(NOW):
            after = [h["id"] for h in Memory.open(self.g.dir).search("alpha", layer="L2")]
        self.assertEqual(after, [])

    def test_include_archive_finds_moved_history_and_says_where(self):
        with at(NOW):
            hits = Memory.open(self.g.dir).search("alpha", layer="L2", include_archive=True)
        self.assertEqual([h["id"] for h in hits], ["task.alpha"])
        hit = hits[0]
        self.assertTrue(hit["archived"])
        self.assertTrue(hit["archive_file"].startswith("changes-"))
        self.assertEqual(hit["at"], OLD)
        self.assertGreater(hit["rev"], 0)

    def test_k_applies_across_live_and_archived(self):
        with at(NOW):
            live = Memory.open(self.g.dir)
            # one new live record mentioning alpha, newer than the archived ones
            live.add_node(id="task.gamma-alpha", type="task", label="follow-up", source="cmd:x")
            both = live.search("alpha", layer="L2", k=10, include_archive=True)
        self.assertEqual(len(both), 2)
        self.assertEqual(both[0]["id"], "task.gamma-alpha")    # newest first
        self.assertNotIn("archived", both[0])                   # live record
        self.assertTrue(both[1]["archived"])                    # archived record
        with at(NOW):
            limited = Memory.open(self.g.dir).search("alpha", layer="L2", k=1,
                                                     include_archive=True)
        self.assertEqual(len(limited), 1)
        self.assertEqual(limited[0]["id"], "task.gamma-alpha")

    def test_flag_is_refused_on_node_layers(self):
        with at(NOW):
            for layer in ("L1", "L3", "L4"):
                with self.assertRaises(ProtocolError) as ctx:
                    Memory.open(self.g.dir).search("alpha", layer=layer, include_archive=True)
                self.assertEqual(ctx.exception.code, "E_ARCHIVE_LAYER")


class ArchiveSearchCliTests(unittest.TestCase):
    def setUp(self):
        with at(OLD):
            self.g = TempGraph()
            self.g.m.add_node(id="task.alpha", type="task", label="alpha", source="cmd:x")
        with at(NOW):
            Memory.open(self.g.dir).archive(days=30, apply=True)

    def tearDown(self):
        self.g.close()

    def test_cli_json_includes_archived_hit(self):
        with at(NOW):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cli_mod.main(["search", self.g.dir, "alpha", "--layer", "L2",
                                     "--include-archive", "--json"])
        self.assertEqual(code, 0)
        hits = json.loads(buf.getvalue())
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0]["archived"])

    def test_cli_refuses_flag_on_l3(self):
        with at(NOW):
            self.assertEqual(quiet(cli_mod.main,
                                   ["search", self.g.dir, "alpha", "--layer", "L3",
                                    "--include-archive"]), 2)


if __name__ == "__main__":
    unittest.main()
