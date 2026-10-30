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

## Why this is a separate document

The migration rules are a contract: adoption is the only path by which data this
project did not write enters it. Keeping the full table here rather than in the
README is part of the documentation budget rule (`README.md` ≤ 12 KiB, every other
`docs/*.md` ≤ 24 KiB, enforced by `tools/check_doc_sizes.py`).
