# Decision #36

[← decision log](../DECISIONS.md) · status: active

**An evidence base is a policy, not an implicit directory.** The same `path:` evidence resolved **0/240** from `graphs/`, **113/240** from the workspace
root and **89/240** from the repository root: the base, not the file, decided the verdict.
Decision: `--evidence-root DIR` (default: the graph's own directory), printed on every run
as `evidence base … (files found N/M, P%)`; legacy strings `path:<rel>#sha256:<hex>` are
verified read-only and counted `verified`/`mismatched`/`malformed`, and a hash is never
invented to raise a count. Cost: one more concept in every bridge invocation.
*Signed 2026-10-31; `tests/test_verify_snapshot.py`; v0.26.0.*
