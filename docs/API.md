# amg API contract (on-disk format `amg/v1`)

The contract version tracks the file format, not the package version: the
`amg/v1` schema has only been added to since it was written, and that is why
entries below are marked "new in vX.Y" rather than renumbered.

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
amg audit  <dir> [--pin baseline.json] [--stale-days N] [--json]
amg export <dir> [--format json|jsonl]
amg mcp   <dir> [--read-only]                        # MCP server over stdio (no network)
amg doctor <dir>                                     # cleans stale tmp files
amg migrate <dir>                                    # normalizes legacy changes[]
amg adopt  <src> <dst> [--group NAME] [--drop-dangling] [--pin-out PATH] [--dry-run]
amg expire <dir> [--apply] [--json]                # opt-in TTL expiry (dry-run default)
amg fingerprint <dir> [--json] [--out PATH]        # canonical state + history digests
amg verify <dir> --expect PATH | --expect-state HEX [--expect-history HEX]
amg handoff <dir> [--by NAME] [--owner NAME] [--note TEXT|-] [--json]
                                     # one bounded handover card; newest supersedes previous
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

`AMG_LOCK_TIMEOUT` (seconds, `0 < x <= 3600`, invalid values fall back to 5)
overrides the write-lock wait. Raise it for burst workloads: on a large graph each
write costs the full rewrite, so 5 s covers roughly 34 queued writes.

