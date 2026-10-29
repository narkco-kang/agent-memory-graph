# amg v0.1 API contract

The contract is also a CI fixture: `tools/check_doc_symbols.py` fails the build if a
capability named here has no code symbol.

## CLI

```
amg init   <dir> --group NAME [--goal TEXT]          # refuses to overwrite
amg add    <dir> --id --type --label --source [--status --owner --note --evidence ...]
amg status <dir> <id> <new-status> --note TEXT       # note required (IR-4)
amg link   <dir> --from ID --to ID --kind KIND
amg search <dir> "query" [--layer L1|L2|L3|L4] [--k 10] [--strict] [--json]
amg digest <dir> [--max-bytes 65536] [--out PATH]
amg check  <dir> [--strict] [--json]
amg audit  <dir> [--pin baseline.json] [--json]
amg export <dir> [--format json|jsonl]
amg doctor <dir>                                     # cleans stale tmp files
amg migrate <dir>                                    # normalizes legacy changes[]
amg adopt  <src> <dst> [--group NAME] [--drop-dangling] [--pin-out PATH] [--dry-run]
amg version
```

`--evidence` takes `locator|content_sha256|captured_at[|grade]` (repeatable).

Exit codes: `0` success/clean, `1` protocol violation or conflicts, `2` usage,
`3` lock timeout or IO failure.

## Exit-code classification (signed 2026-10-29)

`2` means *the caller used the API wrong*; `1` means *the content violates the
protocol*. There is **no default**: a code missing from the table makes the CLI
fail loudly instead of guessing, and `tests/test_exit_codes.py` scans
`src/amg/*.py` to prove every raised code is classified.

| exit | codes | meaning |
|---|---|---|
| `2` | `E_NO_GRAPH` · `E_BAD_TYPE` · `E_BAD_STATUS` · `E_BAD_LAYER` · `E_BAD_EDGE` · `E_BAD_FORMAT` · `E_BAD_ID` · `E_EXISTS` · `E_RULE_APPLIES` · `E_RULE_EXPIRES` · `E_USE_SUPERSEDE` · `E_BAD_SUPERSEDE` · `E_ALREADY_AMG`* | wrong argument, unknown enum, or wrong target — the call was wrong, not the data |
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

## Python

```python
from amg import Memory, ProtocolError, LockTimeout

m = Memory.open("./mem")          # Memory.init("./mem", group="t")
m.add_node(id="task.x", type="task", label="do X", source="group:t 2026-10-29")
m.set_status("task.x", "done", note="pytest green (exit 0)")
m.add_edge("task.x", "artifact.y", kind="produced_by")
hits = m.search("concurrency", layer="L3", k=10)
report = m.check(); audit = m.audit()
adoption = Memory.adopt("./legacy-graph", "./mem", pin_out="./pin.json")
```

`Memory` is the only entry point; every write takes the lock, writes the whole
graph, and replaces the file atomically.

## Node shape

```
id, type, label, status, owner, source, note,
evidence[], conclusion, evidence_grade,
valid_from, valid_until, recorded_at, superseded_at, updatedAt
```

Adoption-only fields (present only on nodes created by `amg adopt`):
`legacy_evidence` (verbatim legacy locator strings), `legacy_source` (the
placeholder it replaced), `superseded_at_inferred` (`true` when the timestamp was
taken from `updatedAt`), and `valid_time_known` (`false` when the validity window
is unknown — every migrated node without a legacy `valid_from`). Absent means
known, so only `amg adopt` sets `false`.

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
known. For `valid_time_known: false` (every migrated node) an expired
`valid_until` becomes a **hint**, and TTL auto-expiry must refuse the node
entirely (`amg.audit.expiry_eligible`): expiring it would delete a fact on the
strength of a timestamp we never had. `audit` also prints a summary hint with the
count of such nodes. TTL auto-expiry is **not implemented in v0.1**; the refusal
rule is enforced so the future implementation cannot inherit the bug.

## Retrieval rules (v0.1)

- L1/L3/L4 **hard-filter `superseded` nodes** (`failures.md:118`, non-negotiable):
  an expired fact is never an answer. L2 is the exception by design — it reads
  `changes[]`, so superseded history stays visible there.
- `digest` excludes superseded nodes and prints `superseded excluded: N` in the
  header.
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
