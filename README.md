# agent-memory-graph (`amg`)

[![ci](https://github.com/narkco-kang/agent-memory-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/narkco-kang/agent-memory-graph/actions/workflows/ci.yml)

**Append-only, evidence-gated semantic memory graph for multi-agent workflows.**

A single-file memory layer for agent teams: what was decided, who is doing what, on
what evidence, and what has expired. No server, no database, no dependencies
(Python ≥ 3.10 standard library only).

A folder of documents comes with it, and most of them are measurements rather than
claims. **Start with [docs/README.md](docs/README.md)**: it says which document
answers which question, and which ones are proposals rather than shipped behaviour.

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
rewriting it — the rules and the measured result of doing so on a real 1063-node
graph are in [docs/ADOPTION.md](docs/ADOPTION.md):

```bash
amg adopt ./legacy-graph ./mem --pin-out ./legacy-pin.json
amg check ./mem && amg audit ./mem --pin ./legacy-pin.json
```

## What problem it solves

Long-running agent teams lose *factual* continuity: which decision is final, what is
blocked, which artifact hash was verified. Chat history is not a source of truth, and
summaries drift. `amg` keeps one append-only graph that survives model switches and
sessions, and it makes "we finished it" **mechanically impossible to record without
evidence**.

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

## Validity: supersede, never delete

```bash
amg status ./mem decision.v1 done --note "v1 approved" \
    --evidence "path:spec.md|<sha>|2026-10-29T18:00:00+08:00"
amg add    ./mem --id decision.v2 --type decision --label "v2 corrects v1" --source "review"
amg audit  ./mem
```

`supersede` stamps `valid_until` / `superseded_at` on the old node, keeps it in the
graph, and adds a `supersedes` edge. Active facts whose `valid_until` has passed are
an audit conflict.

## Fact time vs write time

`changes[].at` is **transaction time** (when the fact was written). It is not validity
time, and using it as one is measurably wrong: facts written 3/10/30 days after they
became true are mis-dated by exactly that lag (`experiments/valid_from_bias/`, 20/20
facts off by >1 day). So fact time is an input, never a guess:

```bash
amg add ./mem --id task.y --type task --label "migration approved" --source "review" \
    --valid-from 2026-01-15T09:30:00+08:00
```

- omitted `--valid-from` means **unknown**, not "now" (`valid_time_known: false`);
- `--valid-until` earlier than `--valid-from` is rejected (exit 2);
- a **future** `valid_from` is accepted but the fact is *not yet in effect*: `audit`
  says "not yet valid", retrieval and `digest` exclude it, expiry ignores it;
- expiry only ever fires when the validity window is known
  (`amg.audit.expiry_eligible`) — an unknown window is reported as a hint.

## Automatic expiry is opt-in

```bash
amg expire ./mem            # dry-run: reports what would expire, writes nothing
amg expire ./mem --apply    # supersedes expired facts, keeps them in history
```

Only facts with a **known** validity window can expire; the action marks them
`superseded` and appends an `expire` record — nothing is deleted, and running it twice
changes nothing. Facts with unknown validity (everything `amg adopt` migrates) are
skipped and counted, so adoption can never trigger mass expiry. There is no background
scheduler. Scheduling examples: [docs/SCHEDULING.md](docs/SCHEDULING.md).

## Retrieval (lexical only)

`amg search ./mem "…" --layer L1|L2|L3|L4 --k 10 [--strict]`

`superseded` nodes are **never returned**; facts whose `valid_from` is in the future
are dropped the same way. History is not lost — it stays in L2 (`changes[]`), the only
layer that shows it. Ranking is two-key: **(anchor present, score)**; results without
evidence are returned by default with `anchor_state: "none"` instead of being dropped,
because on a real graph only 22–36% of lexical hits had anchors and hard-filtering by
default would hide most of the memory (`--strict` is the only anchor filter).

**Not implemented** — measured against a pre-registered bar and rejected for the
default path, or simply out of scope; do not assume them: vector / embedding search
(`experiments/retrieval_eval/`), authentication, multi-tenant isolation,
authorization, a TTL daemon, Windows file-locking verification, node archiving, and
any benchmark above 1,289 nodes. Every one of these is repeated in the document that
would otherwise imply it.

## Measurement, not marketing

`experiments/valid_from_bias/` measures whether transaction time can stand in for fact
time; the numbers are asserted in CI, so the safety feature cannot be quietly removed
later. Every performance claim in this README and in `docs/` comes from a script in
`benchmarks/`, and load sensitivity is printed with it.

## Layout

```
src/amg/       memory (the only public entry point), store, gate, protocol,
               retrieval, digest, audit, migrate, adopt, archive, cli, mcp
tests/         unittest: `python -m unittest discover -s tests -v`
experiments/   reproducible measurements behind the design decisions
tools/         CI gates: doc/code symbols, doc size budgets, dist contents
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success / clean check |
| 1 | protocol violation / check errors / audit conflicts |
| 2 | usage error (bad args, unknown enum, missing graph) |
| 3 | lock timeout / IO failure |

## Prior art (we are not first, and we say so)

MAP-Graph, Letta MemFS, Graphiti, Mem0/A-MEM, governed shared memory — the five
systems this project is measured against, with quotes and the two design commitments
that are **not ours and not implemented here**, are in
[docs/PRIOR-ART.md](docs/PRIOR-ART.md). What ships is the discipline pipeline: task
state as the authority face, expiry as a first-class citizen, write-back as a hard
gate. None of the three is new on its own; the combination, and the refusal to claim
more, is the position.

## MCP server (stdio)

`amg mcp <dir>` exposes the graph to any MCP client over stdin/stdout — no port, no
network, eight tools, all through the same `Memory` methods so the evidence gate
applies unchanged. **No authentication**: whoever can start the process can read and
write. `--read-only` refuses the write tools and advertises only the five read tools,
enforced twice (server dispatch and `Memory` commit). Why authorization is out of
scope by decision, not omission: [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md) §8.
Runnable client: `python examples/mcp_client.py`.

## Handoff cards, cold archive, read audit

- **Handoff** — `amg handoff` stores where the work stands as one bounded card
  (≤ 4,096 B, one active at a time, previous superseded rather than deleted); `audit`
  also enforces that on graphs edited by hand: [docs/HANDOFF.md](docs/HANDOFF.md).
- **Cold archive** — `amg archive` moves old change records out of the live file and
  proves the move five ways on every run (snapshot, payload re-read, remainder +
  pointer, unchanged state digest, contiguous revs), rolling back if the proof fails.
  Moved history stays searchable on request — `amg search --layer L2
  --include-archive` marks which file each old hit came from:
  [docs/ARCHIVE.md](docs/ARCHIVE.md).
- **Read audit** — opt-in `--audit-read` logs only high-risk reads (L4 access,
  `--strict`, superseded hits) to a bounded rotated `reads.jsonl`. Not claimed as
  novel: no precedent was found in five checked projects, and "no precedent" is not a
  shipped capability.

## Fingerprints (tamper evidence, honestly scoped)

`amg fingerprint ./mem --out ./mem.fp.json` records two digests — current state and the
change log — and `amg verify ./mem --expect ./mem.fp.json` exits 1 when the file no
longer matches. Keeping them separate is the useful part: a node edited directly in
the file moves the state digest while the history digest stays put. It is not tamper
*proof*: whoever can write the file can recompute the digests; the evidence comes from
keeping the fingerprint somewhere else: [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md) §7.

## Measured on real graphs

A live 1,289-node / 15.7 MB graph is adopted and measured end to end in
[docs/REAL-WORLD.md](docs/REAL-WORLD.md) — 140 ms to adopt, 0 structural errors,
`audit --pin` to 3 genuine conflicts, reads in single-digit milliseconds, one write at
147–226 ms. Where those bytes go, and what archiving reclaims:
[docs/WRITE-COST.md](docs/WRITE-COST.md) and [docs/ARCHIVE.md](docs/ARCHIVE.md).
Concurrent writers (eight processes, 200 writes, 0 lost, 0 duplicated) and the
latency tail: [docs/CONCURRENCY.md](docs/CONCURRENCY.md).

## Roadmap, contributing, security

Design history and rejected alternatives:
[docs/DESIGN-HISTORY.md](docs/DESIGN-HISTORY.md). Contributions:
[CONTRIBUTING.md](CONTRIBUTING.md) — the gates in `tools/` are the review checklist.
Security posture and reporting: [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
