# Decision #45

[← decision log](../DECISIONS.md) · status: active

**The lock tail is cross-platform, and Windows pays more of it.** DECISIONS #15 concluded that
the ~200 ms tail is starvation from non-FIFO wake-ups, measured on macOS; Windows stayed
“not measured” from v0.15.0 to v0.32.2. `experiments/concurrency/tail_latency.py` now runs the
same measurement in CI on three platforms (5,000 nodes, 8 x 10 burst, `AMG_LOCK_TIMEOUT=180` so a
slow runner does not abort before the distribution is observed). Measured: worst lock wait
10.46 s on ubuntu (874 polls), 6.16 s on macOS (104 polls), 10.49 s on Windows (849 polls), and
all three kept 80/80 writes with `check` clean. The finding that changes what we say: **Windows
p95 is 1.67 s against 0.09–0.15 s elsewhere** while its worst wait matches Linux's, so the
difference is in the wait distribution, not the maximum — an application on Windows feels the
tail that #15 described as a benchmark curiosity. Not fixed: fairness stays unbuilt, on #15's
original trigger (repeated stalls harming a real workflow), and the 10k Windows number is still
unmeasured and still documented as such. Cost: a CI job on three platforms per run, and a claim
that no longer reads “macOS only”.
*Signed 2026-10-31; `experiments/concurrency/tail_latency.py`, `docs/CONCURRENCY.md`; v0.32.3.*
