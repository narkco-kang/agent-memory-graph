#!/usr/bin/env python3
"""One-page health report for a live memory graph. Read-only.

    python3 tools/healthcheck.py <dir> [--json] [--strict] [--no-evidence]

This is the "is my store okay?" command an operator runs on a schedule. It opens the
graph read-only and reports, in one place, the things that are already enforced
separately: structural invariants (`check`), stale work (`audit`), declared-versus-real
evidence bytes (`verify-evidence`'s gate function), and archive integrity
(`archive_verify`).

Exit codes: `0` healthy, `1` a problem was found, `2` usage.

What counts as a problem (exit 1) is deliberately narrow: `check` errors, a `path:`
evidence file whose bytes do not match its declared `content_sha256`, or a failing
archive verification. Stale work items and legacy unanchored nodes are **debt, not
breakage** — they are printed, and only `--strict` turns them into a failure, because
an operator who is paged for a three-day-old task stops reading the report.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402
from amg.gate import verify_evidence  # noqa: E402


def collect(path, check_evidence=True):
    memory = Memory.open(path, read_only=True)
    doc = memory.doc
    check = memory.check()
    audit = memory.audit()
    archive = memory.archive_verify()

    evidence_rows = []
    if check_evidence:
        for node in doc.get("nodes") or []:
            evidence_rows.extend(verify_evidence(node.get("evidence") or [],
                                                 os.path.abspath(path), node.get("id")))
    evidence_counts = {}
    for row in evidence_rows:
        evidence_counts[row["status"]] = evidence_counts.get(row["status"], 0) + 1
    mismatched = [row for row in evidence_rows if row["status"] == "mismatch"]
    outside = [row for row in evidence_rows if row["status"] == "outside_root"]

    problems = []
    if check["errors"]:
        problems.append(f"{len(check['errors'])} structural error(s) — run `amg check`")
    if mismatched:
        problems.append(f"{len(mismatched)} evidence file(s) do not match their declared "
                        f"sha256 — run `amg verify-evidence`")
    if outside:
        problems.append(f"{len(outside)} evidence path(s) leave the graph directory "
                        f"(outside_root) — run `amg verify-evidence`")
    if not archive.get("ok", True):
        problems.append("archive verification failed — run `amg archive --verify`")

    warnings = []
    if audit.get("conflicts"):
        warnings.append(f"{len(audit['conflicts'])} audit conflict(s)")

    return {
        "path": os.path.abspath(path),
        "store": {"nodes": len(doc.get("nodes") or []),
                  "edges": len(doc.get("edges") or []),
                  "changes": len(doc.get("changes") or [])},
        "check": {"ok": check["ok"], "errors": check["errors"],
                  "hints": check.get("hints") or []},
        "audit": {"ok": audit.get("ok"), "conflicts": audit.get("conflicts") or [],
                  "counts": audit.get("counts")},
        "evidence": {"checked": len(evidence_rows), "counts": evidence_counts,
                     "mismatched": mismatched, "outside_root": outside},
        "archive": archive,
        "problems": problems,
        "warnings": warnings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="read-only health report for a graph")
    parser.add_argument("dir")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="also fail on audit conflicts (stale work items)")
    parser.add_argument("--no-evidence", action="store_true",
                        help="skip hashing path: evidence (faster on large graphs)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.dir):
        print(f"✗ not a directory: {args.dir}", file=sys.stderr)
        return 2
    if not os.path.isfile(os.path.join(args.dir, "graph.json")):
        print(f"✗ no graph.json in {args.dir}", file=sys.stderr)
        return 2
    try:
        report = collect(args.dir, check_evidence=not args.no_evidence)
    except Exception as exc:  # a store that cannot be opened is the finding
        print(f"✗ cannot open graph: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    failed = bool(report["problems"]) or (args.strict and bool(report["warnings"]))
    report["healthy"] = not failed
    report["strict"] = bool(args.strict)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        store = report["store"]
        print(f"graph {report['path']}")
        print(f"  store: {store['nodes']} nodes / {store['edges']} edges / "
              f"{store['changes']} changes")
        print(f"  check: {'ok' if report['check']['ok'] else 'ERRORS'} "
              f"({len(report['check']['errors'])} error(s), "
              f"{len(report['check']['hints'])} hint(s))")
        conflicts = report["audit"]["conflicts"]
        print(f"  audit: {len(conflicts)} conflict(s)")
        counts = report["evidence"]["counts"] or {"none": 0}
        print(f"  evidence: {report['evidence']['checked']} item(s) — "
              + ", ".join(f"{name} {count}" for name, count in sorted(counts.items())))
        archive = report["archive"]
        print(f"  archive: {'ok' if archive.get('ok') else 'FAILED'} "
              f"({archive.get('archived_records', 0)} archived record(s))")
        for problem in report["problems"]:
            print(f"  ✗ {problem}")
        for warning in report["warnings"]:
            print(f"  ! {warning}")
        print("  verdict: " + ("healthy" if report["healthy"] else "NEEDS ATTENTION"))
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
