# Pre-registration: IDF-weighted scoring (v0.18.0)

Written on `v0.17.0` (`647f73a`), **before** `src/amg/retrieval.py` was touched.
`docs/DECISIONS.md` #27 named the cause of the 10k recall loss ("the scorer has no
IDF"); this file fixes the change, the criteria and the ship rule before the change
exists. One change, one round. `experiments/retrieval_10k/PREREGISTRATION.md` C4
forbade tuning in that round; this is that round, with its own bar.

## The change (exactly one)

In `src/amg/retrieval.py`, replace the constant per-field contribution with a
**BM25-style term weight**, computed from the document being searched:

```
idf(t)      = ln(1 + N / (1 + df(t)))          # N = visible nodes for the layer
score(n)    = Σ (field, t) matched   WEIGHTS[field] × idf(t)
```

- `df(t)` is the number of **visible** nodes (after the superseded / not-yet-valid /
  L1 / L4 filters) whose `id`, `label`, `note`, `source` or `owner` matches `t`
  under the existing matcher (word boundary + inflection table). Counted once per
  node per token, so a node repeating a word is not counted twice.
- `WEIGHTS` itself is **unchanged** (id 3.0, label 2.0, note 1.0, source/owner 0.5)
  and field matching is unchanged. Only the token weight becomes rarity-aware.
- A query token appearing twice in the query counts once (distinct terms), so a
  repeated word cannot inflate a score. That is part of the same change, not a
  second one.
- Nothing else moves: hard filters, anchor rule, `strict`, `expand`, L2 search,
  output keys and ordering (anchored first, then score, then id) stay as they are.
- Deterministic: same document + same query ⇒ same scores. No dependencies.

## Corpora (all four in one process, baseline included)

The **v0.17.0 scorer is frozen as `baseline.py`** in this directory and run on the
same corpora in the same process, so every comparison is like-for-like and machine
noise cannot be mistaken for the effect. `result.json` records both sides.

| id | corpus | what it tests |
|---|---|---|
| control | frozen 27 nodes, 26 queries | no regression on published numbers |
| N1 | control + 9,973 unrelated distractors (`retrieval_10k`) | no regression at size |
| N2 | control + 9,973 query-vocabulary distractors (`retrieval_10k`) | does rarity help the known failure? |
| **N3** | control + 9,973 **frequent-vocabulary** distractors (new, below) | the regime IDF claims to fix |

**N3 — frequent-vocabulary distractors.** A long-lived memory graph accumulates notes
about the *same* subject, so the common words of the corpus ("the", "graph", "file",
"node", …) are everywhere. Built deterministically: take the 12 most frequent tokens
(≥ 3 chars) by document frequency over the 27-node corpus text; each distractor draws
6 tokens with replacement from those 12 (weights = document frequency), the first 3
form the `label`, the last 3 the `note`; ids `task.nNNNNN`, seed `20261031`, source
`synthetic frequent-vocabulary distractor`. Recorded here before it runs, so it cannot
be reshaped after seeing the numbers.

Metric functions are imported from `experiments/retrieval_eval/run_eval.py`
(`evaluate` + `stratified_halves` + `aggregate`), exactly as `retrieval_10k` does.

## Predictions (recorded now; being wrong is data)

| quantity | predicted | basis |
|---|---|---|
| control r@5 | ≥ 0.808 (may shift ±0.04, not below) | rare words already carry the gold; reweighting should not hurt |
| N1 r@5 | 0.808 (identical) | distractors share almost no query vocabulary, so their df is irrelevant |
| **N2 r@5** | **0.52–0.60, and *not* 0.70** | N2 draws distractor tokens **uniformly** from the union of query tokens, so `df` is near-identical for every query token: IDF has almost no signal to use. This is a structural prediction about the noise model, and it is the reason the v0.17.0 "next step: IDF" is only half a fix. |
| N3 baseline r@5 | 0.45–0.65 | common-word matches outscore the gold node under constant weights |
| **N3 IDF r@5** | **0.85–1.00** | rare query terms (`atomic`, `msvcrt`, `checksum`) get high IDF, common-word distractors collapse to ~0.69 × weight |

## Criteria (fixed now)

| # | Criterion | Verdict rule |
|---|---|---|
| C1 | Frozen 27-node recall does not regress | pass only if `recall@5 ≥ 0.808` **and** `recall@1 ≥ 0.654` |
| C2 | N1 does not regress | pass only if all four metrics ≥ the baseline's |
| C3 | N2 does not regress | pass only if `recall@5 ≥ 0.538` and `recall@1 ≥ 0.481` |
| C4 | The mechanism shows where it should | pass only if N3 `recall@5` improves by **≥ +0.05** over the baseline on the same corpus |
| C5 | Everything published | all four corpora, both scorers, per-bucket rows and latency, whatever the numbers — including a failed N2 target |
| C6 | No tuning inside the round | if the formula or `WEIGHTS` is changed after the first measurement, the round is void and must be re-registered |

**Ship rule (decided now):** ship v0.18.0 only if C1, C2, C3 pass and C4 passes.
If C4 fails, IDF is recorded as a measured non-improvement, `retrieval.py` reverts to
the v0.17.0 scorer, and no release is cut. The N2 target of `recall@5 ≥ 0.70` from
`task.mem-arch-idf-rerank` is **published but not a ship gate** — the prediction above
says it is unreachable by this change alone.

## What this will not establish

- Not that lexical retrieval is as good as semantic retrieval; paraphrase queries stay
  unmatched by construction (an IDF weight cannot match a word that is not there).
- Not that N2 is "solved": if the prediction holds, N2 is a noise model that is
  *invariant* to document-frequency statistics, and the next candidate must come from
  outside that family (query-token discrimination learned from the graph's own
  structure, e.g. id/type priors or phrase proximity).
- Not a real 10k graph: all noise here is synthetic and deterministic.
- No claim about non-English corpora beyond the CJK substring rule that does not change.

## Reproduce

```bash
PYTHONPATH=src python3 experiments/retrieval_idf/run_eval.py            # table
PYTHONPATH=src python3 experiments/retrieval_idf/run_eval.py --json     # result.json
```
