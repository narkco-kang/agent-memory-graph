# Changelog

All notable changes to this project are documented here.
The format follows Keep a Changelog, and this project adheres to SemVer.

## [Unreleased] — v0.2.0 scope (in progress)

CLI surface changes, so the next release is 0.2.0.

### Added (0.2.0)

- **Explicit fact time**: `--valid-from` / `add_node(valid_from=…)`. Absent means
  *unknown*, never the write time — the proxy bias was measured at 100% on lagged
  records and 0% on the control group (`experiments/valid_from_bias/`).
- **`amg expire`**: opt-in, dry-run by default, supersedes instead of deleting,
  idempotent, and it refuses nodes whose validity time is unknown.
- **Batch ingest**: `amg import` / `add_many` — all-or-nothing, one atomic write;
  10,000 nodes in 0.10 s.
- **`amg supersede`**: the core protocol operation is reachable from the CLI.
- **Edge traversal**: `amg related`, `search --expand`, and DAG checks for
  `depends_on` / `supersedes`.
- `docs/BENCHMARKS.md`: read paths to 10k nodes, write scaling, batch, traversal.


- Edge traversal: `amg related <id> [--depth N] [--kind K]` and `search --expand`
  (1-hop neighbors marked `expanded_from`). `depends_on` / `supersedes` cycles
  are a `check` error; other edge kinds may cycle and are counted as a hint.

- `amg import` / `Memory.add_many`: batch writes that validate the whole batch
  before touching the file (one load, N appends, one atomic replace), removing
  the quadratic cost of importing node by node.

- **Explicit fact time**: `amg add --valid-from ISO8601 [--valid-until ISO8601]`
  and `Memory.add_node(valid_from=..., valid_until=...)`. Values are stored
  verbatim; `valid_time_known` is `true` iff `valid_from` was supplied.
- `audit` reports a future `valid_from` as **"not yet valid"** (hint, not
  conflict); retrieval (L1/L3/L4) and `digest` exclude such facts, because they
  are not yet in effect.
- New error codes `E_BAD_VALID_TIME` / `E_BAD_VALID_RANGE` (exit 2), added to the
  explicit classification table and to `docs/API.md`.

### Changed

- **`valid_from` no longer defaults to the write time.** Omitting it means
  unknown (`null`, `valid_time_known: false`). This is the fix justified by
  `experiments/valid_from_bias/`: the transaction-time proxy mis-dates lagged
  facts by exactly the writing lag (20/20 > 1 day).
- `digest` header now shows both exclusion counts
  (`superseded excluded: N, not yet valid excluded: M`).
- Nodes written by 0.1.0 keep their stored `valid_from`; the change affects new
  writes only.

### Added (opt-in expiry)

- `amg expire <dir> [--apply]` and `Memory.expire(apply=False)`: explicit,
  opt-in TTL expiry. **Dry-run by default** (writes nothing); only nodes with a
  known validity window whose `valid_until` has passed and that are not already
  superseded; the action is `status: superseded` + `superseded_at` + one
  `expire` change record — **no node is ever deleted**; idempotent (second
  `--apply` = 0 changes); unknown validity is skipped and counted, so a migrated
  graph has zero eligible nodes. No background scheduler exists.

### Enforced, not just documented

- Expiry still requires a **known** validity window (`amg.audit.expiry_eligible`);
  an unknown window is a hint, never an automatic expiry.
- `amg adopt` keeps refusing to infer validity time.

## [0.2.0] — 2026-10-30

Adds explicit fact time, opt-in expiry, batch ingest and edge traversal. All claims
below are measured or covered by the test suite; absent capabilities stay under
**Not yet**.

### Added

- `Memory` — the single public entry point (`init`/`open`, `add_node`,
  `set_status`, `add_edge`, `supersede`, `search`, `check`, `audit`, `digest`,
  `migrate`, `adopt`, `export`).
- Append-only single-file store: advisory lock, full-graph write, atomic
  `os.replace`, fsync of file and directory. No delete API exists.
- Four enforced invariants: IR-1 append-only, IR-2 real `source`, IR-3 checked
  mutations, IR-4 conclusion-typed nodes cannot be `done` without evidence.
- Evidence contract: objects only — `locator` + `content_sha256` + `captured_at`
  (+ `graph_rev`, optional `grade` 1–5). Bare strings are rejected.
- Bi-temporal supersede: `valid_from` / `valid_until` (validity time) separated
  from `recorded_at` / `superseded_at` (transaction time). Old nodes are kept.
- Retrieval v0.1 (lexical only): layers L1/L2/L3/L4, two-key ranking
  `(anchor present, score)`, degraded hits returned with `anchor_state: "none"`,
  `--strict` as the only filter, `superseded` hard-filtered.
- Digest: pointer-only consolidation, byte-bounded, explicit
  `[truncated N items]` and `superseded excluded: N` markers.
- Audit: legacy coverage ratios, frozen sorted-id-sha256 exemption pin,
  staleness, expiry, dangling edges, `changes[]` key-shape detection.
- `amg adopt`: migrate legacy `group-kg/v1` graphs to `amg/v1` without
  fabricating evidence — legacy strings move to `legacy_evidence`, placeholder
  sources become `adopted:<schema>:<sha12>` provenance, inferred timestamps are
  flagged, identical duplicate edges are merged and counted.
- 16 CLI commands (v0.2 adds `import`, `expire`, `supersede`), exit codes 0/1/2/3 with an explicit
  classification table (no default branch; an unclassified error raises).
- CI: 68 unit tests, a documentation↔code symbol gate (with mutation tests
  proving the gate can fail), and an end-to-end quickstart script.

### Fixed

- Retrieval and digest returned `superseded` nodes (violating the
  "expiry is a first-class citizen" rule). Now hard-filtered; history stays
  reachable through L2.
- Missing-graph errors returned exit code 1 instead of the contractual 2.

### Measured

- Read paths at 1k / 5k / 10k nodes (`check`, `audit`, `search`, `digest`) and
  per-write cost at 100 / 1k / 5k — see `docs/BENCHMARKS.md`. Write path is O(n)
  per write, so bulk ingest is quadratic; batch ingest is not implemented.

### Not yet (do not assume)

- Vector / embedding retrieval (lexical only).
- MCP server, authentication, multi-tenancy, read-side audit logging.
- TTL-based automatic expiry. `valid_until` is stored and audited, never
  auto-applied.
- Windows file locking (POSIX `fcntl` only; untested on Windows).
- Any benchmark above 1,063 nodes; `adopt` has no concurrency stress test.
- Python 3.10/3.12 are only exercised in CI; local runs used 3.15.
