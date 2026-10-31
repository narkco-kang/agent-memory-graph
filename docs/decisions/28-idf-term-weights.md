# Decision #28

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; `experiments/retrieval_idf/`, `result.json`; v0.18.0.*

**IDF term weights ship — and they do not fix query-vocabulary noise.** Pre-registered
    (`experiments/retrieval_idf/PREREGISTRATION.md`) with four corpora and the v0.17.0
    scorer frozen as `baseline.py`, run in the same process so the comparison cannot be
    machine noise. The change: a matched term contributes `WEIGHTS[field] × idf(term)`
    with `idf = ln(1 + N/(1+df))` over the visible nodes, instead of a constant field
    weight; weights, matchers, filters and ordering are unchanged, and a repeated query
    word counts once. All four criteria passed: frozen 27-node recall@5 **0.808 → 0.865**
    (r@1 0.654 → 0.731), N1 unchanged, frequent-word noise at 10k **0.712 → 0.865**, and
    query-vocabulary noise **0.538 → 0.538** with deep ranks improved (r@10 0.538 →
    0.577). The task's `N2 r@5 ≥ 0.70` target was **missed**, and the reason was
    predicted before the run and is structural: N2 draws every distractor token
    *uniformly* from the queries' own vocabulary, so `df` is the same for every query
    term and IDF has no signal to use. That noise model is now known to be invariant to
    document-frequency statistics; beating it needs a signal outside that family (id/type
    priors, phrase proximity). Cost: p50 +3.0 ms at 10k (+4%), one bookkeeping pass, no
    second scan. Two predictions were wrong and are recorded: the small-corpus gain
    (+0.057, expected flat) and the N3 baseline (0.712, predicted 0.45–0.65).
    *Signed 2026-10-31; `experiments/retrieval_idf/`, `result.json`; v0.18.0.*
