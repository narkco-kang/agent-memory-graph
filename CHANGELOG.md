# Changelog

All notable changes to this project are documented here.
The format follows Keep a Changelog, and this project adheres to SemVer.

## [0.4.0] — 2026-10-30

### Notes

- Every "not implemented" claim in the docs was re-run against the code before
  this release (the rule from 0.3.0): no authentication code, no scheduler or
  thread, no socket, no encryption, no embedding in `src/amg/`. The only matches
  for `auth`/`token`/`socket` are the sentences asserting their absence and a
  tokeniser named `_TOKEN`.

### Not shipped in 0.4.0 (do not assume)

- **Authentication / authorization / multi-tenancy.** Decided out of scope with
  reasoning and alternatives (THREAT-MODEL §8, DECISIONS #13), not deferred.
- **Vector retrieval in the default path.** Measured: a local `nomic-embed-text`
  candidate lifts paraphrase `recall@5` 0.750 → 0.950, but misses the
  pre-registered bar in one stratified half and cannot ship as a dependency-free
  default. Optional extra only, and nothing is shipped.
- **Tamper *proof*.** `fingerprint`/`verify` detect edits; a determined attacker
  who can write the file and your stored digest wins (§7a, last two rows).
- **TTL scheduler.** `amg expire` is a command; no daemon.
- **Encryption at rest.** `graph.json` is plain text by design.

### Added

- **Filesystem hygiene checks**: `amg doctor` reports `SEC_WORLD_WRITABLE`,
  `SEC_GROUP_WRITABLE`, `SEC_NETWORK_PATH` and `SEC_GRAPH_SYMLINK` — the
  conditions under which this project's only boundary (file permissions) does not
  hold. `amg doctor --strict` exits 1 (`E_INSECURE_GRAPH`) on a warning; `amg mcp`
  prints the warnings to stderr at startup and keeps serving.

### Changed

- **Authorization decided out of scope** (docs/THREAT-MODEL.md §8, DECISIONS #13):
  no authentication, no per-caller authorization, no multi-tenancy. A token check
  in front of a file the caller can open proves only that they have the file; what
  would actually hold (users, containers, ACLs, read-only mounts) is enforced by
  the OS. The decision lists what to do instead, and the three conditions that
  would reopen it.
- **Semantic retrieval measured, not guessed** (`experiments/retrieval_eval/`):
  a local `nomic-embed-text` candidate (768 dims via ollama) lifts paraphrase
  `recall@5` from 0.750 to 0.950 and `recall@1` from 0.400 to 0.625 with no
  keyword regression — real, measured, and still **not adopted**: one stratified
  half gains +0.100 against a +0.20 bar, and C3 keeps a 274 MB model out of the
  default path of a zero-dependency library. An earlier claim in this repo that
  the semantic arm was "not measurable here" was wrong (a local model was already
  installed); that correction is recorded in the experiment README.
- **Prior art verified in full text** (`docs/PRIOR-ART.md`): MAP-Graph
  (arXiv:2608.10509) already implements and ablates the two ideas this project
  had listed as its own direction, so both are conceded as prior art rather than
  presented as design commitments. The check also established the boundary we may
  cite: the paper states it has "no generic supersession or conflict-resolution
  state machine", and an expiry keyword scan returns nothing. README's "task
  scope" wording was wrong for that paper and is corrected to "scoped access and
  an action-level risk gate".

### Added

- **`amg fingerprint` / `amg verify`**: canonical `state_sha256` (nodes+edges,
  order independent) and `history_sha256` (`changes[]`, in order), plus a verify
  command that exits 1 on mismatch. Keeping them separate is what makes a silent
  edit visible: changing a node in the file moves state and leaves history alone.
  Read-only — `verify` writes nothing, proven by comparing file bytes.
- `docs/THREAT-MODEL.md` §7a states the exact limits, including the row where a
  determined attacker wins, and DECISIONS.md #11 records why there is no in-file
  hash chain over `changes[]` (it would look stronger than the external digest
  while being weaker, because the attacker regenerates it in one pass).

## [0.3.0] — 2026-10-30

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
- **Read-only mode** (`amg mcp <dir> --read-only`, `Memory.open(dir, read_only=True)`):
  write tools are refused with `E_READ_ONLY` before dispatch, only the five read
  tools are advertised, and the underlying `Memory` refuses every commit, so the
  guarantee does not depend on the tool list staying correct. Verified by a
  digest-before/after test that attempts every write tool.
- `docs/THREAT-MODEL.md`: assets, trust boundaries, actor model, threat table,
  what read-only does not cover, and the accepted risks (no tamper evidence,
  read tools unthrottled, same-user file access).
- **Pre-registered retrieval evaluation** (`experiments/retrieval_eval/`): 27-node
  corpus, 26 labelled queries, measured baseline (overall `recall@5` 0.865;
  paraphrase bucket 0.750) and a written acceptance bar a vector retriever must
  clear before it may ship. Buckets are computed from measured token overlap, not
  from declared intent; `tests/test_retrieval_eval.py` locks the baseline numbers.
- **Two zero-dependency retrievers measured and rejected** (`bm25`, `hashed-vec`).
  Both lose to the shipped substring scorer on paraphrase `recall@5`
  (0.750 baseline vs 0.450 / 0.550) and `bm25` also trips the keyword-regression
  guard, so neither ships. The purpose of the experiment was to make that
  rejection possible; the shipped retriever is unchanged and still lexical only.
  A semantic candidate could not be measured here: the available embedding API
  answers `429 {"code":"1113"}` (no covered resource) and no local model is
  installed.
- `docs/SCHEDULING.md`: cron/systemd usage, rollback, and why there is no daemon.

### Fixed

- Windows: cp1252 console crashed on status glyphs; directory `fsync` raised
  `PermissionError` on non-POSIX filesystems.

### Notes

- `E_READ_ONLY` is classified as exit `2` (wrong call), not `1` (bad content):
  the same class as `E_ALREADY_AMG`. The exit-code table has no default, so an
  unclassified code still fails loudly.
- README corrections: it still said read-side audit and read-only were not
  implemented, and used a `grep risk` "no matches" proof that stopped being true
  when read-audit added `is_high_risk`. Both now describe the shipped state, and
  the remaining design-only claims carry commands that were actually run.
- Changelog correction: two bullets (Windows CI, read-side audit) had been
  inserted into the already-released **0.2.0** section by mistake. Both features
  landed after the `v0.2.0` tag, so they belong to 0.3.0 only; the 0.2.0 section
  now matches what that tag actually contained.

### Not shipped in 0.3.0 (do not assume)

- **Vector / embedding retrieval.** Two zero-dependency candidates were measured
  and both were **rejected** (paraphrase `recall@5` 0.450 / 0.550 against the
  lexical baseline 0.750). A semantic candidate was not measurable here: the
  available embedding API answers `429 {"code":"1113"}` and no local model is
  installed. Retrieval is still lexical only.
- **Authentication and multi-tenancy.** Read-only mode limits one session's blast
  radius; it does not authenticate anyone, and there is no per-caller
  authorization or tenant separation.
- **Tamper-evident history.** `changes[]` is append-only by API, not
  cryptographically. A process with file access can rewrite it undetected.
- **TTL scheduler.** `amg expire` is an explicit command; there is no daemon and
  no background thread.
- **Encryption at rest.** `graph.json` is plain text by design.

See `docs/THREAT-MODEL.md` section 8 for the reasoning behind the last three.

## [0.2.0] — 2026-10-30

Adds explicit fact time, opt-in expiry, batch ingest, a CLI for `supersede`, and
edge traversal. Every claim below is measured or covered by the test suite;
capabilities that are absent stay under **Not yet**.

### Added

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
- MCP server, authentication, multi-tenancy, read-side audit logging.
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
