# Is there any lexical signal left for query-vocabulary noise?

An experiment under `PREREGISTRATION.md`: three non-document-frequency rerankers — content-word
coverage (stopwords stripped), title coverage, compactness — applied to the shipped top-100 on the
same four corpora the IDF and coverage rounds used.

Answer: **no.** All nine arm/alpha combinations *lose* N2 recall (best 0.481 vs shipped 0.538), and
a post-hoc split shows why the pooled separability looked positive: on the eleven queries the
scorer already fails, every signal's AUC is at or below chance (0.42 / 0.26 / 0.28).

    PYTHONPATH=src python3 experiments/retrieval_lexical_ceiling/run_lexical.py
    PYTHONPATH=src python3 experiments/retrieval_lexical_ceiling/diagnose_by_solved.py

| file | what it is |
|---|---|
| `PREREGISTRATION.md` | criteria and predictions, written before the run; `## Outcome` appended after |
| `run_lexical.py` | the three arms + the pre-registered diagnostics (D1 AUC, D2 candidate ceiling) |
| `diagnose_by_solved.py` | post-hoc, clearly labelled: splits the AUC by whether the query was already solved |
| `result.json` | machine-readable run output (arms, diagnostics, verdicts) |
| `diagnostic_by_solved.json` | machine-readable post-hoc split |

Decided here: DECISIONS #49 — the lexical rerank family is closed for N2. What remains is a signal
that is not term statistics; it must be evaluated as *candidate generation* as well as reranking,
because 4 of 26 queries have their gold outside the shipped top-100.
