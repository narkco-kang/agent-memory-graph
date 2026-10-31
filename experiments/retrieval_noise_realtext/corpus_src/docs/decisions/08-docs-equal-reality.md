# Decision #8

[← decision log](../DECISIONS.md) · status: active · signed by the log preamble (*signed 2026-10-29*), this entry has no per-entry signature line

**Documentation must equal reality.** CI fails if a documented capability has
   no corresponding symbol. The check only verifies symbol existence — it makes
   no claim about semantics, because a fake semantic check would be worse than
   none.
