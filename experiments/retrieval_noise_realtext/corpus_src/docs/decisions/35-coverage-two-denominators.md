# Decision #35

[← decision log](../DECISIONS.md) · status: active

**A coverage rate needs two denominators, and “not checked” is not a rate.** v0.24.0 printed `1 declared / 1 verified (100%)` while ten conclusion nodes carried no
evidence at all, and `--no-evidence` printed a healthy verdict for a check that never ran.
Decision: `healthcheck` prints three numbers (`evidence rows`, `conclusions anchored`,
`done nodes without evidence`); `--no-evidence` reports `not checked`; `--allow-unverified`
relaxes the exit code only and is recorded as `unverified_accepted`. Cost: three numbers
instead of one headline, because no single percentage is a health claim.
*Signed 2026-10-31; `tests/test_healthcheck.py`; v0.25.0.*
