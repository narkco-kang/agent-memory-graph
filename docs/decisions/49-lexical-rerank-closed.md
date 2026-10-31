# Decision #49

[← decision log](../DECISIONS.md) · status: active

**The lexical rerank family is closed for query-vocabulary noise.** #48 named content-word
weighting / stop-word stripping as the next direction after the coverage loss turned out to be
distribution mismatch. A pre-registered round tested that direction plus two other signals that are
not document frequency — title coverage and compactness — reranking the shipped top-100 on the same
four corpora. **All nine arm/alpha combinations lose N2 recall** (best 0.481 at S3/alpha 0.5 against
the shipped 0.538) and every non-target corpus is harmed too: title coverage costs control 0.057 and
n3 0.115, compactness costs n1 0.057. Nothing passes any gate, so nothing ships.

The informative part is *why* the pooled diagnostic was misleading. Mean separability (AUC of a
signal ranking gold above non-gold inside the top 100) looked usable — 0.665 content coverage, 0.610
compactness — but splitting the same candidates by whether the shipped ranking already put gold in
the top 5 shows the mean was carried by the solved half:

| group | queries | content AUC | title AUC | compact AUC |
|---|---|---|---|---|
| gold already in top 5 | 15 | 0.779 | 0.515 | 0.767 |
| **gold outside top 5** | **11** | **0.421** | **0.258** | **0.275** |

On the queries that need repair the signals are at or below chance. A pooled mean over a candidate
set the scorer mostly already orders correctly measures the solved queries and hides the failures;
that is a general hazard for retrieval diagnostics, not a footnote to this one.

Two limits stay open and are recorded as such. (a) The 0.70 target is **not** shown to be
impossible: the candidate ceiling — the share of queries whose gold is inside the top 100 — is
**0.846**, still above 0.70, so a perfect reranker could in principle pass. What is refuted is that a
lexical one can. (b) Reranking is not the whole problem: **4 of 26 queries have gold beyond the top
100**, so any semantic arm has to be evaluated as candidate generation *and* reranking, not only as
a reorderer of what the scorer already found.

Cost: one round of experiment code plus a pre-registration, and a published direction (#48's) closed
one release after it was named — cheaper than another round spent on term statistics.
*Signed 2026-10-31; `experiments/retrieval_lexical_ceiling/`; v0.33.0.*
