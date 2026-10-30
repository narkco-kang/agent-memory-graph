# Pre-registration: retrieval recall at 10,000 nodes

Written before the run, on `v0.16.0` (`abfc7b1`). The published retrieval numbers
(`../retrieval_eval/`) are on a 27-node corpus. `docs/CONCURRENCY.md` now measures
concurrency at 10k; retrieval at 10k is still unmeasured and is listed as such in the
README. This file fixes what counts as a result before measuring it.

## Question

What happens to lexical retrieval recall when the same 26 queries and the same gold
answers are searched against a graph with 10,000 nodes instead of 27?

## Method

- The frozen corpus and queries are **used unchanged** (`../retrieval_eval/corpus.json`,
  `queries.json`) — no query is edited, no gold id moves.
- **9,973 distractor nodes** are added from the same generator as the write benchmarks
  (`benchmarks/bench.py`): `task.nNNNNN` / "task number N parser queue" / "synthetic
  node N". They intentionally share the vocabulary of the real corpus (`task`, `queue`,
  `parser`), so this is not a deliberately hostile corpus — it is a plausible noise
  floor.
- The build is deterministic (ids and labels are functions of the index), and the
  merged corpus digest is printed so a rerun can be compared byte-for-byte.
- Metrics are computed by the **same functions** as `retrieval_eval/run_eval.py`
  (`evaluate` + `aggregate`), so the numbers are comparable.
- A same-process control run on the 27-node corpus is executed first, so machine
  differences cannot be mistaken for the effect of scale.

## Predictions (recorded before the run; being wrong is data)

| quantity at 10k | predicted | basis |
|---|---|---|
| overall recall@5 | **0.30–0.60** (from 0.808) | 370× more distractors compete for 5 slots |
| overall recall@1 | **0.15–0.40** (from 0.654) | the same, applied to one slot |
| keyword vs paraphrase | keyword retains more | paraphrase queries share few literal tokens |
| share of missed queries where gold *is* matched but ranked 11–100 | **≥ 50%** | the matcher still matches; the ranking dilutes |

## Criteria (fixed now)

| # | Criterion | Verdict rule |
|---|---|---|
| C1 | The corpus is reproducible and the frozen inputs are untouched | pass only if the corpus digest is recorded and both input digests equal those in `retrieval_eval/result.json` |
| C2 | All numbers published, whatever they are | recall@1/5/10, MRR, per bucket, latency, and the failing per-query rows |
| C3 | Misses are classified, not just counted | each miss labelled *ranked 11–100* (dilution) or *beyond 100 / not matched* (matcher or scoring) |
| C4 | No tuning in the same round | if recall collapses, that is the finding. Any ranking change (e.g. IDF weighting) must come with its own pre-registration and its own numbers. |

## What this will not establish

- Nothing about semantic recall: this measures the shipped lexical path only.
- Nothing about write cost or concurrency at 10k (`docs/CONCURRENCY.md` covers that).
- Nothing about other languages, other gold sets, or a real 10k graph — the corpus is a
  frozen English one with synthetic noise.

## Reproduce

```bash
PYTHONPATH=src python3 experiments/retrieval_10k/run_eval.py            # prints table
PYTHONPATH=src python3 experiments/retrieval_10k/run_eval.py --json     # result.json
```

---

## Amendment A (written after noise model N1 ran; **before** N2 was run)

N1 result: recall was **identical** at 10k — 0.654 / 0.808 / 0.865 / 0.763, exactly the
27-node control — with p50 latency 73.75 ms. Prediction "0.30–0.60" was wrong, and the
reason is methodological: the N1 distractors (bench generator: "task number N parser
queue") share almost no vocabulary with the 26 queries, so they never outrank a gold
node. **Graph size alone does not dilute lexical recall; vocabulary overlap does.**

N1 therefore answers a narrower question than the one that matters for a memory graph,
where old notes usually *do* share the words a new query uses. So a second noise model
is added, and its prediction is recorded here, before it runs:

**N2 — query-vocabulary distractors.** 9,973 nodes whose `label`/`note` are built by a
deterministic PRNG from the **union of the 26 queries' tokens** (6 tokens each, plus an
index), so every distractor competes with gold on the words people actually type. Ids
remain `task.nNNNNN`.

| quantity, N2 at 10k | predicted |
|---|---|
| overall recall@1 | 0.30–0.55 |
| overall recall@5 | **0.40–0.70** |
| share of misses that are ranked 11–100 | ≥ 50% (dilution, not unification) |
| latency p50 | within 2× of N1 (73.75 ms) |

Both noise models are published side by side. N2 is not "cheating": it is what a
long-lived memory graph looks like, since most notes discuss what was already asked.

---

## Outcome (recorded after both noise models ran)

Artifacts: `result.json` (both models, all rows, corpus digests). Environment: this
machine, in-process, `v0.16.0` + the v0.17.0 working tree.

| run | nodes | recall@1 | recall@5 | recall@10 | MRR@10 | search p50 |
|---|---|---|---|---|---|---|
| control (frozen 27) | 27 | 0.654 | 0.808 | 0.865 | 0.763 | — |
| **N1 unrelated distractors** | 10,000 | 0.654 | 0.808 | 0.865 | 0.763 | 74.3 ms |
| **N2 query-vocabulary distractors** | 10,000 | **0.481** | **0.538** | 0.538 | **0.515** | 92.5 ms |

| # | Criterion | Result |
|---|---|---|
| C1 | reproducible corpus, frozen inputs untouched | **pass**: `inputs_match_frozen: true`; both corpus digests recorded |
| C2 | all numbers published | **pass**: three runs, per-bucket, per-query rows, latency, in `result.json` |
| C3 | misses classified | **pass**: N2 has 11 misses at k=5 — 4 ranked 11–100 (dilution), 7 beyond 100 (scoring) |
| C4 | no tuning in the same round | **pass**: no code touched; a ranking change would need its own pre-registration |

### Predictions, scored

| prediction | measured | verdict |
|---|---|---|
| N1 recall@5 0.30–0.60 | 0.808 (unchanged) | **wrong** — and the reason is the finding: unrelated noise cannot dilute lexical recall |
| N2 recall@1 0.30–0.55 | 0.481 | right |
| N2 recall@5 0.40–0.70 | 0.538 | right |
| N2 misses mostly dilution (≥ 50% ranked 11–100) | 36% (4/11) | **wrong** — most misses are beyond rank 100 |
| N2 latency within 2× N1 | 92.5 vs 74.3 ms (1.24×) | right |

### What the two models together say

1. **Graph size alone does not cost recall.** 370× more unrelated nodes left every
   metric identical — this disposes of the naive worry that a big memory "dilutes"
   retrieval.
2. **Vocabulary overlap costs recall, and the mechanism is scoring, not matching.**
   With distractors built from the queries' own words, recall@5 falls 0.808 → 0.538;
   of the 11 misses, 7 are beyond rank 100, meaning dozens of distractors outscored the
   gold node rather than the gold node failing to match.
3. **The cause is visible in the scorer**: `WEIGHTS` (id 3.0, label 2.0, note 1.0,
   source 0.5, owner 0.5) has **no term-frequency or IDF notion**, so a note that
   happens to repeat common query words is worth as much as the node that actually
   answers. That is the next candidate — with its own pre-registration, per C4, and
   the frozen 27-node eval as the regression guard.

### What it does not establish

Nothing about a real 10k graph (this is synthetic noise on a frozen English corpus),
nothing about semantic recall, and nothing about how IDF weighting would behave — that
is a hypothesis, not a result.

