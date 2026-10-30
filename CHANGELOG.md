# Changelog

All notable changes to this project are documented here.
The format follows Keep a Changelog, and this project adheres to SemVer.

## [0.22.0] — 2026-10-31

One canonical `changes[]` shape after migration, a `check` that stops advising a no-op,
and documentation moved where it belongs to restore budget headroom.

### Fixed

- `amg migrate` folds the legacy `detail` key into `note` (moved, never dropped) and
  reports `folded_detail` plus any `non_canonical_shapes` left, so the three legacy
  `changes[]` shapes collapse to the canonical one (`changes-key-shapes`).
- `amg check` no longer prints "run `amg migrate`" for a `rev` that `migrate` left null on
  purpose; it reports the rev as unknown by design. The previous advice was a loop that
  could not help.
- **Documentation budget**: the adoption guarantee list moved from `docs/API.md` to
  `docs/ADOPTION.md`, and decisions #9/#10 detail to their owning docs. Both caps were
  1–9 bytes from failing `check_doc_sizes`; API now has 553 B and DECISIONS 33 B of room.

### Tests

293 tests (+3): `detail` folded not dropped and shapes canonical, post-migrate hint
wording, migrate idempotent.

## [0.21.0] — 2026-10-31

Three boundary defects in shipped behaviour, found by the post-release review and fixed
together: two in v0.20.0's verifier, one in `--include-archive` since v0.15.0.

### Security

- **`verify-evidence` no longer reads outside the graph root.** `path:` evidence with an
  absolute path, `..` or a symlink escape resolved to any file on the host, so a public,
  unauthenticated store could be used to hash files it does not own
  (`issue.mem-arch-evidence-locator-out-of-tree`). Paths must resolve inside the root;
  escapes are reported `outside_root`, never opened, and exit 1.

### Fixed

- **`--strict` and JSON no longer fake green**
  (`issue.mem-arch-verify-strict-unverifiable`, `...verify-evidence-boundaries`): `--strict`
  ignored `unverifiable`, and `--json` printed `ok: true` on a strict exit 1. The report
  now separates `ok` (nothing violated) from `all_verified` (every item matched);
  `--strict` requires the latter, and `not_a_file`, `unreadable` and an empty check are
  explicit outcomes instead of passes or crashes.
- **`--include-archive` is no longer starved by `k`** (`issue.mem-arch-archive-k-starve`):
  archived records are older by construction, so a time-ordered merge cut to `k` returned
  **zero** archived hits whenever `k` live records matched — the flag silently did
  nothing. From `k >= 5` the archive keeps `max(1, k // 5)` slots, one per archive file
  first, then recency; below 5 the previous order stands, so live-only searches are
  unchanged.

### Tests

290 tests (+10: 7 verifier boundary cases, 3 archive reservation cases), nine
CI jobs, `tools/verify.py` green.

### Not shipped in 0.21.0 (do not assume)

- No anchored "verified" state is persisted on nodes; `anchor_state: "present"` still
  means *declared*.
- No per-read verification, no search cache, no `verified`/`claimed` split.
- The archive reservation is a floor, not a guarantee that every archived file fits when
  more files than slots have matches.

## [0.20.0] — 2026-10-31

Closes the evidence-authenticity finding from the retrieval attack brief (E1 / `R3`):
declared evidence hashes become observable, and the limitation that stays is written down.

### Added

- `amg verify-evidence <dir> [--id ID] [--strict] [--json]` — hashes `path:` evidence
  locators (resolved against the graph directory unless absolute) and compares them with
  the declared `content_sha256`. Exit 1 on `E_EVIDENCE_MISMATCH`; `--strict` also fails
  on missing paths; `cmd:` / `url:` / `sha256:` locators are reported `unverifiable` and
  never count as passes. This is the first caller of `gate.sha256_of_file`, which existed
  unused since v0.1.
