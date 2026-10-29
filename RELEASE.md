# Release checklist — v0.1.0

Status: **blocked on review** (repository is private until every box is checked).

## Definition of done

| # | Criterion | State |
|---|---|---|
| 1 | CI green: unit tests + doc↔code symbol gate + quickstart | ✅ 68 tests, gate cannot pass on phantom symbols |
| 2 | End-to-end example runs | ✅ `examples/quickstart.sh` |
| 3 | Documentation equals code | ✅ enforced by `tools/check_doc_symbols.py` |
| 4 | Unimplemented capabilities explicitly marked | ✅ README + CHANGELOG "Not yet" |
| 5 | Real-graph migration succeeds (6 criteria below) | ✅ measured, see below |
| 6 | LICENSE + CHANGELOG + release note | ✅ MIT, CHANGELOG.md, this file |
| 7 | Positioning reviewed independently | ✅ review complete; two claims downgraded to "design only, not implemented" in README |

## Known debt after adopting the real graph

`amg adopt` produces a graph where `check` passes with 0 errors. `amg audit`
still reports 4 conflicts, all of them **pre-existing staleness** (untouched for
more than `STALE_DAYS = 3`), not migration artefacts:

- `group.self`
- `decision.kg-per-group`
- `issue.anthropic-stream-tooluse-dropped`
- `freeze.FREEZE-20261025-112530`

Migration is judged by six criteria, all independently measured on the real
graph — **not by `audit --pin` exiting 0**:

1. `check` reports 0 errors
2. node count and change count match the source (1063 nodes; 2177 → 2178 changes
   because adoption itself is recorded)
3. no fabricated evidence (658 legacy strings stay in `legacy_evidence`,
   `evidence` stays empty, `content_sha256` never invented)
4. the exemption pin is self-consistent and recomputable
5. the pin is forward-only (a new write cannot hide behind it)
6. the source file is byte-identical before and after (`sha256` unchanged)

The 4 remaining stale entries are genuine pre-existing debt; suppressing them to
make the pin green would be exactly the fabrication criterion 3 forbids.

Policy (signed): no `--allow-stale` escape hatch will be added — such a flag
becomes the default path and silently voids the threshold. Each entry must
either be touched by its owner (status change with a note) or remain listed
here as known debt. Until then `audit` exits 1 by design.

## Not verified (state them, do not hide them)

- Windows locking; adopt under concurrency; any graph above 1,063 nodes.
- Python 3.10 / 3.12 exercised only in CI, not locally.
- Read-side audit ("who read what") is not implemented. Prior art exists
  (event-sourced audit logs, LangSmith-style traces), so it is not claimed as
  novel either.

## Positioning (pending independent sign-off)

We claim only: **task state as the authority face, expiry as a first-class
citizen, write-back discipline as a hard gate**, with hard authorization kept
separate from graded trust, and evidence requirements scaling with action risk.

Prior art that must be cited in the README before release: MAP-Graph
(arXiv:2608.10509), Letta MemFS, Graphiti (bi-temporal + provenance), Mem0,
A-MEM, Governed Shared Memory (arXiv:2606.24535). The phrase "no prior work"
must not appear anywhere.
