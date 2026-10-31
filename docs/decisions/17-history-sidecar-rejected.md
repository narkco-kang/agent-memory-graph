# Decision #17

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30.*

**History sidecar: rejected. Segmented compression: the sanctioned direction, not
    yet built.** The sidecar measured −82% write cost (147 → ~27 ms) and was rejected
    anyway: `changes[]` entries are descriptions, not replayable operations, so a split
    store has a crash window that can be *detected* but never repaired, and the ledger
    can end up disagreeing with the state it describes: trading the core guarantee for
    speed. The alternative keeps one atomically replaced
    file and compresses history into sealed zlib segments: −54% file size, ~60 ms
    writes, 11 ms to decompress, round-trip verified; the price is explicit — history
    stops being greppable/diffable, `fingerprint` must be defined over decompressed
    meaning, and it needs an `amg/v2` bump. Deferred to the existing trigger (20 MB /
    250 ms p95 / 10k nodes). Design: `docs/DESIGN-HISTORY.md`.
    *Signed 2026-10-30.*
