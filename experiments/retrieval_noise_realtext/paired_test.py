#!/usr/bin/env python3
"""Paired *falsifier* for two realtext ledgers. Not a significance test.

Two ledgers produced by `run_realtext.py` (or by a candidate arm that writes the same shape),
compared query by query over the hit-or-miss convention: a query counts as retrieved when any
gold node is inside the top five.

Why a falsifier and not a significance test: at n=26 one query is 0.0385, and the exact McNemar
test on a single fixed query with zero regressions returns p=1.0. There is no reachable result at
this sample size that could establish a real gain, so this tool is allowed to do exactly one
thing -- refute. Pass semantics: **zero regressions** (`broke == 0`) plus the integer pairs. A
p value is printed as information and is explicitly not a claim; the Holm-Bonferroni correction is
applied only when several candidate ledgers are compared at once (single arm: no multiplicity).

    python3 paired_test.py baseline_ledger.json candidate_ledger.json            # one arm
    python3 paired_test.py baseline_ledger.json candA.json candB.json --json     # Holm

Exit codes: 0 = no regressions, 1 = regressions found, 2 = usage / unreadable ledger.
"""
import argparse
import json
import math
import sys

METRIC = "hit_or_miss"


def load_rows(path):
    with open(path, encoding="utf-8") as fh:
        ledger = json.load(fh)
    rows = ledger.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: no per-query rows (rebuild with run_realtext.py)")
    out = {}
    for row in rows:
        hits = row.get("recall@5", 0.0) > 0
        out[row["id"]] = bool(hits)
    return out, ledger


def exact_mcnemar_p(fixed, broke):
    """Two-sided exact McNemar on the discordant pairs (binomial, p=0.5)."""
    n = fixed + broke
    if n == 0:
        return 1.0
    k = min(fixed, broke)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def compare(baseline, candidate):
    ids = sorted(set(baseline) & set(candidate))
    if len(ids) != len(baseline) or len(ids) != len(candidate):
        raise ValueError("ledgers cover different query ids")
    fixed = sorted(qid for qid in ids if not baseline[qid] and candidate[qid])
    broke = sorted(qid for qid in ids if baseline[qid] and not candidate[qid])
    return {"n": len(ids), "fixed": fixed, "broke": broke,
            "fixed_count": len(fixed), "broke_count": len(broke),
            "both_hit": sum(1 for qid in ids if baseline[qid] and candidate[qid]),
            "both_miss": sum(1 for qid in ids if not baseline[qid] and not candidate[qid]),
            "p_exact_mcnemar": round(exact_mcnemar_p(len(fixed), len(broke)), 6),
            "regressions": len(broke),
            "verdict": "PASS_NO_REGRESSION" if not broke else "FAIL_REGRESSION"}


def holm(arms):
    """Holm-Bonferroni over arms that report a p value: p is information, not a claim."""
    ordered = sorted(arms, key=lambda item: item["result"]["p_exact_mcnemar"])
    total = len(ordered)
    for index, item in enumerate(ordered):
        item["result"]["holm_threshold"] = round(0.05 / (total - index), 6)


def main(argv=None):
    parser = argparse.ArgumentParser(description="paired falsifier for realtext ledgers")
    parser.add_argument("baseline")
    parser.add_argument("candidates", nargs="+")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        baseline, baseline_ledger = load_rows(args.baseline)
        arms = []
        for path in args.candidates:
            candidate, candidate_ledger = load_rows(path)
            arms.append({"candidate": path,
                         "result": compare(baseline, candidate),
                         "candidate_ledger": candidate_ledger.get("schema"),
                         "baseline_ledger": baseline_ledger.get("schema")})
    except (OSError, ValueError, KeyError) as exc:
        print(f"x {exc}", file=sys.stderr)
        return 2

    if len(arms) > 1:
        holm(arms)
    failed = any(arm["result"]["regressions"] for arm in arms)
    payload = {"metric": METRIC,
               "rank_base": baseline_ledger.get("rank_base"),
               "n": len(baseline),
               "significance_claimed": False,
               "note": ("falsifier only: pass means zero regressions; p is printed as information "
                        "and no result at n=26 can establish a gain"),
               "arms": arms,
               "verdict": "FAIL" if failed else "PASS_NO_REGRESSION"}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"metric {METRIC} / rank_base {payload['rank_base']} / n {payload['n']}")
        for arm in arms:
            r = arm["result"]
            extra = f" holm<{r['holm_threshold']}" if "holm_threshold" in r else ""
            print(f"  {arm['candidate']}: fixed {r['fixed_count']} broke {r['broke_count']} "
                  f"(both hit {r['both_hit']}, both miss {r['both_miss']}) "
                  f"p={r['p_exact_mcnemar']}{extra} -> {r['verdict']}")
        print("  p is information only: no significance is claimed at this sample size")
        print(f"VERDICT: {payload['verdict']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
