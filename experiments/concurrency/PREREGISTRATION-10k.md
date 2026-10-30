# Pre-registration: the concurrent-writer burst at 10,000 nodes

Written **before** the run, on `v0.15.0` (`c243236`). The published burst
(`result.json`, `docs/CONCURRENCY.md`) is 8 writers × 25 writes on a ~200-node graph.
The repository says, in words, that concurrency is not measured at 10k — this file
proposes to remove that gap and fixes what counts as a result first.

## Question

1. Does the invariant — **no write lost, none duplicated, one change record each, graph
   still structurally valid** — hold under contention at 10,000 nodes?
2. What does contention cost there, and does the default 5 s lock timeout survive?

## Predictions (recorded before the run; being wrong is data)

| quantity | predicted | basis |
|---|---|---|
| single write, 10k nodes | **70–110 ms** | 8 µs/node measured at 5k (`BENCHMARKS.md`), linear |
| contended p50 | **2–4× the serial p50** | 8 writers queueing on one lock |
| worst lock wait | **< 5,000 ms** (default timeout) | 200 writes × ~0.1 s ≈ 20 s spread over 8 writers |
| correctness | **exact** — 200 nodes, 0 duplicates, 0 missing, 200 change records | the same assertion as the small-graph burst |

## Criteria (fixed now)

| # | Criterion | Verdict rule |
|---|---|---|
| C1 | Correctness is exact | pass **only** if `nodes_present == expected`, `duplicate_ids == 0`, `missing_writes == 0`, `errors == []`, `check_ok`, `changes_for_stress_writes == expected`, `targets_with_wrong_change_count == 0`. No tolerance. |
| C2 | No lock timeout at the default 5 s | if `timeouts > 0`, that is a **finding**: the default is too small at 10k. It will be reported as a failure of this criterion, not repaired by raising `AMG_LOCK_TIMEOUT` inside the same run. |
| C3 | Every number is published | p50/p95/max, throughput, serial baseline, worst wait, poll counts — whatever they are, including if the machine is loaded (load average is recorded and printed with the result). |
| C4 | The environment is stated | macOS/APFS, this machine, load average at run time. `fsync` cost differs on other filesystems; no claim is made beyond this host. |

## What this will **not** establish

- Nothing about Windows (msvcrt byte-range locking), network filesystems, or multi-host
  writers.
- Nothing about 10k-node **retrieval** recall — that is `retrieval_eval/`'s question and
  remains unmeasured at 10k.
- Nothing about the fair-lock proposal in `DECISIONS.md`; a slow tail here is a symptom,
  not a licence to build it.

## Reproduce

```bash
# 10k-node graph, built directly on disk (benchmarks/bench.py::build)
PYTHONPATH=src python3 experiments/concurrency/build_10k.py /tmp/amg-10k
PYTHONPATH=src python3 experiments/concurrency/run_stress.py --graph /tmp/amg-10k \
    --writers 8 --writes 25 --json > experiments/concurrency/result-10k.json
```

---

## Outcome (recorded 2026-10-31, after two runs — criteria above are untouched)

Two runs on a freshly built 10,000-node / 10,000-edge graph (9.35 MB), macOS/APFS,
1-minute load average 4.4 during the build. Artifacts:
`result-10k-run1-timeout.txt` and `result-10k.json`.

| # | Criterion | Result |
|---|---|---|
| C1 | correctness exact | **pass with an adequate timeout**: 200/200 nodes, 0 duplicates, 0 missing, 200 change records (one per write), `check` clean |
| C2 | no timeout at the default 5 s | **FAIL**: run 1 died with `LockTimeout: write lock timeout after 5.0s`; no report was produced, by design |
| C3 | every number published | **pass**: both runs are in the repository, including the failing one |
| C4 | environment stated | **pass**: host/filesystem/load/timeout recorded in `result-10k.json` |

### Predictions vs measurements

| quantity | predicted | measured | verdict |
|---|---|---|---|
| single write at 10k | 70–110 ms | **86.2 ms** (serial p50) | right |
| contended p50 | 2–4× serial | **85.8 ms ≈ 1.0×** | **wrong** — the write itself dominates; queueing shows up in the tail, not the median |
| worst lock wait | < 5,000 ms | **13,522 ms** (821 polls) | **wrong**, and run 1 proves it by timing out |
| correctness | exact | exact (run 2) | right |

Run 2 (timeout 180 s) details: throughput **11.1 writes/s** contended vs **11.3/s**
serial, p50 85.8 ms, p95 112.3 ms, worst individual write 4,790 ms, worst lock wait
13,522 ms.

### What this changes in the product

Nothing in `src/amg/` — this is a measurement. What it changes is documentation and
one decision (`docs/DECISIONS.md` #26): the default 5 s timeout is right for
interactive use and wrong for an 8-writer burst on a 10k graph, and the failure is
already actionable (`LockTimeout` tells the caller to raise `AMG_LOCK_TIMEOUT`). The
option of raising the default was rejected on the grounds that a silent 30-second
stall is worse for an interactive CLI than a fast, explicit error.

### What it still does not establish

Windows, network filesystems, multi-host writers, 10k **retrieval** recall, and any
fairness claim: the 13.5 s wait with 821 polls is a starvation symptom, not proof of a
starvation mechanism (see `DECISIONS.md` #15 for why the fair-lock proposal stays
unbuilt).

