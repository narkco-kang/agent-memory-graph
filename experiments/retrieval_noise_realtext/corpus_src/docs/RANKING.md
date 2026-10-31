# Ranking: scores, and what decides a tie

`amg search` returns hits in one order, defined by a single key (`src/amg/retrieval.py:rank_key`):

```
(anchor_state == "present", round(raw_score, 3), node_id)   sorted descending
```

Three consequences, all of them observable:

1. **Anchored hits come first.** A node with declared evidence outranks one without, whatever the
   scores say. `anchor_state: "present"` means *evidence declared*, not evidence verified; run
   `amg verify-evidence` for the observable half.
2. **The score used for ordering is rounded to three decimals**, the same precision shown in
   `hits[i]["score"]`. Two hits whose raw scores differ by less than 0.0005 are therefore equal for
   ordering purposes.
3. **At an exact tie the node id decides the rank — reversed.** A tie is not a relevance
   judgement. This is deliberate: it makes every run reproducible, and it makes a tie visible
   instead of silently ordering by insertion. It also means that a weight change can move a hit
   past another hit *without* any relevance improvement, purely by resolving a tie differently.

## Boundary ties are a property of the evaluation surface

Define a **boundary tie** at `k` as: the hit at rank `k` and the hit at rank `k+1` have the same
displayed score. When a query sits on a boundary tie, whether the gold node is "in the top five" is
decided by its id. A corpus with many boundary ties cannot distinguish a real ranking improvement
from a tie flip.

`experiments/retrieval_noise_realtext/run_realtext.py` reports this per arm as `tie_surface`, and
the per-query rows in `ledger.json` carry `boundary_tie_at_5` / `boundary_tie_at_10`. Readings at
the pinned corpus (`corpus_pin.json`, 635 paragraphs, 26 queries):

| arm | ties at k=5 | ties at k=10 |
|---|---|---|
| control (real 10k nodes) | 5 / 26 | 4 / 26 |
| n2 (uniform-vocabulary noise) | 10 / 26 | 18 / 26 |
| real text (8-word windows) | **10 / 26** | **17 / 26** |

Ten of the 26 real-text queries end on a tie at the top-5 boundary, and 17 at the top-10
boundary, while N2 ties on 18 at k=10. That is why a
`WEIGHTS` sweep on the 26 queries is non-monotone: `label=1.00/1.05/1.10` all lift one query, while
`1.25` drops back, and the switch is a tie flip rather than a mechanism. Before any weight change is
called a gain, either the query set grows (the recorded minimum is 60) or the metric becomes
tie-aware.

Reproduce:

```sh
PYTHONPATH=src python3 experiments/retrieval_noise_realtext/run_realtext.py
python3 -c "import json; r=json.load(open('experiments/retrieval_noise_realtext/result.json')); \
print({k: v['tie_surface']['k5']['queries'] for k, v in r['arms'].items()})"
```
