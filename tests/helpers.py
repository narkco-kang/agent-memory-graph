import shutil
import tempfile

from amg import Memory

SHA = "a" * 64
SHA2 = "b" * 64


def ev(locator="path:docs/API.md", sha=SHA, captured="2026-10-29T10:00:00+08:00", grade=None):
    item = {"locator": locator, "content_sha256": sha, "captured_at": captured}
    if grade is not None:
        item["grade"] = grade
    return item


class TempGraph:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="amg-test-")
        self.m = Memory.init(self.dir, "t", goal="test")

    def reopen(self):
        self.m = Memory.open(self.dir)
        return self.m

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)
