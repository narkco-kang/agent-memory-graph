# Decision #7

[← decision log](../DECISIONS.md) · status: active · signed by the log preamble (*signed 2026-10-29*), this entry has no per-entry signature line

**Consolidation keeps pointers only.** Digest output references node ids and
   evidence counts; it never copies evidence payloads, and it is bounded by
   `--max-bytes` with an explicit `[truncated N items]` marker. The digest is not
   a second store, so it must stay auditable.
