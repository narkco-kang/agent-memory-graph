# Decision #21

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; three tests in `tests/test_audit.py`.*

**The staleness threshold is policy, not a constant.** `STALE_DAYS = 3` was a
    guess baked into the code; on the first live graph it produced three conflicts at
    3 days, one at 7 and none at 14. A weekly-sync team sees false alarms at the
    default, a monthly team none. So the default stays 3 (the original rule, no
    surprise for existing users) and the threshold becomes `AMG_STALE_DAYS` (integer,
    `0 < x <= 365`, invalid falls back to 3) plus `audit --stale-days N` for a single
    run. Fallback rather than "disable": a typo must not silently turn the check off.
    Same shape as DECISIONS #16 for the lock timeout, for the same reason — the
    library serves teams with different cadences and cannot infer them.
    *Signed 2026-10-31; three tests in `tests/test_audit.py`.*
