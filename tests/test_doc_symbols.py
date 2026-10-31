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


class RecursiveCoverageTests(unittest.TestCase):
    """v0.30.0: a document in a subdirectory must not escape the symbol gate.
    v0.31.0: nor may a document renamed away from `.md`."""

    def test_default_targets_are_recursive(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import check_doc_symbols
        finally:
            sys.path.pop(0)
        fake = tempfile.mkdtemp(prefix="amg-docwalk-")
        for rel in ("README.md", "docs/ok.md", "docs/decisions/new.md",
                    "docs/decisions/v19/more.md", "docs/n/A.markdown",
                    "docs/n/B.txt", "docs/n/NOEXT"):
            path = os.path.join(fake, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x")
        original = check_doc_symbols.ROOT
        check_doc_symbols.ROOT = fake
        try:
            targets = {path.replace(os.sep, "/")
                       for path in check_doc_symbols.default_targets()}
        finally:
            check_doc_symbols.ROOT = original
        self.assertEqual(targets, {"README.md", "docs/ok.md", "docs/decisions/new.md",
                                   "docs/decisions/v19/more.md", "docs/n/A.markdown",
                                   "docs/n/B.txt", "docs/n/NOEXT"})

    def test_renamed_document_cannot_hide_a_phantom_command(self):
        # v0.31.0: on v0.30.0 this page documented `amg teleport` with exit 0, because
        # the gate selected files by `.md` suffix. The suffix was the only difference.
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import check_doc_symbols
        finally:
            sys.path.pop(0)
        fake = tempfile.mkdtemp(prefix="amg-docscope-")
        path = os.path.join(fake, "docs", "n", "PHANTOM.markdown")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("Run `amg teleport` to beam the graph.\n")
        with open(os.path.join(fake, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("entry document, no symbols here\n")
        original = check_doc_symbols.ROOT
        check_doc_symbols.ROOT = fake
        try:
            missing = check_doc_symbols.scan_targets(check_doc_symbols.default_targets())
        finally:
            check_doc_symbols.ROOT = original
        self.assertEqual(len(missing), 1, missing)
        self.assertIn("teleport", missing[0])

    def test_both_gates_see_the_same_files(self):
        # One design was copied twice and the copy diverged in neither place — the
        # v0.31.0 bug was in both. Sharing doc_scope.py fixes it structurally; this
        # test fails if either gate ever stops using it.
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import check_doc_sizes
            import check_doc_symbols
        finally:
            sys.path.pop(0)
        fake = tempfile.mkdtemp(prefix="amg-docscope-")
        for rel in ("README.md", "docs/a.md", "docs/deep/b.markdown", "docs/deep/c.txt"):
            path = os.path.join(fake, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x")
        sizes_root, symbols_root = check_doc_sizes.ROOT, check_doc_symbols.ROOT
        check_doc_sizes.ROOT = check_doc_symbols.ROOT = fake
        try:
            sizes = {p.replace(os.sep, "/") for p in check_doc_sizes.default_targets()}
            symbols = {p.replace(os.sep, "/") for p in check_doc_symbols.default_targets()}
        finally:
            check_doc_sizes.ROOT, check_doc_symbols.ROOT = sizes_root, symbols_root
        self.assertEqual(sizes, symbols)


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
        targets = {path.replace(os.sep, "/") for path in check_doc_symbols.default_targets()}
        # Forward slashes: the gate emits POSIX-style relative paths so its output is
        # identical on every platform (see the Windows fix on 4e0daa6).
        # v0.31.0: every file under docs/, not only `*.md` — the suffix was the bypass.
        docs = set()
        for current, _dirs, names in os.walk(os.path.join(ROOT, "docs")):
            for name in names:
                rel = os.path.relpath(os.path.join(current, name), ROOT)
                docs.add(rel.replace(os.sep, "/"))
        self.assertIn("README.md", targets)
        self.assertEqual(docs - targets, set(), "documents not scanned by the gate")

    def test_gate_runs_on_all_documents_by_default(self):
        res = subprocess.run([sys.executable, SCRIPT], capture_output=True,
                             text=True, cwd=ROOT)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("docs/README.md", res.stdout.replace("\\", "/"))

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
