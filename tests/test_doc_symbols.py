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


if __name__ == "__main__":
    unittest.main()
