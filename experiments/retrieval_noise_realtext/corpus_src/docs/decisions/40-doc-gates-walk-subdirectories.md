# Decision #40

[← decision log](../DECISIONS.md) · status: active

**A gate that cannot see a subdirectory is not a gate.** Both documentation gates derived their file list with one `listdir` level, so a document
placed in `docs/decisions/` would have been invisible to the size budget and to the
code-symbol gate — DECISIONS #18's “a hand-written list is a claim about the past”
reappearing one level down. Decision: both walks are recursive (`os.walk`), with tests that
place documents in nested directories and assert they are covered. Cost: none; this is the
prerequisite for splitting this log (it had 7 B of headroom).
*Signed 2026-10-31; tests in `tests/test_doc_sizes.py`, `tests/test_doc_symbols.py`; v0.30.0.*
