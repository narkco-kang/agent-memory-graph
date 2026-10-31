# Pre-registration: is N2 the noise a real graph produces?

**Disclosure, before anything is claimed:** two exploratory looks were taken *before* this file was
written — (a) a coverage scan of the team's real 410-node graph (`knowledge-graph/graphs/记忆架构开源.json`)
against the 26 frozen queries, and (b) a coverage scan of the top-100 candidates on the `control` and
`n2` corpora. Their numbers are quoted below as *exploration*, not as results. What is pre-registered
here is the **calibrated noise corpus, its construction, and the criterion** — the part where a
tuning knob could hide a desired answer.

## Why

DECISIONS #49 and #50 closed the lexical and semantic families for N2: both land at 0.577 against a
0.588 criterion, and neither raises the N2 candidate ceiling above 0.846. #50 named the open question
explicitly: N2 builds each distractor from **six tokens drawn from the queries' own vocabulary**, put
into `label` and `note`, so it may be a near-duplicate discrimination task rather than the noise a
long-lived memory graph meets. That claim was left as an assertion to be measured.

## Exploration (already seen; recorded so it cannot be presented as a prediction)

| set | competing candidates | mean coverage | median | share ≥ 0.25 | share ≥ 0.5 |
|---|---|---|---|---|---|
| `n2` top-100 distractors | 2,578 | 0.415 | 0.400 | **0.919** | 0.393 |
| `control` top-100 distractors | 146 | 0.147 | 0.167 | **0.144** | 0.027 |
| real 410-node graph, all pairs | 10,660 | 0.018 | 0.000 | 0.028 | 0.007 |
| real 410-node graph, top-100 | see run | — | — | — | — |

The two populations that matter — distractors that *compete* — differ by roughly 6.4× in the share
reaching a quarter of the query. The 410-node scan is a weaker proxy (its ontology is the project's
own nodes, not the eval corpus) and is reported only as a bound.

## The calibrated corpus (fixed here)

`N2-cal`: 10,000 nodes, same generator as N2 except for the token count taken from the query
vocabulary. For each synthetic node, draw `m` (the number of query-vocabulary tokens it contains)
from the **empirical distribution of `control`'s competing distractors**, i.e. the distribution
measured above (mostly 0–1, occasionally 2–3, essentially never 6). Remaining tokens come from a
filler pool — the same `bench.make_node` scaffolding N2 uses, with tokens drawn from a fixed
non-query word list — so the node shape stays comparable. Seed `20261031`, same as N2.

Two checks that the corpus is what it claims to be, both reported:
* its competing-distractor coverage distribution must sit near `control`'s (share ≥ 0.25 within
  ±0.10 absolute), *not* near N2's;
* node count, query set, gold and scorer are unchanged, so the only difference from N2 is the
  distractor construction.

## Criteria (fixed before the run)

This is a **measurement**, not a ship gate. It decides one question: *is the 0.70 target on N2 a
statement about realistic retrieval quality, or about worst-case robustness?*

* **Q1 N2-cal re-baseline**: shipped `recall@5` on N2-cal, reported with the same four corpora as
  reference. Pre-registered prediction: **≥ 0.75** (against 0.538 on N2 and 0.865 on control).
* **Q2 calibration holds**: N2-cal's competing-distractor share ≥ 0.25 is within ±0.10 of control's.
  If it is not, the corpus is rejected and no conclusion is drawn from Q1.
* **Q3 the ranking of corpora is preserved**: N2 stays the hardest, N2-cal sits between N2 and
  control. If N2-cal ≥ control, the calibration is wrong somewhere and is not published as a result.

### Decision rule (fixed before the run)

If Q2 and Q3 hold and Q1 ≥ 0.75, then N2 is published as a **worst-case robustness corpus**, not as
the primary quality measure, and a `N2-cal` result is added **alongside** it. The 0.70 target on N2
stays **unmet and published as unmet**; no target moves. The revision is announced in a decision entry
and the old number is kept visible, per the standing rule that a corrected claim is marked, never
deleted.

If Q1 < 0.75, then N2's construction is not the explanation for the shortfall, the representativeness
objection is recorded as unsupported, and the roadmap says so.

### Predictions (before the run)

