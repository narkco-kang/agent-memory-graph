"""Single-file graph store: advisory lock, full-graph read, atomic replace.

No partial writes: a crash leaves either the old file or the new one.
Locking is `fcntl.flock` on POSIX and `msvcrt.locking` on Windows. Both are exercised
by the cross-process lock and concurrent-writer tests on `windows-latest` in CI; what
is **not** measured on Windows is the latency tail — the burst timings in
`docs/CONCURRENCY.md` are macOS-only and say so.
"""
import contextlib
import json
import os
import random
import tempfile
import time

from .errors import LockTimeout, ProtocolError

if os.name == "nt":  # pragma: no cover - exercised on the Windows CI runner
    import msvcrt
    _POSIX = False
else:
    import fcntl
    _POSIX = True

# Lock retry policy. The measured problem (docs/CONCURRENCY.md) was tail latency,
# not throughput: a fixed 20 ms sleep quantises the wait, so a writer that loses
# the race a few times waits 100-240 ms. Start at 1 ms, double to a 16 ms ceiling,
# and jitter so waiters do not re-collide in lockstep.
LOCK_POLL_START_S = 0.001
LOCK_POLL_MAX_S = 0.016

# Default wait for the write lock. A write on the 15.6 MB real graph costs ~147 ms,
# so 5 s covers roughly 34 writes queued ahead of yours (docs/CONCURRENCY.md);
# beyond that a correct lock still times out. AMG_LOCK_TIMEOUT raises the ceiling
# for burst workloads without changing the default for interactive use.
DEFAULT_LOCK_TIMEOUT = 5.0


def default_lock_timeout() -> float:
    raw = os.environ.get("AMG_LOCK_TIMEOUT")
    if not raw:
        return DEFAULT_LOCK_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT
    return value if 0 < value <= 3600 else DEFAULT_LOCK_TIMEOUT


def dumps(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


class Store:
    def __init__(self, path: str):
        self.dir = os.path.abspath(path)
        self.file = os.path.join(self.dir, "graph.json")
        self.lockfile = os.path.join(self.dir, ".lock")
        # Lock observations, aggregated in O(1) memory. Behaviour is unchanged:
        # these numbers exist to answer "was a slow write slow because it waited
        # for the lock, or because the holder was slow?" (docs/CONCURRENCY.md).
        self.lock_stats = {"acquisitions": 0, "polls": 0, "timeouts": 0,
                           "wait_total_ms": 0.0, "wait_max_ms": 0.0,
                           "polls_max": 0}

    def exists(self) -> bool:
        return os.path.isfile(self.file)

    def read(self) -> dict:
        """Read the graph file. Callers inside a transaction already hold the lock."""
        if not self.exists():
            raise ProtocolError("E_NO_GRAPH", f"no graph at {self.file}")
        with open(self.file, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def read_locked(self) -> dict:
        """Read under the lock, for callers that do not already hold it.

        Windows cannot `os.replace` a file another process has open, so a lock-free
        reader racing a writer makes the *writer* fail with `PermissionError`
        (observed in the concurrency test on Windows CI). Coordinating reads with
        writes removes that failure mode; the cost is that an open waits behind an
        in-flight write, which on this store is milliseconds.
        """
        # Check before locking: `locked()` creates the directory, and opening a
        # missing graph must leave no trace (read-only mode promises that).
        if not self.exists():
            raise ProtocolError("E_NO_GRAPH", f"no graph at {self.file}")
        with self.locked():
            return self.read()

    def _atomic_write(self, doc: dict) -> None:
        payload = dumps(doc)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".graph.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.file)
            if os.name != "nt":  # opening a directory for fsync is POSIX-only
                dirfd = os.open(self.dir, os.O_RDONLY)
                try:
                    os.fsync(dirfd)
                finally:
                    os.close(dirfd)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _acquire(self, fh, timeout: float) -> None:
        """Block until the exclusive lock is held, or raise LockTimeout.

        POSIX uses fcntl.flock; Windows uses msvcrt.locking on one byte at offset
        0. Both are advisory and released when the handle closes, so a crashed
        process cannot wedge the graph.

        Polls are counted because the polling loop is the suspected cause of the
        contention tail: each `OSError` means the lock was held by someone else at
        that instant, so a large poll count with a large wait is starvation, while
        a small poll count with a large wait is a slow holder.
        """
        deadline = time.time() + timeout
        started = time.perf_counter()
        polls = 0
        while True:
            try:
                if _POSIX:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:  # pragma: no cover - Windows runner only
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                wait_ms = (time.perf_counter() - started) * 1000
                stats = self.lock_stats
                stats["acquisitions"] += 1
                stats["polls"] += polls
                stats["wait_total_ms"] = round(stats["wait_total_ms"] + wait_ms, 3)
                stats["wait_max_ms"] = max(stats["wait_max_ms"], round(wait_ms, 3))
                stats["polls_max"] = max(stats["polls_max"], polls)
                return
            except OSError:
                if time.time() >= deadline:
                    self.lock_stats["timeouts"] += 1
                    raise LockTimeout(
                        f"write lock timeout after {timeout}s: {self.lockfile} "
                        f"(another writer held it; on a large graph each write serialises, "
                        f"so raise AMG_LOCK_TIMEOUT for bursts)")
                polls += 1
                ceiling = LOCK_POLL_MAX_S
                backoff = min(ceiling, LOCK_POLL_START_S * (2 ** min(polls - 1, 8)))
                time.sleep(backoff * (0.5 + random.random() / 2))

    def _release(self, fh) -> None:
        if _POSIX:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        else:  # pragma: no cover - Windows runner only
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

    @contextlib.contextmanager
    def locked(self, timeout: float = None):
        timeout = default_lock_timeout() if timeout is None else timeout
        os.makedirs(self.dir, exist_ok=True)
        fh = open(self.lockfile, "a+b")
        if not _POSIX and os.fstat(fh.fileno()).st_size == 0:
            fh.write(b"\0")  # msvcrt locks a byte range; ensure the byte exists
            fh.flush()
        try:
            self._acquire(fh, timeout)
            yield
        finally:
            try:
                self._release(fh)
            except OSError:
                pass
            fh.close()

    @contextlib.contextmanager
    def transaction(self):
        """Yield (doc, commit). commit() bumps rev, stamps updatedAt and saves."""
        with self.locked():
            doc = self.read()
            committed = {"done": False}

            def commit():
                if committed["done"]:
                    return
                from .const import now
                doc["rev"] = int(doc.get("rev", 0)) + 1
                doc["updatedAt"] = now()
                self._atomic_write(doc)
                committed["done"] = True

            yield doc, commit
