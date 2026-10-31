# Decision #6

[← decision log](../DECISIONS.md) · status: active · signed by the log preamble (*signed 2026-10-29*), this entry has no per-entry signature line

**Semantic gates may not reject.** A synchronous near-duplicate gate can fire
   before an asynchronous contradiction detector and wrongly reject a write
   (documented in arXiv:2606.24535). Only the evidence gate may reject, and it
   must raise explicitly — never return `None` silently (the CrewAI
   `read_only → return None` case).
