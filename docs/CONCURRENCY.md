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
   the original fixed 20 ms poll; the advisory lock serialises the critical section
   as designed. Contention costs latency distribution, not throughput.
2. **The median does not move.** p50 ~1.0 ms under contention vs ~1.55 ms serial
   (the contended number is slightly lower, most plausibly because another writer's
   `fsync` has already made the page cache hot for the next one).
3. **The tail is 100× the median, and it is starvation, not polling.** The first
   run of this test showed one write in each run waiting ~234–243 ms. Two
   experiments followed.

### Diagnosis 1 — counters: only a few polls, a long wait

`Store.lock_stats` (observation only) counts acquisitions, failed polls, wait time
and timeouts. Before any change:

| run | worst wait | failed polls by that waiter | polls across all 200 writes |
|---|---|---|---|
| 1 | 226.3 ms | 9 | 31 |
| 2 | 231.0 ms | 8 | 30 |
| 3 | 189.3 ms | 7 | 32 |

Only ~30 failed polls in 200 writes: most acquisitions succeed on the first try,
a handful of writers lose repeatedly. With a 20 ms sleep, 7–9 losses is 140–180 ms
of sleeping, which *looked like* the cause — a fixed poll interval quantising the
wait.

### Diagnosis 2 — faster polling: throughput up, tail unchanged

The retry policy changed to jittered exponential backoff (`LOCK_POLL_START_S` 1 ms,
doubling, ceiling `LOCK_POLL_MAX_S` 16 ms): waiters retry sooner instead of sleeping
a flat 20 ms.

| run | worst wait | failed polls | polls total | p50 | p95 | max | burst throughput |
|---|---|---|---|---|---|---|---|
| 1 | 188.0 ms | 15 | 74 | 1.01 | 2.12 | 189.9 ms | 871 writes/s |
| 2 | 168.2 ms | 14 | 80 | 1.07 | 2.61 | 170.1 ms | 888 writes/s |
| 3 | 199.3 ms | 15 | 66 | 1.03 | 1.67 | 201.1 ms | 853 writes/s |

Throughput rose ~20% (700 → ~870 writes/s, burst window 282 → 229 ms) and p50/p95
did not get worse — but **the tail did not move**. If the tail were the 20 ms
quantum, faster polling would have cut it. It did not, so the quantum hypothesis is
**disproven**.

The arithmetic that fits instead: the worst waiter's wait (168–199 ms) is the same
order as the whole burst (225–234 ms), and it failed only ~15 polls while the other
seven writers performed ~200 writes. One writer was passed over for essentially the
entire burst. `flock` wakeups are not FIFO, so a steady stream of arrivals can keep
a waiter from ever being chosen. **This is starvation, and it is a property of the
lock primitive, not of the retry loop.**

### What changed, and what did not

- **Changed** (measured, kept): jittered exponential backoff instead of a flat
  20 ms sleep. Burst throughput +20%, median and p95 unchanged, same correctness.
- **Not changed** (no evidence yet that it is worth the risk): fairness. A ticket
  lock or an explicit waiter queue would cap the starvation tail, and it would
  touch the one component that must never be wrong. Tracked as an open issue with
  the numbers above; the trigger for building it is a real workflow feeling the
  tail (repeated 200 ms stalls) or a lock timeout in the field, not a benchmark.

## Limits (read before quoting a number)

- **One machine**, macOS on APFS, warm page cache. `fsync` costs differ elsewhere.
- **Small graph** (~200 nodes). On the 15.6 MB real graph a write is 147 ms, so the
  tail would scale with it; this test says nothing about that case.
- **Node-sized writes only.** Batch ingest changes the shape entirely.
- **POSIX `flock` here.** Windows uses `msvcrt` locking and is covered only by the
  two-process exclusivity test in CI — no burst test on Windows, so the tail
  behaviour there is **unmeasured**. (Fairness characteristics of `msvcrt` byte-range
  locking may differ from `flock`; nothing here says they are the same.)
- **No crash during the burst.** Atomicity under concurrent writers is tested
  separately (`test_lock.py`, `test_store.py`), not here.

## If the tail matters

The obvious next step is a fairer handoff than "poll and retry" (a ticket lock, or
`flock` plus an in-process queue keyed by arrival). It was not built because there
is no evidence yet that 240 ms once per 200 writes hurts anyone, and the fix is a
change to the one component that must never be wrong. Whoever builds it should
first add the counters this experiment says are missing.

