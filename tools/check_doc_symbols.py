#!/usr/bin/env python3
"""CI gate: every capability named in the docs must exist as a code symbol.

Scope is deliberately narrow (sign-off 2026-10-29): symbol existence only —
CLI subcommands, Memory methods, exception names. Natural-language semantic
matching is NOT attempted; pretending to do it would produce false greens.

Usage: python3 tools/check_doc_symbols.py README.md docs/API.md
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import LockTimeout, Memory, ProtocolError  # noqa: E402
from amg.cli import COMMANDS  # noqa: E402

CLI_LINE_RE = re.compile(r"^\$?\s*amg\s+([A-Za-z0-9\-_.]+)")
PY_RE = re.compile(r"\b(?:m|Memory)\.([a-z_][a-z0-9_]*)\s*\(")
MEMORY_METHODS = {name for name in dir(Memory) if not name.startswith("_")}
EXCEPTIONS = {"ProtocolError": ProtocolError, "LockTimeout": LockTimeout}
NOT_A_COMMAND = {"commands", "init", "README"}  # prose false positives filtered below


def scan(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def default_targets():
    """README plus every document under docs/, recursively.

    Passing an explicit list stays supported (CI did that until v0.7.0); the default
    list itself was the staleness risk. v0.30.0 makes the walk recursive: a document in
    `docs/decisions/` used to escape the symbol gate entirely, which is the same
    "hand-written list is a claim about the past" failure the gate exists to prevent.
    """
    targets = ["README.md"]
    docs_dir = os.path.join(ROOT, "docs")
    for current, _dirs, names in os.walk(docs_dir):
        for name in sorted(names):
            if name.endswith(".md"):
                rel = os.path.relpath(os.path.join(current, name), ROOT)
                targets.append(rel.replace(os.sep, "/"))
    return sorted(targets)


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    files = argv[1:] or default_targets()
    missing = []
    for path in files:
        if not os.path.isfile(path):
            print(f"skip (missing): {path}")
            continue
        text = scan(path)
        # Line-based on purpose: prose like "from amg import Memory" must not
        # be mistaken for a CLI invocation, and a heading like "amg v0.1" is a
        # version, not a subcommand.
        candidates = []
        for line in text.splitlines():
            m = CLI_LINE_RE.match(line.strip())
            if m:
                candidates.append(m.group(1))
        # inline code spans too: `amg search ...` inside prose
        for span in re.findall(r"`([^`]+)`", text):
            s = span.strip().lstrip("$").strip()
            if s.startswith("amg "):
                candidates.append(s[4:].split()[0])
        for token in sorted(set(candidates)):
            token = token.rstrip(".,`")
            if re.match(r"^v\d", token):
                continue
            if token not in COMMANDS:
                missing.append(f"{path}: CLI command 'amg {token}' is documented but not implemented")
        for meth in sorted(set(PY_RE.findall(text))):
            if meth not in MEMORY_METHODS:
                missing.append(f"{path}: Memory.{meth}() is documented but not implemented")
        for name in sorted(set(re.findall(r"\b(ProtocolError|LockTimeout)\b", text))):
            if name not in EXCEPTIONS:
                missing.append(f"{path}: exception {name} documented but not exported")
    if missing:
        for m in missing:
            print(f"✗ {m}")
        print(f"\n{len(missing)} doc/code gap(s)")
        return 1
    print(f"✓ no doc/code symbol gaps across {len(files)} file(s): {', '.join(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
