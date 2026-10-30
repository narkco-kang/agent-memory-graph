# IDF-weighted scoring — measured outcome (v0.18.0)

Pre-registration written before the code changed: [`PREREGISTRATION.md`](PREREGISTRATION.md).
This round answers the candidate that `DECISIONS #27` named: does weighting terms by
rarity fix what constant field weights could not?

**Result: ship it — but not for the reason the v0.17.0 note guessed.** IDF helps the
realistic regime and the frozen baseline, and it is near-useless against the
query-vocabulary noise model, exactly as the pre-registration predicted.

## The change

```
idf(t)   = ln(1 + N / (1 + df(t)))      # N = visible nodes, df over the searched doc
score(n) = Σ (field, t) matched  WEIGHTS[field] × idf(t)
```

`WEIGHTS`, matching rules, filters, ordering and output shape are unchanged. Distinct
query terms only: a word typed twice cannot inflate a score. `baseline.py` is the
frozen v0.17.0 scorer, run in the same process on the same corpora.

## Measured (26 frozen queries, same gold set)

| corpus | scorer | r@1 | r@5 | r@10 | MRR@10 | p50 |
|---|---|---|---|---|---|---|
| control 27 | baseline | 0.654 | 0.808 | 0.865 | 0.763 | 0.3 ms |
| control 27 | **shipped** | **0.731** | **0.865** | 0.865 | **0.821** | 0.3 ms |
| N1 unrelated 10k | baseline | 0.654 | 0.808 | 0.865 | 0.763 | 74.2 ms |
| N1 unrelated 10k | **shipped** | **0.731** | **0.865** | 0.865 | 0.815 | 77.2 ms |
| N2 query-vocab 10k | baseline | 0.481 | 0.538 | 0.538 | 0.515 | 93.2 ms |
| N2 query-vocab 10k | **shipped** | 0.481 | 0.538 | **0.577** | **0.536** | 97.5 ms |
| N3 frequent-vocab 10k | baseline | 0.654 | 0.712 | 0.712 | 0.731 | 85.5 ms |
| N3 frequent-vocab 10k | **shipped** | **0.731** | **0.865** | **0.865** | **0.821** | 89.1 ms |

Per-query movement: on the control corpus q02 `3 → 1`, q18 `6 → 3` (its only miss
fixed), q26 `3 → 1`; on N3 the same three, and 3 more gold hits enter the deep list.
On N2 the top-5 is unchanged while deep ranks move a lot: q05 `42 → 9`, q16 `99 → 46`,
q20 `68 → 53`, and q12 / q24 / q26 are matched for the first time (ranks 75 / 83 / 17).

## Criteria

| # | Criterion | Result |
|---|---|---|
| C1 | frozen r@5 ≥ 0.808 and r@1 ≥ 0.654 | **pass** (0.865 / 0.731) |
| C2 | N1 no regression | **pass** (all four metrics up or equal) |
| C3 | N2 no regression | **pass** (r@5 equal, r@10 and MRR up) |
| C4 | N3 r@5 gain ≥ +0.05 | **pass** (+0.153) |
| C5 | everything published | this file + `result.json` |
| C6 | no tuning in the round | one change, no formula or weight edits after the first run |

Ship rule (pre-registered): C1–C3 pass and C4 passes ⇒ v0.18.0 ships.

## Predictions that were wrong (kept as wrong)

| prediction | measured | verdict |
|---|---|---|
| control stays ≥ 0.808, may shift ±0.04 | 0.865 (+0.057) | **wrong in the good direction** — rarity also re-ranks the *small* corpus, where common words ("the", "graph") had been padding scores |
| N2 0.52–0.60 and **not** 0.70 | 0.538 | right, including the structural reason below |
| N3 baseline 0.45–0.65 | 0.712 | **wrong** — frequent-word noise is less harmful than assumed, because rare query terms still appear in the gold node only |
| N3 IDF 0.85–1.00 | 0.865 | right |

The N2 target from the task node (`recall@5 ≥ 0.70`) was **not reached** (0.538). It
was pre-registered as a target, not a ship gate, for one structural reason: N2 builds
every distractor from a **uniform** draw over the union of query tokens, so every query
term has nearly the same `df` and IDF has no signal to separate them. That is a
property of the noise model, not of IDF in general — and it is now measured rather than
argued. Beating N2 requires a signal outside document frequency (e.g. id/type priors or
phrase proximity), which is the next candidate, with its own pre-registration.

## Cost

IDF is one extra pass of bookkeeping, not a second scan: matching already iterates every
field, so the pairs are kept during that pass (`_match_fields`) instead of being
recomputed. Measured p50 +3.0 ms at 10k (+4%) and unmeasurable on 27 nodes.
Memory: one short list per matching node, per query.

## What this does not establish

- Nothing about semantic recall: paraphrase misses q06 / q08 / q10 are word-level gaps
  that no weighting can close.
- Nothing about a real 10k graph: N1–N3 are synthetic, deterministic noise models.
- N2 is not "fixed"; r@5 is unchanged and the remaining misses are the same 11 queries.

## Reproduce

```bash
PYTHONPATH=src python3 experiments/retrieval_idf/run_eval.py            # table + verdicts
PYTHONPATH=src python3 experiments/retrieval_idf/run_eval.py --json     # result.json
```
