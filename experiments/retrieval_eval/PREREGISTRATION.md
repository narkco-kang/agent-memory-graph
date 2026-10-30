# Pre-registration: does semantic retrieval beat the lexical scorer?

Written **before** running the evaluation and before writing any candidate
retriever. The point of writing it first is that the acceptance threshold cannot
be moved to fit whatever number comes out.

## Question

The shipped retriever (`src/amg/retrieval.py`) matches literal substrings with
field weights. Users paraphrase. Does a semantic (vector) retriever improve
recall enough to be worth a dependency and a model download — or is the honest
answer "not adopted"?

## Corpus and queries

- `corpus.json` — 28 nodes, amg/v1 node shape, English, no evidence objects (so
  the two-key ranking is not exercised; this measures scoring only).
- `queries.json` — 26 queries with author-assigned gold ids, split A/B (13 each).

**Buckets are measured, not intended.** For each query the harness computes the
token overlap between the query and its gold nodes:

```
overlap = |tokens(query) ∩ tokens(gold node text)| / |tokens(query)|
token   = [a-z0-9]+ with length >= 3, lowercased
```

`overlap < 0.34` → **paraphrase** bucket (the vocabulary does not match, so
substring scoring has little to grip). Otherwise → **keyword** bucket. The
declared intent per query is not consulted.

## Metrics

- `recall@1`, `recall@5`, `recall@10` — fraction of gold ids present in the top
  k, averaged over queries.
- `MRR@10` — mean reciprocal rank of the first gold id (0 when absent).
- Reported overall, per bucket, and **per split (A / B)** separately.

## Acceptance criteria (all three must hold)

**C1 — paraphrase recall@5 improves by at least +0.20 absolute** over the lexical
baseline, **independently in split A and split B**. Both halves, not the pooled
average: with 13 queries per split, one lucky query is 7.7pp, so a pooled-only
win is noise.

**C2 — keyword recall@5 does not drop by more than 0.05 absolute** in either
split. A retriever that gains paraphrase recall by losing exact-match queries is
not an improvement.

**C3 — cost is stated, not hidden.** If the candidate needs a model file or a
third-party package, it may only ship as an **optional extra**, must be disabled
by default, and the docs must say so. A dependency-free candidate that loses to
the baseline is still rejected.

If any criterion fails, the outcome is **not adopted**, and that is written into
`result.json`, `README.md` and the changelog — the same way a passing result
would be. The feature is not "shipped with a caveat".

## Known weaknesses (declared before the numbers exist)

- **Author-labelled gold.** Same person wrote corpus, queries and (later) the
  candidate. No inter-annotator agreement. Mitigation is that both retrievers see
  the identical frozen corpus and queries, so the *comparison* is fair even if
  the absolute numbers are not generalisable.
- **Small n.** 26 queries; a single query is 3.8pp. C1's two-split requirement is
  the only defence against reading noise as signal.
- **Synthetic corpus.** Real graphs are noisier and much larger; nothing here says
  how this scales. Scale is measured separately (`docs/BENCHMARKS.md`).
- **No exclusion of the query's own vocabulary.** A retriever that has seen these
  words during index building is not cheating (that is what an index is), but the
  corpus is static, so nothing tests "new document, new vocabulary".

## Freeze

`corpus.json` and `queries.json` are frozen at the commit that adds this file;
`run_eval.py` records both file digests in `result.json`. Editing a query after a
run invalidates the comparison and must be noted in the changelog.

---

## Amendment v2 (written before any candidate retriever existed)

The first version of C1 was **untestable as written**, and the baseline run
proved it: the A/B split had been assigned by the author before bucketing, so
split A ended up with 1 paraphrase query and split B with 9. "Improvement in both
splits" would have been a requirement on a single query.

Fix: halves are now **stratified mechanically** by bucket in `run_eval.py` — take
each bucket's queries sorted by id, deal them alternately into `H1` / `H2`. No
author discretion, and it cannot be tuned after seeing scores because it is pure
arithmetic over the frozen query file.

C1 v2: paraphrase `recall@5` improves by **≥ +0.20 absolute in both H1 and H2**.

Arithmetic disclosure: each half holds 5 paraphrase queries, so +0.20 is exactly
**one query**. The criterion is therefore "one more paraphrase hit in each half",
not a statistically strong result. It is written this way because a stricter
threshold on n=5 would be theatre; the honest reading is that a candidate passing
it earns a *retry on a larger set*, not a claim of victory.

The baseline numbers (overall `recall@5` 0.865, paraphrase 0.75, keyword 0.938)
were seen before this amendment. They are recorded in `result.json`; the
criterion compares a future candidate against them, so knowing them does not move
the threshold — only the *split* rule was repaired, and it is mechanical.

---

## Amendment v3 (written after the first candidates were measured — reads as an increase in strictness, not a rescue)

Two zero-dependency candidates were measured (bm25, hashed-vec) and both failed
C1 by a wide margin, so nothing here is needed to reject them. The amendment
exists because inspecting *why* the baseline scores 0.750 paraphrase recall
exposed a hole in the metric that would let a worse retriever pass by luck.

**Finding.** The shipped scorer tokenises to `[a-z0-9_-]+` with no minimum length
and matches substrings. A query containing "I" or "a" therefore matches nearly
every node, and the ranking becomes a sort on how often that letter appears.
Worked example, query `q06` "who can see what I searched":

```
model.embedding      score=8  fields=[id, label, note]   <- ranked first
task.batch-write     score=7
decision.atomic-replace score=7
(task.read-audit, the gold node, arrives at rank 5 and scores as a hit)
```

So part of paraphrase `recall@5 = 0.750` is **accidental inclusion**, not recall.
Rank-1 is far less forgiving: paraphrase `recall@1` is 0.400 and MRR 0.498.

**Amendment (effective for the next candidate measured).**

- **C4 — precision@5.** A candidate may not exceed the baseline's precision@5 by
  more than 0.05 *below* it. "Return everything" cannot pass.
- **C1b — paraphrase recall@1 must also improve by ≥ +0.10 in both stratified
  halves**, in addition to recall@5. Rank-1 barely benefits from incidental
  inclusion, so this is the luck-resistant half of the same claim.
- **Query hygiene**: queries whose token set is ≥ 50% stopwords are flagged in
  `result.json` and reported separately; they remain in the score (removing them
  after seeing results would be tuning) but a candidate's win may not come from
  that subset alone — that must be stated explicitly in any adoption note.

Both candidates measured so far fail under v2 and would fail under v3 as well
(paraphrase `recall@1`: bm25 0.35, hashed-vec 0.40, baseline 0.40 — no gain). The
amendment is therefore a constraint on the *next* measurement, and it can only
make adoption harder.
