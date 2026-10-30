# Changelog

All notable changes to this project are documented here.
The format follows Keep a Changelog, and this project adheres to SemVer.

## [0.7.5] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. It turns the
real-world measurement into a re-runnable script and adds a second live graph, so the
published numbers are no longer one graph's anecdote.

### Added

- **`benchmarks/real_graph.py`** — runs the whole `REAL-WORLD.md` measurement against
  any `group-kg/v1` graph: adopt, check, audit (with and without the pin), expire,
  fingerprint, doctor, search, digest, related and one write, then prints the table.
  In-process timings, matching the published run; CLI startup (~48–51 ms) is measured
  and reported separately so the two are never mixed. It verifies the source
  `sha256` before and after and prints **aggregates only** — no ids, labels, notes or
  query strings.
- **A second live graph in `docs/REAL-WORLD.md`**: this project's own bookkeeping
  graph, 187 nodes / 152 edges / 429 changes / 0.44 MB, chosen because its shape is
  different — 172 of 187 `done` nodes carry legacy evidence, no node has a validity
  window, and it is 35× smaller. Adopt 6 ms, check 0 errors in 0.4 ms, audit 172
  conflicts → **0** with the pin, one write **4 ms**.

### Changed

- **`docs/REAL-WORLD.md` records that its numbers move, with evidence.** Re-running
  the script on the first live graph a few hours later (rev 2,570 → 2,604) gives
  1,282 nodes, adopt 142 ms, one write 153 ms, and **pinned conflicts 3 → 4** — time
  passed, so staleness grew. A tool reporting a constant there would be reporting
  the wrong thing.
- The page now states which numbers are **shape-dependent** (IR-4 conflict count
  tracks legacy evidence format, write cost tracks file size at ~10 ms/MB) and which
  are flat (single-digit-millisecond reads on both graphs).

### Not shipped in 0.7.5 (do not assume)

Unchanged from 0.7.4 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.4] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. It makes the
project's own checks one command, and turns the resource-leak cleanup of 0.7.3 into
something CI enforces.

### Added

- **`tools/verify.py`** — runs every self-check in one command and prints one table:
  unit tests (with `ResourceWarning` promoted to an error), the documentation↔code
  gate, both end-to-end examples, the MCP client, and the artifact check when
  `dist/` exists. A skipped step is printed as skipped and never counted as a pass.
  `docs/README.md` now leads with it instead of listing six commands with no order.

### Changed

- **CI promotes `ResourceWarning` to an error** in both the platform test matrix and
  the suite run from inside the sdist. The leaks were cleaned in 0.7.3 (90 warnings
  per Windows run → 0); this keeps them from returning, and it is the same flag
  `verify.py` uses, so CI and a local run check the same thing.

### Not shipped in 0.7.4 (do not assume)

Unchanged from 0.7.3 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.3] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. It adds the
scenario a team actually has — several long-lived MCP processes plus a CLI command
writing one file — and records what the test can and cannot prove.

### Added

- **`tests/test_mcp_concurrency.py`**: two stdio MCP servers (5 writes each) and one
  thread running 5 `amg add` subprocesses, with a fourth thread running `amg check`
  while the writes land. Asserts on every commit and on all four test platforms:
  15 nodes for 15 writes with no duplicates, **exactly one `changes[]` record per
  write**, `check --strict` clean, and no writer *or reader* reporting an error (a
  refusal fails the test instead of being swallowed).
- **`docs/CONCURRENCY.md`** gains "Three writers over two protocols", including one
  limit measured rather than assumed: reverting `Memory.open` to the pre-v0.6.0
  unlocked read leaves the test **green on macOS**, because POSIX lets you replace an
  open file. The test is a regression guard for Windows specifically, and the doc
  says so instead of implying it is platform-neutral.

### Not shipped in 0.7.3 (do not assume)

Unchanged from 0.7.2 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.2] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. This release
adds the first end-to-end proof that another process can actually use the MCP
server, and closes the last install-matrix gap.

### Added

- **`examples/mcp_client.py`** — a working MCP client in the standard library only.
  It starts `amg mcp` twice and asserts, end to end: the handshake returns the
  server's identity; `tools/list` advertises exactly the eight documented tools; an
  evidence-free `done` write is **refused over JSON-RPC** (`E_EVIDENCE_MISSING`,
  `isError: true`) — the write gate is not a CLI feature that MCP can walk around;
  a valid write succeeds and `memory_search` finds it; a `--read-only` server
  advertises five tools and refuses the same write with `E_READ_ONLY`; and
  `amg check --strict` passes on the graph the server wrote. CI runs it on every
  push, on all four test platforms. The protocol tests check frames; this checks
  whether the thing is usable.
- **`examples/*.py` are shipped in the sdist** (previously only `*.sh`), and
  `tools/check_dist.py` now requires `examples/mcp_client.py` to be present.

### Changed

