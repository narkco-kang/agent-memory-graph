# Decision #14

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30.*

**Write cost: measure the bytes before optimising, and do not trade atomicity
    for 20 MB.** Measured on a live 15.6 MB graph: `changes[]` is 79.1% of the
    file, and one write is 148 ms split as parse 75 / render 50 / `fsync` 23 —
    moving the bytes through the process twice, not the disk. Options evaluated in
    `docs/WRITE-COST.md`: cold-archiving nodes reclaims nothing today (oldest node
    is 6 days old, so 0 candidates); compact JSON saves 2.4% and costs
    diffability; incremental writes abandon the "reader sees old or new, never a
    mix" guarantee. The only option with a real payoff is moving old history to a
    sidecar (−80% write), and its price is that the graph stops being one atomic
    copyable file — so it waits for the existing trigger (write p95 > 250 ms, file
    > 20 MB, nodes > 10k) instead of being built speculatively. No `--no-history`
    escape hatch: if history ever moves, it moves for everyone and the guarantees
    are restated with it.
    *Signed 2026-10-30.*
