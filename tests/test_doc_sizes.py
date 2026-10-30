"""The documentation size budget is a contract, so it needs a failing mode.

Pre-registered criteria:
1. the real tree passes (otherwise the gate would ship red, which teaches people to
   ignore it);
2. a README over 12 KiB fails, and the output says by how much — not just "too big";
3. a non-entry document at 20 KiB passes and at 25 KiB fails (24 KiB budget);
4. the numbers in the gate are the numbers stated in docs/README.md;
5. every document is covered by default, so a new one cannot escape the budget;
6. the append-only logs are out of scope on purpose and say so.
"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "check_doc_sizes.py")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True, cwd=ROOT)


def temp_doc(name, size):
    directory = tempfile.mkdtemp(prefix="amg-docsize-")
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("x" * size)
    return path


class DocSizeGateTests(unittest.TestCase):
    def test_real_tree_passes(self):
        res = run()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("within budget", res.stdout)

    def test_entry_document_over_budget_fails_with_overshoot(self):
        path = temp_doc("README.md", 12288 + 100)
        try:
            res = run(path)
        finally:
            os.unlink(path)
        self.assertEqual(res.returncode, 1)
        self.assertIn("over by 100 B", res.stdout)

    def test_entry_document_within_budget_passes(self):
        path = temp_doc("README.md", 12288 - 1)
        try:
            res = run(path)
        finally:
            os.unlink(path)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_other_document_budget_is_larger(self):
        under = temp_doc("NOTES.md", 20 * 1024)
        over = temp_doc("BIG.md", 24 * 1024 + 1)
        try:
            self.assertEqual(run(under).returncode, 0)
            res = run(over)
        finally:
            os.unlink(under)
            os.unlink(over)
        self.assertEqual(res.returncode, 1)

    def test_crlf_checkout_does_not_change_the_measured_size(self):
        # v0.19.0 failed on windows-latest for exactly this: the same document, one
        # byte per line larger in a CRLF checkout. The budget is about content.
        directory = tempfile.mkdtemp(prefix="amg-docsize-")
        path = os.path.join(directory, "README.md")
        lines = [b"x" * 99 for _ in range(122)]        # 12288 bytes as LF content
        try:
            with open(path, "wb") as fh:
                fh.write(b"\r\n".join(lines))
            self.assertGreater(os.path.getsize(path), 12288)
            self.assertEqual(run(path).returncode, 0, run(path).stdout)
        finally:
            os.unlink(path)

    def test_budgets_match_the_documentation(self):
        with open(os.path.join(ROOT, "docs", "README.md"), encoding="utf-8") as fh:
            index = fh.read()
        for needle in ("12 KiB", "24 KiB"):
            self.assertIn(needle, index, f"docs/README.md must state the {needle} budget")

    def test_defaults_cover_every_document(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import check_doc_sizes
        finally:
            sys.path.pop(0)
        targets = {path.replace(os.sep, "/") for path in check_doc_sizes.default_targets()}
        self.assertIn("README.md", targets)
        docs = {"docs/" + name for name in os.listdir(os.path.join(ROOT, "docs"))
                if name.endswith(".md")}
        self.assertEqual(docs - targets, set(), "documents not covered by the budget gate")

    def test_logs_are_out_of_scope_in_words(self):
        res = run("CHANGELOG.md")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("out of scope", res.stdout)


if __name__ == "__main__":
    unittest.main()
