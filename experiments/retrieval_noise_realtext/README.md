# Is the 0.70 target an artifact of N2's construction?

Pre-registered: distractors built from **real prose** — seeded 8-word windows of paragraphs from this
repository's own documentation — instead of tokens sampled from the queries' vocabulary.

**Answer: no. Realistic noise also misses the target.** The real-text corpus lands at recall@5
**0.692** (0.673 with whole paragraphs) against the published 0.70 target, while N2 sits at 0.538. Its
competing-distractor share is 0.476, between control's 0.144 and N2's 0.918, so the calibration check
passes and the corpus stands.

    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/run_realtext.py        # pre-registered
    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/sensitivity_window.py  # post-hoc length sweep

The corpus is **pinned** in `corpus_pin.json`: the numbers belong to that file, not to the current
`README.md`/`docs/*.md`. Earlier, the same script on a later docs state produced whole-paragraph
r@5 0.654 where the committed artifact said 0.673, and nothing failed because nothing pinned the
input. A re-run is now byte-identical against the committed artifacts (`tests/test_realtext_artifacts.py`).

    run_realtext.py --check-corpus      # exit 1 when README/docs drifted from the pin
    run_realtext.py --rebuild-corpus    # re-extract the pin, then re-review every quoted number

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
| `corpus_pin.json` | the frozen prose the windows are cut from, with per-file digests |
| `corpus_snapshot.json`, `result.json`, `ledger.json`, `sensitivity_window.json` | machine-readable outputs |
| `paired_test.py` | falsifier over two ledgers: integer pairs, zero-regression pass, no p-value claim |

Decided here: DECISIONS #52 — publish two noise corpora (N2 worst case, real text realistic), keep the
0.70 target attached to N2 and unmet, and record that #50's suspicion ("the target may only measure an
artifact") is wrong.
