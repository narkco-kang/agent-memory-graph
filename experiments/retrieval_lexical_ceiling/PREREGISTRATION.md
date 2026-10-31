# Pre-registration: is there any lexical signal left for N2?

Written **before** the run; nothing in this file is edited afterwards. An `## Outcome` section is
appended instead, so a wrong prediction stays visible (DECISIONS #25/#26/#28/#29/#47 set that
precedent).

## Why this experiment

DECISIONS #48 corrected #47's mechanism: coverage on N2 was **not** anticorrelated with the gold;
it is positively correlated (gold mean 0.610 vs distractor 0.376) and the damage comes from
**distribution shape** — real answers are bimodal (7/22 full coverage, 8/22 at or below 0.33) while
distractors sit in a narrow band, because a distractor built from the query vocabulary matches
several of its words at once, including **function words** (`can`, `this`).

#48's stated next direction is **content-word weighting / stopword stripping**, and it explicitly
warns that the earlier "content words only" arm (+0.077) was a selectively constructed fixture,
not a shippable reranker: the shipped code cannot know which words were injected.

This experiment asks the only question that can decide whether to keep spending lexical effort at
all: **is any lexical rerank of the shipped top-100 able to move N2 by the +0.05 increment?**
If none can, the 0.70 target needs a signal that is not lexical, and the retrieval roadmap should
say so instead of chasing more term statistics.

## The three candidate signals

All three rerank only the top 100 candidates `amg.retrieval.search(..., k=100)` returns; none can
introduce a hit the scorer did not find. Rerank rule, as in the coverage round:

    reranked = shipped_score * f(hit, query) ** alpha       alpha in {0.5, 1, 2}
    alpha = 0 is exactly the shipped scorer (control arm), ties break by shipped position

| signal | definition | why it could work |
|---|---|---|
| **S1 content coverage** | `|C(q) ∩ tokens(node)| / |C(q)|` where `C(q)` = query tokens minus a fixed stopword list | #48's stated direction: function-word matches stop counting as evidence. q04's distractor would drop from 3 matches to 2 |
| **S2 title coverage** | fraction of query tokens found in `node["label"]` only | a real answer usually has the subject in its title; a distractor that pads six random words into a title cannot be *about* all of them |
| **S3 compactness** | full-query coverage divided by `1 + ln(1 + |tokens(node)|)` | a short answer that contains the words beats a long note that happens to contain them |

The stopword list is **fixed here, before the run**, and is the standard closed-class set (articles,
pronouns, auxiliaries, prepositions, conjunctions, degree adverbs) — no list is fitted to the 26
queries. If `C(q)` is empty for a query, S1 returns 1.0 (no signal, no penalty).

## Corpora and protocol

Identical to the coverage round, so numbers are comparable without any re-derivation: the four
corpora are rebuilt by importing `experiments/retrieval_10k/run_eval.py` and
`experiments/retrieval_idf/run_eval.py`, i.e. the same builders that produced
control 27 / n1 10,000 / n2 10,000 / n3 10,000 and the same 26 frozen queries and gold.

Shipped baseline (`experiments/retrieval_idf`, v0.19.0+ IDF): control 0.865, n1 0.865, **n2 0.538**,
n3 0.865.

## Criteria (fixed before the run)

* **C1 no frozen regression**: control `recall@5 ≥ 0.855` for the selected arm.
* **C2 the target moves**: N2 `recall@5 ≥ 0.588` (+0.05 over 0.538). Selection is on the N2 column
  only; alpha is reported even when the criterion fails.
* **C3 unrelated noise unchanged**: n1 `recall@5 ≥ 0.855`.
* **C4 frequent noise not harmed**: n3 `recall@5 ≥ 0.845`.
* **Hit gate**: the same arm+alpha must satisfy C1–C4 together. Missing them is a result, not a
  reason to retune.

### Diagnostics (reported, not gates)

* **D1 separability AUC**: for each query, within its top-100 candidates, does the signal rank gold
  above non-gold? AUC 0.5 = no information; 1.0 = perfect. Mean over queries that have gold in the
  candidate list. A signal whose AUC is ~0.5 cannot fix the corpus no matter how alpha is tuned,
  so D1 is what decides *why* an arm fails.
* **D2 candidate ceiling**: fraction of queries whose gold is inside the top 100. If D2 < 1.0 the
  loss is generated before reranking and no reranker can repair it.

