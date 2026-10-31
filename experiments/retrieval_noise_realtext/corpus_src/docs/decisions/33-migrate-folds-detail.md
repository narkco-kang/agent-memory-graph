# Decision #33

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; `tests/test_migrate.py`; v0.22.0.*

**`amg migrate` folds legacy `detail` into `note`; `check` stops advising a no-op.**
    A legacy-only key (`detail`) survived `migrate`, keeping a third `changes[]` shape
    (`changes-key-shapes`). `normalize()` now moves it into `note` (never drops it) and
    reports `folded_detail` and any `non_canonical_shapes` left; `check` distinguishes a *missing* rev (run migrate) from
    a *null* rev left by migrate (unknown by design). Idempotent: a second run reports
    `changed: 0`. *Signed 2026-10-31; `tests/test_migrate.py`; v0.22.0.*
