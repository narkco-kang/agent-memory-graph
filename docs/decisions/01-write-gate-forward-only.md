# Decision #1

[← decision log](../DECISIONS.md) · status: active · signed by the log preamble (*signed 2026-10-29*), this entry has no per-entry signature line

**Write gate is forward-only.** A real graph already had 629 of 869 `done`
   nodes without evidence (72%). Hard-failing them on day one would make `check`
   permanently red. So: new writes are gated; legacy nodes are exempted via a
   frozen pin of the sorted id list (not a file hash — that changes every write),
   and `audit` reports the ratio `629/869` as a convergence metric. Any change in
   the pin set must be explained explicitly.
