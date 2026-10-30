# Changelog

All notable changes to this project are documented here.
The format follows Keep a Changelog, and this project adheres to SemVer.

## [Unreleased] — 0.3.0

### Added

- **MCP server over stdio** (`amg mcp <dir>`): eight tools over newline-delimited
  JSON-RPC 2.0, no network listener, no authentication (stated plainly). Every
  tool reuses the library entry points, so the evidence gate applies unchanged.
- **Opt-in read-side audit**: `--audit-read` records high-risk reads (L4 rules,
  strict queries, results touching superseded nodes) to a bounded, rotated
  `reads.jsonl` — deliberately not in `changes[]`.
- **Windows and macOS are tested, not assumed**: CI runs the suite on
  `ubuntu-latest`, `macos-latest` and `windows-latest`; the lock has a `msvcrt`
  implementation with a cross-process exclusivity test.
- `docs/SCHEDULING.md`: cron/systemd usage, rollback, and why there is no daemon.

### Fixed

- Windows: cp1252 console crashed on status glyphs; directory `fsync` raised
  `PermissionError` on non-POSIX filesystems.

## [0.2.0] — 2026-10-30

Adds explicit fact time, opt-in expiry, batch ingest, a CLI for `supersede`, and
edge traversal. Every claim below is measured or covered by the test suite;
capabilities that are absent stay under **Not yet**.

### Added

- **Windows and macOS support is now tested, not assumed**: CI runs the suite on
  `ubuntu-latest`, `macos-latest` and `windows-latest`; the write lock has a
  `msvcrt` implementation and a cross-process exclusivity test.

- **Read-side audit (opt-in)**: `--audit-read` on `search` / `related` records
  high-risk reads (L4 rules, strict queries, results touching superseded nodes)
  to a bounded, rotated `reads.jsonl`. Deliberately not written into `changes[]`,
  which is the write ledger and can never be rotated.

- **Explicit fact time**: `amg add --valid-from ISO8601 [--valid-until ISO8601]`
  and `Memory.add_node(valid_from=…, valid_until=…)`. Values are stored verbatim;
  `valid_time_known` is true only when `valid_from` was supplied.
- **`amg expire <dir> [--apply]`**: opt-in expiry. Dry-run by default, supersedes
  instead of deleting, idempotent, skips nodes with unknown validity and counts
  them, so a migrated graph has zero eligible nodes. No background scheduler.
- **Batch ingest**: `amg import <dir> --from FILE.json` and
  `Memory.add_many(nodes, edges)`. All-or-nothing: every node and edge passes the
  same gates before the file is written; a single bad record leaves the graph
  byte-identical. 10,000 nodes in 0.10 s (previously computed at 6–7 minutes one
  by one).
- **`amg supersede <dir> OLD NEW --note`**: the core protocol operation is now
  reachable from the CLI, not just the library.
- **Edge traversal**: `amg related <id> [--depth N] [--kind K]` and
  `search --expand` (1-hop neighbors marked `expanded_from`, with `--strict`
  still applying). `depends_on` / `supersedes` must form a DAG — a cycle is a
  `check` error; other edge kinds may cycle and are only counted as a hint.
- `docs/BENCHMARKS.md`: read paths at 1k/5k/10k, per-write scaling, batch ingest,
  and traversal latency on a 10k-node / 10k-edge graph.
- `CONTRIBUTING.md`, `SECURITY.md`, and a public roadmap as GitHub issues.

### Changed

- **`valid_from` no longer defaults to the write time.** Omitting it means
  unknown (`null`, `valid_time_known: false`). The transaction-time proxy was
  measured to mis-date lagged facts by exactly the writing lag (20/20 records by
  more than a day) — see `experiments/valid_from_bias/`.
- `digest` header reports both exclusion counts
  (`superseded excluded: N, not yet valid excluded: M`).
- Nodes written by 0.1.0 keep their stored `valid_from`; the new rule applies to
  new writes.
- CLI: 16 commands, exit codes 0/1/2/3 from an explicit table with no default
  branch (an unclassified error raises instead of guessing).

### Fixed

- Retrieval and digest returned `superseded` nodes. Now hard-filtered in L1/L3/L4
  and in the digest; history stays reachable through L2.
- Missing-graph errors returned exit code 1 instead of the contractual 2, and
  unknown-enum errors were classified inconsistently. Both now follow the table.
- `evidence.grade` accepted booleans (a subclass of `int`), which landed `true`
  on disk instead of a grade.

### Enforced, not just documented

- Expiry requires a **known** validity window (`amg.audit.expiry_eligible`); an
  unknown window is a hint, never an automatic expiry.
- `amg adopt` still refuses to infer validity time.
- The documentation↔code gate fails the build when a documented capability has no
  symbol, or when a new error code is not classified; both are mutation-tested.

### Measured

- 119 unit tests, examples (`quickstart.sh`, `lifecycle.sh`) and the symbol gate
  run in CI on Python 3.10 / 3.12.
- Read paths at 10,000 nodes / 10,000 edges: `check` 65.5 ms, `audit` 63.2 ms,
  `search` 83.5 ms, `digest` 62.9 ms. `related` depth 1: 8.1 ms.
- Batch ingest: 10,000 nodes in 0.10 s. Single writes remain O(n) per write.

### Not yet (do not assume)

- Vector / embedding retrieval (lexical only).
- MCP server, authentication, multi-tenancy.
- Background expiry scheduling. `valid_until` is only acted on by `amg expire`.
- Concurrency stress beyond the advisory lock; graphs above 10,000 nodes.
- Python 3.10/3.12 are exercised in CI only; local runs used 3.15.

## [0.1.0] — 2026-10-29

First public release.

- Append-only single-file store: advisory lock, full-graph write, atomic replace.
- Four enforced invariants (IR-1..IR-4) including "a conclusion-typed node cannot
  be `done` without evidence objects".
- Evidence contract with real `content_sha256`; bare strings rejected.
- Bi-temporal `supersede` (old node kept, validity window stamped).
- Lexical L1/L2/L3/L4 retrieval with `anchor_state` and `--strict`.
- Pointer-only bounded digest; audit with legacy coverage pin.
- `amg adopt` for migrating legacy graphs without fabricating evidence.
- 13 CLI commands, 73 tests, documentation↔code symbol gate.
