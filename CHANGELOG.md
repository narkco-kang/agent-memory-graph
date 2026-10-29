# Changelog

All notable changes to this project are documented here.
The format follows Keep a Changelog, and this project adheres to SemVer.

## [0.1.0] — unreleased (private review)

First working version. Everything below is verified by the test suite on disk;
capabilities that are absent are listed under **Not yet**.

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
- 12 (v0.1) + 1 (`adopt`) CLI commands, exit codes 0/1/2/3 with an explicit
  classification table (no default branch; an unclassified error raises).
- CI: 68 unit tests, a documentation↔code symbol gate (with mutation tests
  proving the gate can fail), and an end-to-end quickstart script.

### Fixed

- Retrieval and digest returned `superseded` nodes (violating the
  "expiry is a first-class citizen" rule). Now hard-filtered; history stays
  reachable through L2.
- Missing-graph errors returned exit code 1 instead of the contractual 2.

### Not yet (do not assume)

- Vector / embedding retrieval (lexical only).
- MCP server, authentication, multi-tenancy, read-side audit logging.
- TTL-based automatic expiry. `valid_until` is stored and audited, never
  auto-applied.
- Windows file locking (POSIX `fcntl` only; untested on Windows).
- Any benchmark above 1,063 nodes; `adopt` has no concurrency stress test.
- Python 3.10/3.12 are only exercised in CI; local runs used 3.15.
