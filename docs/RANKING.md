# Ranking: scores, and what decides a tie

`amg search` returns hits in one order, defined by a single key (`src/amg/retrieval.py:rank_key`):

```
(round(raw_score, 3), anchor_state == "present", node_id)   sorted descending
```

Three consequences, all of them observable:

1. **The rounded score decides first; anchoring only decides an exact tie.** Since v0.36.0 a node
   with declared evidence outranks one without **only when their three-decimal scores are equal**.
   Before v0.36.0 anchoring was the first key and outranked every score: an anchored node scoring
   **1.313** beat an unanchored node scoring **3.527**, and on the team's own graph an unanchored
   node could not reach the top 50 for its own label at all — measured **40/40** anchored against
   **0/40** unanchored, and **40/40** against **40/40** after the change. See
   [DECISIONS #55](decisions/55-anchor-is-a-tie-breaker.md).
2. **Anchoring is reported, not gating.** Every hit carries `anchor_state`
   (`present` means *evidence declared*, not evidence verified; run `amg verify-evidence` for the
   observable half). `--strict` is the only filter that returns anchored hits exclusively. Rank
   position is **not** an evidence signal: read `anchor_state`, or use `--strict`.
3. **Between two hits of the same anchoring state, the node id decides — reversed.** A tie is not a
   relevance judgement. This is deliberate: it makes every run reproducible, and it makes a tie
   visible instead of silently ordering by insertion. It also means that a weight change can move a
   hit past another hit *without* any relevance improvement, purely by resolving a tie differently.

## Boundary ties are a property of the evaluation surface

Define a **boundary tie** at `k` as: the hit at rank `k` and the hit at rank `k+1` have the same
displayed score. When a query sits on a boundary tie, whether the gold node is "in the top five" is
decided by the two tie layers above — anchoring first, then id. A corpus with many boundary ties
cannot distinguish a real ranking improvement from a tie flip.

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

## The four synthetic arms are blind to the anchoring key

Moving anchoring from the first key to the second changes **nothing** on the four synthetic arms:
control 0.8654, n1 0.8654, n3 0.8654, n2 0.5385, realtext 0.6923, before and after, to four
decimals. That is structural rather than reassuring — those corpora declare evidence uniformly
(each node is anchored or not as a block), so an anchor component cannot reorder them. Any claim
that the change is safe has to come from the **stratified** measurement in
[DECISIONS #55](decisions/55-anchor-is-a-tie-breaker.md), never from a delta of zero here.

Reproduce:

```sh
PYTHONPATH=src python3 experiments/retrieval_noise_realtext/run_realtext.py
python3 -c "import json; r=json.load(open('experiments/retrieval_noise_realtext/result.json')); \
print({k: v['tie_surface']['k5']['queries'] for k, v in r['arms'].items()})"
python3 tools/glm-mutation-check.py   # exit 0 = the old key breaks >= 2 tests
```
