#!/usr/bin/env python3
"""Verify a graph another tool wrote, without letting it into the write path.

    python3 tools/verify_snapshot.py <graph.json> [...] [--json] [--allow-unverified]
                                     [--keep]

The team's own knowledge graphs are curated by `kg.py` in `group-kg/v1`, so they are
**not** under `amg`'s write gate: nothing blocks a bad write there, and citing an
`amg` guarantee for them would be a false claim (`issue.mem-arch-gate-boundary`). This
bridge closes the observation half, not the blocking half:

1. `amg adopt` the source into a throw-away directory (the source is never written);
2. run the same report `tools/healthcheck.py` runs (`check`, `audit`, real evidence
   hashing, archive verification) on the adopted copy;
3. print per graph: structural errors, evidence rows verified, **conclusion anchoring**
   (`verified/total`, `unanchored`) and the verdict.

It deliberately reuses `healthcheck.collect()`, so a fix to the coverage denominator or
to the "nothing was verified" verdict applies here too — a bridge with its own private
green-light logic would just move the false green one door down
(`ATTACK-HEALTHCHECK-V023.md`, `REATTACK-HEALTHCHECK-V0240.md`).

Exit codes, aggregated over all inputs:

* `0`  every graph adopted, `check` clean, and at least one evidence item verified
       (or `--allow-unverified` accepted a graph whose evidence cannot be observed);
* `1`  adoption failed, or a graph has structural errors / unconfirmable evidence;
* `2`  usage;
* `3`  nothing was verified for at least one graph — the store is not broken, it is
       unproven. Do not read this as "fine": it is the honest number for a curated
       graph whose evidence is citations rather than hashed files.

Exit `0` means "the invariants this report can observe hold"; it never means the
content is correct, and it never means the graph is write-gated.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from amg import Memory  # noqa: E402
import healthcheck  # noqa: E402

EXIT_OK = 0
EXIT_PROBLEM = 1
EXIT_USAGE = 2
EXIT_UNVERIFIED = 3


def snapshot(source, keep=False):
    """Adopt `source` into a temp directory and return (report, adopted_dir)."""
    workdir = tempfile.mkdtemp(prefix="amg-snapshot-")
    dst = os.path.join(workdir, "adopted")
    try:
        adopted = Memory.adopt(source, dst)
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        return {"source": os.path.abspath(source),
                "error": f"{type(exc).__name__}: {exc}"}, None
    # resolve the locators against the graph they came from, not the temp copy
    report = healthcheck.collect(dst, evidence_root=os.path.dirname(os.path.abspath(source)))
    report["source"] = os.path.abspath(source)
    report["adopted"] = adopted
    report["temp_dir"] = workdir
    if not keep:
        shutil.rmtree(workdir, ignore_errors=True)
        report["temp_dir"] = None
    return report, (workdir if keep else None)


def judge(report, allow_unverified=False):
    if report.get("error"):
        return "adoption_failed", EXIT_PROBLEM
    if report["problems"]:
        return "needs_attention", EXIT_PROBLEM
    if report["evidence"]["coverage_state"] == "none":
        return "unverified", (EXIT_OK if allow_unverified else EXIT_UNVERIFIED)
    return "healthy", EXIT_OK


def main(argv=None):
    healthcheck._utf8_console()
    parser = argparse.ArgumentParser(
        description="adopt a foreign-schema graph into a temp dir and report on it")
    parser.add_argument("sources", nargs="+")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-unverified", action="store_true")
    parser.add_argument("--keep", action="store_true", help="keep the adopted copies")
    args = parser.parse_args(argv)

    missing = [path for path in args.sources if not os.path.isfile(path)]
    if missing:
        for path in missing:
            print(f"x not a file: {path}", file=sys.stderr)
        return EXIT_USAGE

    reports, worst = [], EXIT_OK
    for source in args.sources:
        report, _kept = snapshot(source, keep=args.keep)
        verdict, code = judge(report, args.allow_unverified)
        report["verdict"], report["healthy"] = verdict, verdict == "healthy"
        report["allow_unverified"] = bool(args.allow_unverified)
        report["strict_scope"] = ("none: this bridge promotes nothing; "
                                   "unverified evidence stays exit 3")
        report["unverified_accepted"] = (verdict == "unverified"
                                         and bool(args.allow_unverified))
        reports.append(report)
        if code == EXIT_PROBLEM:
            worst = EXIT_PROBLEM
        elif code == EXIT_UNVERIFIED and worst != EXIT_PROBLEM:
            worst = EXIT_UNVERIFIED

    if args.json:
        print(json.dumps({"graphs": reports, "exit": worst},
                         ensure_ascii=False, indent=2))
        return worst

    for report in reports:
        print(f"source {report['source']}")
        if report.get("error"):
            print(f"  x adoption failed: {report['error']}")
            print("  verdict: NEEDS ATTENTION (could not adopt)")
            continue
        store = report["store"]
        adopted = report["adopted"]
        evidence = report["evidence"]
        conclusions = report["conclusions"]
        print(f"  adopted: {store['nodes']} nodes / {store['edges']} edges / "
              f"{store['changes']} changes "
              f"(legacy evidence strings "
              f"{(adopted.get('mapped') or {}).get('evidence_legacy_strings', 0)})")
        print(f"  check: {'ok' if report['check']['ok'] else 'ERRORS'} "
              f"({len(report['check']['errors'])} error(s), "
              f"{len(report['check']['hints'])} hint(s))")
        counts = evidence["counts"] or {"none": 0}
        pct = "" if evidence["coverage"] is None else f" ({evidence['coverage']:.0%})"
        print(f"  evidence rows: {evidence['declared']} declared, "
              f"{evidence['verified']} verified{pct} - "
              + ", ".join(f"{name} {count}" for name, count in sorted(counts.items())))
        if conclusions["total"]:
            anchor = ("n/a" if conclusions["anchor_coverage"] is None
                      else f"{conclusions['anchor_coverage']:.0%}")
            print(f"  conclusions: {conclusions['verified']}/{conclusions['total']} "
                  f"verified ({anchor}), {conclusions['unanchored']} unanchored")
        print(f"  audit: {len(report['audit']['conflicts'])} conflict(s)")
        for problem in report["problems"]:
            print(f"  x {problem}")
        for warning in report["warnings"]:
            print(f"  ! {warning}")
        label = {"needs_attention": "NEEDS ATTENTION", "unverified": "UNVERIFIED",
                 }.get(report["verdict"], "healthy")
        accepted = report["unverified_accepted"]
        print("  verdict: " + label
              + (" (accepted with --allow-unverified)" if accepted else ""))
        if report["temp_dir"]:
            print(f"  kept: {report['temp_dir']}")
    print(f"\n{len(reports)} graph(s); exit {worst}. Exit 0 is not proof that the "
          f"content is correct, and not a claim that the graph is write-gated.")
    return worst


if __name__ == "__main__":
    sys.exit(main())