1. N2-cal shipped `recall@5` ≥ 0.75 (Q1).
2. N2-cal's share ≥ 0.25 lands in 0.10–0.30 (near control's 0.144, not N2's 0.919).
3. n1 and n3 are unchanged, because their generators are not touched.
4. At least one of the eleven N2-failing queries still fails on N2-cal — the noise model is one cause,
   not the only one.

## Outcome

Run on 2026-10-31, `run_calibrated.py` (3 s per corpus build; the four reference corpora are rebuilt
each run). Machine-readable in `result.json`.

### The pre-registered answer

| check | result |
|---|---|
| **Q1** N2-cal `recall@5 ≥ 0.75` | **0.654 — not met** |
| **Q2** N2-cal competing share ≥ 0.25 within ±0.10 of control's 0.144 | **0.606 — not met** |
| **Q3** N2 < N2-cal < control | **0.538 < 0.654 < 0.865 — met** |

**Q2 failed, so by the rule fixed above the corpus is rejected and no conclusion is drawn from Q1.**
That is the outcome: the first calibration attempt did not produce a corpus whose competing noise
matches the real corpus's, and the 0.654 is recorded as a *rejected-run diagnostic*, not a result.

Measured coverage of the candidates that actually compete (top-100, gold excluded):

| corpus | pairs | mean | median | share ≥ 0.25 |
|---|---|---|---|---|
| control (27 real nodes) | 146 | 0.147 | 0.167 | **0.144** |
| n2 (query-vocabulary noise) | 2,578 | 0.415 | 0.400 | **0.918** |
| n2-cal (this attempt) | 2,576 | 0.279 | 0.250 | **0.606** |

### Why it failed, and the deviation

The generator drew each node's query-token count from the **per-pair** coverage distribution measured
on control. That mapping is wrong: in a 27-node corpus each node competes for many queries, so a
handful of nodes produces the 0.144 share; in a 10,000-node pool the top-100 is selected *by* the
match, so only the highest-coverage nodes survive selection regardless of their base rate.

**Deviation, recorded:** the pre-registration said a failed Q2 means the corpus is rejected outright.
I did not stop there — I probed an explicit token-count mix to see whether the base rate could
compensate, and report every probe:

| mix (0 / 1 / 2+ query tokens) | competing share ≥ 0.25 |
|---|---|
| 0.55 / 0.43 / 0.02 | **0.537** |
| 0.70 / 0.28 / 0.02 | **0.516** |
| 0.80 / 0.19 / 0.01 | **0.497** |

Even at 80% zero-token nodes the competing share stays near 0.50: with ~2,000 nodes carrying two
query tokens, those nodes fill the top-100 on their own. The base rate cannot fix a selection effect
of this size, so no token-count mix reaches 0.144 — the generator's *shape* is wrong, not its
parameters. This is why the probes are recorded as a failure mechanism rather than a tuning exercise,
and why the run above is still the pre-registered one.

### What this settles, and what it does not

1. **Still unmeasured**: whether N2 represents the noise a real graph produces. The question was right
   to ask; this attempt to answer it failed its own calibration check.
2. **The gap is real but its size is not calibrated**: control's competing distractors reach a quarter
   of the query 14.4% of the time, N2's 91.8% of the time. That 6.4× is measured; whether it is
   *inflated* relative to a real 10k graph needs a corpus built from realistic note text, not token
   soup.
3. **The next design must sample real notes, not tokens**: draw distractor text from actual notes
   (the team's graph has 410) or from a template that preserves note-like word distributions, then
   solve the induced share by construction — and check it with the same Q2 rule before any Q1 number
   is reported. That design is pre-registered next, not now.
4. N2 remains the hardest corpus, the 0.70 target remains **unmet**, and nothing in `src/amg/` moved.

### Predictions scored

| # | prediction | result |
|---|---|---|
| 1 | N2-cal r@5 ≥ 0.75 | **wrong** — 0.654 |
| 2 | N2-cal share ≥ 0.25 lands in 0.10–0.30 | **wrong** — 0.606 |
| 3 | n1 and n3 unchanged | **correct** — both 0.865, their generators untouched |
| 4 | at least one N2-failing query still fails on N2-cal | not evaluated: the corpus was rejected before per-query analysis would be meaningful |
