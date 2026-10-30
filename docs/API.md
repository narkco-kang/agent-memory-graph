# amg v0.1 API contract

The contract is also a CI fixture: `tools/check_doc_symbols.py` fails the build if a
capability named here has no code symbol.

## CLI

```
amg init   <dir> --group NAME [--goal TEXT]          # refuses to overwrite
amg add    <dir> --id --type --label --source [--status --owner --note --evidence ...]
amg import <dir> --from FILE.json                   # batch: all-or-nothing, one write
                    [--valid-from ISO8601] [--valid-until ISO8601]
amg status <dir> <id> <new-status> --note TEXT       # note required (IR-4)
amg link   <dir> --from ID --to ID --kind KIND
amg supersede <dir> OLD NEW --note TEXT            # keep the old node, stamp its window
amg search <dir> "query" [--layer L1|L2|L3|L4] [--k 10] [--strict] [--expand] [--json]
amg related <dir> ID [--depth N] [--kind KIND] [--json]   # walk edges (new in v0.2)
amg digest <dir> [--max-bytes 65536] [--out PATH]
amg check  <dir> [--strict] [--json]
amg audit  <dir> [--pin baseline.json] [--json]
amg export <dir> [--format json|jsonl]
amg mcp   <dir>                                     # MCP server over stdio (no network)
amg doctor <dir>                                     # cleans stale tmp files
amg migrate <dir>                                    # normalizes legacy changes[]
amg adopt  <src> <dst> [--group NAME] [--drop-dangling] [--pin-out PATH] [--dry-run]
amg expire <dir> [--apply] [--json]                # opt-in TTL expiry (dry-run default)
amg version
```

`--audit-read` is available on `search` and `related` (see below).

`--evidence` takes `locator|content_sha256|captured_at[|grade]` (repeatable).

`amg import` takes a JSON file shaped as `{"nodes": [...], "edges": [...]}` (a
bare list is treated as `nodes`). It is **all-or-nothing**: every node and edge is
validated with the same gates as a single write, and the file is written once
only if the whole batch passes. Duplicate ids (against the graph or inside the
batch), unknown enums, missing sources and conclusion-typed `done` nodes without
evidence reject the entire batch.

Exit codes: `0` success/clean, `1` protocol violation or conflicts, `2` usage,
`3` lock timeout or IO failure.

## Exit-code classification (signed 2026-10-29)

`2` means *the caller used the API wrong*; `1` means *the content violates the
protocol*. There is **no default**: a code missing from the table makes the CLI
fail loudly instead of guessing, and `tests/test_exit_codes.py` scans
`src/amg/*.py` to prove every raised code is classified.

| exit | codes | meaning |
|---|---|---|
| `2` | `E_NO_GRAPH` · `E_BAD_TYPE` · `E_BAD_STATUS` · `E_BAD_LAYER` · `E_BAD_EDGE` · `E_BAD_FORMAT` · `E_BAD_ID` · `E_EXISTS` · `E_RULE_APPLIES` · `E_RULE_EXPIRES` · `E_USE_SUPERSEDE` · `E_BAD_SUPERSEDE` · `E_BAD_VALID_TIME` · `E_BAD_VALID_RANGE` · `E_ALREADY_AMG` · `E_BAD_BATCH` · `E_BAD_FILE` · `E_BAD_DEPTH`* | wrong argument, unknown enum, or wrong target — the call was wrong, not the data |
| `1` | `E_NO_SOURCE` · `E_NOTE_REQUIRED` · `E_EVIDENCE_MISSING` · `E_EVIDENCE_FORMAT` · `E_DUP_ID` · `E_DUP_EDGE` · `E_NO_NODE` · `E_IMMUTABLE` · `E_ADOPT_UNSUPPORTED`* · `E_ADOPT_DANGLING`* | the evidence gate rejected the content, or the graph would break an invariant |
| `0` | — | success / clean `check` / clean `audit` |
| `3` | — | lock timeout or IO failure (not a `ProtocolError`) |

