#!/usr/bin/env python3
"""CI gate: a document that outgrows its budget is a document nobody finishes.

The rule comes from a field-tested public workbench (mashanglinyu/luanyujia-workbench,
MIT — credited in docs/PRIOR-ART.md): handovers ≤ 4 KB, scene memory ≤ 25 KB, a single
skill ≤ 12 KB, because a file over the line is one a reader skips. This project has
fourteen documents and, until this gate existed, no size contract at all — the entry
document had silently grown to 20 KB of material that already lived in `docs/`.

Budgets (both stated in docs/README.md; the test asserts they match this file):

  * an **entry** document (`README.md`, `docs/README.md`) — 12 KiB;
  * any other `docs/*.md` — 24 KiB.

Scope is deliberately narrow: `CHANGELOG.md` and `RELEASE.md` are append-only logs
read top-to-bottom-never, so a size cap there would force deleting history. They are
out of scope in words, not silently exempted by a pattern.

Usage:
    python3 tools/check_doc_sizes.py                 # README.md + every docs/*.md
    python3 tools/check_doc_sizes.py path [...]      # explicit (tests use this)
    python3 tools/check_doc_sizes.py --json

Exit codes: 0 within budget, 1 over budget, 2 nothing to check.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY_BUDGET = 12 * 1024
DOC_BUDGET = 24 * 1024
ENTRY_BASENAME = "README.md"
# Ignored on purpose: logs, not documents (see the module docstring).
OUT_OF_SCOPE = {"CHANGELOG.md", "RELEASE.md"}


def budget_for(path):
    return ENTRY_BUDGET if os.path.basename(path) == ENTRY_BASENAME else DOC_BUDGET


def default_targets():
    """README plus every document in docs/ — a new document cannot escape the gate."""
    targets = ["README.md"]
    docs_dir = os.path.join(ROOT, "docs")
    if os.path.isdir(docs_dir):
        targets += sorted("docs/" + name for name in os.listdir(docs_dir)
                          if name.endswith(".md"))
    return targets


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
        size = os.path.getsize(full)
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
