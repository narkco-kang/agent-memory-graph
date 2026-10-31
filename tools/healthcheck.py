#!/usr/bin/env python3
"""One-page health report for a live memory graph. Read-only.

    python3 tools/healthcheck.py <dir> [--json] [--strict] [--no-evidence]
                                [--allow-unverified]

This is the "is my store okay?" command an operator runs on a schedule. It opens the
graph read-only and reports, in one place, the things that are already enforced
separately: structural invariants (`check`), stale work (`audit`), declared-versus-real
evidence bytes (`verify-evidence`'s gate function), and archive integrity
(`archive_verify`).

Exit codes: `0` pass, `1` a problem was found, `2` usage, `3` nothing could be
verified (the store is not broken, it is unproven).

Verdicts (`verdict` in `--json`, last line in text):

* `healthy` - no problem, and at least one `path:` evidence file hashed to its declared
  digest. Evidence-checking skipped with `--no-evidence` also lands here: the operator
  chose not to look, and the report says so instead of pretending it looked;
* `needs_attention` - a problem: a structural error, evidence that mismatches, is
  missing, is not a file, or cannot be read, evidence outside the graph root, a failed
  archive verification (and, with `--strict`, stale work items);
* `unverified` - nothing is broken, but **zero** evidence items could be observed: no
  evidence at all, or only `cmd:`/`url:`/`sha256:` locators, which carry no local bytes.
  This is v0.24.0. Before it, a store with 0 verified evidence items printed
  `verdict: healthy` and exited 0 - an operator's dashboard said "fine" about a store
  whose every claim was unproven (`ATTACK-HEALTHCHECK-V023.md` §2.1, §2.2). A third
  exit code exists so a cron job can tell "unproven" from "broken". A store that
  intentionally holds only remote/command anchors can opt in with `--allow-unverified`
  (exit 0, verdict still `unverified`).

What counts as a problem (exit 1) is deliberately narrow: `check` errors, evidence that
cannot be confirmed (`mismatch`, `missing`, `not_a_file`, `unreadable`, `outside_root`),
or a failing archive verification. Stale work items and legacy unanchored nodes are
**debt, not breakage** - they are printed, and only `--strict` turns them into a
failure, because an operator who is paged for a three-day-old task stops reading.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import Memory  # noqa: E402
from amg.gate import verify_evidence  # noqa: E402

EXIT_PROBLEM = 1
EXIT_USAGE = 2
EXIT_UNVERIFIED = 3


def _utf8_console():
    """Windows consoles default to a legacy code page; the verdict line must not crash.

    The output strings are ASCII on purpose (the glyphs in the CLI are not printable
    everywhere either), and this is the belt: the stream is reconfigured when possible.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass


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
    counts = {}
    for row in evidence_rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    verified = counts.get("ok", 0)
    mismatched = [row for row in evidence_rows if row["status"] == "mismatch"]
    outside = [row for row in evidence_rows if row["status"] == "outside_root"]
    unconfirmed = {name: [row for row in evidence_rows if row["status"] == name]
                   for name in ("missing", "not_a_file", "unreadable")}

    problems = []
    if check["errors"]:
        problems.append(f"{len(check['errors'])} structural error(s) - run `amg check`")
    if mismatched:
        problems.append(f"{len(mismatched)} evidence file(s) do not match their declared "
                        f"sha256 - run `amg verify-evidence`")
    if outside:
        problems.append(f"{len(outside)} evidence path(s) leave the graph directory "
                        f"(outside_root) - run `amg verify-evidence`")
    for status, rows in unconfirmed.items():
        if rows:
            problems.append(f"{len(rows)} evidence locator(s) {status} - the proof cannot "
                            f"be observed - run `amg verify-evidence`")
    if not archive.get("ok", True):
        problems.append("archive verification failed - run `amg archive --verify`")

    warnings = []
    if audit.get("conflicts"):
        warnings.append(f"{len(audit['conflicts'])} audit conflict(s)")

    # Coverage is its own number: "0 checked" and "0 failed" look identical in a problem
    # list, and the difference between them is the whole point of this report.
    if not check_evidence:
        coverage_state, coverage = "not_checked", None
    elif verified == 0:
        coverage_state, coverage = "none", 0.0
    elif verified == len(evidence_rows):
        coverage_state, coverage = "full", 1.0
    else:
        coverage_state, coverage = "partial", round(verified / len(evidence_rows), 4)

    return {
        "path": os.path.abspath(path),
        "store": {"nodes": len(doc.get("nodes") or []),
                  "edges": len(doc.get("edges") or []),
                  "changes": len(doc.get("changes") or [])},
        "check": {"ok": check["ok"], "errors": check["errors"],
                  "hints": check.get("hints") or []},
        "audit": {"ok": audit.get("ok"), "conflicts": audit.get("conflicts") or [],
                  "counts": audit.get("counts")},
        "evidence": {"checked": len(evidence_rows), "declared": len(evidence_rows),
                     "verified": verified, "coverage": coverage,
                     "coverage_state": coverage_state, "counts": counts,
                     "mismatched": mismatched, "outside_root": outside,
                     "missing": unconfirmed["missing"],
                     "not_a_file": unconfirmed["not_a_file"],
                     "unreadable": unconfirmed["unreadable"]},
        "archive": archive,
        "problems": problems,
        "warnings": warnings,
    }


