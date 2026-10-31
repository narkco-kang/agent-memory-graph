# Decision #15

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30.*

**Lock retry backs off; lock fairness is not implemented.** The burst test showed
    one write per 200 waiting ~200 ms. Instrumenting the lock (`Store.lock_stats`)
    showed the worst waiter failed only ~15 polls while seven others completed the
    burst, and shortening the poll interval (flat 20 ms → jittered 1 ms doubling to
    16 ms) raised throughput ~20% (700 → 870 writes/s) **without moving the tail**.
    So the cause is starvation from non-FIFO `flock` wakeups, and faster polling was
    not the fix. The backoff is kept for the throughput; a ticket lock or waiter
    queue is not built, because it changes the one component that must never be
    wrong and there is no evidence yet that the tail harms a real workflow. Trigger
    to build it: repeated ~200 ms stalls observed in use, or a lock timeout in the
    field — not a benchmark.
    *Signed 2026-10-30.*
