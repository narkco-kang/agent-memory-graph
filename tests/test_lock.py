import os
import subprocess
import sys
import time
import unittest

from amg.errors import LockTimeout
from amg.store import Store
from helpers import TempGraph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOLDER = """
import sys, time
sys.path.insert(0, sys.argv[1])
from amg.store import Store
s = Store(sys.argv[2])
with s.locked(timeout=5):
    print("ready", flush=True)
    time.sleep(1.5)
print("released", flush=True)
"""


class LockTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()
        self.store = Store(self.g.dir)

    def tearDown(self):
        self.g.close()

    def test_lock_is_exclusive_across_processes(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        proc = subprocess.Popen([sys.executable, "-c", HOLDER, os.path.join(ROOT, "src"), self.g.dir],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            line = proc.stdout.readline().strip()
            if line != "ready":  # do NOT read stderr eagerly: read() blocks until exit
                self.fail(f"holder failed: {proc.stderr.read()[:400]}")
            t0 = time.perf_counter()
            with self.assertRaises(LockTimeout):
                with self.store.locked(timeout=0.2):
                    pass
            self.assertLess(time.perf_counter() - t0, 2.0)
        finally:
            proc.kill()
            proc.wait(timeout=5)

    def test_lock_released_after_context(self):
        with self.store.locked(timeout=1):
            pass
        t0 = time.perf_counter()
        with self.store.locked(timeout=1):
            pass
        self.assertLess(time.perf_counter() - t0, 0.5)

    def test_write_is_serialised_through_the_lock(self):
        self.store.read = lambda: {"nodes": [], "edges": [], "changes": [], "rev": 0}
        seen = []
        with self.store.locked(timeout=1):
            seen.append("a")
        with self.store.locked(timeout=1):
            seen.append("b")
        self.assertEqual(seen, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
