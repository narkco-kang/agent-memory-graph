# Is the 0.70 target an artifact of N2's construction?

Pre-registered: distractors built from **real prose** — seeded 8-word windows of paragraphs from this
repository's own documentation — instead of tokens sampled from the queries' vocabulary.

**Answer: no. Realistic noise also misses the target.** The real-text corpus lands at recall@5
**0.692** (0.673 with whole paragraphs) against the published 0.70 target, while N2 sits at 0.538. Its
competing-distractor share is 0.476, between control's 0.144 and N2's 0.918, so the calibration check
passes and the corpus stands.

    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/run_realtext.py        # pre-registered
    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/sensitivity_window.py  # post-hoc length sweep

| file | what it is |
|---|---|
| `PREREGISTRATION.md` | construction, calibration-first ordering, criteria, predictions; `## Outcome` appended |
| `run_realtext.py` | builds the corpus from repository prose, reports calibration before recall |
| `sensitivity_window.py` | post-hoc: same construction at 8 / 20 / whole-paragraph lengths |
| `result.json`, `sensitivity_window.json` | machine-readable outputs |

Decided here: DECISIONS #52 — publish two noise corpora (N2 worst case, real text realistic), keep the
0.70 target attached to N2 and unmet, and record that #50's suspicion ("the target may only measure an
artifact") is wrong.
