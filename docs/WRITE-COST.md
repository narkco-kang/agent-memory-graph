# Where the write cost goes (measured on the real graph)

The real-graph run ([`REAL-WORLD.md`](REAL-WORLD.md)) showed one write at **147 ms**
on a 15.3 MB graph. This page answers the next question — *what would make it
faster, and is any of it worth doing now* — by measuring the bytes and the time
rather than guessing.

Source: the same live graph, adopted to `amg/v1` (1,249 nodes, 640 edges, 2,559
change records, 15,580,438 bytes). Numbers from `perf_counter`, three iterations.

## Where the bytes are

| section | bytes | share |
|---|---|---|
| `changes[]` (event log) | 12,317,037 | **79.1%** |
| `nodes[]` | 3,079,209 | 19.8% |
| `edges[]` | 84,203 | 0.5% |
| document overhead | 99,988 | 0.6% |

The history is four fifths of the file. Any plan that starts by trimming *nodes*
is aimed at the small part.

## Where the time goes (one write = read, render, persist)

| step | time |
|---|---|
| parse `graph.json` (`json.load`, 15.6 MB) | 75.1 ms |
| render (`json.dumps`, indent=2) | 50.3 ms |
| `fsync` + replace | 22.5 ms |
| **total** | **147.9 ms** |

Which matches the single `add_node` measured end to end (147 ms). The cost is
dominated by moving 15.6 MB of JSON through the process **twice**, not by the disk.

## Options, with their measured payoff and their price

| option | measured payoff | price | verdict |
|---|---|---|---|
| **A. Cold-archive old nodes** (>30 d untouched) | **0 nodes qualify**: the oldest node in this graph is 6 days old, p50 = 1 day | a second file to keep consistent, plus audit coverage | **deferred** — nothing to reclaim today |
| **B. Move old `changes[]` to a sidecar file** | nodes+edges only = 3.22 MB, render 6.7 ms (vs 50.3); estimated write ≈ 30 ms, i.e. **−80%** | breaks the single-file atomic property: two files, one `os.replace` no longer covers both; `check`/`audit`/`digest`/`fingerprint` must span files; copying a graph stops being one file | **not now** — see below |
| **C. Compact JSON** (drop `indent=2`) | 15,209,100 bytes: **2.4% saved**, render 42.6 ms (vs 50.3) | destroys line-diffability, which is a stated design goal (graphs live in git) | **rejected** — 2.4% is not worth it |
| **D. Incremental writes** (touch only changed regions of the file) | theoretical | abandons the crash guarantee ("a reader sees old or new, never a mix"); every write path would need a journal of its own | **rejected** — the atomicity guarantee is the product |

## Decision

Nothing changes today. The trigger for revisiting stays the roadmap's:

> write p95 > 250 ms, **or** file > 20 MB, **or** nodes > 10k

Measured headroom: 147 ms / 15.6 MB against those thresholds — roughly two-thirds
of the way on both axes, and growing at about 12 MB of history per 1,000 writes at
this graph's density. When it trips, option **B** is the one with a real payoff,
and its price is explicit: the graph stops being one copyable file, so `check`,
`audit`, `digest` and `fingerprint` all gain a second input and the atomicity claim
has to be restated rather than quietly weakened.

(Policy note: the earlier signed ruling forbids adding an escape hatch that becomes
the default path — so there is no `--no-history` flag. If history ever moves, it
moves for everyone, with the guarantees rewritten.)

## Reproduce

```bash
PYTHONPATH=src python3 - <<'PY'
import json, os, sys, tempfile, time
sys.path.insert(0, "src")
from amg import Memory
from amg.store import dumps
src = "/path/to/legacy-graph.json"
dst = os.path.join(tempfile.mkdtemp(), "mem")
Memory.adopt(src, dst, group="probe")
doc, path = Memory.open(dst).doc, os.path.join(dst, "graph.json")
def ms(fn, n=3):
    t = time.perf_counter()
    for _ in range(n): fn()
    return round((time.perf_counter() - t) / n * 1000, 1)
print("parse", ms(lambda: json.load(open(path, encoding="utf-8"))))
print("dumps", ms(lambda: dumps(doc)))
print("sizes", {k: len(json.dumps(doc[k], indent=2).encode()) for k in ("nodes", "edges", "changes")})
PY
```

## Limits

- One graph, one week of history, one machine (macOS). A graph with years of
  history would show a higher share for `changes[]`, not a lower one.
- `fsync` cost depends on the filesystem; the 22.5 ms here is APFS on this laptop.
- Option B's 30 ms estimate is a projection from measured parts (parse of 3.2 MB,
  render 6.7 ms, `fsync` of 3.2 MB), not an implemented and measured feature. It is
  labelled as an estimate for that reason.