### Pre-registered predictions (before any number was seen)

1. **All three arms fail C2.** No lexical signal closes a 0.062 gap on a noise model whose
   distractors are drawn from the queries' own vocabulary and land in the title.
2. **D1: every signal's mean AUC ≤ 0.55.** If this holds together with 1, the conclusion is that
   N2 needs a non-lexical signal — not more term statistics — and the roadmap entry for vector
   retrieval should be re-scoped from "evaluate" to "the only remaining candidate".
3. **D2 = 1.0**: the gold is already in the candidate list for every query, so the loss is pure
   ranking, not candidate generation.
4. **C1/C3/C4 hold at alpha ≤ 1** for whatever arm is selected (the signal is multiplicative and
   bounded, so it cannot reorder anything except within close score bands).

If prediction 2 fails (some AUC > 0.7) while 1 still holds, that combination is the interesting
negative: signal exists but is drowned by the score scale — which would point at score
normalisation, not at a new signal.

## Outcome

Run on 2026-10-31, 7.6 s, `run_lexical.py` then `diagnose_by_solved.py`; machine-readable in
`result.json` and `diagnostic_by_solved.json`.

| arm | N2 r@5 at alpha 0.5 / 1 / 2 | control | n1 | n3 |
|---|---|---|---|---|
| shipped (alpha 0, all arms) | **0.538** | 0.865 | 0.865 | 0.865 |
| S1 content coverage | 0.442 / 0.442 / 0.442 | 0.865 | 0.865 | 0.865 |
| S2 title coverage | 0.404 / 0.327 / 0.192 | 0.808 | 0.808 | 0.750 |
| S3 compactness | 0.481 / 0.481 / 0.442 | 0.846 | 0.808 | 0.808 |

`alpha = 0` reproduces the shipped metrics on all four corpora (checked in the run, not asserted).

**No arm moves N2 up at all.** The best of the nine arm/alpha combinations — S3 at alpha 0.5 —
*loses* 0.057 and takes control from 0.865 to 0.846, so every gate (C1–C4) fails; the +0.05
increment is not approached, let alone the 0.70 target. Verdict: **no ship**, and the stop-word /
content-weight direction that #48 named is closed.

### Predictions scored

| # | prediction | result |
|---|---|---|
| 1 | all three arms fail C2 | **correct** — all nine combinations are worse than 0.538 |
| 2 | every signal's mean AUC ≤ 0.55 | **wrong** — S1 0.665, S3 0.610 (S2 0.433) |
| 3 | D2 = 1.0 (gold always in the top 100) | **wrong** — 0.846 on N2: **4 of 26 queries have gold beyond the top 100** |
| 4 | C1/C3/C4 hold at alpha ≤ 1 | **wrong** — S2 costs control 0.057 and n3 0.115; S3 costs n1 0.057 |

Prediction 2's failure looked at first like the "interesting negative" branch this file anticipated
(signal exists, score scale drowns it). It is not: the pooled mean is carried by queries the shipped
scorer already solves, and `diagnose_by_solved.py` splits it:

| group | queries | S1 AUC | S2 AUC | S3 AUC |
|---|---|---|---|---|
| solved (gold already in top 5) | 15 | 0.779 | 0.515 | 0.767 |
| **failing (gold outside top 5)** | **11** | **0.421** | **0.258** | **0.275** |
| gold beyond top 100 | 4 | — | — | — |

On the eleven queries that need repair, all three signals are **at or below chance**. The pooled
AUC of 0.665 was an artifact of averaging the solved half in — which is exactly the kind of number
this project's pre-registration rule exists to stop being quoted.

### What this settles

1. The lexical rerank family is exhausted for N2: content-word coverage (the direction #48 named),
   title coverage and compactness all lose recall, and none has usable signal on the failing half.
   DECISIONS #49 records the closure; no further term-statistic variant is worth a round.
2. The 0.70 target is *not* refuted as impossible: a perfect reranker could still reach the
   candidate ceiling, 0.846 ≥ 0.70. What is refuted is that a lexical one can.
3. Two of the 26 queries can only be fixed by changing candidate generation (4 have gold outside the
   top 100), so a semantic arm must be evaluated at both levels — ranking *and* candidate recall —
   not only as a reranker.
