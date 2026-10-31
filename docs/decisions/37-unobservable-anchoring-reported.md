# Decision #37

[← decision log](../DECISIONS.md) · status: active

**Thin anchoring is reported, never silent.** One anchored conclusion plus nineteen `cmd:` conclusions (5% coverage) printed `healthy`,
exit 0, zero warnings, because the verdict key was “at least one verified”. Decision:
`conclusions` gains `unobservable` (evidence present but not observable), the line prints
`1/20 verified (5%), 0 unanchored, 19 unobservable`, that raises a warning and fails under
`--strict`; `--no-evidence` prints `not checked` rather than a 0% rate. Cost: a third
bucket to explain, and a warning on graphs that used to look clean.
*Signed 2026-10-31; `tests/test_verify_snapshot.py`; v0.27.0.*
