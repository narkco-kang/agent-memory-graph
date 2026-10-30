# Real-world runs: two live graphs

Everything else in `docs/BENCHMARKS.md` uses synthetic graphs. This page has
measurements from two **live** `group-kg/v1` graphs written daily by a multi-agent
team, of deliberately different shape:

- a command-centre graph: 1,249 nodes, 640 edges, 2,558 changes, 15.3 MB;
- this project's own bookkeeping graph: 187 nodes, 152 edges, 429 changes, 0.44 MB,
  no validity windows and legacy evidence throughout.

The second one exists because a single graph invited readers to treat its numbers as
general. Where the two disagree, the shape is usually the explanation, and the
sections below say which numbers move and why.

Method (re-runnable, no private content copied into this repository):

1. copy nothing — `amg adopt` reads the source in place and writes a new directory;
2. record the source `sha256` before and after (it must not change);
3. run `check`, `audit`, `audit --pin`, `expire` (dry-run), `fingerprint`,
   `doctor`, `search`, `digest`, `related` and one write, timing each with
   `perf_counter`;
4. publish aggregates only — no node ids, labels or notes leave the source graph.

Step 3 is now code: `benchmarks/real_graph.py <graph.json>` performs the whole run
and prints the table below. Timings are **in-process** (library calls), matching this
page; a CLI invocation additionally costs ~48–51 ms of interpreter startup, measured
by the script and reported separately, so the two kinds of number are never mixed.

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
- **Two graphs, both from one team's tooling.** That is twice the evidence, not a
  representative sample; 1,282 nodes is still not 10k, and the synthetic benchmarks
  cover that separately and are labelled as synthetic.
- **Windows and macOS numbers are not here** — this run is on macOS. Correctness
  on Windows is in CI; latency there is unmeasured.
- **The 3 stale conflicts are left unfixed** on purpose. Fixing them by touching
  nodes would make `audit` green without changing the underlying state, which is
  the failure mode `--pin` exists to avoid. They stay visible.
- **No content inspection.** This page deliberately contains no node text, no
  labels and no ids, because the source graph is internal.

## Second live graph: 187 nodes, different shape

The first graph is a command centre: tasks, decisions and artefacts, 15.4 MB, mostly
written by an agent pipeline. The second is this project's own bookkeeping graph —
187 nodes, 437,602 bytes, rev 429 — and its shape is different in the ways that
matter for this library: **no node carries a validity window**, 115 of 187 nodes hold
legacy evidence as bare locator strings, and the graph is 35× smaller.

| step | result | time |
|---|---|---|
| `adopt` | 187 → 187 nodes, 152 → 149 edges (3 duplicate edges merged), 429 → 430 changes | **6 ms** |
| source file after adopt | `sha256` unchanged | — |
| `check` | **0 errors** | 0.4 ms |
| `audit` (no pin) | **172 conflicts** — 172 × `done` without evidence (IR-4) | 0.4 ms |
| `audit --pin` | **0 conflicts**, pin report `match: true` | 0.3 ms |
| `expire` (dry-run) | 0 eligible — no node carries `valid_until` | 2.7 ms |
| `fingerprint` | state + history digests, rev 430 | 1.7 ms |
| `doctor` | no hygiene findings | 0.0 ms |
| `search` k=10 / k=50 | 10 hits | 0.4 / 0.4 ms |
| `digest` (65,536 B budget) | 65,526 bytes | 0.4 ms |
| `related` depth 1 | 11 neighbours | 0.1 ms |
| one `add_node` | file rewritten atomically | **4 ms** |

## Re-running the first graph later: the numbers move, and should

The measurement above is dated. Re-running the same script on the same live graph at
rev 2,604 (it kept being written) gives:

| step | first run (rev ~2,570) | re-run (rev 2,604) |
|---|---|---|
| nodes / edges / changes | 1,249 / 636 / 2,570 | 1,282 / 635 / 2,594 |
| `adopt` | 140 ms | 142 ms |
| `check` | 4.4 ms | 4.0 ms |
| `audit` (no pin) | 1,029 conflicts | 1,059 conflicts |
| `audit --pin` | **3** conflicts | **4** conflicts |
| `expire` (dry-run) | 78 ms | 78.5 ms |
| `fingerprint` | 64 ms | 65.5 ms |
| `search` k=10 | 6.7–7.5 ms | 6.9 ms |
| one `add` | 147 ms | 153 ms |

