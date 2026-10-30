# Benchmarks

Measured on 2026-10-30, single process, local SSD, macOS, Python 3.15.
Reproduce with `PYTHONPATH=src python3 benchmarks/bench.py` (it writes
`benchmarks/result.json`).

The dataset is **synthetic but schema-shaped like a real graph**: 2 change
records per node (the real graph we migrated had 2,048 changes for 1,027 nodes)
and one evidence object per node. Edge density is varied explicitly, because
edges turned out to matter less than expected — see below.

## Read paths (median of 3, in-process)

| nodes | edges | file | `check` | `audit` | `search` L3 | `digest` (64 KiB) |
|---|---|---|---|---|---|---|
| 1,000 | 0 | 0.86 MB | 5.5 ms | 5.3 ms | 5.3 ms | 5.3 ms |
| 1,000 | 1,000 | 0.93 MB | 6.2 ms | 5.9 ms | 6.2 ms | 5.5 ms |
| 5,000 | 5,000 | 4.67 MB | 33.1 ms | 29.6 ms | 32.3 ms | 29.9 ms |
| 10,000 | 0 | 8.65 MB | 58.6 ms | 57.1 ms | 75.7 ms | 58.1 ms |
| 10,000 | 10,000 | 9.35 MB | 65.5 ms | 63.2 ms | 83.5 ms | 62.9 ms |

Read paths are linear in the number of nodes and changes, and at 10k they stay
under 100 ms. `digest` output is bounded by its byte budget (65,536 B), not by
graph size.

## Write path — the honest limitation

| nodes | first `add_node` | mean `add_node` (20 writes) |
|---|---|---|
| 100 | 1.5 ms | 1.3 ms |
| 1,000 | 7.9 ms | 8.4 ms |
| 5,000 | 39.1 ms | 39.8 ms |

Every write reloads, re-serializes and atomically replaces the whole file, so a
single write costs O(n): roughly 8 µs per existing node at 5k. **Measured at 10k
since v0.16.0** (serial p50 inside the concurrency burst, `docs/CONCURRENCY.md` §"At
10,000 nodes"): **86.2 ms**, inside the 70–110 ms this table extrapolated.

**Bulk ingest was therefore quadratic.** Summing the measured per-write cost gave
about **6–7 minutes** to ingest 10,000 nodes one `add_node` at a time (a computed
extrapolation, not an end-to-end run). The fix is a batch API — one load, N
appends, one write — not a faster serializer.

## Batch ingest (`amg import` / `Memory.add_many`)

| nodes | wall time | per node |
|---|---|---|
| 1,000 | 0.01 s | 0.01 ms |
| 5,000 | 0.05 s | 0.01 ms |
| 10,000 | 0.10 s | 0.01 ms |

Measured, not extrapolated: 10,000 nodes in **0.10 s**, roughly four orders of
magnitude faster than repeated single writes. The batch is all-or-nothing: every
node and edge is validated with the same gates before the file is written, so a
single bad record rejects the whole batch and leaves the graph byte-identical.

Before v0.2 edges added roughly 10% to the read paths and were never walked —
they were stored, validated and counted only. v0.2 adds traversal, measured here
on a 10,000-node / 10,000-edge graph:

| operation | latency |
|---|---|
| `related` depth 1 | 8.1 ms |
| `related` depth 2 | 7.8 ms |
| `search` plain | 82.2 ms |
| `search --expand` (1 hop per hit) | 92.8 ms |
| expand overhead | **+10.6 ms** |

Traversal builds the adjacency once per call, so its cost is bounded by the graph
rather than the depth; expanding ten hits costs about 11 ms on top of the search.

## Real graph

A live 1,249-node / 15.3 MB graph (written daily by a multi-agent team for a week)
is measured end to end in [`REAL-WORLD.md`](REAL-WORLD.md): adoption 140 ms, `check`
0 errors in 4.4 ms, `audit --pin` down to 3 genuine conflicts, reads single-digit
milliseconds, and **one write 147 ms** — the number behind the cold-archive
trigger. [`WRITE-COST.md`](WRITE-COST.md) breaks that number down (parse 75 ms /
render 50 ms / `fsync` 23 ms) and prices the options against it.

## Retrieval quality (not latency)

Latency is measured above; quality is measured separately and pre-registered in
[`experiments/retrieval_eval/`](../experiments/retrieval_eval/README.md). On the frozen
27-node corpus with 26 labelled queries the shipped v0.18.0 scorer measures overall
`recall@5` **0.865**, `recall@1` 0.731, keyword bucket 0.969, paraphrase bucket 0.700,
and 0.865 under frequent-word noise at 10,000 nodes
([`retrieval_idf/`](../experiments/retrieval_idf/README.md)). Uniform query-vocabulary
noise still holds it to **0.538**
([`retrieval_10k/`](../experiments/retrieval_10k/README.md)). The acceptance bar for a
semantic retriever (C1/C2/C3) is written there before any candidate existed.

## Not measured

- Edges: the *synthetic* latency dataset has none, so edge traversal cost is not
  measured there; the real-graph run measures `related` at depth 1 only.
- Concurrency throughput at 10k nodes: the burst test runs on a small graph only.
  Correctness under concurrent writers and the latency tail are measured in
  [`CONCURRENCY.md`](CONCURRENCY.md) (8 writers × 25 writes).
- Windows: latency is not benchmarked on Windows. Correctness is — the suite runs
  on `windows-latest` in CI, including the cross-process lock test.
- Vector retrieval: measured candidates (bm25, hashed-vec, and a local embedding model
  when one is reachable) lost to the lexical baseline on its pre-registered bar; no
  vector path ships (`experiments/retrieval_eval/`).
- A real 10k graph: retrieval quality at scale is measured on synthetic noise models
  only (`experiments/retrieval_10k/`, `experiments/retrieval_idf/`).
