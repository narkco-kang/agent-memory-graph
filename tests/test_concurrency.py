"""Concurrent writers must not lose or duplicate anything. Small, on every commit.

The full burst (8 writers × 25 writes, with latency measurement) lives in
`experiments/concurrency/run_stress.py` and `docs/CONCURRENCY.md`; CI machines are
too noisy for its timings, but they can still check the correctness properties.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402

WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from amg import Memory
m = Memory.open(sys.argv[2])
tag = sys.argv[3]
for i in range(int(sys.argv[4])):
    m.add_node(id="race.%s.n%d" % (tag, i), type="task", label="w %s %d" % (tag, i),
               source="concurrency test", note="n", by="race")
"""

WRITERS, WRITES = 3, 3


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.join(tempfile.mkdtemp(prefix="amg-race-"), "mem")
        Memory.init(self.dir, group="race")

    def test_concurrent_writers_lose_nothing(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        procs = [subprocess.Popen(
            [sys.executable, "-c", WRITER, os.path.join(ROOT, "src"), self.dir, str(i), str(WRITES)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env)
            for i in range(WRITERS)]
        for proc in procs:
            _, err = proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 0, f"writer failed: {err[-500:]}")

        m = Memory.open(self.dir)
        ids = [n["id"] for n in m.doc["nodes"]]
        expected = {f"race.{i}.n{j}" for i in range(WRITERS) for j in range(WRITES)}
        self.assertEqual(set(ids), expected, "a concurrent write was lost or duplicated")
        self.assertEqual(len(ids), len(expected))

        counts = {}
        for change in m.doc["changes"]:
            target = change.get("target")
            if target in expected:
                counts[target] = counts.get(target, 0) + 1
        self.assertEqual(len(counts), len(expected), "a write left no change record")
        self.assertEqual(set(counts.values()), {1}, "a write produced more than one change record")
        self.assertTrue(m.check()["ok"], m.check()["errors"])
        self.assertEqual(m.doc["rev"], len(expected), "rev must advance once per committed write")


if __name__ == "__main__":
    unittest.main()