def verdict_of(report, strict=False, allow_unverified=False):
    """One word for the state of the store, and the exit code that matches it.

    `--allow-unverified` relaxes the exit code, never the verdict: a store with no
    observable evidence is still described as `unverified` when its owner accepted it.
    """
    if report["problems"] or (strict and report["warnings"]):
        return "needs_attention", EXIT_PROBLEM
    if report["evidence"]["coverage_state"] == "none":
        return "unverified", (0 if allow_unverified else EXIT_UNVERIFIED)
    return "healthy", 0


def main(argv=None):
    _utf8_console()
    parser = argparse.ArgumentParser(description="read-only health report for a graph")
    parser.add_argument("dir")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="also fail on audit conflicts (stale work items)")
    parser.add_argument("--no-evidence", action="store_true",
                        help="skip hashing path: evidence (faster on large graphs); the "
                             "report then says evidence was not checked, never verified")
    parser.add_argument("--allow-unverified", action="store_true",
                        help="accept a store whose evidence cannot be observed locally "
                             "(verdict stays `unverified`, exit 0 instead of 3)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.dir):
        print(f"x not a directory: {args.dir}", file=sys.stderr)
        return EXIT_USAGE
    if not os.path.isfile(os.path.join(args.dir, "graph.json")):
        print(f"x no graph.json in {args.dir}", file=sys.stderr)
        return EXIT_USAGE
    try:
        report = collect(args.dir, check_evidence=not args.no_evidence)
    except Exception as exc:  # a store that cannot be opened is the finding
        print(f"x cannot open graph: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_PROBLEM

    report["strict"] = bool(args.strict)
    report["allow_unverified"] = bool(args.allow_unverified)
    report["verdict"], code = verdict_of(report, args.strict, args.allow_unverified)
    report["healthy"] = report["verdict"] == "healthy"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        store = report["store"]
        evidence = report["evidence"]
        print(f"graph {report['path']}")
        print(f"  store: {store['nodes']} nodes / {store['edges']} edges / "
              f"{store['changes']} changes")
        print(f"  check: {'ok' if report['check']['ok'] else 'ERRORS'} "
              f"({len(report['check']['errors'])} error(s), "
              f"{len(report['check']['hints'])} hint(s))")
        print(f"  audit: {len(report['audit']['conflicts'])} conflict(s)")
        if evidence["coverage_state"] == "not_checked":
            print("  evidence: skipped (--no-evidence) - NOT VERIFIED")
        else:
            counts = evidence["counts"] or {"none": 0}
            pct = "" if evidence["coverage"] is None else f" ({evidence['coverage']:.0%})"
            print(f"  evidence: {evidence['declared']} declared, "
                  f"{evidence['verified']} verified{pct} - "
                  + ", ".join(f"{name} {count}" for name, count in sorted(counts.items())))
        archive = report["archive"]
        print(f"  archive: {'ok' if archive.get('ok') else 'FAILED'} "
              f"({archive.get('archived_records', 0)} archived record(s))")
        for problem in report["problems"]:
            print(f"  x {problem}")
        for warning in report["warnings"]:
            print(f"  ! {warning}")
        verdict = report["verdict"]
        label = ("NEEDS ATTENTION" if verdict == "needs_attention"
                 else "UNVERIFIED" if verdict == "unverified" else "healthy")
        accepted = verdict == "unverified" and report["allow_unverified"]
        print("  verdict: " + label
              + (" (accepted with --allow-unverified)" if accepted else ""))
    return code


if __name__ == "__main__":
    sys.exit(main())
