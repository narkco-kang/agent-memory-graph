# Real-world run: 1,249-node graph, 15.3 MB

Everything else in `docs/BENCHMARKS.md` uses synthetic graphs. This page is one
run against a **live** graph that has been written daily by a multi-agent team for
a week: 1,249 nodes, 640 edges, 2,558 change records, 15,297,657 bytes.

Method (re-runnable, no private content copied into this repository):

1. copy nothing — `amg adopt` reads the source in place and writes a new directory;
2. record the source `sha256` before and after (it must not change);
3. run `check`, `audit`, `audit --pin`, `expire` (dry-run), `fingerprint`,
   `doctor`, `search`, `digest`, `related` and one write, timing each with
   `perf_counter`;
4. publish aggregates only — no node ids, labels or notes leave the source graph.

## Results

| step | result | time |
|---|---|---|
| `adopt` (legacy → `amg/v1`, 15.3 MB) | 1,249 → 1,249 nodes, 640 → 636 edges (4 duplicate edges merged), 2,558 → 2,570 changes (adoption recorded) | **140 ms** |
| source file after adopt | `sha256` unchanged | — |
| `check` | **0 errors** | 4.4 ms |
| `audit` (no pin) | **1,029 conflicts** — 1,026 × `done` without evidence (IR-4), 3 × stale | 2.6 ms |
| `audit --pin` (pin from adopt) | **3 conflicts**, pin report `match: true` | 2.6 ms |
| `audit` hints | 568 × conclusion without evidence grade, 1 × unknown-validity summary | — |
| `expire` (dry-run) | 0 eligible, 30 already superseded, 0 skipped — no node carries `valid_until` at all | 78 ms |
| `fingerprint` | state + history digests, rev 2,570 | 64 ms |
| `doctor` | no hygiene findings | 0.1 ms |
| `search` k=10 | 3 generic queries | 6.7 / 7.0 / 7.5 ms |
| `search` k=50 | 50 hits returned | 6.2 ms |
| `digest` (65,536 B budget) | 65,511 bytes — under budget, truncation reported | 3.3 ms |
| `related` depth 1 | 3 neighbours | 0.5 ms |
| one `add_node` on the adopted graph | file rewritten atomically | **147 ms** |

## What these numbers say

1. **Migration is cheap and honest.** 15 MB in 140 ms, source untouched, zero
   structural errors after adoption. The 1,026 IR-4 conflicts are the *point* of
   the design: legacy records are `done` with evidence stored as bare strings, and
   adoption refuses to invent `content_sha256` for them. The exemption pin, which
   records the hash of the sorted id list at adoption time, drops the count to 3 —
   and those 3 are genuine staleness that no tool should paper over.
2. **Reads are not the problem at this size.** Every read path is single-digit
   milliseconds on a 15 MB graph: `check` 4.4 ms, `audit` 2.6 ms, `digest` 3.3 ms,
   `search` ~7 ms.
3. **The write path is where the wall is.** `add_node` takes 147 ms because the
   store rewrites and `fsync`s the whole file. That is linear in file size, and it
   is the number behind the roadmap trigger "write p95 > 250 ms or file > 20 MB or
   nodes > 10k": today's graph is 15.3 MB and 147 ms, i.e. roughly two-thirds of
   the way to the trigger on both axes.
4. **Expiry is inert on migrated data, by design.** No node carries `valid_until`,
   so `expire` finds nothing to do — the honest state, not a failure. A month of
   writes without anyone recording a validity window means the TTL machinery
   cannot act, which is exactly why expiry is opt-in.

## What this run does not tell you

- **No concurrency.** One process, one writer. The advisory lock was exercised
  only by the test suite (`test_lock.py`), not under load.
- **One graph, one week, one team.** 1,249 nodes is not 10k; the synthetic
  benchmarks cover that separately and are labelled as synthetic.
- **Windows and macOS numbers are not here** — this run is on macOS. Correctness
  on Windows is in CI; latency there is unmeasured.
- **The 3 stale conflicts are left unfixed** on purpose. Fixing them by touching
  nodes would make `audit` green without changing the underlying state, which is
  the failure mode `--pin` exists to avoid. They stay visible.
- **No content inspection.** This page deliberately contains no node text, no
  labels and no ids, because the source graph is internal.

## Reproduce on your own graph

```bash
SRC=/path/to/legacy-graph.json
D=$(mktemp -d)/mem
time amg adopt "$SRC" "$D" --group my-group --pin-out /tmp/pin.json
shasum -a 256 "$SRC"                      # unchanged
time amg check "$D"                       # 0 errors
amg audit "$D" --json | jq '.conflicts|length'
amg audit "$D" --pin /tmp/pin.json --json | jq '.conflicts|length'
time amg expire "$D"                      # dry-run
amg fingerprint "$D" --out /tmp/fp.json
amg doctor "$D"
```
