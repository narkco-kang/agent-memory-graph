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
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from amg import Memory  # noqa: E402
from amg.gate import sha256_of_file  # noqa: E402
import healthcheck  # noqa: E402

# `path:<rel>#sha256:<hex>` is the one legacy-string shape that carries its own declared
# digest. Parsing it is the only way a curated graph's coverage can grow without writing
# into the store or fabricating hashes (B+ decision); a string without a digest stays a
# citation and is reported, never guessed.
LEGACY_HASH_RE = re.compile(r"^path:(?P<path>.+)#sha256:(?P<sha>[0-9a-f]{64})$")
LEGACY_MALFORMED_RE = re.compile(r"#sha256:")


def verify_legacy_strings(doc, root):
    """Hash legacy `path:x#sha256:h` strings read-only; count what cannot be parsed.

    Also returns which nodes those strings belong to, so the report's anchoring numbers
    describe the graph rather than the storage shape (`evidence` vs `legacy_evidence`).
    """
    checked = verified = 0
    mismatched, malformed, missing = [], [], []
    with_evidence_nodes, verified_nodes = set(), set()
    for node in doc.get("nodes") or []:
        if node.get("legacy_evidence"):
            with_evidence_nodes.add(node.get("id"))
        for raw in node.get("legacy_evidence") or []:
            match = LEGACY_HASH_RE.match(str(raw))
            if not match:
                if LEGACY_MALFORMED_RE.search(str(raw)):
                    malformed.append({"node": node.get("id"), "string": raw})
                continue
            checked += 1
            rel = match.group("path")
            expected = match.group("sha")
            candidate = rel if os.path.isabs(rel) else os.path.join(root, rel)
            if not os.path.isfile(candidate):
                missing.append({"node": node.get("id"), "string": raw})
                continue
            try:
                actual = sha256_of_file(candidate)
            except OSError:
                missing.append({"node": node.get("id"), "string": raw})
                continue
            if actual == expected:
                verified += 1
                verified_nodes.add(node.get("id"))
            else:
                mismatched.append({"node": node.get("id"), "string": raw})
    return {"checked": checked, "verified": verified, "mismatched": mismatched,
            "malformed": malformed, "missing": missing,
            "evidence_nodes": with_evidence_nodes, "verified_nodes": verified_nodes}

EXIT_OK = 0
EXIT_PROBLEM = 1
EXIT_USAGE = 2
EXIT_UNVERIFIED = 3


def snapshot(source, keep=False, evidence_root=None):
    """Adopt `source` into a temp directory and return (report, adopted_dir).

    `evidence_root` is the directory the source's `path:` locators are relative to, and
    it must be stated, not guessed: the same file resolves to three different answers
    under `graphs/`, the workspace root and the repository root (measured 0/240, 113/240,
    89/240 for this project's own graph). The default is the source's own directory,
    which is only correct when the writer meant it that way.
    """
    workdir = tempfile.mkdtemp(prefix="amg-snapshot-")
    dst = os.path.join(workdir, "adopted")
    try:
        adopted = Memory.adopt(source, dst)
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        return {"source": os.path.abspath(source),
                "error": f"{type(exc).__name__}: {exc}"}, None
    root = os.path.abspath(evidence_root or os.path.dirname(os.path.abspath(source)))
    # resolve the locators against that root, not against the temp copy
    adopted_memory = Memory.open(dst, read_only=True)
    legacy = verify_legacy_strings(adopted_memory.doc, root)
    report = healthcheck.collect(dst, evidence_root=root,
                                 extra_evidence_nodes=legacy["evidence_nodes"],
                                 extra_verified_nodes=legacy["verified_nodes"])

    counts = report["evidence"]["counts"]
    path_rows = sum(counts.get(name, 0) for name in
                    ("ok", "mismatch", "missing", "not_a_file", "unreadable", "outside_root"))
    found = counts.get("ok", 0) + counts.get("mismatch", 0)
    report["snapshot"] = {
        "resolve_root": root,
        "exists_rate": (round(found / path_rows, 4) if path_rows else None),
        "path_rows": path_rows,
        "files_found": found,
        "legacy_strings": {key: legacy[key] for key in
                           ("checked", "verified", "mismatched", "malformed", "missing")},
        "observed_verified": report["evidence"]["verified"] + legacy["verified"],
    }
    report["source"] = os.path.abspath(source)
    report["adopted"] = adopted
    report["temp_dir"] = workdir
    if not keep:
        shutil.rmtree(workdir, ignore_errors=True)
        report["temp_dir"] = None
    return report, (workdir if keep else None)