`*` adopt-specific codes: `E_ALREADY_AMG` means `adopt` was pointed at an
`amg/v1` graph (wrong target); `E_ADOPT_UNSUPPORTED` / `E_ADOPT_DANGLING` mean
the legacy source itself violates the protocol (unknown enum / duplicate id /
dangling edge).

`E_EVIDENCE_FORMAT` is exit **1** on purpose: it looks like a format error, but
it is the gate rejecting content, and it must never masquerade as a bad command
line.

## Edges and traversal (v0.2)

`amg related <id> [--depth N] [--kind KIND]` walks edges in both directions and
returns each neighbor with the connecting edge, its direction, the depth it was
reached at, and `anchor_state`. `search --expand` attaches 1-hop neighbors of each
hit, marked `expanded_from`.

Cycle policy: `depends_on` and `supersedes` must form a DAG — a cycle there is a
`check` error. Other kinds may legitimately cycle and are only counted as a hint.

## MCP server (stdio, v0.3)

`amg mcp <dir>` speaks newline-delimited JSON-RPC 2.0 on stdin/stdout and exposes
eight tools: `memory_search`, `memory_add`, `memory_status`, `memory_supersede`,
`memory_related`, `memory_check`, `memory_audit`, `memory_digest`.

- **stdio only** — it opens no socket and listens on no port.
- **no new write paths** — every tool calls the same `Memory` methods, so the
  evidence gate, IR-2 and IR-4 apply unchanged. A rejected write is returned as
  `isError: true` with the protocol error code in the text.
- **no authentication.** Whoever can start the process can read and write the
  graph. It is a local, trusted, single-user tool; do not wrap it in a network
  transport without adding an authorization layer first.
- stdout carries protocol frames only; diagnostics go to stderr.

## Read-side audit (opt-in, v0.3)

`--audit-read` on `search` / `related` writes a JSONL event to `<graph>/reads.jsonl`
only when the read is **high-risk**: `--layer L4` (rule access), `--strict`
queries, or results that include `superseded` nodes. Default reads stay zero-cost
and are not logged.

- Not written into `changes[]`: read events would drown the write ledger, and
  `changes[]` is append-only so it could never be rotated.
- Bounded and rotated: 1 MiB per segment, one older segment kept (`reads.jsonl.1`).
- `reads.jsonl` contains query text — treat it as data, not as a secret store.

## Python

```python
from amg import Memory, ProtocolError, LockTimeout

m = Memory.open("./mem")          # Memory.init("./mem", group="t")
m.add_node(id="task.x", type="task", label="do X", source="group:t 2026-10-29")
m.add_node(id="task.y", type="task", label="do Y", source="plan",
           valid_from="2026-01-15T09:30:00+08:00")   # fact time, optional
m.set_status("task.x", "done", note="pytest green (exit 0)")
m.add_edge("task.x", "artifact.y", kind="produced_by")
hits = m.search("concurrency", layer="L3", k=10)
report = m.check(); audit = m.audit()
adoption = Memory.adopt("./legacy-graph", "./mem", pin_out="./pin.json")
expiry = m.expire(apply=False)   # dry-run; apply=True to supersede expired facts
```

`Memory` is the only entry point; every write takes the lock, writes the whole
graph, and replaces the file atomically.

## Node shape

```
id, type, label, status, owner, source, note,
evidence[], conclusion, evidence_grade,
valid_from, valid_until, recorded_at, superseded_at, updatedAt
```

`valid_from` / `valid_until` are **caller-supplied fact time** (ISO-8601, stored
verbatim) or `null`. They are never defaulted to the write time: `changes[].at`
is transaction time, and using it as fact time is measurably wrong (see
`experiments/valid_from_bias/`). `valid_time_known` is `true` iff `valid_from`
was supplied; expiry refuses nodes whose validity window is unknown.

Adoption-only fields (present only on nodes created by `amg adopt`):
`legacy_evidence` (verbatim legacy locator strings), `legacy_source` (the
placeholder it replaced), `superseded_at_inferred` (`true` when the timestamp was
taken from `updatedAt`).

`type` ∈ group · member · task · decision · artifact · issue · model · env · question · rule
`status` ∈ proposed · open · in_progress · done · blocked · superseded
`edge.kind` ∈ depends_on · blocks · produced_by · owned_by · decided_by · supersedes · relates_to · part_of

