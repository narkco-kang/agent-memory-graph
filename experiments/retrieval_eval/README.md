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

### After the v0.14.0 matcher change

`docs/DECISIONS.md` #25 changed ASCII matching from substring to word-boundary +
inflection (and made identifier queries lookups). Re-run on the same frozen corpus:

| group | n | recall@1 | recall@5 | recall@10 | MRR@10 |
|---|---|---|---|---|---|
| overall | 26 | 0.654 | **0.808** | 0.865 | **0.763** |
| keyword | 16 | 0.875 | **0.969** | 0.969 | 0.969 |
| paraphrase | 10 | 0.300 | 0.550 | 0.700 | 0.433 |

Keyword improved and MRR improved; overall recall@5 fell because two queries had been
reached only through substrings **inside other words** (`i` in `high-risk`, `one` in
`gone`) — the per-query analysis is in `../retrieval_precision/PREREGISTRATION.md`. Both
number sets are kept here on purpose: a baseline that gets overwritten is a baseline
nobody can audit.
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

## Candidates measured

`run_eval.py bm25 hashed-vec local-embed` — all implement the same hard filters
(superseded / not-yet-valid) as the shipped scorer.

| retriever | overall r@5 | keyword r@5 | paraphrase r@5 | paraphrase r@1 | verdict |
|---|---|---|---|---|---|
| lexical baseline (shipped) | 0.865 | 0.938 | 0.750 | 0.400 | — |
| `bm25` (tokens + IDF, per-field) | 0.731 (−0.134) | 0.906 (−0.032) | 0.450 (−0.300) | 0.350 | **not adopted** |
| `hashed-vec` (word + char-trigram, 512 dims) | 0.808 (−0.057) | 0.969 (+0.031) | 0.550 (−0.200) | 0.400 | **not adopted** |
| `local-embed` (`nomic-embed-text`, 768 dims, local) | **0.962 (+0.097)** | 0.969 (+0.031) | **0.950 (+0.200)** | 0.625 | **not adopted** (C1-H2, C3) |

Failed checks, per the pre-registered criteria:

- `bm25`: C1 paraphrase-H1 −0.400, C1 paraphrase-H2 −0.200, **and** C2 keyword-H2
  −0.062 (limit 0.05).
- `hashed-vec`: C1 paraphrase-H1 −0.400, C1 paraphrase-H2 +0.000.
- `local-embed`: C1 paraphrase-H2 **+0.100** (needs +0.20) and **C3** — it needs a
  local ollama daemon plus a 274 MB model file, so it may not be the default path
  of a zero-dependency library. H1 alone cleared the bar (+0.300).

### What the numbers actually say

1. **The shipped scorer beats every dependency-free upgrade, for an unflattering
   reason:** it matches substrings with no minimum token length, so `"searched"`
   matches `search` and `"encoder"` matches `encode` — a crude stemmer nobody
   designed. `bm25` replaces that with exact tokens and loses 13 points overall.
2. **Keyword queries are not the problem** (`hashed-vec` already improves them).
   The whole gap is paraphrase, and it is semantic: every query the lexical
   candidates miss shares **zero** content tokens with its gold node.
3. **A real embedding model closes most of that gap**: +0.097 overall, +0.200
   paraphrase, paraphrase `recall@1` 0.400 → 0.625, with no keyword regression.
   It still does not clear the pre-registered bar — one stratified half gains
   +0.300, the other only +0.100 — and it cannot be the default (C3). Being
   measurable and being adoptable are different questions, and both answers are
   "no" for the default path.
4. **Part of the baseline's 0.750 paraphrase recall is accidental** (worked
   example in `PREREGISTRATION.md`, amendment v3): a query containing "I" matches
   nearly every node. Paraphrase `recall@1` (0.400) is the honest figure, which is
   why amendment v3 adds a recall@1 requirement and a precision guard before the
   next candidate is measured.

### The semantic arm, measured locally (and an earlier claim corrected)

An earlier run of this experiment said the semantic arm was "not measurable here"
because the hosted embedding API answered `429 {"code":"1113"}` and no
sentence-transformer was installed. **That was wrong**: `ollama` was already
running on this machine with `nomic-embed-text` (768 dims, 137M params) pulled —
I had checked one tool and concluded about the environment. The measurement above
is that model, served over `http://127.0.0.1:11434/api/embed`, with vectors cached
by exact text so a re-run is deterministic.

Reproduce: `PYTHONPATH=src python3 experiments/retrieval_eval/run_eval.py local-embed`
(requires `ollama` with `nomic-embed-text`; the vector cache is gitignored, so it
rebuilds on first run). No Python package was added to the project for this, and
nothing was added to the shipped library.

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
- [x] Semantic candidate measured locally (`nomic-embed-text`): +0.200 paraphrase,
  still below the bar in one half, and C3 keeps it out of the default path.
- [x] Connection to issue #2: **not adopted for the default path**; the measured
  numbers are the deliverable, not a feature.
- [ ] Decision on issue #2: stays open with this blocker written down; the README
  keeps saying "lexical only".

## Reproduce

```bash
PYTHONPATH=src python3 experiments/retrieval_eval/run_eval.py              # baseline
PYTHONPATH=src python3 experiments/retrieval_eval/run_eval.py bm25 hashed-vec   # candidates + verdicts
```
