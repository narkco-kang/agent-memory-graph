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


def write_fixture(path, text, newline="\n"):
    """Write `text` to `path` with a pinned newline, and return the digest of what landed.

    Use this for any fixture whose digest a test will declare. Two releases have now gone
    red on Windows for the same reason: `open(path, "w")` translates `\\n` to `\\r\\n` there,
    so the file holds `b"...\\r\\n"` while the test declares `sha256(b"...\\n")`. The digest
    does not match, the node lands in `mismatch`, and a test that was supposed to prove
    something about the code proves something about the platform instead.

    v0.37.4 fixed this inside `test_audit_verify_buckets`; v0.38.2 shipped
    `test_check_is_shape_only` that reproduced it verbatim, because the fix lived in one
    file instead of in the place every test writes from. Returning the digest read back
    from disk — rather than one computed from the string — makes the mistake impossible to
    repeat: there is nothing left to declare by hand.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


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
    """A throwaway graph, with the evidence base scoped to its lifetime.

    Why the save/restore exists (v0.38.0): `Memory.evidence_root` is a CLASS attribute,
    on purpose — decision #56 gives one evidence base per process rather than one per
    node. This helper used to set it to `ROOT` and never put it back, so whichever test
    file ran first decided the evidence base for every test after it. The symptom was
    exactly today's recurring one: each file passed alone, the suite failed, because the
    object under measurement had been changed by the test that ran before it.

    Restoring in `close()` is not enough — tests that fail before `close()` would still
    leak. `__exit__` plus `restore()` cover both, and `_save_base` runs before anything
    that can raise.
    """

    def __init__(self, evidence_root=ROOT):
        self.dir = tempfile.mkdtemp(prefix="amg-test-")
        # Whatever the previous holder left, remember it so close() can put it back.
        self._previous_base = Memory.evidence_root
        # `ev()` cites real files in the repo, so write-time verification resolves
        # against the repo root. A test that cites files inside its own throwaway graph
        # passes evidence_root=None (the graph dir) instead.
        Memory.evidence_root = evidence_root
        self.m = Memory.init(self.dir, "t", goal="test")

    def reopen(self):
        self.m = Memory.open(self.dir)
        return self.m

    def restore(self):
        """Put the evidence base back the way this helper found it."""
        Memory.evidence_root = self._previous_base

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        self.restore()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