## Evidence shape

```
{"locator": "path:…|cmd:…|url:…|sha256:…",
 "content_sha256": "<64 hex>", "captured_at": "<iso8601>",
 "graph_rev": <int>, "grade": 1..5}
```

## Expiry and `valid_time_known`

`audit` only reports **conflicts** for expired facts whose validity time is
known. For `valid_time_known: false` (every migrated node, and any node without a
supplied `valid_from`) an expired `valid_until` becomes a **hint**, and TTL
auto-expiry must refuse the node entirely (`amg.audit.expiry_eligible`): expiring
it would delete a fact on the strength of a timestamp we never had. `audit` also
prints a summary hint with the count of such nodes, and reports a future
`valid_from` as "not yet valid" (a hint, not a conflict).

`amg expire <dir> [--apply]` is the opt-in implementation:

- **dry-run by default** — nothing is written without `--apply`;
- only nodes whose validity window is **known**, whose `valid_until` has passed
  and that are not already superseded;
- the action is `status: superseded` + `superseded_at` + one `expire` change
  record; **no node is ever deleted** (IR-1);
- idempotent: a second `--apply` reports `applied 0` and writes nothing;
- unknown validity is skipped and counted, so an adopted graph has **zero**
  eligible nodes by construction;
- exit `0`; the report lists eligible ids and the
  `applied` / `skipped_unknown_validity` / `already_superseded` counts.

Supplying `valid_until` without `valid_from` is accepted but stays
`valid_time_known: false`, so it cannot trigger an expiry conflict — pass both
bounds if you want the window to count. TTL auto-expiry is **not implemented**;
the refusal rule is enforced so a future implementation cannot inherit the bug.

## Retrieval rules (v0.1)

- L1/L3/L4 **hard-filter `superseded` nodes** (`failures.md:118`, non-negotiable):
  an expired fact is never an answer. L2 is the exception by design — it reads
  `changes[]`, so superseded history stays visible there.
- Nodes whose `valid_from` is in the future are **not yet in effect**: they are
  filtered from L1/L3/L4 and from `digest` (audit reports "not yet valid").
- `digest` excludes superseded nodes and prints `superseded excluded: N` in the
  header (plus `not yet valid excluded: N`).
- Anchor handling is separate: unanchored hits are returned degraded
  (`anchor_state: "none"`); `--strict` filters those out. `--strict` does not
  re-enable superseded nodes.

## Adoption (legacy `group-kg/v1` → `amg/v1`)

```
amg adopt <src-dir> <dst-dir> [--group NAME] [--drop-dangling] [--pin-out PATH] [--dry-run] [--json]
```

Guarantees, all covered by `tests/test_adopt.py`:

- **never writes to `src`** (byte-identical before/after, `src_sha256` reported);
- **never overwrites `dst`** — an existing `graph.json` is refused;
- **never fabricates evidence**: legacy bare strings are preserved in
  `legacy_evidence`, `evidence` stays `[]`. The legacy ratio is reported by
  `audit`, so the debt stays visible instead of being papered over;
- placeholder sources (`""`/`unknown`/`manual`) become
  `adopted:<src-schema>:<src-sha12>`, with the old value kept in `legacy_source`;
- `superseded_at`/`valid_until` are inferred from `updatedAt` only and flagged;
- `valid_from` stays `null` when unknown (never back-filled from `changes[].at`)
  and the node is stamped `valid_time_known: false`;
- duplicate ids, unknown enums and dangling edges are **refusals**; dangling
  edges may be dropped only with `--drop-dangling`, and the count is reported;
- edges that repeat an identical `(from, to, kind)` triple are merged (no
  information is lost) and the count is reported;
- `--pin-out` writes the frozen exemption baseline for `amg audit --pin`.

Exit codes: `0` adopted and the resulting graph passes `check`; `1` the source
data is unsupported or the result would not pass `check`; `2` wrong input
(missing graph, destination exists, source is already `amg/v1`).

## Deliberately absent

No `delete`, no in-place note edit, no vector index, no auth, no network. See
[DECISIONS.md](DECISIONS.md) for why.
