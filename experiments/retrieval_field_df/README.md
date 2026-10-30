# Field-specific IDF — measured outcome (rejected, no release)

Pre-registration written before the code changed:
[`PREREGISTRATION.md`](PREREGISTRATION.md). This round tested the third direction in
`docs/memory-arch/RETRIEVAL-NEXT-ATTACK.md` §3 (Glm仔's brief): count document frequency
per **(field, term)** instead of per term, so a word that fills `note` cannot make the
same word look common in `id`.

**Verdict: rejected.** It lifted the query-vocabulary noise model by +0.058 recall@5, at
the price of one frozen query — and the pre-registered bar said a frozen `r@5` drop
larger than 0.01 kills the direction. No release was cut; `src/amg/retrieval.py` was
reverted to v0.18.0.

## The change that was measured (and is not in the product)

```
N_f        = visible nodes whose field f is non-empty
df(f, t)   = visible nodes where term t matches field f
idf(f, t)  = ln(1 + N_f / (1 + df(f, t)))
score(n)   = Σ (field, t) matched   WEIGHTS[field] × idf(field, t)
```

Nothing else changed; `baseline.py` is the frozen v0.18.0 scorer and both run in the
same process on the four corpora from `experiments/retrieval_idf/`.

## Measured

| corpus | scorer | r@1 | r@5 | r@10 | MRR@10 | p50 | p95 |
|---|---|---|---|---|---|---|---|
| control 27 | v0.18.0 | 0.731 | **0.865** | 0.865 | 0.821 | 0.3 ms | 0.6 ms |
| control 27 | field-df | 0.731 | **0.827** | 0.865 | 0.814 | 0.3 ms | 0.6 ms |
| N1 10k | v0.18.0 | 0.731 | **0.865** | 0.865 | 0.815 | 78.3 ms | 152.9 ms |
| N1 10k | field-df | 0.731 | **0.827** | 0.865 | 0.813 | 79.2 ms | 150.4 ms |
| N2 10k | v0.18.0 | 0.481 | 0.538 | 0.577 | 0.536 | 97.6 ms | 186.4 ms |
| N2 10k | field-df | **0.519** | **0.596** | **0.635** | **0.575** | 100.4 ms | 184.8 ms |
| N3 10k | v0.18.0 | 0.731 | **0.865** | 0.865 | 0.821 | 89.7 ms | 185.1 ms |
| N3 10k | field-df | 0.731 | **0.865** | 0.865 | 0.817 | 90.6 ms | 186.6 ms |

Only **one** frozen query moved: q18 `3 → 6` (note-only match — its gold's only match is
in `note`, whose own IDF is lower than the pooled one). That single rank costs 0.038 of
overall recall@5, because the frozen set has 26 queries and multi-gold averaging.

## Criteria

| # | Criterion | Result |
|---|---|---|
| C1 | frozen `r@5 ≥ 0.865`, `r@1 ≥ 0.731`, `MRR ≥ 0.821` | **FAIL** (0.827 / 0.731 / 0.814) |
| C2 | N1 no regression | **FAIL** (r@5 0.827) |
| C3 | N3 `r@5 ≥ 0.865` | pass (0.865) |
| C4 | N2 `r@5 ≥ 0.538` | pass (0.596) |
| C5 | 10k p95 ≤ 1.25× | pass (0.991×) |
| C6 | hit sets unchanged | **FAIL as written** — see below |
| C7 | no tuning in the round | pass (no formula or weight edit after the first run) |

Ship rule: C1–C5 and C6 pass ⇒ ship. C1 and C2 failed, so no release.

**C6 was my pre-registration error, recorded rather than reinterpreted.** I wrote "the
set of matched node ids is identical", but the harness compares the **top-100** list at
10k nodes, and any reordering moves membership at that cut. The changes are all on N2
(19 queries); control, N1 and N3 have **zero** changes, and no match is dropped —
IDF stays strictly positive, so the hit set is unchanged by construction. The criterion
should have said "no match dropped, not top-k membership"; because it was written
before the run, the verdict stands as FAIL and the correction is here instead of in the
pre-registration.

## Predictions

| prediction | measured | verdict |
|---|---|---|
| frozen r@5 0.865–0.923 (up or equal) | 0.827 | **wrong** — I expected id hits to win, missed that the only move is a note-only query losing rank |
| note-only queries may lose rank (named cost) | q18 3 → 6 | right |
| N3 ≥ 0.865 | 0.865 | right |
| N2 0.538–0.615, still < 0.70 | 0.596 | right |
| p95 ≤ 1.25× | 0.991× | right |

## What this establishes

- The field-specific-DF family is **not free**: the gain on uniform noise is real
  (+0.058 r@5), but it is bought from queries whose only literal evidence is a long
  `note`. Under this project's pre-registered bar, that is a rejection.
- The `N2 ≥ 0.70` target is still unreachable: 0.596 is the best result so far, and the
  three unmatched paraphrase queries cap the theoretical maximum at 23/26 ≈ 0.885.
- A real decision is now open: **is `frozen −0.038` an acceptable price for `N2 +0.058`?**
  That is a trade-off policy, not a measurement; it must be pre-registered as such (with
  both numbers fixed) before a future round may run it — granting it after seeing the
  numbers would be tuning.

## What this does not establish

- Nothing about id/type priors or phrase adjacency; both remain untested (the brief's
  §1/§2 attacks still apply).
- Nothing about a real graph; all noise is synthetic and deterministic.
- Nothing about score comparability across graph sizes (`issue.mem-arch-idf-live-df-drift`
  is untouched by this round).

## Reproduce

```bash
PYTHONPATH=src python3 experiments/retrieval_field_df/run_eval.py            # table + verdicts
PYTHONPATH=src python3 experiments/retrieval_field_df/run_eval.py --json     # result.json
```
