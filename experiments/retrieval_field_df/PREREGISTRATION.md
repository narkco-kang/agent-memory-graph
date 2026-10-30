# Pre-registration: field-specific document frequency (BM25F-style), v0.19.0

Written on `v0.18.0` (`1ddcdec`), **before** `src/amg/retrieval.py` is touched, taking
up the third direction in `docs/memory-arch/RETRIEVAL-NEXT-ATTACK.md` §3 (Glm仔's
brief) rather than its §1/§2 alternatives (id/type priors, phrase adjacency). The brief
supplies the attack surface; the criteria below are mine, because the brief's draft
mixed up buckets (`kw` vs `overall`) and proposed an impossible N2 bar.

## The change (exactly one)

v0.18.0 counts document frequency per **term**, pooled across fields (E2 in the
brief). A term common in `note` therefore lowers the IDF of the same term matched in
a rare `id`. The change: count per **(field, term)** and keep one IDF per pair.

```
N_f        = visible nodes whose field f is non-empty
df(f, t)   = visible nodes where term t matches field f
idf(f, t)  = ln(1 + N_f / (1 + df(f, t)))
score(n)   = Σ (field, t) matched   WEIGHTS[field] × idf(field, t)
```

- `WEIGHTS`, matchers, hard filters, anchor rule, ordering and the output shape are
  **unchanged**. `N_f` uses only the field's own population, so a field that is often
  empty (`source`, `owner`) cannot look artificially rare.
- Hit sets are unchanged by construction: IDF stays strictly positive
  (`ln(1 + N/(1+df)) > 0`), so `if score <= 0: continue` never drops a match that the
  v0.18.0 scorer would have kept. Only the ranking moves.
- No caching, no per-field weights, no priors, no position tracking: one variable.

## Baseline

`baseline.py` is the **frozen v0.18.0 scorer**, run in the same process on the same
corpora, so every comparison is baseline-vs-candidate rather than against a remembered
number. The four corpora come from `experiments/retrieval_idf/run_eval.py` (control 27,
N1 unrelated 10k, N2 query-vocabulary 10k, N3 frequent-vocabulary 10k) — identical
builders, same seeds, so N1–N3 stay comparable across the two rounds.

Metrics come from `experiments/retrieval_eval/run_eval.py`, as in both earlier rounds.

## Corpus fact recorded before the run

Over the frozen 26 queries, the gold node matches in `id` for **14**, in `label` for
**18**, in `note` for **17**; five queries match only in `note` (q05, q18, q24, q26 and
partly q19), one only in `label` (q20), three not at all (q06, q08, q10 — paraphrase
gaps, unchanged by any weighting). This is the only corpus statistic gathered before
the run; no candidate score was computed.

## Predictions (recorded now; being wrong is data)

| quantity | predicted | basis |
|---|---|---|
| frozen overall r@5 | **0.865–0.923** (up or equal) | 14 queries have an id hit; id's `N_f/df` ratio is the sharpest rarity signal in the corpus |
| frozen overall r@1 | 0.731–0.808 | same, applied to one slot |
| note-only queries (q05, q18, q24, q26) | **may lose rank** — this is the expected cost | a `note` hit now gets `note`'s own (lower) IDF instead of the pooled one, so the v0.18.0 gains on these can shrink |
| N3 r@5 | ≥ 0.865 (same as v0.18.0) | frequent-word distractors match in `label`/`note`, so per-field rarity separates them at least as well |
| N2 r@5 | 0.538–0.615, still **< 0.70** | N2 is uniform within each field too, so field-specific df has no more signal than term df; the target stays out of reach for this family |
| p95 latency at 10k | ≤ 1.25× v0.18.0 | df is now a dict keyed by (field, term): a few thousand dict updates per query, no second scan |

## Criteria (fixed now)

| # | Criterion | Verdict rule |
|---|---|---|
| C1 | Frozen recall does not regress | pass only if `r@5 ≥ 0.865`, `r@1 ≥ 0.731`, `MRR@10 ≥ 0.821` (v0.18.0 values) |
| C2 | N1 does not regress | all four metrics ≥ v0.18.0's N1 |
| C3 | N3 does not regress | `r@5 ≥ 0.865` |
| C4 | N2 does not regress | `r@5 ≥ 0.538`; the `≥ 0.70` target is reported, not a gate |
| C5 | Latency stays in budget | 10k p95 ≤ 1.25 × v0.18.0 p95, measured in the same process |
| C6 | Hit sets are unchanged | for every frozen query, the set of matched node ids is identical to v0.18.0's (only order may change) |
| C7 | No tuning in the round | if the formula or `WEIGHTS` changes after the first measurement, the round is void and re-registered |

**Ship rule (decided now):** ship only if C1–C5 and C6 pass. A frozen `r@5` drop below
0.855 (>0.01) kills the direction; it is not revived by tuning. If it ships, the note-only
regressions are published, not hidden.

## What this will not establish

- Nothing about semantic recall; the three unmatched paraphrase queries stay unmatched.
- Nothing about N2 beyond "still not fixed": uniform noise is invariant to document
  frequency at every granularity, which is now measured twice.
- Nothing about a real 10k graph, other languages, or score thresholds across graphs —
  absolute scores still depend on corpus size (`issue.mem-arch-idf-live-df-drift`).
- No claim about id/type priors or phrase adjacency; they stay untested candidates.

## Reproduce

```bash
PYTHONPATH=src python3 experiments/retrieval_field_df/run_eval.py            # table
PYTHONPATH=src python3 experiments/retrieval_field_df/run_eval.py --json     # result.json
```