The pinned-conflict count went **3 → 4** because time passed: staleness is a
property of *now*, not of the graph. A tool that reported a constant here would be
reporting the wrong thing.

## What the two graphs say together

- **Read paths are flat and fast**: single-digit milliseconds on both, 15.4 MB and
  0.44 MB alike. The `audit` conflict count grows with data; its *time* does not.
- **Write cost tracks file size**, not node count: ~4–6 ms at 0.44 MB, ~153 ms at
  15.4 MB — about 10 ms per MB, which is the whole-file rewrite plus `fsync`. That is
  why the trigger is stated in bytes as well as nodes.
- **The IR-4 conflict count measures legacy evidence format, not graph health**:
  172 of 172 `done` nodes here, 1,026 of 1,249 there — both collapse under the pin
  (to 0 and 4 respectively). Without the pin the number would say "almost everything
  is broken", which would be false.
- **Expiry is inert in both, for the same reason**: nobody records `valid_until`.
  Same honest state on 187 nodes and on 1,282.
- **Adoption cost is linear in bytes**: 6 ms for 0.44 MB, 142 ms for 15.4 MB.

## What the 4 pinned conflicts actually are

"3–4 stale conflicts" has been quoted often enough that it deserves a breakdown. On
the first live graph at rev 2,604, with the adoption pin applied, all four conflicts
are staleness, and they are not all the same kind:

| node type | status | untouched | has note | has owner |
|---|---|---|---|---|
| `group` | in_progress | 7 d | yes | no |
| `decision` | in_progress | 7 d | yes | no |
| `issue` | in_progress | 5 d | yes | yes |
| `task` | blocked | 3 d | yes | yes |

Two conclusions, the second less comfortable:

1. **Three of the four are real debt**: work items untouched for 3–7 days, owned,
   with notes. Nothing is wrong with the tool; the team has not closed them. Fixing
   them by editing status would make `audit` green without the work being done, which
   is why they stay visible.
2. **One of the four was a false positive**, and 0.7.7 fixed it: `group` nodes are
   long-lived by nature — a group marked `in_progress` stays that way for the life of
   the group, and its `updatedAt` does not move when its children change. The rule
   assumes a short-lived work item, so `group`, `env` and `member` (registrations, not
   work) are now exempt (DECISIONS #20). The refusal to change it quietly is the
   point: audit output is a contract, so the change came with a decision, four tests
   and this note.

Measured after the fix, on the same graph at rev 2,610 (1,288 nodes):
`audit --pin` reports **3 conflicts**, `pin match: true` — the three work items above,
and no registry node. The unpinned count is 1,064, i.e. the legacy-evidence class
grew with the graph.

Each of those conflicts is also a structured finding (`kind: stale_work_item`) carrying
the node, its type, its status, its owner and `age_days` — so an agent can act on
"whose item is 7 days old" without parsing the sentence (v0.9.0).

The threshold is configurable (`AMG_STALE_DAYS`, or `--stale-days` for one run),
because "too long" depends on the team's cadence. On that graph it reads:

| threshold | conflicts |
|---|---|
| 3 days (default) | 3 |
| 7 days | 1 |
| 14 days | 0 |
| 30 days | 0 |

A team that meets weekly would see three false alarms at the default; one that meets
monthly would see none at 30. The tool cannot know which team it is, so it does not
pretend to: default stays 3 (the original rule), the knob is one environment variable,
and invalid values fall back to the default rather than silently disabling the check.

The unpinned `audit` on the same graph reports about 1,060 conflicts, which is also
worth reading precisely: they are almost all "`done` without structured evidence",
the legacy-format artefact — not 1,060 broken facts.

## Measurement conditions: the same file, up to 25× slower

Every timing on this page was taken on an otherwise idle machine, and that is part of
the measurement, not a footnote. The same `adopt` of the same 15.4 MB file:

| when | load average (1 min) | `adopt` |
|---|---|---|
| published run | < 1 | 140 ms |
| re-run a few hours later | < 1 | 142 ms |
| while the host was busy | 24.8 | **1,055 ms** |

CLI startup shows the same effect: 48 ms idle, **552 ms at load 24**. So the numbers
here are only comparable against runs at similar load, which is why
`benchmarks/real_graph.py` now prints the load average and flags runs above 2.0 as
inflated. Comparing a loaded run against an idle one says nothing about the code.

## Reproduce on your own graph

```bash
# one command, prints the whole table (in-process timings and aggregates only)
python3 benchmarks/real_graph.py /path/to/graph.json --label "my graph"

# or step by step through the CLI
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
