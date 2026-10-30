import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "check_doc_symbols.py")


class DocSymbolGateTests(unittest.TestCase):
    """The gate must be able to fail; a green gate that never fails is theatre."""

    def _run(self, text):
        fd, path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            return subprocess.run([sys.executable, SCRIPT, path], capture_output=True, text=True)
        finally:
            os.unlink(path)

    def test_gate_passes_on_real_docs(self):
        res = subprocess.run([sys.executable, SCRIPT, "README.md", "docs/API.md"],
                             capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_gate_catches_phantom_command(self):
        res = self._run("Run `amg teleport` to beam the graph.\n")
        self.assertEqual(res.returncode, 1)
        self.assertIn("teleport", res.stdout)

    def test_gate_catches_phantom_method(self):
        res = self._run("Call `m.forget_everything()` when done.\n")
        self.assertEqual(res.returncode, 1)
        self.assertIn("forget_everything", res.stdout)


class DocCoverageTests(unittest.TestCase):
    """Documents must be reachable from the index, and commands from the contract.

    Both failures are silent by nature: an unlinked document is still in the
    repository, and an undocumented command still runs. Only a test makes them
    visible — the symbol gate cannot, because it only checks what is written.
    """

    def test_gate_defaults_cover_every_document(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import check_doc_symbols
        finally:
            sys.path.pop(0)
        targets = set(check_doc_symbols.default_targets())
        docs = {
            os.path.join("docs", name)
            for name in os.listdir(os.path.join(ROOT, "docs"))
            if name.endswith(".md")
        }
        self.assertIn("README.md", targets)
        self.assertEqual(docs - targets, set(), "documents not scanned by the gate")

    def test_gate_runs_on_all_documents_by_default(self):
        res = subprocess.run([sys.executable, SCRIPT], capture_output=True,
                             text=True, cwd=ROOT)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("docs/README.md", res.stdout)

    def test_docs_index_links_every_document(self):
        with open(os.path.join(ROOT, "docs", "README.md"), encoding="utf-8") as fh:
            index = fh.read()
        unlinked = sorted(
            name
            for name in os.listdir(os.path.join(ROOT, "docs"))
            if name.endswith(".md")
            and name != "README.md"
            and f"docs/{name}" not in index
            and f"({name})" not in index
        )
        self.assertEqual(unlinked, [], "documents missing from docs/README.md")

    def test_api_documents_every_command(self):
        sys.path.insert(0, os.path.join(ROOT, "src"))
        try:
            from amg.cli import COMMANDS
        finally:
            sys.path.pop(0)
        with open(os.path.join(ROOT, "docs", "API.md"), encoding="utf-8") as fh:
            api = fh.read()
        missing = sorted(name for name in COMMANDS if f"amg {name}" not in api)
        self.assertEqual(missing, [], f"commands missing from docs/API.md: {missing}")


if __name__ == "__main__":
    unittest.main()
