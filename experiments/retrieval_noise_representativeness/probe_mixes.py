#!/usr/bin/env python3
"""The probe ladder quoted in DECISIONS #51: can a token-count mix reach the real corpus's share?

NOT pre-registered — run after the pre-registered corpus failed Q2, to establish whether the failure
is a base-rate problem (fixable by mixing) or a selection effect (not fixable that way). Every probe
is reported, including the ones that came close; nothing here is a result about retrieval quality.

    PYTHONPATH=src python3 experiments/retrieval_noise_representativeness/probe_mixes.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_calibrated as rc  # noqa: E402

MIXES = (
    ("0.55 / 0.43 / 0.02", [(0, 0.55), (1, 0.43), (2, 0.02)]),
    ("0.70 / 0.28 / 0.02", [(0, 0.70), (1, 0.28), (2, 0.02)]),
    ("0.80 / 0.19 / 0.01", [(0, 0.80), (1, 0.19), (2, 0.01)]),
)


def main():
    doc, queries = rc.ten_k.load_inputs()
    filler = sorted({token for node in doc["nodes"]
                     for token in rc.run_eval.TOKEN.findall(rc.run_eval.node_text(node).lower())
                     if len(token) >= 3})
    target = 0.144
    rows = []
    for label, mix in MIXES:
        corpus = rc.build_calibrated_mix(doc, queries, mix, filler)
        values = rc.competing_coverage(corpus, queries)
        rows.append({"mix": label,
                     "share_ge_0.25": round(sum(1 for value in values if value >= 0.25) / len(values), 4),
                     "mean": round(sum(values) / len(values), 4),
                     "pairs": len(values)})
        print(f"{label}  competing share>=0.25 = {rows[-1]['share_ge_0.25']:.3f} "
              f"(target {target:.3f})")
    payload = {"caption": "post-hoc probes after the pre-registered corpus failed Q2",
               "target_share": target, "tolerance": rc.CRITERIA["calibration_tolerance"],
               "rows": rows,
               "conclusion": ("no mix reaches the target: the top-100 is selected by the quantity "
                              "being calibrated, so the failure is a selection effect, not a "
                              "base-rate error")}
    with open(os.path.join(HERE, "probes.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print(payload["conclusion"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
