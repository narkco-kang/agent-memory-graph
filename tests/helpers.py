import hashlib
import os
import shutil
import tempfile

from amg import Memory
import pathlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: A digest that is well-formed but wrong. Kept for tests that need a claim nobody
#: proved; write-time verification refuses to create such a node through the normal
#: path, so those tests append directly to the document instead.
SHA = "a" * 64
SHA2 = "b" * 64


def _digest_of(rel_path):
    path = os.path.join(ROOT, rel_path)
    try:
        return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    except OSError:
        return SHA


def ev(locator="path:docs/API.md", sha=None, captured="2026-10-29T10:00:00+08:00", grade=None):
    """Evidence item. `sha` defaults to the REAL digest of the referenced file.

    v0.37.0 verifies digests at write time, so a fabricated default would make every
    fixture that concludes with evidence fail for the wrong reason — the fixture would
    be testing the guard instead of the thing it means to test. Passing `sha=SHA`
    explicitly still means "make a claim nobody proved".
    """
    if sha is None:
        rel = locator[len("path:"):] if locator.startswith("path:") else ""
        sha = _digest_of(rel) if rel else SHA
    item = {"locator": locator, "content_sha256": sha, "captured_at": captured}
    if grade is not None:
        item["grade"] = grade
    return item


class TempGraph:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="amg-test-")
        # `ev()` cites real files in the repo, so write-time verification resolves
        # against the repo root. Tests that cite files inside the throwaway graph
        # directory set `Memory.evidence_root = None` (or their own base) themselves.
        Memory.evidence_root = ROOT
        self.m = Memory.init(self.dir, "t", goal="test")

    def reopen(self):
        self.m = Memory.open(self.dir)
        return self.m

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)
