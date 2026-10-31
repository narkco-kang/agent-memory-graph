# Operating a live memory graph

The runbook: what to run, how often, what a bad answer looks like, and which numbers
were measured. Unmeasured things are marked as such — that is the house rule.

## 0. The one command worth memorising

```bash
python3 tools/healthcheck.py ./mem          # one-page, read-only
python3 tools/healthcheck.py ./mem --json   # same, machine-readable
python3 tools/healthcheck.py ./mem --strict # stale work items also fail
python3 tools/healthcheck.py ./mem --allow-unverified  # accept "nothing to verify"
python3 tools/healthcheck.py ./mem --no-evidence       # skip hashing; verdict says NOT CHECKED
python3 tools/verify_snapshot.py ../kg/graph.json     # verify a graph another tool wrote
```

It reports store size, `check` errors and hints, audit conflicts, evidence that was
actually hashed against its declared `content_sha256`, **conclusion anchoring**, and
archive integrity. **Debt is not breakage**: stale work items and unanchored `done`
nodes are printed but only fail with `--strict`, because paging someone for a
three-day-old task trains them to ignore the report.

### Coverage has two denominators, and both are printed

`evidence rows: 1 declared, 1 verified (100%)` says only that every *evidence row that
exists* was hashed. It does not say that knowledge is anchored. v0.24.0 printed that
line alone for a graph where ten other `done` nodes carried no evidence at all
(`issue.mem-arch-coverage-denominator`), so the report now always prints:

```
  evidence rows: 1 declared, 1 verified (100%) - ok 1
  conclusions: 1/1 verified (100%), 0 unanchored
  done nodes: 11 total, 10 without evidence
```

`conclusions` counts `done` nodes of conclusion type (`decision`, `artifact`, or
`conclusion: true`) — the ones the write gate requires evidence for — and how many of
them carry at least one *verified* item. `done nodes` counts every finished node without
any evidence, which is what migration leaves behind. Read all three; a single percentage
is not a health statement.

### Verdicts and exit codes

The last line is a verdict, and the exit code matches it — a scheduler keys on the code,
a human reads the line:

| verdict | exit | meaning | first action |
|---|---|---|---|
| `healthy` | 0 | no problem, and at least one `path:` evidence file hashed to its declared digest | nothing |
| `needs_attention` | 1 | `check` errors, or evidence that mismatches / is missing / is a directory / cannot be read / is outside the graph root, or archive verification failed (stale work and unanchored nodes too, with `--strict`) | the `x` line above the verdict names the command to run |
| `unverified` | 3 | nothing is broken, but **zero** evidence items could be observed: no evidence at all, or only `cmd:`/`url:`/`sha256:` anchors, which carry no local bytes | write `path:` evidence for claims that matter, or accept the gap explicitly |
| `not_checked` | 0 | `--no-evidence` was passed: negative findings are about `check`/`audit`/`archive` only. It is also a **warning**, so `--strict` fails on it | re-run without `--no-evidence` when the answer matters |

`unverified` exists because "0 checked" and "0 failed" look identical in a problem list.
v0.23.0 printed `healthy` and exited 0 on a store whose every claim was unproven (an
`adopt`ed graph empties the evidence layer by design, and a `cmd:`-only graph has nothing
local to hash) — that is a dashboard saying "fine" about "unknown"
(`ATTACK-HEALTHCHECK-V023.md` §2.1–2.2). `--allow-unverified` keeps the verdict honest
and relaxes only the exit code, for stores whose evidence is intentionally remote; the
JSON records `unverified_accepted: true` so a log can tell "verified" from "exempted".
`--no-evidence` yields `not_checked`, never `healthy` — a report that did not look must
not read like one that looked and found nothing (`REATTACK-HEALTHCHECK-V0240.md`).
`--strict` covers debt only (stale work, unanchored nodes); it never means "all evidence
verified", and the JSON says so in `strict_scope`.

### Verifying a graph another tool wrote

A graph curated by another tool (ours: `kg.py`, schema `group-kg/v1`) is **not** under
`amg`'s write gate. `tools/verify_snapshot.py <graph.json> [--evidence-root DIR]` adopts
a copy into a temp directory and runs the same report above. It never writes the source,
and it inherits the numbers — including `unverified` (exit 3), because a curated graph's
evidence is usually citations, not hashed files.

**The evidence base must be stated, not guessed.** The same graph answers three different
things depending on which directory `path:` is resolved against — measured on this
project's own graph: `graphs/` 0/240 files found, the workspace root 113/240, the
repository root 89/240. So `--evidence-root DIR` is explicit (default: the graph's own
directory), and every run prints `evidence base: … (files found N/M, P%)`. A base chosen
by the tool would be a guess, and a wrong guess reads as `missing` — a false alarm — or
as found, which is worse.

**Legacy strings that carry their own digest are verified, never invented.** A curated
string shaped `path:<rel>#sha256:<hex>` is hashed read-only and counted
(`legacy strings: 3 with #sha256, 2 verified, 1 mismatched, 0 malformed`); a string with
a broken digest is reported malformed; any other string stays a citation and is never
promoted to evidence. That is the only way coverage grows without fabricating a hash.

