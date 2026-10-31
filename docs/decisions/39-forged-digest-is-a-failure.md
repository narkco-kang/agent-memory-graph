# Decision #39

[← decision log](../DECISIONS.md) · status: active

**A forged digest is a failure, not an untested claim.** A legacy `path:x#sha256:<forged>` produced `UNVERIFIED` exit 3 — the same code as declaring
no digest at all, so a toxic claim and an absent one were indistinguishable without
`--strict`. Decision: a legacy `mismatched` digest enters `problems` (exit 1); a malformed
`#sha256` stays a warning because it declared nothing verifiable; and `done` and `conclusions`
now use one ruler (`has_evidence`, which counts a verified legacy string), which moved the
team's own graph from 292 to 108 done-without-evidence. Cost: graphs with stale digests go
from exit 3 to exit 1, which is louder.
*Signed 2026-10-31; `tests/test_verify_snapshot.py`; v0.29.0.*
