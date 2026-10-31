# Decision #31

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; `tests/test_evidence_verify.py`; v0.20.0.*

**Evidence hashes are declared, not proven — disclose and make them observable.**
    `content_sha256` is caller-supplied; the gate checks shape only, so a fabricated hash
    is accepted and wins the `anchor_state == "present"` sort key
    (`issue.mem-arch-evidence-sha-forgeable`). v0.20.0 ships disclosure (`docs/API.md`,
    `docs/THREAT-MODEL.md`: `present` means *declared*) and `amg verify-evidence`:
    re-hashes `path:` locators, exit 1 on mismatch, `cmd:`/`url:`/`sha256:` reported
    `unverifiable`, never a pass. Not shipped: per-read verification, an `anchor_state`
    verified/claimed split, any claim `--strict` means verified.
    *Signed 2026-10-31; `tests/test_evidence_verify.py`; v0.20.0.*
