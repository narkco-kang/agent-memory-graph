#!/usr/bin/env python3
"""Run every check this repository makes about itself, in one command.

The README and docs/README.md tell a reader to verify claims with five or six
separate commands; this runs them in order and prints one table. It is the same work
CI does, minus the platform matrix.

    python3 tools/verify.py             # everything available here
    python3 tools/verify.py --no-examples

Steps, in the order a failure is most likely to be informative:

  1. unit tests, with ResourceWarning promoted to an error (the suite closes every
     file and pipe it opens; that is enforced, not hoped for)
  2. documentation↔code symbol gate over README and every docs/*.md
  3. the end-to-end examples, including the MCP client
  4. artifact check — only if `dist/` holds a build to inspect

Exit codes: 0 all steps passed (skips allowed and printed), 1 a step failed,
2 usage. A skipped step is never counted as a pass.
"""
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")


def env():
    e = dict(os.environ)
    existing = e.get("PYTHONPATH")
    e["PYTHONPATH"] = SRC if not existing else SRC + os.pathsep + existing
    return e


def python(*args):
    return [sys.executable, *args]


def steps(include_examples):
    items = [
        ("unit tests (warnings are errors)",
         python("-W", "error::ResourceWarning", "-m", "unittest", "discover", "-s", "tests")),
        ("documentation↔code gate",
         python(os.path.join("tools", "check_doc_symbols.py"))),
    ]
    if include_examples:
        items += [
            ("example: quickstart", ["bash", os.path.join("examples", "quickstart.sh")]),
            ("example: lifecycle", ["bash", os.path.join("examples", "lifecycle.sh")]),
            ("example: MCP client", python(os.path.join("examples", "mcp_client.py"))),
            ("example: handoff", ["bash", os.path.join("examples", "handoff.sh")]),
            ("example: archive", ["bash", os.path.join("examples", "archive.sh")]),
        ]
    items.append(("artifacts in dist/", python(os.path.join("tools", "check_dist.py"), "dist")))
    return items


def run(command):
    return subprocess.run(command, cwd=ROOT, env=env(), capture_output=True, text=True)


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    include_examples = "--no-examples" not in argv[1:]

    print(f"verifying {ROOT}\n")
    failures = 0
    skipped = 0
    for name, command in steps(include_examples):
        if name.startswith("artifacts") and not os.path.isdir(os.path.join(ROOT, "dist")):
            print(f"  –  {name}: skipped (no dist/ — run `python -m build --outdir dist .`)")
            skipped += 1
            continue
        if command[0] == "bash" and shutil.which("bash") is None:
            print(f"  –  {name}: skipped (bash is not available)")
            skipped += 1
            continue
        started = time.perf_counter()
        result = run(command)
        elapsed = time.perf_counter() - started
        if result.returncode == 0:
            print(f"  ✓  {name} ({elapsed:.1f}s)")
            continue
        failures += 1
        print(f"  ✗  {name} ({elapsed:.1f}s, exit {result.returncode})")
        tail = (result.stdout + result.stderr).strip().splitlines()[-15:]
        for line in tail:
            print(f"       {line}")

    print()
    if failures:
        print(f"✗ {failures} step(s) failed, {skipped} skipped")
        return 1
    print(f"✓ all steps passed ({skipped} skipped)")
    return 0


if __name__ == "__main__":
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print(__doc__)
        sys.exit(0)
    sys.exit(main(sys.argv))
