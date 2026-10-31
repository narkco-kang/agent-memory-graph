# Decision #38

[← decision log](../DECISIONS.md) · status: active

**The verification bridge may not have its own green light.** A foreign graph with one verified legacy string and zero anchored conclusions got `healthy`
from the bridge while the same run printed `0/20 verified, 20 unanchored`, and `healthcheck
--strict` on the same file was red. Decision: the bridge judges with
`verdict_of(require_full_anchoring=True)` — `healthy` requires every done conclusion to be
anchored, otherwise `partially_verified` (exit 3); verified legacy `path:#sha256:` strings
count as anchoring; the bridge gains `--strict`, which can raise debt but never turn a
failure into a pass. Two postures, documented: `healthcheck` keeps the debt posture for its
own repository, the bridge verifies graphs it did not write. Cost: two vocabularies for the
same words, stated in `docs/OPERATIONS.md`.
*Signed 2026-10-31; `tests/test_verify_snapshot.py`; v0.28.0.*
