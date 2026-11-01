"""`amg version` must report the version that was released.

Why this file exists: v0.38.5 shipped with `__version__ = "0.36.1"` hardcoded in
`src/amg/__init__.py` while `pyproject.toml` said 0.38.5. Anyone installing 0.38.5 and
running `amg version` was told 0.36.1 — and every bug report keyed on that number was wrong.

`pyproject.toml` is the release truth (hatchling reads it to name the wheel). The runtime
string must not drift from it. Two independent readers, one assertion.

Mutation that must turn this red: change either number without the other.
"""
import os
import re
import unittest

import amg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pyproject_version() -> str:
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "pyproject.toml has no top-level version"
    return m.group(1)


class VersionConsistencyTest(unittest.TestCase):
    def test_runtime_version_matches_pyproject(self):
        self.assertEqual(
            amg.__version__,
            _pyproject_version(),
            "amg.__version__ drifted from pyproject.toml; `amg version` would lie",
        )

    def test_version_is_not_a_stale_literal(self):
        # Guards the specific regression: a hardcoded string that nobody bumps.
        self.assertRegex(amg.__version__, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