- **The `package` job now covers macOS, and the minimum Python on two platforms**:
  ubuntu / macos / windows on 3.12, plus ubuntu and windows on 3.10. Nine CI jobs.
  macOS previously had only an editable install, so the wheel had never been
  installed there either.

### Not shipped in 0.7.2 (do not assume)

Unchanged from 0.7.1 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.1] — 2026-10-30

A packaging release: **no library behaviour changes**. It exists because the sdist
published with 0.7.0 could not run the tests it contained.

### Fixed

- **The sdist was incomplete.** With no `MANIFEST.in`, `python -m build` shipped
  `src/` and `tests/` but not `docs/`, `tools/`, `experiments/`, `examples/` or
  `benchmarks/`. Running the shipped suite from the unpacked archive gave **17
  errors and 4 failures — every one of them file-not-found** (`docs/API.md`,
  `tools/check_doc_symbols.py`, the experiment scripts). The wheel was unaffected,
  which is why install-only verification missed it. `MANIFEST.in` now carries
  everything the tests read; the sdist goes 70 KB → 376 KB, and its own **190-test
  suite passes from inside the unpacked archive**.
- **License metadata modernised.** `license = {text = "MIT"}` is deprecated
  (PEP 639; setuptools warns that builds stop working after 2027-02-18). Now
  `license = "MIT"` with `license-files = ["LICENSE"]`, build requires
  `setuptools>=77`, and the wheel metadata carries `License-Expression: MIT`.

### Added

- **`tools/check_dist.py`** — checks the built artifacts, deriving its expectations
  from the working tree: every module in `src/amg/` must be in the wheel, the
  entry point must be `amg = amg.cli:main`, the metadata must carry an SPDX licence,
  and the sdist must contain every `docs/*.md`, the tools, examples and experiment
  scripts its own tests read. Against 0.7.0's first sdist it reports **20
  problems**; against the fixed build it is clean.
- **CI job `package`** — builds sdist and wheel, runs `check_dist.py`, installs the
  wheel into a fresh venv, then unpacks the sdist and runs its shipped test suite.

### Not shipped in 0.7.1 (do not assume)

Identical to 0.7.0 — nothing was added to the library: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in
the default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.0] — 2026-10-30

A small release: one operational knob, one design note, and a reading index. The
on-disk format is unchanged (`amg/v1`); nothing here needs a migration.

### Added

- **`docs/DESIGN-HISTORY.md`**: the write-cost fix, designed before it is built —
  and the obvious version of it rejected with measurements. A history sidecar would
  cut writes 147 ms → ~27 ms, but `changes[]` records are descriptions rather than
  replayable operations, so a split store gains a crash window that can only be
  detected, never repaired. The sanctioned direction is zlib-sealed history segments
  inside the single atomic file: −54% size (15.6 MB → 7.2 MB), write ~60 ms,
  11 ms to decompress on read, atomicity intact, at the cost of text-greppable
  history and an `amg/v2` format bump. Not built; DECISIONS #17 records why and the
  trigger.

- **`AMG_LOCK_TIMEOUT`** (seconds, clamped to `(0, 3600]`, nonsense falls back to
  5 s) — because the default is now known to be load-dependent rather than safe:
  on the real 15.6 MB graph a write costs ~147 ms, so 5 s covers about 34 queued
  writes and 8 writers × 5 writes times out (measured; the run aborted). The
  timeout error names the variable. Fairness would not fix it — the queue still has
  to drain — which is now stated with arithmetic in `docs/CONCURRENCY.md`.

- **`docs/README.md`**: a reading index, because a folder of measurements is worse
  than useless if the document describing a *proposal* is read as a feature.
  Every document is tagged measured / contract / proposal / decision / operational,
  and there is a reading order per intent (deciding, using, changing storage,
  auditing claims). A test fails if a document is added without being indexed.

- **The documentation↔code gate now scans every document by default**
  (`tools/check_doc_symbols.py` with no arguments reads `README.md` and every
  `docs/*.md`). CI used to pass a fixed list of two files; documents were added and
  the gate kept checking the same two, so the gate was green about a shrinking
  share of the docs. The list is now derived, and a test asserts the default covers
  every document. The success line also names the files it checked, so "12 files"
  is auditable rather than a number to trust.

### Fixed

- **A stale command count in the README.** It said `cli.py` has "16 commands";
  `COMMANDS` has had 20 since `fingerprint`, `verify` and `doctor` landed — a
  number nobody re-checked. Replaced with a pointer to `docs/API.md`, and a new
  test asserts that every command in `COMMANDS` appears in `docs/API.md`, so an
  undocumented command now fails the build. (The same class of error as the 0.3.0
  false-absence claims: green tests cannot catch a number that is merely old.)

### Not shipped in 0.7.0 (do not assume)