- `tests/test_evidence_verify.py` — 11 cases, including the original attack as an
  executable record: a fabricated hash is accepted by the write gate, still shows
  `anchor_state: "present"`, and is caught by `verify-evidence`.

### Disclosed, not fixed

- `content_sha256` is still **caller-declared**: the write gate validates shape, not
  bytes, so a fabricated hash still wins the retrieval sort key. `docs/API.md` and
  `docs/THREAT-MODEL.md` now state that `present` means *declared*.
- Not shipped: per-read verification (I/O on the hot path; referenced files move), an
  `anchor_state` `verified`/`claimed` split (a label without persisted verification), and
  any claim that `--strict` means verified.
- `cmd:` / `url:` evidence remains unverifiable offline — reported as such, never a pass.

## [0.19.1] — 2026-10-31

Patch: the documentation size gate measures content, not the checkout's line endings.

### Fixed

- `tools/check_doc_sizes.py` folds CRLF to LF before counting. v0.19.0's
  `windows-latest` job failed on `docs/DECISIONS.md` (24,450 B of content, ~300 B larger
  in a CRLF checkout) while the same tree passed on Linux and macOS — a red CI caused by
  `core.autocrlf`, not by length. Regression test: a CRLF document whose LF content is
  inside budget now passes on every platform (`tests/test_doc_sizes.py`).
- No document was trimmed to work around it, and the budgets are unchanged.

### Not shipped in 0.19.1 (do not assume)

- No product change; no document content change; identical behaviour to v0.19.0.

## [0.19.0] — 2026-10-31

Defect round for the two retrieval issues the attack brief registered (`R1`, `R2`):
**scores become bounded and labelled, and the change is measured to move no rank.**

### Changed

- `src/amg/retrieval.py`: IDF divided by `ln(1 + N)`, so each matched (field, term)
  contributes at most its field weight and a score is in `(0, 7.0 × terms]` instead of
  growing with graph size. Ordering uses the value before the common divisor, so the
  normalization cannot reorder anything.
- Every hit gains **`score_kind`**: `idf` (L1/L3/L4), `recency` (L2 — the 1.0 constant,
  ordered by `at`; not a match score), `expansion` (`--expand` neighbours). Additive;
  docs and the MCP tool description now forbid comparing scores across kinds.

### Verified

- `experiments/score_scale/`: **every ranked id list and every metric identical** to
  v0.18.0 on all four corpora (control, N1, N2, N3).
- Bounded: worst frozen score 8.716 (bound 7.0 × terms). Residual 27→10k drift on one
  gold is 1.375× against v0.18.0's 3.799× — *bounded, not invariant*, and published as
  such; `issue.mem-arch-idf-live-df-drift` stays open with that wording.
- 268 tests (+7), nine CI jobs, `tools/verify.py` nine steps.

### Not shipped in 0.19.0 (do not assume)

- No ranking change; recall is identical by construction and by measurement.
- No search cache; no evidence-content verification (`R3` is the next round).
- Scores are not probabilities and are not comparable between different queries.

## [0.18.0] — 2026-10-31

The IDF round that 0.17.0 named: **rarity-aware scoring ships, and it is measured to fix
the realistic noise model but not the adversarial one.**

### Changed

- `src/amg/retrieval.py`: a matched term contributes `WEIGHTS[field] × idf(term)`,
  `idf = ln(1 + N/(1+df))` over the visible nodes, instead of a constant field weight.
  Field weights, matchers, hard filters, anchor rule and ordering are unchanged; a query
  token repeated twice counts once. `_match_fields()` keeps the matches from the existing
  scan, so this is bookkeeping, not a second pass over the graph.

### Measured (26 frozen queries, both scorers in one process)

| corpus | baseline r@1 / r@5 | shipped r@1 / r@5 |
|---|---|---|
| control 27 | 0.654 / 0.808 | **0.731 / 0.865** |
| N1 unrelated 10k | 0.654 / 0.808 | **0.731 / 0.865** |
| N2 query-vocabulary 10k | 0.481 / 0.538 | 0.481 / 0.538 (r@10 0.538 → 0.577) |
| N3 frequent-vocabulary 10k | 0.654 / 0.712 | **0.731 / 0.865** |