Exit 0 from the bridge means "the observable invariants hold", never "this graph is
write-gated" and never "its content is correct".

## 1. What is already enforced (do not re-implement it)

| Guarantee | Where |
|---|---|
| writes are gated: evidence objects, conclusion nodes done only with evidence | `docs/API.md` §Evidence shape; `tests/test_gate.py` |
| expired / superseded facts never come back from L1/L3/L4 | `docs/API.md` §Retrieval |
| every write is one atomic replace under a lock | `docs/CONCURRENCY.md` |
| archive moves are proven on every `--apply` and rolled back from a snapshot on failure | `docs/ARCHIVE.md` |
| state and history digests are reproducible without trusting the file | `amg fingerprint`, `amg verify` |

## 2. Schedule

| cadence | command | why |
|---|---|---|
| every working day | `python3 tools/healthcheck.py ./mem` | one report instead of four commands |
| nightly | `amg check --strict` | structural invariants, catches hand edits |
| weekly | `amg audit --pin ./pin.json` | stale work; the first run writes the pin |
| after any large write burst | `amg archive --verify` | proves cold history is still accounted for |
| before an upgrade | `amg fingerprint --out before.json` | lets `amg verify` prove nothing moved |

A run that prints nothing is a pass **only** for the jobs that say so; `check` and
`healthcheck` always print a verdict line on purpose.

## 3. Backups

`graph.json` is the whole state (`changes[]` included); `archive/` is history that is
separate by design. A backup is:

```bash
cp ./mem/graph.json ./backup/graph-$(date +%Y%m%dT%H%M).json
```

Restore is a copy back while no writer runs, then `amg check` and
`amg verify --expect ./before.json` if you kept a fingerprint — that distinguishes
"restored" from "restored and identical". Do not copy `archive/` into another graph
directory: archive records are bound to the ledger they came from and
`amg archive --verify` will report them as foreign.

## 4. Large graphs

Measured, not estimated:

| graph | one write | note |
|---|---|---|
| 1,063 nodes (real team graph) | 147 ms | 79% of the file is `changes[]` (`docs/WRITE-COST.md`) |
| 10,000 nodes | 86.2 ms | `docs/CONCURRENCY.md` |
| after archiving the cold ledger | 72.7 ms | same real graph |

- Archive before blaming the lock: `amg archive --older-than-days 30 --apply --verify`.
- Size the lock timeout from the write cost, not from hope:
  `AMG_LOCK_TIMEOUT ≥ writers × writes × per-write seconds`. At 10k nodes, 8 writers ×
  25 writes is ~17 s of serialised work, so the 5 s default is *expected* to fail
  (`docs/CONCURRENCY.md`). Example: `AMG_LOCK_TIMEOUT=30`.
- Retrieval at 10k nodes: same 26 queries, p50 ~100 ms, recall unaffected by node count
  alone; vocabulary-overlap noise is the measured weakness (`docs/BENCHMARKS.md`).

## 5. Upgrading

```bash
python3 -m pip install --upgrade "amg @ git+https://github.com/narkco-kang/agent-memory-graph@vX.Y.Z"
amg version
amg check ./mem
python3 tools/healthcheck.py ./mem
```

The on-disk contract is `amg/v1` and only gains fields. If `amg check` reports a legacy
`changes[]` shape, run `amg migrate` once — it normalizes shapes, never renumbers a rev
and never invents one.

## 6. When something is wrong

| symptom | meaning | first action |
|---|---|---|
| `LockTimeout` | another writer holds the lock longer than your timeout | check `AMG_LOCK_TIMEOUT` sizing (§4); never delete `.lock` by hand |
| `check` errors | the file violates an invariant (hand edit, disk fault) | restore from the last backup, then `amg check` |
| `E_EVIDENCE_MISMATCH` | a `path:` evidence file's bytes are not what the node declared | `amg verify-evidence ./mem`; fix the claim or the evidence, do not re-declare the hash to silence it |
| `E_ARCHIVE_VERIFY` | the archive move could not be proven; the pre-move snapshot was written back | inspect the snapshot, then `amg archive --verify` |
| audit conflicts | stale `in_progress`/`blocked` work | close or re-date the work items; do not widen the threshold to hide them |
| `verdict: UNVERIFIED` (exit 3) | no evidence item could be observed — nothing is broken, nothing is proven | add `path:` evidence for the claims that matter, or pass `--allow-unverified` once you accept the gap; do not "fix" it by declaring hashes you did not compute |
| evidence `missing` / `not_a_file` / `unreadable` | a declared `path:` proof is gone, is a directory, or cannot be read | restore the file or correct the claim: the gate rejects a re-declared hash that does not match the bytes |

## 7. What this runbook is not

- Not multi-user. There is no authentication or authorization: the OS user is the
  boundary (`SECURITY.md`, `THREAT-MODEL.md`). Do not put the MCP server behind a
  network transport.
- Not a claim of being used. No external user has cold-started this in public; that is
  recorded as unverified, not assumed.
- Not Windows-latency numbers: correctness runs on `windows-latest` in CI, latency on
  Windows is unmeasured.
- Not a real 10k graph: the 10k numbers are a synthetic graph with deterministic noise.
