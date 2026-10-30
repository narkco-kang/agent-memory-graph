# Cold archive of the change ledger

Every write in `amg` rewrites the whole graph file. On the largest real graph we
measure (`docs/WRITE-COST.md`) that is **~147–226 ms** per write at 15.7 MB — and
**79% of those bytes are the change ledger**, not current state. History is the
cheapest thing to move out: an old change record is read only by `L2` search, the
history digest and the audit's counts, and unlike a node it has no referential
integrity (nothing points at a change record).

`amg archive` moves a cold prefix of the ledger into `archive/changes-*.json`,
leaving a one-line pointer in its place.

## The rule it follows, and where the rule came from

**Snapshot first, move second, prove nothing was lost third.**

That is not our invention: it is the field rule from
[mashanglinyu/luanyujia-workbench](https://github.com/mashanglinyu/luanyujia-workbench)
(MIT) — recorded in [`PRIOR-ART.md`](PRIOR-ART.md) — whose stated lesson was blunt:
without a snapshot, the comparison script could not even be run. We adopt the rule
and add the part a repository cannot: a machine-checkable proof that runs on every
invocation, and a rollback when it fails.

## What qualifies

A **prefix** of `changes[]`, and only that:

| Condition | Behaviour |
|---|---|
| record's `at` parses and is older than the cutoff | eligible |
| record's `at` is newer than the cutoff | stops the prefix; nothing after it moves |
| record has no parseable `at` | stops the prefix; unknown time is never a reason to move history |
| old record sitting *behind* a newer one | counted as `deferred_behind_newer`, never taken out of order |

Taking a prefix is what keeps rev numbers contiguous after the move. The cutoff is a
policy, not a constant: `--older-than-days N` or `AMG_ARCHIVE_DAYS`
(`0 < N <= 3650`, nonsense falls back to 30 — never to 0, same ruling as
`AMG_STALE_DAYS`, DECISIONS #21).

## The proof (runs on every `--apply`)

Five checks, against artefacts produced independently of each other:

1. **Snapshot.** The exact bytes about to be replaced are written to
   `archive/snapshots/graph-r<rev>-<stamp>.json`; its `sha256` is reported.
2. **Archive payload.** After writing the archive file it is **re-read from disk**
   and must reproduce the moved records, canonically and in order, matching the
   digest stored in its header.
3. **Live ledger.** The persisted graph must be exactly *remainder + one pointer* —
   not approximately, not the right count.
4. **State untouched.** `state_sha256` (`fingerprint`) must be **identical** before
   and after: archiving moves history, never nodes or edges.
5. **Structure + rev continuity.** `check()` must still pass, and rev numbers must be
   contiguous across the archive/live boundary — a hole there is the visible symptom
   of a dropped record. A ledger carrying records **without** an integer `rev`
   (graphs written before `amg migrate` existed) makes contiguity *unknowable*, not
   false: that check reports unknown and the move proceeds, with the unnumbered count
   printed. `amg migrate` numbers such records, after which the check is enforceable.

If any check fails, the snapshot is written back and the command exits 1 with
`E_ARCHIVE_VERIFY`. The graph is not left in a state whose history nobody can
account for.

`amg archive --verify` re-runs the proof later, from disk only, against the live
ledger: it recomputes each payload digest and requires every rev number to appear
exactly once across archives plus live history.

## Measured (2026-10-31, this machine, 1-minute load ≈ 3.4)

`benchmarks/archive_cost.py` adopts a legacy `group-kg/v1` graph into a temporary
directory, measures, and prints aggregates only (no ids, labels or notes).

| graph | file | nodes / edges / changes | ledger share | archive @1 d | file after | single write |
|---|---|---|---|---|---|---|
| C仔指挥部 (real team graph) | 15.7 MB | 1289 / 635 / 2604 | **79.0%** | 2275 records | 5.9 MB (−62.2%) | 226.1 → 72.7 ms |
| 记忆架构开源 (this project's own graph) | 498 KB | 198 / 160 / 454 | 48.8% | 265 records | 337 KB (−32.3%) | 7.7 → 5.5 ms |

`archive --verify` cost 207.9 ms / 7.4 ms respectively on those graphs; the proof
itself is not free, but it runs once per archive, not once per write.

At the **default 30 days, 0 records qualify today** on both graphs — they are 8 days
old. That is the honest reading: this capability reclaims nothing until history
crosses the cutoff. It is insurance for a graph that keeps growing, priced above so
the decision is not a guess.

Load sensitivity is real and already documented (`docs/WRITE-COST.md`): the same
adoption measured 140 ms at idle and 1055 ms at load 24.8. Treat the table as a
direction, and re-run the script for a number you intend to quote.

## What it does not do

- **No node archiving.** Cold *nodes* are a different problem (edges point at them);
  this version moves ledger records only, and says so rather than half-doing both.
- **No compression, no dependencies.** The archive is plain JSON, readable with
  `cat` a decade from now.
- **No deletion.** Records leave the live file; they are not destroyed. Delete
  nothing is the recovery story: restore = copy the archived `changes` back, or take
  the snapshot.
- **`L2` search sees live history by default.** A plain `amg search --layer L2`
  answers from the live ledger; moved history is searched only when you ask:
  `--include-archive` (or `Memory.search(..., include_archive=True)`), and every hit
  then carries `archived: true` plus the `archive_file` it came from, so old history is
  never mistaken for current history. There is no index over the archive: the search
  scans the archive files, which is fine at "old history" sizes and would need
  measuring on a graph with years of it.
- **Snapshots cost a full graph copy each run** (15.7 MB in the first table row) and
  are never cleaned up automatically. They are emergency restore points; delete old
  ones once you trust the verification.
- **Not exposed over MCP** (the stdio server's tool list is unchanged in 0.11.0) and
  **not automatic** — no background job prunes your history.
- **Does not make `history_sha256` cover archived history.** `fingerprint` prints
  the live history digest; the archive's own payload digests plus the contiguity
  check are what cover the moved records.

## Recovery

```bash
# what was moved, and does the boundary still add up
amg archive ./mem --verify

# the records themselves, in order
cat ./mem/archive/changes-r<rev>-<stamp>.json

# the bytes before a specific run, exactly as they were
cp ./mem/archive/snapshots/graph-r<rev>-<stamp>.json ./mem/graph.json
```

## Related decisions

`DECISIONS.md` #24 (why the ledger, not nodes) and #21 (thresholds are policy).
Write-cost background and the cold-archive trigger line: `docs/WRITE-COST.md`.