- **The N2 `recall@5 ≥ 0.70` target was missed (0.538)** — predicted before the run:
  N2 samples distractor tokens uniformly from the query vocabulary, so `df` is the same
  for every query term and IDF has nothing to weight. Deep ranks improve (q05 42→9,
  q16 99→46); the top-5 does not move.
- Cost: p50 +3.0 ms at 10k (+4%); +6 tests pin the mechanism (261 total).

### Added

- `experiments/retrieval_idf/` — pre-registration, frozen v0.17.0 baseline, harness, a
  fourth corpus (N3 frequent-vocabulary noise), `result.json`, and a README that records
  the two wrong predictions.

### Not shipped in 0.18.0 (do not assume)

- **N2 is not fixed**: the same 11 queries miss at 5, and 3 of them are word-level gaps
  (q06, q08, q10) that no ranking weight can close.
- No real-graph 10k retrieval; every noise model here is synthetic.
- No phrase/proximity matching and no id/type priors — those are the named next
  candidates, each needing its own pre-registration.

## [0.17.0] — 2026-10-31

Second half of the 10k gap: **retrieval recall at 10,000 nodes is measured**, and the
result inverts the obvious guess.

### Added

- `experiments/retrieval_10k/` — pre-registration (with predictions, an amendment for a
  second noise model, and an outcome table), harness, `result.json`, README.
- Two noise models on the same frozen 26 queries: **N1** unrelated distractors
  (bench generator), **N2** distractors built from the queries' own tokens (seeded).

### Measured

| run | nodes | recall@1 | recall@5 | recall@10 | MRR@10 | p50 |
|---|---|---|---|---|---|---|
| control | 27 | 0.654 | 0.808 | 0.865 | 0.763 | — |
| N1 unrelated | 10,000 | 0.654 | 0.808 | 0.865 | 0.763 | 74.3 ms |
| N2 query-vocabulary | 10,000 | **0.481** | **0.538** | 0.538 | **0.515** | 92.5 ms |

1. **Size alone costs nothing** (370× more unrelated nodes, identical metrics).
2. **Vocabulary overlap costs 0.27 recall@5, and the cause is scoring**: 7 of the 11
   misses are beyond rank 100. `WEIGHTS` in `src/amg/retrieval.py` has no IDF, so a note
   repeating common query words outscores the node that answers.

### Fixed

- The README no longer says "retrieval recall at 10k is unmeasured"; it states both
  halves of the 10k question, with the weakness named. `docs/API.md`'s retrieval rules
  now warn that scoring has no IDF and point at the numbers.

### Not shipped in 0.17.0 (do not assume)

- **No IDF, no re-ranking change, no code touched at all** — criterion C4 of the
  pre-registration forbade tuning in the same round. IDF weighting is the next candidate
  with its own pre-registration.
- No real-graph 10k retrieval numbers: this is synthetic noise on a frozen corpus.
- No semantic recall; no claim that a bigger graph is "fine" — only that *unrelated*
  size is, and that *related* noise is not.

## [0.16.0] — 2026-10-31

Removed a documented gap: **concurrency at 10,000 nodes is measured**, and the naive
configuration fails there — which is the useful part.

### Added

- `experiments/concurrency/PREREGISTRATION-10k.md` — criteria and predictions written
  before the run, plus an outcome section that records two **wrong** predictions.
- `experiments/concurrency/build_10k.py` and two artifacts: `result-10k.json` (the run
  that completed) and `result-10k-run1-timeout.txt` (the run that died). Both are in
  the repository, including the failing one.
