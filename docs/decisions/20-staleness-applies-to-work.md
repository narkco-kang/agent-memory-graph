# Decision #20

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30; four tests in `tests/test_audit.py`.*

**Staleness applies to work, not to registrations.** The audit rule "an
    `in_progress` or `blocked` node untouched for 3 days is stale" assumed every node
    is a short-lived work item. On the first live graph it flagged a `group` node
    that had been `in_progress` for 7 days — correct by the letter, noise in
    practice: a group registration is long-lived, and its `updatedAt` does not move
    when its children change. `group`, `env` and `member` are now exempt
    (`LONG_LIVED_TYPES`), while an unknown type is still checked: exemptions are
    explicit so that a new kind of work cannot become invisible by omission. Three of
    the four original conflicts were genuine work items and remain reported.
    *Signed 2026-10-30; four tests in `tests/test_audit.py`.*
