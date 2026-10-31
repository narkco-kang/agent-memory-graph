# Decision #32

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; tests; v0.21.0.*

**v0.20.0's verifier leaked the graph root; `--include-archive` starved.** Fixed
    in v0.21.0 with tests. (a) `path:` evidence could leave the graph root
    (absolute/`..`/symlink), making a public store a content oracle: it must now resolve
    inside, escapes are `outside_root` and never hashed.
    (b) `--strict` ignored `unverifiable` and JSON said `ok: true` on a strict exit 1: the
    report separates `ok` (nothing violated) from `all_verified` (all matched);
    `--strict` requires the latter; `not_a_file`/`unreadable`/empty are explicit, not
    green. (c) `--include-archive` returned zero archived hits when `k` live records
    matched: from `k >= 5` it keeps `max(1, k // 5)` slots, one per file first; below 5,
    unchanged. *Signed 2026-10-31; tests; v0.21.0.*
