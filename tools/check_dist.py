#!/usr/bin/env python3
"""Check that the built artifacts are complete and self-consistent.

Run after `python -m build --outdir dist .`:

    python tools/check_dist.py dist

Why this exists: v0.7.0's first sdist shipped `src/` and `tests/` but no `docs/`,
`tools/` or `experiments/`, so the tests inside the artifact could not run
(17 errors, 4 failures — all file-not-found). Meanwhile the wheel was fine, so an
install check alone would not have noticed. This script checks both, and derives
its expectations from the working tree instead of a hard-coded list: a new module
or document must appear in the artifacts or this fails.

Exit codes follow the project convention: 0 clean, 1 check failures, 2 usage.
"""
import os
import sys
import tarfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fail(msg):
    print(f"✗ {msg}")
    return 1


def read_version():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("version = "):
                return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit(fail("pyproject.toml has no version"))


def expected_modules():
    """Derived, not listed: every module in src/amg must be in the wheel."""
    src = os.path.join(ROOT, "src", "amg")
    return sorted(name for name in os.listdir(src) if name.endswith(".py"))


def expected_docs():
    docs = os.path.join(ROOT, "docs")
    return sorted("docs/" + name for name in os.listdir(docs) if name.endswith(".md"))


def find_one(dist, suffix):
    matches = sorted(
        name for name in os.listdir(dist) if name.endswith(suffix) and not name.startswith(".")
    )
    if len(matches) != 1:
        raise SystemExit(fail(f"expected exactly one {suffix} in {dist}, found {len(matches)}: {matches}"))
    return os.path.join(dist, matches[0])


def check_wheel(path, version):
    problems = []
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        stem = f"agent_memory_graph-{version}.dist-info"
        for module in expected_modules():
            if f"amg/{module}" not in names:
                problems.append(f"wheel is missing amg/{module}")
        if not any(n.startswith(f"{stem}/licenses/") for n in names):
            problems.append("wheel is missing the LICENSE file")
        entry = f"{stem}/entry_points.txt"
        if entry not in names:
            problems.append("wheel is missing entry_points.txt")
        else:
            text = zf.read(entry).decode()
            if "amg = amg.cli:main" not in text:
                problems.append("wheel console script is not `amg = amg.cli:main`")
        meta_name = f"{stem}/METADATA"
        if meta_name in names:
            meta = zf.read(meta_name).decode()
            if f"Version: {version}" not in meta:
                problems.append("wheel metadata version disagrees with pyproject.toml")
            if "License-Expression:" not in meta:
                problems.append("wheel metadata has no SPDX License-Expression")
        else:
            problems.append("wheel is missing METADATA")
    return problems


def check_sdist(path):
    """The sdist must contain everything its own test suite reads."""
    problems = []
    must_have = (
        ["pyproject.toml", "README.md", "LICENSE", "MANIFEST.in"]
        + expected_docs()
        + [
            "tools/check_doc_symbols.py",
            "tools/doc_scope.py",   # both doc gates import it (v0.31.0)
            "tests/test_doc_symbols.py",
            "examples/quickstart.sh",
            "examples/lifecycle.sh",
            "examples/mcp_client.py",
            "benchmarks/bench.py",
            "experiments/retrieval_eval/run_eval.py",
            "experiments/valid_from_bias/run_experiment.py",
            "experiments/concurrency/run_stress.py",
        ]
    )
    with tarfile.open(path) as tf:
        members = [m.name for m in tf.getmembers() if m.isfile()]
    # archives are rooted at <name>-<version>/
    inner = {name.split("/", 1)[1] for name in members if "/" in name}
    for name in must_have:
        if name not in inner:
            problems.append(f"sdist is missing {name}")
    if any("__pycache__" in name for name in inner):
        problems.append("sdist contains __pycache__")
    return problems


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    dist = argv[1] if len(argv) > 1 else "dist"
    if not os.path.isdir(dist):
        print(f"usage: {os.path.basename(argv[0])} DIST_DIR", file=sys.stderr)
        print(f"✗ no such directory: {dist}", file=sys.stderr)
        return 2

    version = read_version()
    wheel = find_one(dist, ".whl")
    sdist = find_one(dist, ".tar.gz")
    print(f"version {version}")
    print(f"wheel   {os.path.basename(wheel)}")
    print(f"sdist   {os.path.basename(sdist)}")

    problems = check_wheel(wheel, version) + check_sdist(sdist)
    if problems:
        for problem in problems:
            print(f"✗ {problem}")
        print(f"\n{len(problems)} artifact problem(s)")
        return 1
    print(
        f"✓ wheel has all {len(expected_modules())} modules, entry point and licence; "
        f"sdist has all {len(expected_docs())} documents, tools, examples and tests"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
