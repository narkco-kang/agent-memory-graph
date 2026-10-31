# Decision #50

[← decision log](../DECISIONS.md) · status: active

**The similarity family is closed for N2 — and the remaining question is the noise model, not the
model.** #49 closed lexical reranking and left one direction open: a semantic arm, which had never
been measured on N2 (the earlier embedding round measured paraphrase queries only). A pre-registered
round ran three arms — RRF rerank of the shipped top-100, pure full-corpus semantic retrieval, and
their union — against a local `nomic-embed-text` daemon, digest pinned in the pre-registration.

| corpus | shipped | rerank | semantic | hybrid |
|---|---|---|---|---|
| control (27) | 0.865 | 0.865 | **0.981** | 0.923 |
| n1 (10k unrelated) | 0.865 | 0.865 | **0.962** | 0.904 |
| **n2 (10k query-vocabulary)** | **0.538** | **0.577** | **0.577** | **0.577** |
| n3 (10k frequent) | 0.865 | 0.865 | 0.904 | **0.942** |

All three arms miss the pre-registered +0.05 by 0.011 (N2 +0.039) and none approaches 0.70, so
nothing ships; they do pass every regression gate (control, n1, n3 all hold or improve). The
*informative* miss is the candidate ceiling: semantics was predicted to at least *find* the four gold
nodes lexical search never reaches, and it does not — the semantic ceiling on N2 is 0.846, identical
to the shipped one. N2's distractors are built by placing the query's own words in `label` and
`note`, which makes them near-duplicates of the query in any bag-of-vectors sense; cosine is no more
adversarial to that construction than `df` was. On the corpora where noise is not built from the
query, the same model lifts recall to 0.962 and 0.942, so the N2 number is a statement about the
noise model rather than about embeddings.

The aggregate also hides churn worth recording: all three arms show 0.577 at recall@5 while fixing
`q05`/`q26`/`q16`/`q24` and breaking `q04` (2 → 23 or beyond 100) and `q14` (1 → 5 or 27). `q04` is
the same query #48 used as its example — a true answer matching one content word, now displaced by an
embedding that finds the query-word soup closer. Mean recall cannot see six boundary crossings in
opposite directions; arms must ship the per-query table.

Decisions: **(a)** no further similarity method is spent on N2 — lexical (#49) and semantic (here)
are both closed; **(b)** the 0.70 target stays **unmet and published as unmet**; **(c)** revising the
noise model is a *separate* decision that must be measured, not asserted — N2's construction makes it
a near-duplicate-discrimination task, and whether that is the noise a long-lived memory graph faces
is an open, pre-registerable question (recorded as `issue.mem-arch-n2-representativeness`); **(d)**
embeddings stay optional-only: `src/amg/` is untouched and the 274 MB model plus a daemon remain
outside the zero-dependency default path.

Cost: roughly six minutes of local embedding plus one pre-registration, to replace "we never measured
embeddings on N2" with a number and a mechanism — and to stop the next round from re-running the same
family under a new name.
*Signed 2026-10-31; `experiments/retrieval_semantic/`; v0.33.1.*
