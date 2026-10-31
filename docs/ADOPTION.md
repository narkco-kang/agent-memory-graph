# Adopting a legacy `group-kg/v1` graph

`amg adopt <src> <dst>` reads an older graph and writes an `amg/v1` graph into a
**new** directory. It never writes to the source, never overwrites the destination,
and it refuses to invent data:

- legacy evidence strings cannot become evidence objects (we do not hold the cited
  artifact), so they stay in `legacy_evidence` and `evidence` is empty — `audit`
  keeps reporting them as legacy debt instead of pretending they are fine;
- placeholder sources become explicit provenance `adopted:<schema>:<sha12>`;
- `superseded_at` / `valid_until` inferred from `updatedAt` are flagged
  `superseded_at_inferred`; `valid_from` stays `null` when unknown;
- duplicate ids, unknown enums and dangling edges are refusals (dangling edges can
  only be dropped with `--drop-dangling`, and the count is reported);
- edges that repeat an identical `(from, to, kind)` triple are merged (nothing is
  lost) and the count is reported; `--pin-out` writes the frozen exemption baseline
  for `amg audit --pin`;
- the source is byte-identical afterwards (`src_sha256` reported), and an existing
  destination `graph.json` is refused, never overwritten.

Exit codes: `0` adopted and the result passes `check`; `1` the source is unsupported or
the result would not pass `check`; `2` wrong input (missing graph, destination exists,
source already `amg/v1`).

`amg migrate` then canonicalizes `changes[]` in the adopted graph: missing `target`/`rev`
are filled with `null` (never invented), the legacy `detail` key is folded into `note`
(never dropped), and the shapes before/after are printed.

## Measured on a real graph

Our own 1063-node team graph (source snapshot 2026-10-29, adopted copy in `/tmp`,
source byte-identical afterwards):

| | before | after |
|---|---|---|
| `check` errors | 1143 | **0** |
| edges | 580 | 576 (4 duplicate identical triples merged, counted) |
| placeholder sources | 451 | 0 (replaced by `adopted:…` provenance) |
| evidence | 658 strings, 0 valid objects | 658 in `legacy_evidence`, 0 claimed |
| `superseded` without timestamp | 29 | 0 (inferred from `updatedAt`, flagged) |

`audit --pin` then leaves **3 conflicts**: work items (`task`, `issue`, `decision`)
left `in_progress`/`blocked` for 3–7 days. Those are real hygiene debt of that graph,
not artifacts of adoption, and they are reported rather than silenced. A fourth one
used to appear for a `group` node — a registration that is long-lived by nature, not
a work item — which 0.7.7 stopped counting; `REAL-WORLD.md` has the breakdown.

## What counts as a successful adoption

Six checks, all of which must be observed on the **adopted copy**, none of which is a
proxy for the others:

1. `check` errors are `0` on the adopted copy (`amg check <dst>`).
2. The counts the tool printed add up: `nodes N→N`, `edges M→M−merged` with the merged
   count printed, and `changes[]` length accounted for (adoption appends its own entry;
   `migrate` must not change the count).
3. **No fabricated evidence**: `evidence` holds `0` claimed objects unless the source
   really had valid ones; legacy locator strings are in `legacy_evidence` and their
   count is printed. Adoption must never invent a hash to make an anchor look verified.
4. The pin is self-consistent and recomputable: `--pin-out` written, then `audit --pin`
   reports `pin.match: true` and the same conflict set on a second run.
5. The pin is **forward-only**: it may exempt what existed at pin time and nothing
   added afterwards, and every node it does not cover is reported as unanchored
   (measured: 887/1063 after adoption vs 647/782 before — more honest, not less).
6. The source file is byte-identical afterwards (`src_sha256` before/after equal) — the
   tool never writes to the source.

**Do not use `audit --pin`'s exit code as the success criterion.** A real graph usually
carries genuine stale work, so `audit --pin` exits `1` with `pin.match: true`; requiring
exit `0` would push an operator to close or re-date live work items, or to widen the
staleness threshold, to make a migration look clean — that is manufacturing a green
report. The success criterion is "nothing was lost, invented, or silently exempted", and
the remaining conflicts are tasks for the graph's owner, not migration failures.

Corollary for the operator: after `adopt`, run `audit --pin` once so the exemption
baseline exists; `tools/verify_snapshot.py <graph.json>` is the recurring version of
this — it adopts a copy into a temp dir, resolves evidence against the original graph's
directory and reports `unverified` (exit 3) instead of claiming coverage a curated graph
does not have (v0.25.0); otherwise every legacy node shows up as an unanchored obligation and
the report is noise. Also record which gate governs which graph — an adopted graph is
under `amg`'s write gate and evidence verifier; a graph still written by another tool
(ours: `kg.py`, `group-kg/v1`) is not, and no document should imply otherwise.

## Why this is a separate document

The migration rules are a contract: adoption is the only path by which data this
project did not write enters it. Keeping the full table here rather than in the
README is part of the documentation budget rule (`README.md` ≤ 12 KiB, every other
`docs/*.md` ≤ 24 KiB, enforced by `tools/check_doc_sizes.py`).
