# Lexical precision (pre-registered)

`retrieval_eval/` measures **recall** against a semantic-vs-lexical comparison. This
directory measures a different claim: whether the lexical matcher answers queries that
**cannot distinguish anything**.

- `PREREGISTRATION.md` — criteria, fixed before implementation, plus a dated outcome
  section (including the two criteria that failed and why that was the correct result).
- `run_eval.py` — the harness. Frozen corpus by default; `--graph <legacy.json>` adopts
  a real graph into a temporary directory (aggregates only, no ids printed).
- `result.json` — last run on the frozen corpus.

```bash
PYTHONPATH=src python3 experiments/retrieval_precision/run_eval.py
PYTHONPATH=src python3 experiments/retrieval_precision/run_eval.py --graph /path/to/graph.json
```

## What changed (v0.14.0)

| behaviour | before | after |
|---|---|---|
| ASCII match | raw substring | whole word **or regular inflection** (`rank`/`ranking`) |
| ASCII token of one character | matched everywhere | dropped: it cannot distinguish |
| query with `.`/`:`/`/`/`_` | split into words (`task.a` → `task`, `a`) | one identifier lookup |
| CJK | substring | unchanged (a character is a word) |

## Measured

| measurement | before | after |
|---|---|---|
| `a` / `e` / `i` / `x` / `q` on the real 1,289-node graph | 10 hits each (`k=10`) | **0** |
| `task.a`, `issue.zzz`, `missing.node` (no such node) | 10 hits each | **0** |
| identifier lookups naming a live node, top-1 | — | **20/20** |
| frozen-eval overall recall@5 | 0.865 | 0.808 |
| frozen-eval overall recall@1 | 0.654 | 0.654 |
| frozen-eval keyword recall@5 | 0.938 | **0.969** |
| frozen-eval MRR@10 | 0.744 | **0.763** |

The recall move is analysed per query in `PREREGISTRATION.md`: two of 26 queries were
reached only through substrings inside other words (`i` in `high-risk`, `one` in
`gone`), one was a real inflection case and is recovered, one improved. The trade is
recorded, not hidden — `docs/DECISIONS.md` #25.

## What this does not measure

- **Semantic recall.** Paraphrase queries still lose to a real embedding model; that is
  `retrieval_eval/`'s question and it is unchanged (the semantic candidate remains
  rejected for the default path).
- **Query cost.** The matcher compiles a small regex per token per query; it is not
  benchmarked here, and it is not on the write path.
- **Non-English morphology.** The suffix table is English; other languages get boundary
  matching only, which is a real limit and is stated rather than assumed.
