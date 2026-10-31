# Pre-registration: a rerank signal outside the document-frequency family

Written **before** the run, and not edited afterwards (an outcome section is appended instead,
so a failed prediction stays visible — DECISIONS #25/#26/#28/#29 all set that precedent).

## Why this experiment

DECISIONS #28 shipped IDF weights: the frozen 27-query baseline went 0.808 → 0.865 and
frequent-vocabulary noise (N3) 0.712 → 0.865, but **query-vocabulary noise (N2) did not move —
0.538 → 0.538**, against a published target of 0.70. #28 stated the reason before it was
measured and it held: N2 draws every distractor token *uniformly* from the queries' own
vocabulary, so `df` is the same for every query term and IDF has no signal to spend.

So the next step must use a signal that is **not** document frequency. DECISIONS #29 rejected a
field-split df (it bought N2 +0.058 for frozen r@5 −0.038). This experiment tests the other
candidate named in `task.mem-arch-beyond-df-rerank`: **rerank by query coverage** — how much of
the query a hit actually contains, independent of how rare each term is.

## The signal

For a hit `h` and query `q`:

    coverage(h, q) = |tokens(q) ∩ tokens(node_text(h))| / |tokens(q)|

    reranked_score = shipped_score(h) × coverage(h, q) ** alpha

Ties fall back to shipped score, then to id, so the ordering is total and reproducible.
`alpha = 0` is exactly the shipped scorer and is the control arm; `alpha ∈ {0.5, 1, 2}` are the
candidate arms. Selection happens on **N2 only**; the other three corpora are regression checks.

Rationale: a distractor containing one random query token has coverage 1/|q|; a hit containing the
whole query has coverage 1. IDF cannot see this because in N2 every added token is equally rare.

## Corpora and protocol

Same four corpora, same frozen queries, same gold, same process — built by importing
`experiments/retrieval_idf/run_eval.py`'s builders, so the nodes are byte-identical to the ones
the IDF round measured:

| name | nodes | what it is |
|---|---|---|
| control | 27 | the frozen real graph |
| n1 | 10,000 | unrelated-noise distractors |
| n2 | 10,000 | query-vocabulary noise (the target) |
| n3 | 10,000 | frequent-vocabulary noise |

Candidate lists come from `amg.retrieval.search(..., k=100)` — the reranker only reorders the top
100, it cannot invent a hit. Recall is measured against the same gold, at k = 1/5/10, plus MRR.

## Criteria (fixed before the run)

* **C1 no frozen regression**: control `recall@5 ≥ 0.855` (shipped 0.865, tolerance 0.01).
* **C2 the target moves**: N2 `recall@5 ≥ 0.588` (+0.05 over 0.538) for the selected alpha.
  This is the *increment* criterion. The published 0.70 target is reported separately and is not
  a ship gate; missing it is a result, not a reason to retune alpha.
* **C3 unrelated noise unchanged**: n1 `recall@5 ≥ 0.855`.
* **C4 frequent noise not harmed**: n3 `recall@5 ≥ 0.845`.
* **C5 honest bookkeeping**: alpha is chosen from the N2 column only, and the choice is reported
  even if it fails.

Ship rule: if C1–C4 hold for one alpha, the rerank may ship behind its own decision entry.
Otherwise the direction is recorded as rejected — no tuning, no alpha hunting after the fact.

## Predictions (scored as right/wrong afterwards)

1. `alpha = 1` is the best N2 arm; `alpha = 2` over-penalises long queries and loses recall@1.
2. Coverage buys N2 `recall@5` between **+0.03 and +0.08** (i.e. 0.568–0.618) — enough to matter,
   likely not enough for 0.70.
3. Control `recall@5` drops by **≤ 0.01** at `alpha = 1` (most gold hits already cover the query).
4. n3 stays within 0.01 of 0.865 (its distractors are frequent words, not query words, so
   coverage and IDF agree there).
