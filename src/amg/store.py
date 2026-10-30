"""Single-file graph store: advisory lock, full-graph read, atomic replace.

No partial writes: a crash leaves either the old file or the new one.
fcntl-based locking is POSIX-only; Windows locking is NOT verified (README).
"""
import contextlib
import json
import os
import tempfile
import time

from .errors import LockTimeout, ProtocolError

if os.name == "nt":  # pragma: no cover - exercised on the Windows CI runner
    import msvcrt
    _POSIX = False
else:
    import fcntl
    _POSIX = True


def dumps(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


class Store:
    def __init__(self, path: str):
        self.dir = os.path.abspath(path)
        self.file = os.path.join(self.dir, "graph.json")
        self.lockfile = os.path.join(self.dir, ".lock")

    def exists(self) -> bool:
        return os.path.isfile(self.file)

    def read(self) -> dict:
        if not self.exists():
            raise ProtocolError("E_NO_GRAPH", f"no graph at {self.file}")
        with open(self.file, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _atomic_write(self, doc: dict) -> None:
        payload = dumps(doc)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".graph.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.file)
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
        """
        deadline = time.time() + timeout
        while True:
            try:
                if _POSIX:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:  # pragma: no cover - Windows runner only
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.time() >= deadline:
                    raise LockTimeout(f"write lock timeout after {timeout}s: {self.lockfile}")
                time.sleep(0.02)

    def _release(self, fh) -> None:
        if _POSIX:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        else:  # pragma: no cover - Windows runner only
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

    @contextlib.contextmanager
    def locked(self, timeout: float = 5.0):
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