- `docs/CONCURRENCY.md` §"At 10,000 nodes": 86.2 ms per write at 10k (the extrapolation
  held), 200 writes = ~17.2 s of work, burst window 17.95 s, worst lock wait 13.52 s,
  p50 85.8 ms / p95 112.3 ms contended against 86.2 ms serial — **throughput is
  write-cost bound, not lock-bound** (11.1/s vs 11.3/s).

### Fixed

- **A false confidence, not a bug**: the default 5 s lock timeout *does not* survive
  8 × 25 writes at 10k (run 1 died with `LockTimeout`). The default is kept on purpose
  (DECISIONS #26); what changed is that the limit is now measured and the sizing rule
  is written down (`timeout ≥ writers × writes × per-write cost`, here ≥ 18 s).
- `docs/BENCHMARKS.md` now carries the measured 10k write cost next to the 5k
  extrapolation, instead of leaving the 10k number as a projection.

### Not shipped in 0.16.0 (do not assume)

- No 10k **retrieval** recall numbers, no 10k Windows run, no multi-host or network
  filesystem numbers.
- No fairer lock: the 13.5 s wait with 821 polls is a starvation *symptom*; attributing
  it to unfairness needs the counter experiment that DECISIONS #15 keeps unbuilt.

## [0.15.0] — 2026-10-31

New: the archive is reachable over MCP. Fixed: two "not implemented" claims that were
false — in the direction that made the project look less verified than it is.

### Added

- **`memory_search` accepts `include_archive`** (MCP, `layer: "L2"` only). Archived
  hits come back marked `archived: true` with their `archive_file`, exactly as from the
  CLI; any other layer returns `E_ARCHIVE_LAYER` as `isError: true`. The tool list stays
  at eight — this is a search option, not a ninth tool, and a test pins both facts.
  `docs/ARCHIVE.md` no longer says the archive is invisible over MCP.

### Fixed

- **Two stale "not implemented" entries were wrong, and are corrected in the honest
  direction.** The README listed "Windows file-locking verification" and "any benchmark
  above 1,289 nodes" as not done. Both were false: `test_lock.py` and
  `test_concurrency.py` run and pass on `windows-latest` in CI (cross-process
  exclusivity, serialised writes, concurrent writers losing nothing), and
  `docs/BENCHMARKS.md` has synthetic 1k/5k/10k measurements. What is still true is
  narrower and is what the list now says: the **Windows latency tail is unmeasured**
  (burst timing is macOS-only), and **concurrency and recall are not measured at 10k**.
  `src/amg/store.py`'s module docstring said "Windows locking is NOT verified" for the
  same reason and now states the real coverage.

### Not shipped in 0.15.0 (do not assume)

- No MCP tool archives anything: `amg archive` remains a CLI/library operation, because
  a write that moves history should be an explicit, leased decision, not an agent tool.
- No Windows burst/latency measurement; no 10k-node concurrency or retrieval numbers.

## [0.14.0] — 2026-10-31

Changed behaviour: **lexical matching is word-aware**, so queries that cannot
distinguish anything stop returning answers — and the recall that costs is published,
not absorbed.

### Changed

- **ASCII matches a whole word or its regular inflection**, never a raw substring:
  `rank` finds `ranking`, `searched` finds `search`. A one-character ASCII token is
  dropped. Before this, `a` matched `archive` and nearly everything else: on the real
  1,289-node graph, `a`/`e`/`i`/`x` each returned the full `k=10`.
- **A query containing `.` `:` `/` `_` is an identifier lookup.** `task.a` asks for
  that id instead of splitting into every `task` plus the letter `a`, which used to
  return ten unrelated `task.*` nodes for an id that does not exist. Word separators
  (`-`, `.`, `_`, `/`) still allow prefix lookups (`task.read` → `task.read-audit`).
- **CJK is unchanged** (substring; a character is a word), and single CJK characters
  remain searchable.

### Measured (`experiments/retrieval_precision/`, pre-registered)

| measurement | before | after |
|---|---|---|
| one-letter queries, real graph, `k=10` | 10 hits each | **0** |
| nonexistent identifier (`task.a`, `issue.zzz`, `missing.node`) | 10 hits each | **0** |
| identifier lookups naming a live node, top-1 | — | **20/20** |
| frozen-eval keyword recall@5 | 0.938 | **0.969** |
| frozen-eval MRR@10 | 0.744 | **0.763** |
| frozen-eval overall recall@5 | 0.865 | **0.808** |
| frozen-eval overall recall@1 | 0.654 | 0.654 |

The overall drop is analysed per query, not explained away: two of 26 eval queries were
reached only through substrings **inside other words** (`i` in `high-risk`, `one` in
`gone`), one was a genuine inflection case and is recovered, one improved. Both the
pre-registration criteria that failed and the override are recorded (DECISIONS #25,
`experiments/retrieval_precision/PREREGISTRATION.md` §Outcome).

### Not shipped in 0.14.0 (do not assume)

- **No stemmer and no synonyms.** A 14-entry English suffix table, no dependency;
  other languages get word-boundary matching only.
- **No stopword handling**: a query made only of common words (`the if do`) still
  matches loosely, because those words are words.
- **No semantic matching.** Paraphrase recall is unchanged at 0.55 in this eval; the
  embedding candidate remains rejected for the default path.

## [0.13.0] — 2026-10-31

New capability: **the history that was moved out stays searchable**, on request and
labelled as history.

### Added

- **`amg search <dir> "q" --layer L2 --include-archive`** and
  `Memory.search(..., include_archive=True)`. The cold archive
  (`archive/changes-*.json`) is read with no index and no second store — it is plain
  JSON, and `archive.load_records()` returns the records with the file they came from.
  Every archived hit carries `archived: true` and `archive_file`, so an old record can
  never be mistaken for a current one; `k` applies across live and archived records
  together, newest first; archived hits keep their original `at` and `rev`.
- **The flag is refused on node layers** (`E_ARCHIVE_LAYER`, exit 2) instead of being
  silently ignored: an L3 result set cannot contain ledger records, and a success that
  changed nothing would be a lie about what was searched.
- Default L2 behaviour is unchanged, and there is a test that asserts it: moving
  history must not change what a plain search answers.

### Why this closes a documented gap

0.11.0 shipped the archive with "`L2` search sees live history only" written into
`docs/ARCHIVE.md` and the CHANGELOG. That was honest but inconvenient: the first
question after "I moved my old history out" is "can I still find it?". Now the answer
is yes, with the provenance attached. The docs, the example
(`examples/archive.sh`, in CI) and the not-shipped list are updated together.

### Not shipped in 0.13.0 (do not assume)

- **No index** over the archive: a search reads the archive files. Fine at old-history
  sizes; unmeasured on a graph with years of history, and said so.
- No cross-file rank normalisation beyond `(at, rev)`, no archive pruning, no
  `--include-archive` for node layers.

## [0.12.0] — 2026-10-31

New contract: **documentation size budgets**, and the README restructured to fit one.

### Added

- **`tools/check_doc_sizes.py`** — the budget gate: `README.md` and `docs/README.md`
  ≤ 12 KiB, every other `docs/*.md` ≤ 24 KiB. It fails with the exact overshoot, and
  runs in CI next to the symbol gate and in `tools/verify.py`. The rule is adapted from
  the same public workbench as the handover card (`docs/PRIOR-ART.md`), where a file
  over the line is defined as one a reader skips. `CHANGELOG.md` and `RELEASE.md` are
  out of scope **in words** — append-only logs, where a cap would mean deleting
  history — not silently exempted.
- **`docs/ADOPTION.md`** — the adoption contract (nothing fabricated, nothing
  overwritten) and the measured before/after table on a real 1063-node graph, moved
  out of the README. The README keeps a three-line summary and links.
- **`docs/PRIOR-ART.md`** gains an "At a glance" list of the six systems this project is
  measured against, and the two `grep` commands that re-check the two commitments it
  does **not** ship (hard authorization, risk-scaled evidence).

### Changed

- **README.md 20,315 → 10,552 bytes**, and nothing was deleted: duplicated material
  moved back to the document that owns it (adoption → `ADOPTION.md`, prior art →
  `PRIOR-ART.md`, MCP tools → `API.md`, handoff/archive detail → `HANDOFF.md` /
  `ARCHIVE.md`). A README that restated the docs was a second source of truth that
  could drift; the budget makes the drift expensive.
- `docs/README.md` states the budgets as a contract and says what to do when a
  document reaches one: move detail to the owning document, do not delete it.

### Not shipped in 0.12.0 (do not assume)

- No automatic document splitting, no word-count or reading-time metric, no per-file
  budget overrides: one entry budget, one reference budget, no escapes.

## [0.11.1] — 2026-10-31

### Fixed

- **A false alarm on legacy ledgers.** `amg archive`'s rev-contiguity check treated a
  record without an integer `rev` as a failure, so a graph written before
  `amg migrate` existed refused to archive and rolled back (`E_ARCHIVE_VERIFY`) —
  safe, but wrong: contiguity is *unknowable* when numbers are missing, not violated.
  The check now reports `rev_contiguous: null` with `rev_unnumbered: N` and lets the
  move through; `amg archive --verify` reports `rev_continuity: null` the same way.
  Duplicate rev numbers are still hard evidence and still fail. `amg migrate` numbers
  the records and makes the check enforceable. Found by probing the edge case before
  calling 0.11.0 done; `tests/test_archive.py` covers it.

## [0.11.0] — 2026-10-31

New capability: **cold archiving of the change ledger** — move old history out of the
live file and prove on every run that nothing was lost.

### Added

- **`amg archive <dir>`** (`--older-than-days N`, `--apply`, `--verify`, `--json`) and
  `Memory.archive(days=..., apply=...)` / `Memory.archive_verify()`. A cold **prefix**
  of `changes[]` moves into `archive/changes-r<rev>-<stamp>.json`, leaving one pointer
  record; a record without a parseable `at` stops the prefix, and an old record behind
  a newer one is counted as `deferred_behind_newer` rather than taken out of order.
  Dry-run by default; nothing is written without `--apply`.
- **A proof, not a checksum of our own output.** Every `--apply` snapshots the file to
  `archive/snapshots/`, then verifies five independent things: the archive file
  re-read from disk reproduces the moved records, the live ledger is exactly
  remainder + one pointer, `state_sha256` is unchanged (nodes and edges untouched),
  `check()` still passes, and rev numbers are contiguous across the boundary. A failed
  proof writes the snapshot back and exits 1 with `E_ARCHIVE_VERIFY`.
- **`amg archive --verify`** re-runs the proof later from disk only: it recomputes each
  payload digest and requires every rev number to appear exactly once across archives
  plus live history, so a dropped record shows up as a hole rather than as silence.
- **`docs/ARCHIVE.md`** — the rule and its credited source, what qualifies, the five
  checks, measured before/after numbers on two real graphs, recovery commands, and the
  list of what it deliberately does not do. `examples/archive.sh` runs the whole cycle
  (dry-run, apply, verify, tamper rejection) in CI.
- **`benchmarks/archive_cost.py`** — re-runnable pricing: adopts a legacy graph into a
  temporary directory and reports file size, ledger share, eligible records, bytes
  after, single-write latency before/after and verification cost, aggregates only.
- `AMG_ARCHIVE_DAYS` (policy, not constant: `0 < x <= 3650`, invalid values fall back
  to 30 — never to 0), same ruling as `AMG_STALE_DAYS`.

### Measured (macOS, 1-minute load ≈ 3.4, re-runnable with the benchmark)

| graph | file | ledger share | archive @1 d | file after | single write |
|---|---|---|---|---|---|
| 15.7 MB real team graph | 1289 nodes / 2604 changes | 79.0% | 2275 records | 5.9 MB (−62.2%) | 226.1 → 72.7 ms |
| this project's own graph | 198 nodes / 454 changes | 48.8% | 265 records | 337 KB (−32.3%) | 7.7 → 5.5 ms |

At the default 30-day cutoff **0 records qualify** on both graphs (they are 8 days
old). That is stated rather than worked around.

### Not shipped in 0.11.0 (do not assume)

- **No node archiving.** Edges cross the boundary; moving cold *nodes* is a different
  design that this release does not pretend to have.
- **`L2` search sees live history only.** Archived records are not searched; `grep` or
  `--verify` is how you inspect them.
- **No compression and no dependencies** — the archive is plain JSON.
- **Not exposed over MCP**, and **not automatic**: no background job prunes history.
- **Snapshots are kept, one full graph copy per run**, and never cleaned up
  automatically.

## [0.10.0] — 2026-10-31

New capability: **handoff cards** — a bounded, superseding record of where the work
stands, so a new session reads one thing instead of searching.

### Added

- **`handoff` node type and `amg handoff <dir>`** (`--by`, `--owner`, `--note -`,
  `--json`). Exactly one card is active: writing a new one supersedes the previous
  through the normal supersede path, so the history stays in the ledger. The card is
  capped at **4,096 bytes**; an empty or oversized card is refused
  (`E_BAD_HANDOFF`, `E_HANDOFF_TOO_LARGE`, exit 2) and writes nothing.
  `Memory.write_handoff()` / `Memory.handoff()` are the same operations in Python.
- **`audit` enforces the invariants a hand-edited graph can break**:
  `handoff_over_budget` and `multiple_active_handoffs` are conflicts, so the limit is
  not merely advisory. Handoff nodes are registrations, not work items, so they are
  exempt from staleness (same class as DECISIONS #20).
- **`docs/HANDOFF.md`** — the four questions a handover answers, the three rules it
  follows, and what this project adds over the pattern's source; `examples/handoff.sh`
  runs the whole cycle in CI.
- Pattern credit: the handover discipline (`§〇 交接`: overwrite, ≤4 KB, pointers not
  transcripts) is taken from
  [mashanglinyu/luanyujia-workbench](https://github.com/mashanglinyu/luanyujia-workbench)
  (MIT) and recorded in `docs/PRIOR-ART.md`; this is an adaptation, not an invention.
  The node-typed form, supersede-on-write and the double enforcement are ours.

### Fixed

- **A misleading audit hint**: `valid_time_known=false` counted registrations
  (group/env/member) and said "migrated validity time is unknown" even on a fresh
  graph written today. Registrations are not TTL candidates and are no longer counted;
  the wording now states the actual reason (no fact time recorded).

### Not shipped in 0.10.0 (do not assume)

Unchanged: no authentication / authorization / multi-tenancy (out of scope by
decision), no vector retrieval in the default path (measured, rejected), no tamper
*proof*, no TTL scheduler, no encryption at rest, no lock fairness, and history
compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.9.0] — 2026-10-31

Additive: `audit` now returns structured findings alongside its strings, so a reader
(or an agent) can tell who is responsible without parsing a sentence.

### Added

- **`audit()["findings"]`** — one entry per conflict or hint, derived from the same
  record as the human string, in the same order: `severity` (`conflict`/`hint`),
  `kind` (`done_without_evidence`, `stale_work_item`, `expired_but_active`,
  `dangling_edge`, `pin_changed`, and five hint kinds), the `detail` string, plus the
  node, its type/status/owner, and `age_days`/`limit_days` where relevant; dangling
  edges carry the `edge` object. `conflicts` and `hints` are unchanged, so existing
  consumers see no difference. Measured on the first live graph: 3 conflict findings
  and 602 hint findings, with the string lists matching the findings exactly.
- The human lists are now **generated from** the findings instead of being built
  separately, so text and `--json` cannot diverge by construction (DECISIONS #22); a
  test asserts the two views stay identical.

### Not shipped in 0.9.0 (do not assume)

Unchanged: no authentication / authorization / multi-tenancy (out of scope by
decision), no vector retrieval in the default path (measured, rejected), no tamper
*proof*, no TTL scheduler, no encryption at rest, no lock fairness, and history
compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.8.0] — 2026-10-31

**A new capability, not a fix**: the staleness threshold is now policy, because the
right value is a property of the team's cadence rather than of the tool.

### Added

- **`AMG_STALE_DAYS`** (integer days, `0 < x <= 365`, invalid values fall back to 3)
  and **`amg audit --stale-days N`** for one run. Measured on the first live graph,
  the same three work items produce **3 conflicts at 3 days, 1 at 7, 0 at 14** — a
  weekly-sync team sees false alarms at the default, a monthly team none. Default
  stays 3 (the original rule), so existing users see no change. Fallback rather than
  disable: a typo must not silently turn the check off, same rule as
  `AMG_LOCK_TIMEOUT` (DECISIONS #21).
- **`Memory.audit(stale_days=...)`** for callers that do not want a process-wide
  environment variable.

### Not shipped in 0.8.0 (do not assume)

Unchanged: no authentication / authorization / multi-tenancy (out of scope by
decision), no vector retrieval in the default path (measured, rejected), no tamper
*proof*, no TTL scheduler, no encryption at rest, no lock fairness, and history
compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.7] — 2026-10-30

**A behaviour change, and the first library change since 0.6.0**: `audit` no longer
reports long-lived registration nodes as stale.

### Fixed

- **Staleness now applies to work, not to registrations.** The rule "an `in_progress`
  or `blocked` node untouched for 3 days is stale" assumed every node is a
  short-lived work item. On the first live graph it flagged a `group` node
  `in_progress` for 7 days — correct by the letter, noise in practice: a group
  registration is long-lived, and its `updatedAt` does not move when its children
  change. `group`, `env` and `member` are exempt (`LONG_LIVED_TYPES`); **an unknown
  type is still checked**, so a new kind of work cannot become invisible by omission.
  Measured on that graph at rev 2,610: `audit --pin` **4 → 3 conflicts**, pin still
  matches. The three remaining are real work items (`task`/`issue`/`decision`
  untouched 3–7 days) and stay reported. DECISIONS #20; four tests in
  `tests/test_audit.py`, including one that a `question` node is still checked.

### Not shipped in 0.7.7 (do not assume)

Unchanged from 0.7.6 — no authentication / authorization / multi-tenancy (out of
scope by decision), no vector retrieval in the default path (measured, rejected), no
tamper *proof*, no TTL scheduler, no encryption at rest, no lock fairness, and
history compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.6] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. Two numbers
that were quoted without context now have it: the stale-conflict count, and the
conditions the timings were taken under.

### Added

- **`docs/REAL-WORLD.md` breaks down the pinned conflicts.** On the first live graph
  all four are staleness, but not one kind: three are work items (`task`/`issue`/
  `decision`) untouched 3–7 days with owners and notes — real debt, left visible on
  purpose — and **one is a `group` node**, which is long-lived by nature and flagged
  by a rule that assumes a short-lived work item. That false-positive class is
  recorded as a finding; changing which types the rule covers changes `audit` output
  for existing users, so it needs a decision and a test, not a quiet patch.
- **`benchmarks/real_graph.py` prints the load average** and flags runs above 2.0 as
  inflated, because the effect is large: the same `adopt` of the same 15.4 MB file is
  **140–142 ms idle and 1,055 ms at load 24.8**, and CLI startup goes **48 ms → 552
  ms**. `docs/REAL-WORLD.md` records this as a measurement-condition table, so its
  numbers are not compared across conditions.

### Not shipped in 0.7.6 (do not assume)

Unchanged from 0.7.5 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, no change to the audit rules, and history
compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

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
