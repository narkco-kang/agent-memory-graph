# Does a semantic arm close N2?

Pre-registered test of the only direction DECISIONS #49 left open, using a local embedding daemon
(`ollama nomic-embed-text`, digest recorded in the pre-registration) — no new package dependency and
`src/amg/` untouched.

**Answer: no, and the reason is the noise model, not the model.** All three arms land on N2
recall@5 **0.577** (+0.039) against a +0.05 criterion and a 0.70 target, while the *same* model lifts
the real corpus 0.865 → **0.981** and the two non-adversarial noise corpora to 0.962 / 0.942.

    PYTHONPATH=src python3 experiments/retrieval_semantic/run_semantic.py          # ~6 min cold
    PYTHONPATH=src python3 experiments/retrieval_semantic/diagnose_moved_queries.py

| file | what it is |
|---|---|
| `PREREGISTRATION.md` | backend digest, three arms, criteria, predictions; `## Outcome` appended after |
| `run_semantic.py` | cache + three arms (RRF rerank / pure semantic / hybrid) + per-arm ceilings |
| `diagnose_moved_queries.py` | post-hoc: per-query gold rank, so churn is not averaged away |
| `result.json`, `diagnostic_moved_queries.json` | machine-readable outputs |

Embeddings are cached under `/tmp/amgembed-cache/<digest-prefix>/`, keyed by text SHA-256, so reruns
are free. The cache is keyed by model digest on purpose: a different model must not silently reuse
another model's vectors.

Decided here: DECISIONS #50 — the similarity family is closed for N2; the open question moved from
"which model" to "is N2 the noise a memory graph actually faces", which is a separate, measurable
decision.
