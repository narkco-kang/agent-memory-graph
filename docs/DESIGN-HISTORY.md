# Design note: making the write cheap without losing the guarantee

**Status: proposal, not built.** Nothing in this document is implemented. It exists
because two independent measurements point at the same wall, and the obvious fix
(and the one I assumed) turned out to be the wrong one.

## Why this is on the table

1. `docs/WRITE-COST.md`: `changes[]` is **79.1%** of a 15.6 MB graph; one write is
   147 ms = parse 75 + render 50 + `fsync` 23.
2. `docs/CONCURRENCY.md`: on that graph, 8 writers × 5 writes (40 queued writes)
   **times out** against the default 5 s lock — because 40 × 150 ms ≈ 6 s of queue,
   and a fair lock would not help. The lever is a cheaper write, not a fairer lock.

## The option I assumed, and why it fails

The natural fix is to move old `changes[]` into an append-only sidecar file, so
`graph.json` holds only state (3.24 MB, measured) and writes append one line
(0.12 ms, measured). Write cost would drop from 147 ms to about **27 ms** (−82%).

It fails on a property this project does not have: **`changes[]` is not a
write-ahead log.** A record is

```json
{"at": "...", "by": "cli", "op": "add", "target": "task.x", "rev": 42, "note": "..."}
```

— a *description* of what happened, not a replayable operation with a payload.
There is nothing to re-apply. So with state in one file and history in another:

| crash point | single file today | sidecar |
|---|---|---|
| between append and state replace | impossible (one `os.replace`) | history has a change the state does not; **cannot be replayed**, only detected |
| between state replace and append | impossible | state advanced with no change record; the ledger silently lies about *how* it got there |

The only honest repair is to make every write a deterministic operation with a full
payload (a real WAL), which changes the schema for every writer and every consumer.
That is a much bigger change than the problem warrants today.

**Conclusion: do not ship the sidecar.** It buys 82% of the write cost by giving up
the one guarantee the store is built around ("a reader sees old or new, never a
mix") plus ledger integrity.

## The option that keeps the guarantee

Compress the history **inside the single file**, in sealed segments:

```json
{"schema": "amg/v1", "nodes": [...], "edges": [...],
 "changes": [{"compression": "zlib", "data_b64": "..."}, ...],   // sealed, 500 records each
 "changes_tail": [ ... ]}                                       // newest records, plain text
```

Measured on the same live graph (2,573 change records, 5 sealed segments, 73-record
tail):

| | current | segmented + zlib |
|---|---|---|
| file size | 15,618,095 B | **7,179,446 B** (−54.0%) |
| render (JSON) | 50.3 ms | 14.6 ms |
| write incl. `fsync` | ~148 ms | **~60 ms** (parse ~35 + render 15 + `fsync` ~10) |
| read: decompress all segments | — | 11.2 ms |
| zlib ratio on `changes[]` | — | **4.2×** (12.2 MB → 2.9 MB) |
| round-trip verified | — | yes (`json.loads(zlib.decompress(...)) == sealed`) |

Sealing costs nothing at write time: a segment is compressed **once** when it
fills, and the write path only re-renders the plain-text tail plus the already
compressed blobs. (Compressing the whole array on every write would cost 217 ms —
measured — which is exactly the trap of doing this naively.)

### What it costs

- **History stops being readable with `jq`/`grep`/`git diff` as text.** `amg audit`
  and `amg digest` keep working (they would decompress), but an operator who greps
  the file for an op or a date loses that. For a project whose storage is "plain
  JSON so it can be reviewed in a diff", that is a real regression, not a detail.
- **`fingerprint`/`verify` semantics**: the state digest is unchanged (nodes/edges),
  but the history digest must be defined over the *decompressed* records, so the
  fingerprint stops being a function of the file bytes and becomes a function of
  the file's meaning. That has to be written down before it ships.
- **A format version bump.** Existing files stay readable (an uncompressed
  `changes[]` list is still valid input), but new writes would produce a shape old
  readers do not understand. So it is `amg/v2` with a migrate path, not a silent
  change.
- **New failure mode**: a corrupt blob is detected only when decompressed. `check`
  would have to decompress to validate, which is 11 ms it does not currently spend.

## Recommendation

Build **segmented compression inside the single file**, not the sidecar — and only
when the existing trigger fires:

> file > 20 MB, write p95 > 250 ms, nodes > 10k, **or** a real workflow hits
> `LockTimeout` with `AMG_LOCK_TIMEOUT` already raised.

Today the live graph is 15.6 MB / 147 ms per write, i.e. two-thirds of the way on
both axes, and the concurrency timeout is reproducible at 8 writers — so this is a
*when*, not an *if*. What it is not is urgent enough to take on the format bump and
the loss of text-greppable history without a user asking for it.

## If someone builds it: the checklist

1. Format: `amg/v2`, segment size as a constant, tail threshold as a constant.
2. Read path accepts v1 (plain list) and v2 (sealed segments + tail) — no flag, no
   dual behaviour to forget.
3. `check`, `audit`, `digest`, `fingerprint`, `export` all operate on the
   decompressed view; add a test that corrupting one blob is reported, not ignored.
4. `amg migrate` converts v1 → v2 in one atomic replace, and the old file stays
   byte-identical until the replace (same rule as `adopt`: never mutate the source).
5. Benchmarks rerun and the numbers above replaced with new ones — including the
   8-writer burst, which is the acceptance test.
6. `docs/WRITE-COST.md` and this file updated in the same commit; if the result is
   less than −30% write time, revert rather than keeping complexity for nothing.

## Reproduce the measurements

The prototypes are in this conversation's history, not in the repo; they only read a
graph and write to a temp directory. The reproducible parts are already in the repo:
`docs/WRITE-COST.md` (byte split, parse/render/fsync timings) and
`experiments/concurrency/run_stress.py --graph DIR` (burst, timeouts). The zlib
ratios above can be re-derived with:

```python
import json, zlib
doc = json.load(open("graph.json", encoding="utf-8"))
raw = json.dumps(doc["changes"], ensure_ascii=False, separators=(",", ":")).encode()
print(len(raw), len(zlib.compress(raw, 6)))   # 12,224,580 -> 2,907,090 on the live graph
```
