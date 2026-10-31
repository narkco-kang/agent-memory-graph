# Is N2 the noise a real graph produces?

Pre-registered attempt to calibrate N2's distractor construction against the real corpus, plus the
honest failure of that attempt.

**Answer: the question is still open, and the attempt failed its own calibration check.** The
measured contrast is real — competing distractors reach a quarter of the query 14.4% of the time on
the real corpus versus 91.8% on N2 (6.4×) — but a 10,000-node pool built to reproduce 14.4% produced
60.6%, because the top-100 is selected by the quantity being calibrated.

    PYTHONPATH=src python3 experiments/retrieval_noise_representativeness/run_calibrated.py   # ~15 s

| file | what it is |
|---|---|
| `PREREGISTRATION.md` | criteria, decision rule, predictions; discloses the two preliminary scans; `## Outcome` appended |
| `run_calibrated.py` | builds N2-cal (three generator variants), measures competing coverage, re-runs the five corpora |
| `result.json` | machine-readable: coverage tables, all five corpora, verdicts |

Decided here: DECISIONS #51 — synthetic noise corpora must be calibrated **on the competing subset**,
and that check runs before any recall number is reported. The next design samples distractor text from
real notes rather than tokens. N2's 0.538 and the unmet 0.70 target are unchanged.
