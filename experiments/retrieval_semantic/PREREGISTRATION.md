# Pre-registration: does a semantic arm close N2?

Written **before** any embedding was computed for this corpora set; nothing here is edited
afterwards. An `## Outcome` section is appended instead (DECISIONS #25/#26/#28/#29/#47/#49).

## Why this experiment

DECISIONS **#49** closed the lexical rerank family: three non-`df` signals all lost N2 recall, and
on the eleven queries that need repair every one of them was at or below chance. It recorded two
open limits: the candidate ceiling (gold inside the top 100) is **0.846**, so the 0.70 target is not
impossible in principle; and **4 of 26** queries have gold beyond the top 100, so a semantic arm
must be judged on candidate generation as well as on reordering.

An embedding round *did* run earlier — paraphrase recall@5 0.750 → 0.950 — and was rejected for
shipping, because a 274 MB model and a daemon are not part of a zero-dependency CLI's default path
(DECISIONS on optional-only embeddings). **What was never measured is N2.** That is the gap here:
if embeddings close N2, the roadmap entry changes from "no signal" to "a signal that the default
build cannot afford"; if they do not, the 0.70 target itself has to be re-examined.

## Backend (fixed here, before the run)

`sentence-transformers` is **not** used. The backend is the already-installed local daemon:

| fact | value |
|---|---|
| model | `nomic-embed-text:latest` (ollama) |
| digest | `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f` |
| parameters / quantisation | 137M / F16 |
| embedding length | 768 |
| transport | `POST http://127.0.0.1:11434/api/embed`, local only |

This is an **experiment backend**: nothing in this directory adds a dependency to the package, and
`src/amg/` is not modified by this round. The digest is recorded so a later reader can tell whether
a different model was behind the numbers.

Embedded text is the **same** `node_text` the lexical scorer uses (`id`, `label`, `note`, `source`,
`owner`, `type`), and the queries are embedded verbatim, so the only difference from the shipped
scorer is the representation, not the input.

## The three arms

| arm | what it does | what it answers |
|---|---|---|
| **A rerank** | cosine over the shipped top-100; order by reciprocal-rank fusion with the shipped order (`k = 60`) | can semantics fix *ordering*? |
| **B semantic-only** | embed every node in the corpus, take the cosine top-100 | can semantics fix *candidate generation* (the 4/26)? |
| **C hybrid** | union of the shipped top-100 and the semantic top-100, fused by RRF (`k = 60`) | the deployable shape if A or B alone is not enough |

RRF is used rather than a weighted score blend because the two scores are on incomparable scales and
any blend weight would be an extra tuned parameter on the target corpus. `k = 60` is the literature
default and is fixed now.

## Corpora and protocol

The same four corpora and the same 26 frozen queries as the lexical rounds, rebuilt from
`experiments/retrieval_10k/run_eval.py` and `experiments/retrieval_idf/run_eval.py`: control 27,
n1 10,000, n2 10,000 (query-vocabulary noise, the target), n3 10,000 (frequent-vocabulary noise).
Embeddings are cached by text SHA-256 so a rerun does not re-embed, and the cache is keyed by the
model digest above.

Shipped baseline (v0.19.0+ IDF): control 0.865, n1 0.865, **n2 0.538**, n3 0.865.

## Criteria (fixed before the run)

* **C1 no frozen regression**: control `recall@5 ≥ 0.855`.
* **C2 the target moves**: N2 `recall@5 ≥ 0.588` (+0.05). The published 0.70 target is reported
  separately and is not a ship gate.
* **C3 unrelated noise unchanged**: n1 `recall@5 ≥ 0.855`.
* **C4 frequent noise not harmed**: n3 `recall@5 ≥ 0.845`.
* **Arm selection**: each arm is reported on all four corpora; an arm "passes" only if C1–C4 hold
  together. No weight or threshold is tuned on n2 after the fact.

### Diagnostics (reported, not gates)

* **D1 candidate ceiling per arm**: share of queries whose gold is inside that arm's top-100.
  Arm B is the only one that can raise it; if it does not, candidate generation is not the lever.
* **D2 per-bucket recall**: paraphrase vs keyword, because the earlier embedding round's +0.20 came
  from paraphrase queries and N2's damage is not confined to them.
* **D3 latency**: p50 / max per query, measured as the fused retrieval path would pay it.

### Pre-registered predictions (before any number is seen)

1. **Arm A (rerank) fails C2**: reordering cannot repair queries whose gold is not in the candidate
   set, and on the other eleven the lexical evidence already points the wrong way.
2. **Arm B raises the ceiling from 0.846 to ≈1.0** — the gold is semantically about the query, so a
   full-corpus semantic search should at least *find* it.
3. **Arm C passes C2** (N2 ≥ 0.588) but misses 0.70.
4. **No arm is free**: at least one of C1/C3/C4 fails for each arm, because the distractors are
   sentences about the same vocabulary — exactly what embeddings treat as similar.

If prediction 3 holds and only the non-target gates fail, the honest conclusion is that the 0.70
target needs *both* a semantic candidate generator and a precision guard, and the roadmap should say
so; it would still not ship, because embeddings cannot enter the default zero-dependency path.

## Outcome

Run on 2026-10-31: 29,973 texts embedded through the local daemon (≈105 s per 10k corpus, cached),
then `diagnose_moved_queries.py`. Machine-readable in `result.json` and
`diagnostic_moved_queries.json`.

| corpus | shipped | A rerank | B semantic | C hybrid | ceiling (shipped / B / C) |
|---|---|---|---|---|---|
| control (27) | 0.865 | 0.865 | **0.981** | 0.923 | 0.885 / 1.000 / 1.000 |
| n1 (10k unrelated) | 0.865 | 0.865 | **0.962** | 0.904 | 0.885 / 1.000 / 1.000 |
| **n2 (10k query-vocabulary)** | **0.538** | **0.577** | **0.577** | **0.577** | 0.846 / 0.846 / 0.885 |
| n3 (10k frequent) | 0.865 | 0.865 | 0.904 | **0.942** | 0.885 / 1.000 / 1.000 |

N2 detail: recall@1 0.481 → 0.500, recall@5 0.538 → 0.577, recall@10 0.577 → 0.615, MRR@10
0.543 → 0.580 (A/C) / **0.619** (B).

**Verdict: no arm ships.** All three pass C1/C3/C4 and all three miss C2 by 0.011 — +0.039 against
the required +0.05 — and the 0.70 target is not approached. The result is positive and still below
the bar: this is a miss, not a rejection of the measurement.

### Predictions scored

| # | prediction | result |
|---|---|---|
| 1 | arm A fails C2 | **correct** |
| 2 | arm B raises the N2 ceiling from 0.846 to ≈1.0 | **wrong** — B's N2 ceiling is **0.846**, exactly the shipped one |
| 3 | arm C passes C2 (≥ 0.588) but misses 0.70 | **wrong** — C is 0.577, so it misses C2 as well |
| 4 | no arm is free: C1/C3/C4 fails for each | **wrong** — all three pass all three regression gates |

### Why the ceiling prediction is the informative miss

Prediction 2 assumed semantic search would at least *find* the four gold nodes that lexical search
misses. It does not: B's N2 candidate ceiling equals the shipped 0.846, so the 4/26 that #49 left
open stay open under embeddings too. The distractors are built by placing the query's own words in
`label` and `note`, which makes them near-duplicates of the query in any bag-of-vectors sense —
cosine is no more adversarial to that construction than `df` was. On the two corpora where the noise
is *not* built from the query (n1, n3) the same model lifts recall to 0.962 / 0.942, and on the real
corpus to 0.981, which is what makes the N2 number a statement about the noise model rather than
about the model.

### The per-query churn the aggregate hides

The three arms share recall@5 = 0.577 on N2 by coincidence, not by behaving alike:

* fixed: `q05` 9 → 2 (A/C), `q26` 17 → 1 (all), `q16` 46 → 1 (B), `q24` 83 → 1 (B);
* broken: `q04` 2 → 23 (A) / beyond 100 (B) / 24 (C), `q14` 1 → 5 (A/C) / 27 (B).

Six queries cross the top-5 boundary in opposite directions. `q04` is the same query #48 used as its
example — a true answer matching one content word, now pushed out by an embedding that finds the
query-word soup closer. Any future arm must report this table, not only the mean.

### What this settles

1. **The similarity family is closed for N2** — lexical in #49, semantic here. Both arms land at
   0.577 against a 0.588 criterion and a 0.70 target, and neither raises the candidate ceiling.
2. **The measurement is not the problem.** On control/n1/n3 the same model lifts recall by 0.04–0.12,
   so the backend, the cache and the fusion are working; the N2 number is about N2.
3. **A benchmark question is now legitimate but has to be answered as its own decision**, not by
   quietly retuning the target: N2's distractors are built from the queries' own vocabulary, which
   makes it a near-duplicate-discrimination task. Whether that is the noise a long-lived memory
   graph actually faces has to be measured, not asserted (see DECISIONS #50's open issue).
4. Embeddings remain **optional-only**: nothing in `src/amg/` changed, and the 274 MB model plus a
   daemon are still outside the zero-dependency default path.
