# Decision #27

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31.*

**Scale does not dilute lexical recall; vocabulary overlap does, and the scorer is
    why.** At 10k, unrelated noise changed nothing (0.654/0.808/0.865/0.763);
    query-vocabulary noise cost **r@5 0.808 → 0.538** (no IDF). Measurement, reasoning
    and wrong predictions: `experiments/retrieval_10k/README.md`. *Signed 2026-10-31.*
