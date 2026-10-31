# Decision #34

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; `tests/test_healthcheck.py`; v0.24.0.*

**"Nothing was verified" is not "healthy".** v0.23.0's `healthcheck` treated
    `unverifiable` as neither problem nor debt, so an `adopt`ed graph (evidence emptied
    by design) or a `cmd:`-only graph printed `healthy`, exit 0; `--strict` missed it
    (`ATTACK-HEALTHCHECK-V023` §2.1–2.2). v0.24.0 adds verdict `unverified` + exit `3`,
    reports coverage (`verified/declared`), and counts `missing`/`not_a_file`/
    `unreadable` as problems. `--allow-unverified` relaxes the exit code only.
    *Signed 2026-10-31; `tests/test_healthcheck.py`; v0.24.0.*