## On a real 15.6 MB graph: the timeout is the binding constraint

The small-graph numbers above hide the case that actually bites: a write on the
real 15.6 MB graph costs ~147 ms (whole-file rewrite + `fsync`, see
`WRITE-COST.md`), so a burst of writers queues seconds of work. Same harness, with
the graph adopted from a live one (`--graph DIR`), 5 writes per writer:

| writers × writes | writes | outcome | worst lock wait | p50 | p95 | max |
|---|---|---|---|---|---|---|
| 2 × 5 | 10 | all present, `check` clean | **0.85 s** | 147.7 ms | 169.5 ms | 169.5 ms |
| 4 × 5 | 20 | all present, `check` clean | **2.51 s** | 149.4 ms | 153.1 ms | 166.7 ms |
| 8 × 5 | 40 | **`LockTimeout` after 5.0 s** — the run aborted | — | — | — | — |
| 8 × 5, `AMG_LOCK_TIMEOUT=60` | 40 | all present, `check` clean | **5.95 s** | 149.1 ms | 2.88 s | 3.99 s |

The arithmetic, which the table fits almost exactly:

```
per-write cost      ~150 ms  (147-152 ms measured, serial and contended alike)
burst of 40 writes  ~6.0 s   (measured burst window: 6.7 s)
worst wait          5.95 s   = the queue ahead of the last writer, drained
default timeout      5.0 s   = about 34 queued writes
```

So **fairness is not the fix here**: even a perfectly FIFO lock has to drain ~6 s of
writes before the last writer gets in. The binding constraint is `timeout <
queued_writes × per_write_cost`. That has three consequences, all documented rather
than patched over:

1. **The default stays 5 s** — it is fine for interactive single-agent use, which is
   what this library is for.
2. **Bursts must raise it**: `AMG_LOCK_TIMEOUT` (seconds) is read by every lock
   acquisition, clamped to `(0, 3600]`, nonsense values fall back to 5 s. The
   timeout error now names the variable instead of leaving the user to guess.
3. **The real fix is cheaper writes**, not a fairer lock: the history sidecar priced
   in `WRITE-COST.md` would take a write from ~150 ms to ~30 ms, which moves the
   same 5 s budget from 34 queued writes to ~170.

