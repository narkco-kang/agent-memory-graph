#!/usr/bin/env python3
"""CI gate: a document that outgrows its budget is a document nobody finishes.

The rule comes from a field-tested public workbench (mashanglinyu/luanyujia-workbench,
MIT — credited in docs/PRIOR-ART.md): handovers ≤ 4 KB, scene memory ≤ 25 KB, a single
skill ≤ 12 KB, because a file over the line is one a reader skips. This project has
fourteen documents and, until this gate existed, no size contract at all — the entry
document had silently grown to 20 KB of material that already lived in `docs/`.

Budgets (both stated in docs/README.md; the test asserts they match this file):

  * an **entry** document (`README.md`, `docs/README.md`) — 12 KiB;
  * any other file under `docs/`, at any depth and under any name — 24 KiB.

Scope: every regular file under `docs/` plus the repository `README.md`, selected by
`tools/doc_scope.py` — by **directory, not by suffix** (v0.31.0). Until then the walk
matched `.md`, so renaming a page to `.markdown`, `.txt` or giving it no extension
made its size invisible to this gate; the verifier measured three 30,000 B files
passing. A budget you can escape with `mv` is not a budget.

`CHANGELOG.md` and `RELEASE.md` are append-only logs read top-to-bottom-never, so a
size cap there would force deleting history. They are out of scope in words, not
silently exempted by a pattern, and they live outside `docs/`.

The budget is measured in **bytes of content**, with CRLF folded to LF first: a Windows
checkout with `core.autocrlf` writes a `\r` per line, which would count the same document
larger there than on Linux/macOS and fail CI for a checkout setting rather than for
length (v0.19.1 — v0.19.0's Windows job failed exactly that way).

Usage:
    python3 tools/check_doc_sizes.py                 # README.md + every docs/*.md
    python3 tools/check_doc_sizes.py path [...]      # explicit (tests use this)
    python3 tools/check_doc_sizes.py --json

Exit codes: 0 within budget, 1 over budget, 2 nothing to check.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from doc_scope import document_files  # noqa: E402

ROOT = os.path.dirname(HERE)
ENTRY_BUDGET = 12 * 1024
DOC_BUDGET = 24 * 1024
ENTRY_BASENAME = "README.md"
# Ignored on purpose: logs, not documents (see the module docstring).
OUT_OF_SCOPE = {"CHANGELOG.md", "RELEASE.md"}


def budget_for(path):
    return ENTRY_BUDGET if os.path.basename(path) == ENTRY_BASENAME else DOC_BUDGET


def default_targets():
    """README plus every document under docs/, recursively, whatever it is named.

    v0.30.0: the walk used to list only `docs/*.md`, so a document placed in a
    subdirectory (`docs/decisions/…`) silently escaped the budget — the same "a
    hand-written list is a claim about the past" failure the gate exists to prevent.
    A directory is not an exemption.
    v0.31.0: the walk also used to match `.md`, so renaming the same page escaped it.
    Both gates now delegate to `tools/doc_scope.py`, which selects by directory.
    """
    return document_files(ROOT)


def document_size(full):
    """Content bytes with line endings normalized to LF (see the module docstring)."""
    with open(full, "rb") as fh:
        return len(fh.read().replace(b"\r\n", b"\n"))


def check(paths):
    rows = []
    for path in paths:
        if os.path.basename(path) in OUT_OF_SCOPE:
            rows.append({"path": path, "skipped": "log file, out of scope"})
            continue
        full = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if not os.path.isfile(full):
            rows.append({"path": path, "error": "missing"})
            continue
        size = document_size(full)
        budget = budget_for(path)
        rows.append({"path": path.replace(os.sep, "/"), "bytes": size, "budget": budget,
                     "pct": round(100.0 * size / budget, 1), "over": max(0, size - budget)})
    over = [r for r in rows if r.get("over")]
    return {"ok": not over and not any(r.get("error") for r in rows),
            "entry_budget": ENTRY_BUDGET, "doc_budget": DOC_BUDGET,
            "rows": rows, "over": [r["path"] for r in over]}


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass
    args = [a for a in argv[1:] if not a.startswith("--")]
    as_json = "--json" in argv[1:]
    targets = args or default_targets()
    if not targets:
        print("nothing to check", file=sys.stderr)
        return 2
    report = check(targets)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for row in report["rows"]:
            if row.get("skipped"):
                print(f"  - {row['path']}: skipped ({row['skipped']})")
            elif row.get("error"):
                print(f"  ✗ {row['path']}: {row['error']}")
            elif row["over"]:
                print(f"  ✗ {row['path']}: {row['bytes']} B > {row['budget']} B "
                      f"budget ({row['pct']}%, over by {row['over']} B)")
            else:
                print(f"  ✓ {row['path']}: {row['bytes']} B / {row['budget']} B "
                      f"({row['pct']}%)")
        checked = [r for r in report["rows"] if "bytes" in r]
        print(f"{len(checked)} document(s) within budget "
              f"(entry ≤ {report['entry_budget']} B, docs ≤ {report['doc_budget']} B)"
              if report["ok"] else
              f"✗ {len(report['over'])} document(s) over budget: {', '.join(report['over'])}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
