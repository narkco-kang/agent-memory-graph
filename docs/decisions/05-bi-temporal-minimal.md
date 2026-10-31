# Decision #5

[← decision log](../DECISIONS.md) · status: active · signed by the log preamble (*signed 2026-10-29*), this entry has no per-entry signature line

**Bi-temporal, minimally.** Validity time (`valid_from`/`valid_until`) is
   separate from transaction time (`recorded_at`/`superseded_at`). Never
   back-fill `valid_from` from the change log: `changes[].at` is *when it was
   written*, not *when the fact became true*.
