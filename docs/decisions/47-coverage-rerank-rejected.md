# Decision #47

[← decision log](../DECISIONS.md) · status: amended (#48)

**Coverage reranking is rejected: it is anti-correlated with the answer under query noise.**
The shipped scorer leaves query-vocabulary noise (N2) at recall@5 0.538 against a 0.70 target,
and #28 explained why IDF cannot move it. `experiments/retrieval_beyond_df/` pre-registered the
next candidate outside the frequency family: rerank the top 100 by how much of the query a hit
contains (`score x coverage ** alpha`). Measured on the same four frozen corpora: N2 **0.538 ->
0.481**, control 0.865 -> 0.846, unrelated noise 0.865 -> 0.808, frequent noise 0.865 -> 0.808;
all four pre-registered criteria failed, no ship, no retuning. The mechanism is the finding: N2
injects distractor tokens *from the query's own vocabulary*, so coverage counts the injected
tokens too and a distractor that absorbs three of them outranks the gold node — the feature is
not merely useless here, it points away from the answer. All four predictions were wrong and are
recorded as wrong. Consequence for the next attempt: a usable signal must distinguish source
tokens from injected ones (term proximity inside one field), not aggregate over query tokens.
Cost: one experiment and a rejected direction; N2 stays at 0.538 and still misses its target.
*Signed 2026-10-31; `experiments/retrieval_beyond_df/`; v0.32.6.*