Unchanged: authentication/authorization/multi-tenancy (out of scope by decision),
vector retrieval in the default path (measured, rejected), tamper *proof*, TTL
scheduler, encryption at rest, lock fairness. **History compression — the subject
of `docs/DESIGN-HISTORY.md` — is not built**: it is a design with a trigger, not a
capability, and the document says so in its first line.

## [0.6.0] — 2026-10-30

### Fixed

- **Windows: a reader could make a concurrent writer fail.** `os.replace` cannot
  replace a file another process has open, and `Memory.open` read the graph without
  the lock, so one agent's startup read could turn another agent's atomic write into
  `PermissionError [WinError 5]`. `Store.read_locked()` now reads under the lock and
  `Memory.open` uses it; opening a missing graph still creates nothing
  (`LockedReadTests`). Found by the new concurrency test on Windows CI, not by a
  user.

### Changed

- **Lock retry now backs off with jitter** (`LOCK_POLL_START_S` 1 ms doubling to a
  16 ms ceiling) instead of sleeping a flat 20 ms. Measured effect on an 8-writer
  burst: throughput ~700 → ~870 writes/s, p50/p95 unchanged, **tail unchanged**
  (168–199 ms). The change is kept for the throughput, not for the tail — see the
  diagnosis in `docs/CONCURRENCY.md`.
- **The contention tail is diagnosed, not hypothesised**: `Store.lock_stats`
  (observation only) shows the worst waiter loses only ~15 polls while the other
  seven writers complete ~200 writes, and its wait matches the whole burst — i.e.
  starvation from non-FIFO `flock` wakeups, not the polling interval. Fairness was
  not implemented; the open issue records the numbers and the trigger.

### Added

- **Concurrency burst test** (`experiments/concurrency/run_stress.py`,
  `docs/CONCURRENCY.md`): 8 processes × 25 writes against one graph, three runs —
  **200/200 nodes present, 0 duplicates, 0 lost, exactly one change record per
  write, `check` clean, no lock timeouts**. Throughput is unchanged by contention
  (~700 vs ~640 writes/s) because the lock serialises the critical section, but the
  latency tail is ~240 ms against a ~1 ms median. The cause of that tail is stated
  as a hypothesis (unfair `flock` wakeups plus 20 ms polling), not a finding, and
  the counters needed to prove it do not exist yet.
- `tests/test_concurrency.py`: a 3×3 version of the same four properties runs on
  every commit, including Windows.

### Not shipped in 0.6.0 (do not assume)

Unchanged: authentication/authorization/multi-tenancy (out of scope by decision),
vector retrieval in the default path (measured, rejected), tamper *proof*, TTL
scheduler, encryption at rest, and write-path speed work (priced, deferred).
Lock **fairness** is also not implemented — the starvation tail is diagnosed and
documented, not fixed (DECISIONS #15).

## [0.5.0] — 2026-10-30

**A measurement release: no behaviour changes.** Every claim below is a number
taken on a live graph or a priced option, and nothing in `src/amg/` changed except
the version string. If you are upgrading for features, there are none.

### Added

- **Write-cost analysis** (`docs/WRITE-COST.md`): on the live 15.6 MB graph,
  `changes[]` is **79.1%** of the bytes and a write is 148 ms = parse 75 +
  render 50 + `fsync` 23. Four options are priced with measurements: cold-archive
  reclaims nothing (oldest node 6 days, 0 candidates), compact JSON saves 2.4% and
  costs git diffability, incremental writes abandon the atomicity guarantee, and a
  history sidecar would cut writes ~80% at the cost of the single-file property.
  Nothing was built: the existing trigger (p95 > 250 ms / 20 MB / 10k nodes) is
  two-thirds away and the analysis is recorded so the decision does not need
  rediscovering.

- **Real-graph measurements** (`docs/REAL-WORLD.md`): a live 1,249-node / 15.3 MB
  graph adopted in 140 ms with the source `sha256` unchanged, `check` clean in
  4.4 ms, `audit` 1,029 conflicts before the exemption pin and **3 after** (all
  genuine staleness), `audit --pin` report `match: true`, `expire` correctly inert
  (no node carries `valid_until`), reads in single-digit milliseconds, and a
  single write at **147 ms** — the number behind the cold-archive trigger, now
  measured on real data instead of projected from a synthetic benchmark.
  Aggregates only: no node ids, labels or notes are reproduced.

### Not shipped in 0.5.0 (do not assume)

Unchanged from 0.4.0 — this release added no capability:

- Authentication / authorization / multi-tenancy (out of scope by decision).
- Vector retrieval in the default path (measured and rejected; optional extra only).
- Tamper *proof* (`fingerprint`/`verify` detect; the losing cases are tabulated).
- TTL scheduler (`amg expire` is a command; no daemon).
- Encryption at rest (`graph.json` is plain text by design).
- Write-path speed work: priced in `docs/WRITE-COST.md`, deliberately not built —
  the trigger (p95 > 250 ms / 20 MB / 10k nodes) is still ahead of the live graph.

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
