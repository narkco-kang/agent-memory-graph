"""Exit-code classification (maintainer ruling 2026-10-29).

Rule: `2` means *the caller used the API wrong*; `1` means *the content violates
the protocol*. There is deliberately **no default** — an unclassified code is a
programming error and must fail loudly, never silently become 1.
"""
import contextlib
import glob
import io
import os
import re
import unittest

from amg import ProtocolError
from amg.cli import (ERROR_EXIT_CODES, EXIT_CODES_BY_ERROR, USAGE_EXIT_CODES,
                     exit_code_for)
from helpers import TempGraph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "amg")
CODE_LITERAL = re.compile(r'"(E_[A-Z0-9_]+)"')


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args)


class ExitCodeTableTests(unittest.TestCase):
    def test_two_sets_are_disjoint_and_complete(self):
        self.assertFalse(set(USAGE_EXIT_CODES) & set(ERROR_EXIT_CODES))
        self.assertEqual(set(EXIT_CODES_BY_ERROR),
                         set(USAGE_EXIT_CODES) | set(ERROR_EXIT_CODES))

    def test_each_usage_code_maps_to_2(self):
        for code in sorted(USAGE_EXIT_CODES):
            self.assertEqual(EXIT_CODES_BY_ERROR[code], 2, code)
            self.assertEqual(exit_code_for(ProtocolError(code, "x")), 2, code)

    def test_each_error_code_maps_to_1(self):
        for code in sorted(ERROR_EXIT_CODES):
            self.assertEqual(EXIT_CODES_BY_ERROR[code], 1, code)
            self.assertEqual(exit_code_for(ProtocolError(code, "x")), 1, code)

    def test_every_code_raised_in_source_is_classified(self):
        raised = set()
        for path in glob.glob(os.path.join(SRC, "*.py")):
            with open(path, encoding="utf-8") as fh:
                raised |= set(CODE_LITERAL.findall(fh.read()))
        missing = sorted(raised - set(EXIT_CODES_BY_ERROR))
        self.assertEqual(missing, [], f"unclassified codes raised in src/amg: {missing}")

    def test_unclassified_code_must_fail_loudly(self):
        with self.assertRaises(RuntimeError):
            exit_code_for(ProtocolError("E_NOT_IN_THE_TABLE", "boom"))

    def test_docs_api_lists_every_code(self):
        with open(os.path.join(ROOT, "docs", "API.md"), encoding="utf-8") as fh:
            text = fh.read()
        missing = sorted(code for code in EXIT_CODES_BY_ERROR if code not in text)
        self.assertEqual(missing, [], f"codes missing from docs/API.md: {missing}")


class CliExitCodeEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.g = TempGraph()

    def tearDown(self):
        self.g.close()

    def _cli(self, *args):
        from amg import cli
        return quiet(cli.main, list(args))

    def test_usage_errors_exit_2(self):
        m = self.g
        self.assertEqual(self._cli("init", m.dir, "--group", "other"), 2)          # E_EXISTS
        self.assertEqual(self._cli("add", m.dir, "--id", "x", "--type", "nope",
                                   "--label", "L", "--source", "s"), 2)            # E_BAD_TYPE
        self.assertEqual(self._cli("add", m.dir, "--id", "x", "--type", "task",
                                   "--label", "L", "--source", "s",
                                   "--status", "nope"), 2)                         # E_BAD_STATUS
        self.assertEqual(self._cli("search", m.dir, "x", "--layer", "L9"), 2)      # E_BAD_LAYER
        self.assertEqual(self._cli("link", m.dir, "--from", "a", "--to", "b",
                                   "--kind", "nope"), 2)                            # E_BAD_EDGE
        self.assertEqual(self._cli("add", m.dir, "--id", "rule.x", "--type", "rule",
                                   "--label", "R", "--source", "s"), 2)            # E_RULE_APPLIES
        m.m.add_node("task.a", "task", "A", source="s")
        self.assertEqual(self._cli("status", m.dir, "task.a", "superseded",
                                   "--note", "n"), 2)                              # E_USE_SUPERSEDE

    def test_content_violations_exit_1(self):
        m = self.g
        m.m.add_node("task.a", "task", "A", source="s")
        self.assertEqual(self._cli("add", m.dir, "--id", "task.a", "--type", "task",
                                   "--label", "A", "--source", "s"), 1)            # E_DUP_ID
        self.assertEqual(self._cli("status", m.dir, "task.a", "done", "--note", ""), 1)  # E_NOTE_REQUIRED
        self.assertEqual(self._cli("status", m.dir, "ghost", "done", "--note", "n"), 1)  # E_NO_NODE
        self.assertEqual(self._cli("add", m.dir, "--id", "decision.d", "--type", "decision",
                                   "--label", "D", "--source", "s", "--status", "done"), 1)  # E_EVIDENCE_MISSING
        bad_ev = "path:README.md|nothex|2026-10-29T10:00:00+08:00"
        self.assertEqual(self._cli("add", m.dir, "--id", "decision.e", "--type", "decision",
                                   "--label", "E", "--source", "s", "--evidence", bad_ev), 1)  # E_EVIDENCE_FORMAT


if __name__ == "__main__":
    unittest.main()
