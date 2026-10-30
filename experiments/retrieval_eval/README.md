# Retrieval evaluation (pre-registered)

This directory exists because of one rule: **the metric comes before the
feature**. A semantic retriever is not "better" because it sounds better; it is
better if it moves `recall@5` on a frozen query set without losing exact-match
queries — or it is not adopted.

- `PREREGISTRATION.md` — the criterion, written before any candidate existed,
  including the amendment that fixed a split-design flaw the baseline exposed.
- `corpus.json` — 27 nodes in `amg/v1` node shape, English, no evidence objects.
- `queries.json` — 26 queries with author-assigned gold ids (A/B authored split
  kept for the record; scoring uses stratified halves instead).
- `run_eval.py` — the harness. Buckets by **measured** token overlap, not intent.
- `result.json` — output of the last run, with digests of both input files.

## Reproduce

```bash
PYTHONPATH=src python3 experiments/retrieval_eval/run_eval.py
```

## Baseline (lexical, `amg.retrieval.search`)

Measured on commit `068cfbd`, corpus `a183dc443ee4`, queries `3dced7bb2fcf`:

| group | n | recall@1 | recall@5 | recall@10 | MRR@10 |
|---|---|---|---|---|---|
| overall | 26 | 0.654 | **0.865** | 0.904 | 0.744 |
| keyword (overlap ≥ 0.34) | 16 | 0.812 | 0.938 | 1.000 | 0.898 |
| paraphrase (overlap < 0.34) | 10 | 0.400 | **0.750** | 0.750 | 0.498 |
| paraphrase-H1 | 5 | 0.400 | 0.700 | 0.700 | 0.480 |
| paraphrase-H2 | 5 | 0.400 | 0.800 | 0.800 | 0.517 |
| keyword-H1 | 8 | 0.812 | 0.875 | 1.000 | 0.889 |
| keyword-H2 | 8 | 0.812 | 1.000 | 1.000 | 0.906 |

What this says, plainly:

1. **Keyword queries are nearly solved** (0.938 recall@5). Any new retriever has
   little room and a real risk of regression.
2. **Paraphrase recall is where the gap is** — 0.750, and every paraphrase
   failure is a vocabulary mismatch, not a ranking bug: e.g. "do I need to pip
   install anything" returns nothing relevant because the node says "standard
   library".
3. `recall@1` on paraphrase is 0.40: even when the right node is in the top 5, it
   is often not first. A vector retriever would have to fix ordering, not just
   recall.

## The bar a candidate must clear

C1 `paraphrase recall@5` ≥ **+0.20 absolute in both halves** (baseline 0.700 /
0.800 → required 0.900 / 1.000). With five queries per half this is literally
"one more paraphrase hit per half", and is a bar for *continuing*, not a claim of
victory.

C2 `keyword recall@5` may drop by at most **0.05 absolute** in either half — this
is what rules out "better semantics, worse exact match" replacements that would
annoy the users who actually type identifiers.

C3 cost must be declared: a model download may only ship as an optional extra,
off by default.

If a candidate cannot clear this, the honest outcome is **not adopted**, and the
result gets written down here rather than the experiment being quietly dropped.

## Status

- [x] Pre-registration, corpus, queries, harness, baseline numbers.
- [ ] Candidate retriever measured against the bar (next).
- [ ] Decision recorded: adopted / not adopted, with the numbers that decided it.