def judge(report, allow_unverified=False, strict=False):
    """Delegate to the health report's verdict, with legacy observations counted in.

    The bridge has no private green light any more: it used to return `healthy` as soon
    as one legacy hash verified, while its own report printed `0/20 verified, 20
    unanchored` (Glm仔 N3). `verdict_of` now owns the boundary — including
    `partially_verified` (something verified, no conclusion anchored, exit 3) — so a fix
    there applies here automatically.
    """
    if report.get("error"):
        return "adoption_failed", EXIT_PROBLEM
    observed = (report.get("snapshot") or {}).get("observed_verified")
    return healthcheck.verdict_of(report, strict=strict,
                                  allow_unverified=allow_unverified,
                                  observed_verified=observed,
                                  require_full_anchoring=True)


def main(argv=None):
    healthcheck._utf8_console()
    parser = argparse.ArgumentParser(
        description="adopt a foreign-schema graph into a temp dir and report on it")
    parser.add_argument("sources", nargs="+")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-unverified", action="store_true")
    parser.add_argument("--keep", action="store_true", help="keep the adopted copies")
    parser.add_argument("--strict", action="store_true",
                        help="also fail on debt: unanchored nodes and unobservable "
                             "evidence")
    parser.add_argument("--evidence-root", metavar="DIR", default=None,
                        help="directory the source's path: locators are relative to; "
                             "required when it is not the graph's own directory")
    args = parser.parse_args(argv)

    missing = [path for path in args.sources if not os.path.isfile(path)]
    if missing:
        for path in missing:
            print(f"x not a file: {path}", file=sys.stderr)
        return EXIT_USAGE

    reports, worst = [], EXIT_OK
    for source in args.sources:
        report, _kept = snapshot(source, keep=args.keep,
                                 evidence_root=args.evidence_root)
        verdict, code = judge(report, args.allow_unverified, args.strict)
        report["verdict"], report["healthy"] = verdict, verdict == "healthy"
        report["allow_unverified"] = bool(args.allow_unverified)
        report["strict_scope"] = ("audit conflicts + unanchored/unobservable conclusions "
                                  "(not evidence); --strict never turns a failed check "
                                  "into a pass")
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
                  f"verified ({anchor}), "
                      f"{conclusions['unanchored_conclusions']} unanchored")
        snapshot_meta = report["snapshot"]
        rate = snapshot_meta["exists_rate"]
        print(f"  evidence base: {snapshot_meta['resolve_root']} "
              f"(files found {snapshot_meta['files_found']}/{snapshot_meta['path_rows']}"
              + ("" if rate is None else f", {rate:.0%}") + ")")
        legacy = snapshot_meta["legacy_strings"]
        if legacy["checked"] or legacy["malformed"]:
            print(f"  legacy strings: {legacy['checked']} with #sha256, "
                  f"{legacy['verified']} verified, {len(legacy['mismatched'])} mismatched, "
                  f"{len(legacy['missing'])} unreadable/missing, "
                  f"{len(legacy['malformed'])} malformed")
        print(f"  audit: {len(report['audit']['conflicts'])} conflict(s)")
        for problem in report["problems"]:
            print(f"  x {problem}")
        for warning in report["warnings"]:
            print(f"  ! {warning}")
        label = {"needs_attention": "NEEDS ATTENTION", "unverified": "UNVERIFIED",
                 "partially_verified": "PARTIALLY VERIFIED (no conclusion anchored)",
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
