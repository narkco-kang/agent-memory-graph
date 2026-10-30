import os
import subprocess
import sys
import time
import unittest

from amg.errors import LockTimeout, ProtocolError
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
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env)
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
            for stream in (proc.stdout, proc.stderr):
                stream.close()

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


class LockStatsTests(unittest.TestCase):
    """The counters exist to diagnose contention; they must not change behaviour."""

    def setUp(self):
        self.g = TempGraph()
        self.store = Store(self.g.dir)

    def tearDown(self):
        self.g.close()

    def test_uncontended_acquisition_is_counted_with_no_polls(self):
        with self.store.locked(timeout=1):
            pass
        stats = self.store.lock_stats
        self.assertEqual(stats["acquisitions"], 1)
        self.assertEqual(stats["polls"], 0)
        self.assertEqual(stats["timeouts"], 0)
        self.assertGreaterEqual(stats["wait_max_ms"], 0)

    def test_timeout_is_counted(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        proc = subprocess.Popen([sys.executable, "-c", HOLDER, os.path.join(ROOT, "src"), self.g.dir],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", env=env)
        try:
            if proc.stdout.readline().strip() != "ready":
                self.fail(f"holder failed: {proc.stderr.read()[:400]}")
            with self.assertRaises(LockTimeout):
                with self.store.locked(timeout=0.2):
                    pass
            self.assertEqual(self.store.lock_stats["timeouts"], 1)
            self.assertEqual(self.store.lock_stats["acquisitions"], 0)
        finally:
            proc.kill()
            proc.wait(timeout=5)
            for stream in (proc.stdout, proc.stderr):
                stream.close()

    def test_poll_bounds_are_sane(self):
        import amg.store as store_mod
        self.assertLessEqual(store_mod.LOCK_POLL_START_S, store_mod.LOCK_POLL_MAX_S)
        self.assertLess(store_mod.LOCK_POLL_MAX_S, 0.05, "a long poll ceiling recreates the old tail")


class LockedReadTests(unittest.TestCase):
    """A reader must not race a writer: on Windows that makes the *writer* fail."""

    def setUp(self):
        self.g = TempGraph()
        self.store = Store(self.g.dir)

    def tearDown(self):
        self.g.close()

    def test_open_waits_for_a_held_lock_then_succeeds(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        proc = subprocess.Popen([sys.executable, "-c", HOLDER, os.path.join(ROOT, "src"), self.g.dir],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", env=env)
        try:
            if proc.stdout.readline().strip() != "ready":
                self.fail(f"holder failed: {proc.stderr.read()[:400]}")
            t0 = time.perf_counter()
            doc = self.store.read_locked()
            waited = time.perf_counter() - t0
            self.assertIn("nodes", doc)
            self.assertGreater(waited, 0.3, "read_locked should have waited for the holder")
        finally:
            proc.kill()
            proc.wait(timeout=5)
            for stream in (proc.stdout, proc.stderr):
                stream.close()

    def test_missing_graph_raises_without_creating_the_directory(self):
        import tempfile
        missing = os.path.join(tempfile.mkdtemp(prefix="amg-noread-"), "absent")
        with self.assertRaises(ProtocolError):
            Store(missing).read_locked()
        self.assertFalse(os.path.isdir(missing))


class LockTimeoutConfigTests(unittest.TestCase):
    """A default timeout is a policy, not a constant: bursts must be able to raise it."""

    def setUp(self):
        self.g = TempGraph()
        self.store = Store(self.g.dir)

    def tearDown(self):
        self.g.close()

    def test_default_is_five_seconds(self):
        import amg.store as store_mod
        os.environ.pop("AMG_LOCK_TIMEOUT", None)
        self.assertEqual(store_mod.default_lock_timeout(), 5.0)

    def test_env_var_raises_the_ceiling(self):
        import amg.store as store_mod
        os.environ["AMG_LOCK_TIMEOUT"] = "42"
        try:
            self.assertEqual(store_mod.default_lock_timeout(), 42.0)
        finally:
            os.environ.pop("AMG_LOCK_TIMEOUT", None)

    def test_nonsense_values_fall_back_to_the_default(self):
        import amg.store as store_mod
        for raw in ("abc", "0", "-3", "999999"):
            os.environ["AMG_LOCK_TIMEOUT"] = raw
            try:
                self.assertEqual(store_mod.default_lock_timeout(), 5.0, raw)
            finally:
                os.environ.pop("AMG_LOCK_TIMEOUT", None)

    def test_env_var_actually_changes_the_wait(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        proc = subprocess.Popen([sys.executable, "-c", HOLDER, os.path.join(ROOT, "src"), self.g.dir],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", env=env)
        try:
            if proc.stdout.readline().strip() != "ready":
                self.fail(f"holder failed: {proc.stderr.read()[:400]}")
            os.environ["AMG_LOCK_TIMEOUT"] = "0.25"
            t0 = time.perf_counter()
            try:
                with self.assertRaises(LockTimeout) as ctx:
                    with self.store.locked():
                        pass
            finally:
                os.environ.pop("AMG_LOCK_TIMEOUT", None)
            waited = time.perf_counter() - t0
            self.assertLess(waited, 1.5)
            self.assertIn("AMG_LOCK_TIMEOUT", str(ctx.exception))
        finally:
            proc.kill()
            proc.wait(timeout=5)
            for stream in (proc.stdout, proc.stderr):
                stream.close()
