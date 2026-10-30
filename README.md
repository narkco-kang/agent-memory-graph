# agent-memory-graph (`amg`)

[![ci](https://github.com/narkco-kang/agent-memory-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/narkco-kang/agent-memory-graph/actions/workflows/ci.yml)

**Append-only, evidence-gated semantic memory graph for multi-agent workflows.**

A single-file memory layer for agent teams: what was decided, who is doing what,
on what evidence, and what has expired. No server, no database, no dependencies
(Python ≥ 3.10 standard library only).

```bash
pip install -e .
amg init ./mem --group my-team --goal "ship the thing"
# bulk write: one load, one atomic write, all-or-nothing
amg import ./mem --from nodes.json
amg add   ./mem --id task.a --type task --label "write the parser" --source "standup 2026-10-29"
amg status ./mem task.a in_progress --note "started, branch feat/parser"
amg search ./mem "parser" --json
amg check ./mem --strict
```

Already have a graph from the earlier `group-kg/v1` format? Adopt it instead of
rewriting it:

```bash
amg adopt ./legacy-graph ./mem --pin-out ./legacy-pin.json
amg check ./mem
amg audit ./mem --pin ./legacy-pin.json
```

## What problem it solves

Long-running agent teams lose *factual* continuity: which decision is final, what
is blocked, which artifact hash was verified. Chat history is not a source of
truth, and summaries drift. `amg` keeps one append-only graph that survives model
switches and sessions, and it makes "we finished it" **mechanically impossible to
record without evidence**.

Four invariants are enforced by code, not by discipline:

| ID | Invariant | Where |
|---|---|---|
| IR-1 | Append-only: no delete API; `changes[]` only grows; `supersede` keeps the old node with a validity window | `src/amg/memory.py` |
| IR-2 | Every node has a real `source` (`unknown` / `manual` are rejected) | `src/amg/protocol.py` |
| IR-3 | Every mutation is followed by a verifiable check (0/1/2/3 exit codes) | `src/amg/cli.py` |
| IR-4 | A conclusion-typed node cannot be `done` without evidence objects | `src/amg/gate.py` |

## Evidence is an object, not a string

```json
{"locator": "path:docs/API.md", "content_sha256": "…64 hex…",
 "captured_at": "2026-10-29T18:00:00+08:00", "graph_rev": 12, "grade": 2}
```

- `content_sha256` is the hash of the **cited artifact**. A node id or a graph rev
  must never stand in for it.
- Bare strings (`"path:README.md"`) are rejected: they cannot be verified.
- `grade` 1–5 records how strongly the evidence was verified (1 = reproduced on
  disk / executed; 5 = claim only). Retrieval quality is a *separate* field.
- Fact time is separate again: `valid_from` / `valid_until` are caller-supplied
  (or unknown) and are never inferred from the write time.

## Adopting an existing graph

`amg adopt <src> <dst>` reads a legacy `group-kg/v1` graph and writes an
`amg/v1` graph into a **new** directory. It never writes to the source, never
overwrites the destination, and it refuses to invent data:

- legacy evidence strings cannot become evidence objects (we do not hold the
  cited artifact), so they stay in `legacy_evidence` and `evidence` is empty —
  `audit` keeps reporting them as legacy debt instead of pretending they're fine;
- placeholder sources become explicit provenance `adopted:<schema>:<sha12>`;
- `superseded_at`/`valid_until` inferred from `updatedAt` are flagged
  `superseded_at_inferred`; `valid_from` stays `null` when unknown;
- duplicate ids, unknown enums and dangling edges are refusals (dangling edges
  can only be dropped with `--drop-dangling`, and the count is reported).

Measured on our own 1063-node graph (source snapshot 2026-10-29, adopted copy in
`/tmp`, source byte-identical afterwards):

| | before | after |
|---|---|---|
| `check` errors | 1143 | **0** |
| edges | 580 | 576 (4 duplicate identical triples merged, counted) |
| placeholder sources | 451 | 0 (replaced by `adopted:…` provenance) |
| evidence | 658 strings, 0 valid objects | 658 in `legacy_evidence`, 0 claimed |
| `superseded` without timestamp | 29 | 0 (inferred from `updatedAt`, flagged) |

`audit --pin` then leaves **4 conflicts**: stale `in_progress`/`blocked` nodes
untouched for 4–5 days. Those are real hygiene debt of that graph, not artifacts
of adoption, and they are reported rather than silenced.

## Validity: supersede, never delete

```bash
amg status ./mem decision.v1 done --note "v1 approved" --evidence "path:spec.md|<sha>|2026-10-29T18:00:00+08:00"
amg add    ./mem --id decision.v2 --type decision --label "v2 corrects v1" --source "review"
amg status ./mem decision.v2 done --note "approved" --evidence "path:spec.md|<sha>|2026-10-29T18:10:00+08:00"
amg audit  ./mem
```

`supersede` stamps `valid_until` / `superseded_at` on the old node, keeps it in the
graph, and adds a `supersedes` edge. Active facts whose `valid_until` has passed
are an audit conflict.

## Fact time vs write time

`changes[].at` is **transaction time** (when the fact was written). It is not
validity time, and using it as one is measurably wrong: facts written 3/10/30 days
after they became true are mis-dated by exactly that lag
(`experiments/valid_from_bias/`, 20/20 facts off by >1 day).

So fact time is an input, never a guess:

```bash
amg add ./mem --id task.y --type task --label "migration approved" --source "review" \
    --valid-from 2026-01-15T09:30:00+08:00
```

- omitted `--valid-from` means **unknown**, not "now" (`valid_time_known: false`);
- `--valid-until` earlier than `--valid-from` is rejected (exit 2);
- a **future** `valid_from` is accepted but the fact is *not yet in effect*:
  `audit` says "not yet valid", retrieval and `digest` exclude it, and expiry
  ignores it;
- expiry only ever fires when the validity window is known
  (`amg.audit.expiry_eligible`) — an unknown window is reported as a hint.

## Automatic expiry is opt-in

```bash
amg expire ./mem            # dry-run: reports what would expire, writes nothing
amg expire ./mem --apply    # supersedes expired facts, keeps them in history
```

Only facts with a **known** validity window can expire. The action marks them
`superseded` and appends an `expire` record — no node is deleted, and running it
twice changes nothing. Facts with unknown validity (everything `amg adopt`
migrates) are skipped and counted, so adoption can never trigger mass expiry.
There is no background scheduler: expiry happens when you run the command.

## Retrieval (v0.1: lexical only)

`amg search ./mem "…" --layer L1|L2|L3|L4 --k 10 [--strict]`

`superseded` nodes are **never returned**: expiry is a first-class citizen, so
L1/L3/L4 drop them before ranking, and `digest` excludes them while printing
`superseded excluded: N`. Facts whose `valid_from` is still in the future are
dropped the same way (`not yet valid excluded: N`). History is not lost — it
stays in L2 (`changes[]`), which is the only layer that shows it.

Ranking is two-key: **(anchor present, score)**. Results without evidence are
returned by default with `anchor_state: "none"` instead of being dropped —
`--strict` is the only filter *for anchors*. This is deliberate: on a real graph
only 22–36% of lexical hits had anchors, so hard-filtering by default would hide
most of the memory. (Superseded filtering is a different rule and is not
optional; `--strict` does not re-enable expired facts.)

**Not implemented in v0.1** (planned, and documented as such): vector / embedding
search, MCP server, authentication, multi-tenant isolation, a TTL scheduler
(`amg expire` is an explicit opt-in command; nothing expires in the
background), Windows file locking, and any 10k-node benchmark above 1,063 nodes.
Do not assume them.

One rule is enforced *before* that feature exists: adopted nodes carry
`valid_time_known: false`, and expiry must refuse them (`amg.audit.expiry_eligible`)
— `audit` reports an expired `valid_until` on such a node as a hint, not a
conflict. Deleting a fact on the strength of a timestamp we never had would be
worse than having no TTL at all.

## Measurement, not marketing

`experiments/valid_from_bias/` measures whether transaction time can stand in for
fact time. For facts written 3 / 10 / 30 days after they became true, the
`changes[].at` proxy is off by exactly that lag (20/20 exceed 1 day; the
zero-lag control group is 0/10). That is why `valid_from` is never back-filled
from the change log, and why v0.2 has to accept an explicit fact-time input
instead of inferring it. The numbers are asserted in CI, so the safety feature
cannot be quietly removed later.

## Layout

```
src/amg/
  memory.py    Memory — the only public entry point
  store.py     advisory lock + full-graph atomic replace
  gate.py      evidence gate (the only component allowed to reject a write)
  protocol.py  IR-1..IR-4 structural checks
  retrieval.py L1/L2/L3/L4 lexical retrieval
  digest.py    bounded, pointer-only consolidation (M4)
  audit.py     legacy coverage, staleness, expiry, integrity
  migrate.py   normalize legacy `changes[]` shapes
  adopt.py     legacy graph -> amg/v1, never fabricating evidence
  cli.py       16 commands, exit codes 0/1/2/3
tests/         unittest, run with `python -m unittest discover -s tests -v`
experiments/   reproducible measurements behind the design decisions
tools/check_doc_symbols.py  CI gate: every documented capability needs a symbol
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success / clean check |
| 1 | protocol violation / check errors / audit conflicts |
| 2 | usage error (bad args, unknown enum, missing graph) |
| 3 | lock timeout / IO failure |

## Prior art (we are not first, and we say so)

- **MAP-Graph** (arXiv:2608.10509) — multi-agent shared memory with provenance,
  task scope, and risk gating. Closest prior work.
- **Letta MemFS** — memory as a git repository of Markdown, shared via
  commit/push/pull; version history and content hashes.
- **Graphiti** — bi-temporal invalidation (supersede, never delete) and
  episode→fact provenance; has a pluggable judgment backend (Jev).
- **Mem0 / A-MEM** — additive extraction and memory evolution; A-MEM rewrites
  prior memory in place, which is also a known error-propagation risk.
- **Governed Shared Memory for Multi-Agent LLM Systems** (arXiv:2606.24535) —
  scoped retrieval, provenance, temporal supersession, policy propagation in a
  production service; also documents that a synchronous near-duplicate gate can
  pre-empt an asynchronous contradiction detector and wrongly reject writes.

What this repository actually ships is the **discipline pipeline**: task state as
the authority face, expiry as a first-class citizen, and write-back discipline as
a hard gate. Each of the three exists as code with tests. None of the three is
new on its own — Letta MemFS, Graphiti and CrewAI cover parts of it.

Two further ideas are **design only in v0.1, and neither is implemented**: hard
authorization kept separate from graded trust, and evidence requirements scaling
with action risk. Do not read them as features:

```bash
grep -rnE "authoriz|permission|read_only" src/amg/   # no matches
grep -rn "risk" src/amg/                             # no matches
```

Read-side audit ("who read what") is likewise not implemented in v0.1, and is
not claimed as novel: independent verification found no prior implementation in
the five projects checked, but "no precedent" is not a shipped capability.

## Edges

`amg related <id> [--depth N] [--kind K]` walks edges in both directions;
`amg search ... --expand` attaches 1-hop neighbors of each hit (marked
`expanded_from`). `depends_on` / `supersedes` must stay acyclic (`check` errors on
a cycle); other kinds may cycle and are only counted.

## Read-side audit (opt-in)

Writes are always logged in `changes[]`; reads are not, unless you ask for it.
`--audit-read` logs only high-risk reads — L4 rule access, `--strict` queries, and
results that include superseded nodes — to a bounded, rotated `reads.jsonl`
(1 MiB per segment, one segment kept). Reads are never written into `changes[]`.
Note that `reads.jsonl` contains query text.

## Expiry scheduling

Expiry is a command, not a daemon: `amg expire ./mem --apply` is safe to run from
cron or a systemd timer (dry-run by default, idempotent, never deletes, refuses
unknown validity). See [docs/SCHEDULING.md](docs/SCHEDULING.md) for examples and
the rollback story.

## Roadmap, contributing, security

The backlog is public as GitHub issues (batch ingest, vector retrieval, MCP
server, auth/multi-tenancy, read-side audit, expiry scheduler, Windows locking,
edge benchmarks). See [CONTRIBUTING.md](CONTRIBUTING.md) for the rules — the
short version is: docs must equal code, no unverified claims, never fabricate an
evidence hash. Security posture: local single-tenant file store, **no auth**, no
network — see [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