`AMG_STALE_DAYS` (days, `0 < x <= 365`, invalid values fall back to 3) is the age at
which `audit` calls an `in_progress`/`blocked` work item stale. `amg audit
--stale-days N` overrides it for one run. The threshold is a property of the team's
cadence, not of the tool (DECISIONS #21); node types that register something
long-lived (`group`, `env`, `member`) are never reported as stale.

Exit codes: `0` success/clean, `1` protocol violation or conflicts, `2` usage,
`3` lock timeout or IO failure.

## Exit-code classification (signed 2026-10-29)

`2` means *the caller used the API wrong*; `1` means *the content violates the
protocol*. There is **no default**: a code missing from the table makes the CLI
fail loudly instead of guessing, and `tests/test_exit_codes.py` scans
`src/amg/*.py` to prove every raised code is classified.

| exit | codes | meaning |
|---|---|---|
| `2` | `E_NO_GRAPH` · `E_BAD_TYPE` · `E_BAD_STATUS` · `E_BAD_LAYER` · `E_BAD_EDGE` · `E_BAD_FORMAT` · `E_BAD_ID` · `E_EXISTS` · `E_RULE_APPLIES` · `E_RULE_EXPIRES` · `E_USE_SUPERSEDE` · `E_BAD_SUPERSEDE` · `E_BAD_VALID_TIME` · `E_BAD_VALID_RANGE` · `E_ALREADY_AMG` · `E_BAD_BATCH` · `E_BAD_FILE` · `E_BAD_DEPTH`* · `E_READ_ONLY` · `E_NO_EXPECTATION` · `E_BAD_FINGERPRINT` · `E_BAD_HANDOFF` · `E_HANDOFF_TOO_LARGE` | wrong argument, unknown enum, or wrong target — the call was wrong, not the data |
| `1` | `E_NO_SOURCE` · `E_NOTE_REQUIRED` · `E_EVIDENCE_MISSING` · `E_EVIDENCE_FORMAT` · `E_DUP_ID` · `E_DUP_EDGE` · `E_NO_NODE` · `E_IMMUTABLE` · `E_ADOPT_UNSUPPORTED`* · `E_ADOPT_DANGLING`* · `E_FINGERPRINT_MISMATCH` · `E_INSECURE_GRAPH` | the evidence gate rejected the content, or the graph would break an invariant |
| `0` | — | success / clean `check` / clean `audit` |
| `3` | — | lock timeout or IO failure (not a `ProtocolError`) |

`E_READ_ONLY` is `2` and not `1`: asking a read-only session to write is the
caller addressing a capability that session does not have (the same class as
`E_ALREADY_AMG`), not graph content violating the protocol.

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
- **`--read-only`** refuses the write tools (`E_READ_ONLY`, returned as
  `isError: true`) and advertises only the five read tools. The guarantee is
  enforced twice: the server refuses before dispatch, and the underlying
  `Memory` refuses every commit — so a tool added later cannot silently reopen
  the write path. Tested by hashing `graph.json` before and after a session that
  attempts every write tool (`tests/test_readonly.py`). It does **not**
  authenticate the client and does not stop another process from writing the
  file: see [THREAT-MODEL.md](THREAT-MODEL.md) §5.
- stdout carries protocol frames only; diagnostics go to stderr.

## Filesystem hygiene (`doctor --strict`, v0.4)

This project has no authentication; its only boundary is file permissions. So
`amg doctor` reports conditions where that boundary does not hold, using finding
codes that are **not** protocol errors (`SEC_` prefix):

| finding | severity | meaning |
|---|---|---|
| `SEC_WORLD_WRITABLE` | warn | `graph.json` or its directory is world-writable: any local user can rewrite the memory |
| `SEC_GROUP_WRITABLE` | info | the same for everyone in the file's group |
| `SEC_NETWORK_PATH` | warn | the path looks like an SMB/NFS/UNC mount, where the advisory lock and the permission boundary do not hold |
| `SEC_GRAPH_SYMLINK` | warn | `graph.json` is a symlink, so the bytes live somewhere else |

`amg doctor <dir> --strict` exits 1 (`E_INSECURE_GRAPH`) on any `warn`; plain
`amg doctor` still succeeds and only prints. `amg mcp` prints the same warnings to
stderr at startup and keeps serving — a warning is not a lock, and pretending
otherwise would be worse than saying it.

Scheduling advice: run `amg doctor --strict` from cron where a misconfigured
permission should page someone, not silently pass.

## Fingerprints and what they do not prove (v0.4)

`amg fingerprint <dir>` prints two SHA-256 digests:

- `state_sha256` — nodes and edges, canonicalised so that re-ordering the file
  does not change it;
- `history_sha256` — the `changes[]` records, in order.

They are separate because they detect different lies. Editing a node directly in
the file moves `state_sha256` while `history_sha256` stays put — the mismatch is
what `amg verify` reports, and it is a fact about the bytes, not an accusation
about a person.

```bash
amg fingerprint ./mem --out ./mem.fp.json     # store this OUTSIDE the graph dir
amg verify ./mem --expect ./mem.fp.json       # exit 0 match, 1 mismatch, 2 usage
```

**What it proves:** the file you are looking at is byte-for-byte the content the
digest was computed from (canonicalised), and whether state and history moved
together.

**What it does not prove:** that no one rewrote anything. A process that can write
`graph.json` can also recompute the fingerprints. The digest only has value where
it is *witnessed* somewhere else — a git commit, a CI log, a ticket, another host:

```bash
amg fingerprint ./mem --json > ./witness.json
git add ./mem/graph.json ./witness.json && git commit -m "memory: <fingerprint>"
```

Because of that, there is deliberately **no** in-file hash chain over `changes[]`
(see DECISIONS.md #11): it would look stronger than the external digest while
providing less, since an attacker regenerates the whole chain in one pass.

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
ro = Memory.open("./mem", read_only=True)   # every write raises E_READ_ONLY
fp = m.fingerprint()                       # {"state_sha256": ..., "history_sha256": ...}
report = m.verify_fingerprint(fp)          # {"ok": True, "checked": [...], "mismatched": []}
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

### Handoff cards (`handoff` nodes, v0.10.0)

A `handoff` node answers four questions for whoever reads next — *who am I, where did
we get to, what is next, what is blocked* — in one card of **at most 4,096 bytes**.
Exactly one card is active: writing a new one supersedes the previous, so the history
stays in the ledger and the reader still gets a single answer.

```bash
amg handoff ./mem --by kimi --owner mini --note -     # read the card from stdin
amg handoff ./mem                                    # print the active card
amg handoff ./mem --json                             # id, by, owner, at, bytes, max_bytes
```

`Memory.write_handoff(note, by=..., owner=...)` is the same operation from Python;
`Memory.handoff()` returns the active card or `None`. An empty card and a card over
the limit are refused (`E_BAD_HANDOFF`, `E_HANDOFF_TOO_LARGE`, exit 2) and write
nothing. `audit` reports `handoff_over_budget` and `multiple_active_handoffs` as
conflicts, because a hand-edited graph can hold states the CLI would refuse.
Background and the rules this follows: [`HANDOFF.md`](HANDOFF.md).

### `audit()` findings (v0.9.0)

`audit()` returns the human lists `conflicts` and `hints` (unchanged) plus a
structured `findings` array derived from the same entries, in the same order:

```json
{"severity": "conflict", "kind": "stale_work_item",
 "detail": "<id>: in_progress untouched for 10d (limit 3d)",
 "node": "<id>", "type": "task", "status": "in_progress",
 "owner": "kimi", "age_days": 10, "limit_days": 3}
```

`severity` is `conflict` (audit fails) or `hint` (informational). Kinds:
`done_without_evidence`, `stale_work_item`, `expired_but_active`, `dangling_edge`
(with an `edge` object), `pin_changed`, and the hints `not_yet_valid`,
`expired_though_validity_unknown`, `conclusion_without_grade`, `unknown_validity`,
`changes_key_shapes`. `node` is the id the caller has to act on and `owner` is
carried through (null when absent), because "who is responsible" is the first
question a reader asks and previously had to be looked up.

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