Both are consistent with [DECISIONS #15](decisions/15-lock-retry-backoff.md)/#16: build the expensive thing when a real
workflow needs it, and say so with these numbers instead of "locks are slow".

## At 10,000 nodes: same arithmetic, bigger queue

The previous section predicted the shape; this one measures it at the size where the
answer matters for a long-lived team. Graph built on disk with
`experiments/concurrency/build_10k.py` (10,000 nodes, 10,000 edges, 9.35 MB), then the
same 8 × 25 burst. Pre-registration and predictions: `experiments/concurrency/PREREGISTRATION-10k.md`.

| run | timeout | outcome | worst lock wait | p50 | p95 | max |
|---|---|---|---|---|---|---|
| 1 | default **5 s** | **`LockTimeout`** — a writer died, no report produced | — | — | — | — |
| 2 | `AMG_LOCK_TIMEOUT=180` | 200/200 nodes, 0 duplicates, 0 missing, 200 change records, `check` clean | **13.52 s** | 85.8 ms | 112.3 ms | 4.79 s |

Arithmetic check: per-write cost at 10k is **86.2 ms** (serial p50, measured here —
the extrapolation in `BENCHMARKS.md` said 70–110 ms, so it holds), so 200 writes are
**~17.2 s** of work, and the measured burst window was **17.95 s**. The last writer
waits behind most of that queue, which is why its wait was 13.5 s and why the default
5 s could not survive. Throughput was 11.1 writes/s contended against 11.3/s serial:
at this size the **write cost**, not the lock, is the limit.

Two predictions from the pre-registration were wrong, and are recorded as wrong:
contended p50 did **not** inflate (85.8 ms ≈ 1.0× serial), because queueing shows up
in the tail; and the worst wait was 13.5 s, not < 5 s.

Operationally: size the timeout to the burst, not to a feeling.
`AMG_LOCK_TIMEOUT ≥ writers × writes × per_write_cost` is the safe form; for the
200-write, 10k-node case that is ≥ 18 s, so 30–60 s is a sane setting. The default
stays 5 s for interactive use ([DECISIONS #26](decisions/26-lock-timeout-stays-5s.md)), and the error already names the knob.

## The tail on three operating systems (v0.32.3)

[DECISIONS #15](decisions/15-lock-retry-backoff.md) read the tail as starvation from non-FIFO lock wake-ups, measured on **macOS
only**; Windows stayed "not measured" from v0.15.0 to v0.32.2. `experiments/concurrency/tail_latency.py`
now measures the same thing everywhere, in CI, on a 5,000-node graph with an 8 x 10 burst
(`AMG_LOCK_TIMEOUT=180` so the run finishes; the timeout decides when a run stops, not what a
waiter waited — `worst_wait_ms` comes from the lock's own counters):

| platform | one write, no contention | contended p50 | p95 | max | worst lock wait | polls | waiters > 100 ms |
|---|---|---|---|---|---|---|---|
| ubuntu-latest | 137.9 ms | 146.4 ms | 151.8 ms | 155.8 ms | 10.46 s | 874 | 7 |
| macos-latest | 94.6 ms | 82.5 ms | 94.9 ms | 148.5 ms | 6.16 s | 104 | 7 |
| windows-latest | 168.8 ms | 151.8 ms | **1,672 ms** | **6,431 ms** | 10.49 s | 849 | 8 |

All three runs kept 80/80 writes with one change record each and `check` clean.

What this does and does not say:

- The tail is **not a macOS artefact**: ubuntu sees the same worst wait with 8x the polls, so
  #15's cause survives the platform change.
- **Windows is materially worse in what a caller feels** — p95 1.67 s against 0.09–0.15 s —
  while its worst *lock wait* is comparable to Linux's. The difference is in the distribution
  of waits, not in the maximum.
- These are shared cloud runners at 5,000 nodes. **The 10k Windows figure is still not
  measured** and no document should imply it is.
- The 5 s default stays policy (#26): at 168.8 ms a write, 8 x 10 queued writes need about
  13.5 s, so the arithmetic — not a defect — is why the plain default aborts first.

## A real bug the Windows burst test found

The CI version of this burst (3 writers × 3 writes) failed on Windows with:

```
PermissionError: [WinError 5] Access is denied: '.graph.<x>.tmp' -> 'graph.json'
```

Windows cannot `os.replace` a file that another process has open, and `Memory.open`
used to read the graph **without** the lock. So one writer's startup read could make
a different writer's atomic replace fail — a real failure mode for any Windows user
with two agents, not a flake.

Fix: `Store.read_locked()` reads under the lock, and `Memory.open` uses it. Cost: an
open now waits behind an in-flight write (milliseconds on this store). A missing
graph still raises `E_NO_GRAPH` **before** locking, so opening a non-existent
directory creates nothing — the read-only promise that opening leaves no trace
still holds, and both properties are tested in `tests/test_lock.py`
(`LockedReadTests`).

## CI coverage

`tests/test_concurrency.py` runs a smaller version (3 writers × 3 writes) on every
commit, including Windows: same four assertions (all nodes, no duplicates, one
change record each, `check` clean). It does not measure latency — CI machines are
too noisy for that to mean anything.

## Three writers over two protocols: two MCP sessions and a CLI

Everything above drives writers through the library or the CLI. A team does
something else: each agent holds its own long-lived `amg mcp` process, and a human
or script occasionally runs a CLI command — three processes, two protocols, one
file.

`tests/test_mcp_concurrency.py` builds exactly that: two stdio MCP servers (each
writing 5 nodes) and one thread running 5 `amg add` subprocesses, plus a fourth
thread running `amg check` while the writes land. Assertions, on every commit and on
all four test platforms:

- every node exists, none written twice (15 nodes for 15 writes);
- exactly one `changes[]` record per write, and no write with two records;
- `check --strict` passes on the merged result;
- no writer *or reader* reported an error — a refusal is collected and fails the
  test rather than being swallowed.

The concurrent reader is there for the v0.6.0 Windows bug above: a read that opens
the file while another process replaces it is the shape of that failure. One honest
limit, measured locally: reverting `Memory.open` to the unlocked read leaves this
test **green on macOS**, because POSIX allows replacing an open file. The test is a
regression guard for Windows specifically, which is why it runs on the Windows
runner and why the fix is stated as Windows-motivated rather than platform-neutral.
