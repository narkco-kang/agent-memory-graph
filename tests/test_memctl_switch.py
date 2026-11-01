"""`memctl switch`: the five steps, and the two that must be impossible to skip.

`memctl` lives outside the package (it is a team tool, not library code), so these
tests drive it as a subprocess in a throwaway workspace.

The two guards that carry the weight:

* **step 1 refuses while a writer may be active.** Two lock schemes are in play —
  `kg.py` creates `<group>.lock`, `amg` locks `.lock`. They are not mutually exclusive,
  so a concurrent window does not lose a field, it loses whole records: measured, two
  writers × 5 writes left 5 of 10 nodes. Refusing is the only safe move.
* **a failure after the switch rolls the config back.** A half-switched entry point is
  worse than a failed one: the next reader gets data from a backend nobody chose.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import pathlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMCTL = os.path.join(os.path.dirname(ROOT), "tools", "memctl")


def make_workspace():
    """A miniature workspace: knowledge-graph/graphs/<group>.json + a copy of memctl."""
    ws = tempfile.mkdtemp(prefix="amg-switch-")
    graphs = os.path.join(ws, "knowledge-graph", "graphs")
    os.makedirs(graphs)
    os.makedirs(os.path.join(ws, "tools"))
    with open(os.path.join(graphs, "grp.json"), "w", encoding="utf-8") as fh:
        json.dump({"schema": "group-kg/v1", "group": "grp", "session": "", "goal": "",
                   "updatedAt": "2026-11-01T00:00:00+08:00", "rev": 0,
                   "nodes": [], "edges": [], "changes": []}, fh, ensure_ascii=False)
    tool = os.path.join(ws, "tools", "memctl")
    shutil.copy(MEMCTL, tool)
    return ws, tool


def run_tool(ws, tool, *args, amg="/nonexistent/amg"):
    env = dict(os.environ)
    env["MEMCTL_CONF"] = os.path.join(ws, ".conf.json")
    env["MEMCTL_AMG"] = amg
    return subprocess.run([sys.executable, tool, *args], capture_output=True,
                          text=True, encoding="utf-8", env=env, cwd=ws, timeout=60)


class SwitchGuardTest(unittest.TestCase):
    def setUp(self):
        self.ws, self.tool = make_workspace()
        self.graphs = os.path.join(self.ws, "knowledge-graph", "graphs")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def conf(self):
        path = os.path.join(self.ws, ".conf.json")
        if not os.path.exists(path):
            return {"backend": "kg"}
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_an_active_lock_blocks_the_switch(self):
        """MUTATION GUARD: skip step 1 and this fails — the switch proceeds."""
        with open(os.path.join(self.graphs, ".lock"), "w") as fh:
            fh.write("held")
        res = run_tool(self.ws, self.tool, "switch", "grp", "amg")
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("拒绝切换", res.stderr)
        self.assertEqual(self.conf().get("backend", "kg"), "kg",
                         "a refused switch must not have written the config")

    def test_force_records_the_override_instead_of_hiding_it(self):
        with open(os.path.join(self.graphs, ".lock"), "w") as fh:
            fh.write("held")
        res = run_tool(self.ws, self.tool, "switch", "grp", "amg", "--force")
        self.assertIn("--force", res.stderr)

    def test_a_failure_after_the_switch_rolls_the_config_back(self):
        """MUTATION GUARD: drop the rollback path and this fails."""
        # amg is pointed at a path that does not exist, so the probe write fails.
        res = run_tool(self.ws, self.tool, "switch", "grp", "amg")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("rollback", res.stderr)
        self.assertEqual(self.conf().get("backend"), "kg",
                         "a failed switch must leave the previous backend in place")

    def test_switching_to_the_current_backend_is_a_no_op(self):
        res = run_tool(self.ws, self.tool, "switch", "grp", "kg")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("无需切换", res.stdout)

    def test_verify_rejects_a_graph_with_a_broken_rev_sequence(self):
        path = os.path.join(self.graphs, "grp.json")
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["rev"] = 5
        doc["changes"] = [{"at": "2026-11-01T00:00:00+08:00", "by": "t", "op": "add-node",
                           "target": "x", "note": "", "rev": 2}]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        res = run_tool(self.ws, self.tool, "verify", "grp")
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("new_corruption", res.stdout)


class VerifySplitsLegacyFromCorruptionTest(unittest.TestCase):
    """`verify` must not treat "history never wrote rev" as damage.

    Measured on the team's graph C仔指挥部: 8 leading nulls predate the `rev` field,
    and 2 later nulls (index 796, 896) are damage. Back-filling the first group to
    make the output look clean would be forging an audit chain, so they are reported
    and allowed; only the second group blocks a switch.
    """

    def setUp(self):
        self.ws, self.tool = make_workspace()
        self.path = os.path.join(self.ws, "knowledge-graph", "graphs", "grp.json")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def write(self, changes, rev):
        with open(self.path, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["changes"] = changes
        doc["rev"] = rev
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)

    @staticmethod
    def change(rev, at="2026-11-01T00:00:00+08:00"):
        return {"at": at, "by": "t", "op": "add-node", "target": f"n{rev}", "note": "", "rev": rev}

    def run_verify(self):
        return run_tool(self.ws, self.tool, "verify", "grp")

    def test_leading_nulls_are_legacy_and_do_not_block(self):
        """MUTATION GUARD: call legacy nulls corrupt and C仔指挥部 can never switch."""
        changes = [self.change(None) for _ in range(3)] + [self.change(1), self.change(2)]
        self.write(changes, 2)
        res = self.run_verify()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("legacy_missing_rev   3", res.stdout)
        self.assertIn("new_corruption       0", res.stdout)

    def test_a_null_after_the_first_real_rev_is_corruption(self):
        """MUTATION GUARD: call corruption legacy and damage never blocks."""
        changes = [self.change(1), self.change(None), self.change(2)]
        self.write(changes, 2)
        res = self.run_verify()
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("new_corruption       1", res.stdout)

    def test_a_duplicate_rev_is_corruption(self):
        self.write([self.change(1), self.change(1)], 1)
        self.assertEqual(self.run_verify().returncode, 1)

    def test_a_backwards_rev_is_corruption(self):
        self.write([self.change(2), self.change(1)], 2)
        self.assertEqual(self.run_verify().returncode, 1)

    def test_top_level_rev_disagreeing_with_the_last_record_is_corruption(self):
        self.write([self.change(1), self.change(2)], 9)
        res = self.run_verify()
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("top-level rev is 9", res.stdout)

    def test_a_switch_is_not_blocked_by_legacy_nulls(self):
        """The whole point: C仔指挥部 has 8 of them and still must be switchable."""
        changes = [self.change(None) for _ in range(8)] + [self.change(i) for i in (1, 2, 3)]
        self.write(changes, 3)
        res = run_tool(self.ws, self.tool, "switch", "grp", "amg")
        self.assertNotIn("verify 失败", res.stderr)


class CorruptionBaselineTest(unittest.TestCase):
    """A known defect must not block every future upgrade; a new one must still block.

    Measured on C仔指挥部: two records from 10-26 and 10-27 lost their rev. Freezing
    them at the first switch makes them a registered known limitation. Anything that
    appears later is a fault. The two failure directions are tested on purpose:
    treating known damage as new locks the group forever; treating new damage as known
    lets a corrupt ledger switch silently.
    """

    def setUp(self):
        self.ws, self.tool = make_workspace()
        self.graphs = os.path.join(self.ws, "knowledge-graph", "graphs")
        self.path = os.path.join(self.graphs, "grp.json")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def write(self, changes, rev):
        with open(self.path, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["changes"] = changes
        doc["rev"] = rev
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)

    @staticmethod
    def change(rev, at="2026-11-01T00:00:00+08:00", op="add-node", target="t"):
        return {"at": at, "by": "t", "op": op, "target": target, "note": "", "rev": rev}

    def freeze(self, entries):
        """Freeze a baseline the way `switch` does at its first run."""
        path = os.path.join(self.ws, ".conf.json")
        conf = json.loads(pathlib.Path(path).read_text(encoding="utf-8")) if os.path.exists(path) else {"backend": "kg"}
        conf.setdefault("corruption_baseline", {})["grp"] = entries
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(conf, fh)

    def test_unfrozen_damage_blocks(self):
        self.write([self.change(1), self.change(None)], 1)
        self.assertEqual(run_tool(self.ws, self.tool, "verify", "grp").returncode, 1)

    def test_a_frozen_defect_does_not_block(self):
        """MUTATION GUARD: treat known damage as new and this fails."""
        self.write([self.change(1), self.change(None)], 1)
        self.freeze([{"index": 1, "at": "2026-11-01T00:00:00+08:00", "op": "add-node",
                      "target": "t", "rev": None}])
        res = run_tool(self.ws, self.tool, "verify", "grp")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("known_corruption", res.stdout)

    def test_new_damage_still_blocks_after_a_freeze(self):
        """MUTATION GUARD: treat new damage as known and this fails."""
        self.write([self.change(1), self.change(None)], 1)
        self.freeze([{"index": 1, "at": "2026-11-01T00:00:00+08:00", "op": "add-node",
                      "target": "t", "rev": None}])
        self.write([self.change(1), self.change(None), self.change(None, at="2026-11-02T00:00:00+08:00")], 1)
        res = run_tool(self.ws, self.tool, "verify", "grp")
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("new_corruption", res.stdout)

    def test_the_baseline_is_frozen_once_and_not_appended(self):
        """A baseline that can grow on demand is a universal key."""
        path = os.path.join(self.ws, ".conf.json")
        self.write([self.change(1), self.change(None)], 1)
        self.freeze([{"index": 1, "at": "2026-11-01T00:00:00+08:00", "op": "add-node",
                      "target": "t", "rev": None}])
        first = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        run_tool(self.ws, self.tool, "verify", "grp")
        second = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        self.assertEqual(first["corruption_baseline"], second["corruption_baseline"],
                         "verify must never extend the baseline")


class AlreadySwitchedStillFreezesTest(unittest.TestCase):
    """A group switched before the baseline existed must still be able to freeze it.

    Measured in production: `switch 测试群 amg` flipped the global backend, so the other
    two groups were "already amg" on their next call — and the early return skipped the
    freeze, leaving C仔指挥部 reporting `new_corruption 2 (blocking)` forever. Skipping
    the freeze must not be a silent consequence of "nothing to switch".
    """

    def setUp(self):
        self.ws, self.tool = make_workspace()
        self.graphs = os.path.join(self.ws, "knowledge-graph", "graphs")
        self.path = os.path.join(self.graphs, "grp.json")
        with open(os.path.join(self.ws, ".conf.json"), "w", encoding="utf-8") as fh:
            json.dump({"backend": "amg"}, fh)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def write_broken(self):
        with open(self.path, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["changes"] = [
            {"at": "2026-11-01T00:00:00+08:00", "by": "t", "op": "add-node",
             "target": "a", "note": "", "rev": 1},
            {"at": "2026-11-02T00:00:00+08:00", "by": "t", "op": "fix-edge",
             "target": None, "note": "", "rev": None},
        ]
        doc["rev"] = 1
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)

    def test_an_already_switched_group_gets_its_baseline_frozen(self):
        """MUTATION GUARD: return early on "already amg" and this fails."""
        self.write_broken()
        res = run_tool(self.ws, self.tool, "switch", "grp", "amg")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("补冻结", res.stdout)
        verify = run_tool(self.ws, self.tool, "verify", "grp")
        self.assertEqual(verify.returncode, 0, verify.stdout)
        self.assertIn("new_corruption", verify.stdout)

    def test_a_second_call_does_not_freeze_twice(self):
        self.write_broken()
        run_tool(self.ws, self.tool, "switch", "grp", "amg")
        first = json.loads(pathlib.Path(os.path.join(self.ws, ".conf.json")).read_text(encoding="utf-8"))["corruption_baseline"]
        run_tool(self.ws, self.tool, "switch", "grp", "amg")
        second = json.loads(pathlib.Path(os.path.join(self.ws, ".conf.json")).read_text(encoding="utf-8"))["corruption_baseline"]
        self.assertEqual(first, second, "the baseline may only be written once")

    def test_a_clean_group_needs_no_baseline(self):
        res = run_tool(self.ws, self.tool, "switch", "grp", "amg")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        conf = json.loads(pathlib.Path(os.path.join(self.ws, ".conf.json")).read_text(encoding="utf-8"))
        self.assertNotIn("grp", conf.get("corruption_baseline") or {})


if __name__ == "__main__":
    unittest.main()
