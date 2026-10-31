# Is the 0.70 target an artifact of N2's construction?

Pre-registered: distractors built from **real prose** — seeded 8-word windows of paragraphs from this
repository's own documentation — instead of tokens sampled from the queries' vocabulary.

**Answer: no. Realistic noise also misses the target.** The real-text corpus lands at recall@5
**0.692** (0.673 with whole paragraphs) against the published 0.70 target, while N2 sits at 0.538. Its
competing-distractor share is 0.476, between control's 0.144 and N2's 0.918, so the calibration check
passes and the corpus stands.

    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/run_realtext.py        # pre-registered
    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/sensitivity_window.py  # post-hoc length sweep

The corpus is **frozen, not live**: `corpus_src/` holds the 71 prose files the windows are cut
from, with a `corpus_version`; documentation edits cannot move a published number. Refreshing is an
explicit version bump that re-quotes every number, and drift is an audit, not a gate:

    run_realtext.py                          # measure from the frozen corpus + pin
    run_realtext.py --refresh-corpus         # copy live docs into corpus_src, bump version, re-run
    run_realtext.py --check-corpus           # audit: drift size + pin age; never fails

This is a **same-domain regression set, not an independent validation set**: distractors and gold
nodes come from the same documentation, so a gain can be a gain at matching this repository's prose
style. `result.json` carries that declaration under `representativeness` and a test fails without it.
Numbers are comparable within one `corpus_version`, never across versions.

Two conventions are published, because at n=26 they disagree about the 0.70 target: `fractional_r5`
(gold coverage, **0.692**) and `hit_or_miss` (any gold in the top five, **0.731**). Per-query rows
live in `ledger.json` with `rank_base: 1` and the out-of-reach set. `paired_test.py` compares two
ledgers as a **falsifier**: pass means zero regressions; at n=26 a single fix with no regression is
p = 1.0, so no significance is claimed.

| file | what it is |
|---|---|
| `PREREGISTRATION.md` | construction, calibration-first ordering, criteria, predictions; `## Outcome` appended |
| `run_realtext.py` | builds the corpus from the pin (or from repository prose), reports calibration before recall |
| `sensitivity_window.py` | post-hoc: same construction at 8 / 20 / whole-paragraph lengths |
| `corpus_src/` + `manifest.json` | the frozen prose files (with `corpus_version`) |
| `corpus_pin.json` | the extracted paragraphs the windows are cut from, with per-file and source digests |
| `corpus_snapshot.json`, `result.json`, `ledger.json`, `sensitivity_window.json` | machine-readable outputs |
| `paired_test.py` | falsifier over two ledgers: integer pairs, zero-regression pass, no p-value claim |

Decided here: DECISIONS #52 — publish two noise corpora (N2 worst case, real text realistic), keep the
0.70 target attached to N2 and unmet, and record that #50's suspicion ("the target may only measure an
artifact") is wrong.
