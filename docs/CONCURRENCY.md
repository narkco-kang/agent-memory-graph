# Concurrency: what 200 concurrent writes actually do

The lock has unit tests for exclusivity between two processes. They do not answer
the question a user actually has: *if several agents write at once, does anything
get lost or double-counted, and what does it cost?*

This page answers it with a burst test. Reproduce:

```bash
PYTHONPATH=src python3 experiments/concurrency/run_stress.py            # 8 × 25
PYTHONPATH=src python3 experiments/concurrency/run_stress.py --writers 8 --writes 25 --json
```

## Method

- One graph, freshly initialised, plus one pre-existing node.
- **8 independent OS processes**, each opening the graph once and writing **25
  nodes** in a loop (`add_node`, one transaction per write) — 200 writes total,
  all in flight together.
- Every writer records per-write latency; the parent verifies the result against
  the ledger and against `check`.
- A **serial baseline** of 25 writes from one process runs on the same graph
  afterwards, in its own process, so interpreter startup is excluded from both
  throughput figures (each writer reports its own start/finish wall clock).
- Three runs, all reported below rather than the best one.

## Correctness (three runs, identical outcome)

| check | result |
|---|---|
| nodes present | **200 / 200** |
| duplicate ids | 0 |
| missing writes | 0 |
| change records for those 200 writes | **200**, exactly one per target |
| wrong per-target change counts | 0 |
| `check` after the burst | **0 errors** |
| writer exceptions (incl. lock timeouts) | 0 |

No lost updates, no double-counting, and the event log agrees with the state —
which is the property that matters: a lost update here would be a silently missing
fact, and a duplicated change record would make the ledger lie about how many times
something happened.

## Cost under contention

| run | contended p50 / p95 / max | burst throughput | serial p50 / p95 / max | serial throughput |
|---|---|---|---|---|
| 1 | 1.05 / 3.32 / **243.47** ms | 696 writes/s (287 ms) | 1.55 / 1.87 / 2.19 ms | 631 writes/s (40 ms) |
| 2 | 1.02 / 4.05 / **233.99** ms | 710 writes/s (282 ms) | 1.55 / 1.71 / 2.17 ms | 639 writes/s (39 ms) |
| 3 | 0.99 / 1.69 / **242.09** ms | 708 writes/s (282 ms) | 1.56 / 1.67 / 2.11 ms | 648 writes/s (39 ms) |

## What this says

1. **No throughput penalty.** ~700 writes/s contended vs ~640 writes/s serial on
   this graph size. No parallelism gain either — the advisory lock serialises the
   critical section, as designed. The point is that contention does not *cost*
   throughput, only latency distribution.
2. **The median does not move.** p50 is ~1.0 ms under contention, ~1.55 ms serial
   (the contended number is slightly lower, most plausibly because another writer's
   `fsync` has already made the page cache hot for the next one).
3. **The tail is 100× the median.** One write in each run waited **~234–243 ms**.
   That is the number a user would feel, and it is not explained by the work: at
   ~1 ms per write, a 240 ms wait means a waiter was passed over many times. The
   plausible mechanism is that `flock` wakeups are not fair and the waiter polls in
   20 ms steps, so a steady stream of arrivals can starve it for dozens of rounds.

   **This is a hypothesis, not a measurement** — the experiment shows the tail, not
   its cause. Proving it needs lock-acquisition counters inside the store, which
   does not exist yet.

## Limits (read before quoting a number)

- **One machine**, macOS on APFS, warm page cache. `fsync` costs differ elsewhere.
- **Small graph** (~200 nodes). On the 15.6 MB real graph a write is 147 ms, so the
  tail would scale with it; this test says nothing about that case.
- **Node-sized writes only.** Batch ingest changes the shape entirely.
- **POSIX `flock` here.** Windows uses `msvcrt` locking and is covered only by the
  two-process exclusivity test in CI — no burst test on Windows, so the tail
  behaviour there is **unmeasured**.
- **No crash during the burst.** Atomicity under concurrent writers is tested
  separately (`test_lock.py`, `test_store.py`), not here.

## If the tail matters

The obvious next step is a fairer handoff than "poll and retry" (a ticket lock, or
`flock` plus an in-process queue keyed by arrival). It was not built because there
is no evidence yet that 240 ms once per 200 writes hurts anyone, and the fix is a
change to the one component that must never be wrong. Whoever builds it should
first add the counters this experiment says are missing.

## CI coverage

`tests/test_concurrency.py` runs a smaller version (3 writers × 3 writes) on every
commit, including Windows: same four assertions (all nodes, no duplicates, one
change record each, `check` clean). It does not measure latency — CI machines are
too noisy for that to mean anything.
