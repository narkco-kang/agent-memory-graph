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

## Candidates measured (zero-dependency only)

`run_eval.py bm25 hashed-vec` — both are implemented in `candidates.py`, both
pass the same hard filters (superseded / not-yet-valid) as the shipped scorer.

| retriever | overall r@5 | keyword r@5 | paraphrase r@5 | paraphrase r@1 | verdict |
|---|---|---|---|---|---|
| lexical baseline (shipped) | **0.865** | 0.938 | **0.750** | 0.400 | — |
| `bm25` (tokens + IDF, per-field) | 0.731 (−0.134) | 0.906 (−0.032) | 0.450 (−0.300) | 0.350 | **not adopted** |
| `hashed-vec` (word + char-trigram, 512 dims hashed, IDF cosine) | 0.808 (−0.057) | 0.969 (+0.031) | 0.550 (−0.200) | 0.400 | **not adopted** |

Failed checks, per the pre-registered criteria:

- `bm25`: C1 paraphrase-H1 −0.400 (needs +0.20), C1 paraphrase-H2 −0.200,
  **and** C2 keyword-H2 −0.062 (limit 0.05).
- `hashed-vec`: C1 paraphrase-H1 −0.400, C1 paraphrase-H2 +0.000.

### What the numbers actually say

1. **The shipped scorer wins, and that is not a compliment to it.** `bm25` is the
   textbook upgrade and loses 13 points overall: the baseline matches *substrings*
   with no minimum token length, so "searched" matches "search" and "encoder"
   matches "encode" for free — a crude stemmer nobody designed. Removing that
   accident costs recall, which is a real (if unglamorous) property worth keeping.
2. **Keyword queries are not the problem.** `hashed-vec` even improves them
   (+0.031) — character trigrams tolerate morphology. The whole gap is paraphrase.
3. **No dependency-free representation closes the paraphrase gap.** Both
   candidates miss the same three queries, and each of those shares *zero* content
   tokens with its gold node: "do I need to pip install anything" → a node that
   says "standard library". Trigrams cannot invent that link, only meaning can.
4. **Part of the baseline's 0.750 paraphrase recall is accidental** (see the
   worked `q06` example in `PREREGISTRATION.md`, amendment v3): a query
   containing "I" matches almost every node, so the hit arrives by ordering luck.
   Paraphrase `recall@1` (0.400) is the honest number, which is why amendment v3
   adds a recall@1 requirement and a precision guard before anything else is
   measured.

## The semantic arm was not measurable here

The obvious next candidate is a real embedding model, and filing a number for it
would have been easy to fake. It was not measurable in this environment:

- GLM `embedding-3` and `embedding-2` both return HTTP 429
  `{"code":"1113","message":"余额不足或无可用资源包"}` with the local key — the
  subscription does not cover embeddings;
- no local sentence-transformer model is installed, and shipping one would add a
  dependency plus a download (C3).

So the question "would a semantic retriever clear the bar?" is **open**, with a
concrete blocker rather than a guess. What we do know: the three paraphrase
queries that both candidates miss share no content tokens with their gold nodes,
so the gap is not lexical. That is evidence for the direction, not a measurement
of it.

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
- [x] Two zero-dependency candidates measured: **both not adopted** (numbers above).
- [x] Amendment v3: precision guard + paraphrase `recall@1` requirement, because
  the 0.750 paraphrase `recall@5` is partly accidental inclusion.
- [ ] Semantic candidate measured — **blocked**: no embedding resource
  (`1113`), no local model. Nothing shipped in its place.
- [ ] Decision on issue #2: stays open with this blocker written down; the README
  keeps saying "lexical only".

## Reproduce

```bash
PYTHONPATH=src python3 experiments/retrieval_eval/run_eval.py              # baseline
PYTHONPATH=src python3 experiments/retrieval_eval/run_eval.py bm25 hashed-vec   # candidates + verdicts
```
