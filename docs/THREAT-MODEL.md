# Threat model

Scope: `agent-memory-graph` v0.3.0 — the CLI, the Python library, and `amg mcp`
(the stdio MCP server). Written before implementing read-only mode, so the
guarantee below is stated with its limits instead of implied.

This document describes **what the software can and cannot protect**. If a
threat is not listed as mitigated, assume it is not mitigated.

## 1. What is being protected

| Asset | Where it lives | What it leaks |
|---|---|---|
| Node content (labels, notes) | `graph.json` → `nodes[]` | Project state, decisions, issue text |
| Evidence pointers (`locator`, `content_sha256`) | `graph.json` → `nodes[].evidence[]` | File paths, URLs, command lines, content hashes |
| Transaction history | `graph.json` → `changes[]` | Who wrote what, when, and with which note |
| Read log (opt-in) | `reads.jsonl` | Query text and the fact that a high-risk read happened |
| Audit pin | wherever the caller put it | Hashes of id lists; not secret, but integrity-relevant |

`graph.json` is **plain, human-readable JSON**. There is no encryption at rest
and no key material anywhere in this project.

## 2. Trust boundaries

```
OS user  ──(the only real boundary)──  │  nothing inside this box authenticates anyone
                                       │
   CLI ──┐                             │
   lib ──┼──> Memory ──> Store ──> graph.json
   mcp ──┘                             │
```

There is exactly **one** enforcement boundary that matters: the operating
system's file permissions for the user running the process. Everything above it
is convenience. Concretely: any process running as the same user has the same
authority over the memory as the memory's owner. The CLI, the library and the
MCP server are three doors into the same room, and none of them has a lock.

`amg mcp` opens **no socket and no port** and makes no outbound request. It
speaks newline-delimited JSON-RPC on stdin/stdout. If you put a network
transport in front of it, you have removed the only boundary the system has,
and this document no longer applies.

## 3. Actors

- **A1 — the user.** Fully trusted. Nothing here defends against them.
- **A2 — a local client of the same OS user.** A coding agent, a script, an
  editor plugin. Untrusted *in intent* but fully trusted *in capability*: it can
  also just open the file.
- **A3 — a prompt-injected A2.** An agent that was told by page content, an
  issue body or a tool result to write to memory. This is the actor read-only
  mode exists for.
- **A4 — another OS user / a network peer.** Outside the boundary. Only file
  permissions and the absence of a listener stand in the way.
- **A5 — the supply chain.** Zero runtime dependencies, so the surface is the
  Python standard library. `amg mcp` does not import third-party code.

## 4. Threats

| # | Threat | Status | Where |
|---|---|---|---|
| T1 | A2/A3 writes a node through `amg mcp` to plant a false "done" conclusion | **Mitigated by `--read-only`** (two layers) | §5 |
| T2 | A2/A3 bypasses the evidence gate or IR-2/IR-4 by going through MCP instead of the CLI | **Mitigated by construction**: no tool has its own write path; all call `Memory`, and `Memory` raises | §6 |
| T3 | A2/A3 overrides history: rewrites `changes[]`, or edits a `done` node back to `open` without a note | **Partially mitigated**: the API refuses, a file writer does not | §7 |
| T4 | A2/A3 exfiltrates the whole memory with `memory_search`/`memory_digest`/`memory_audit` | **Not mitigated.** Reads are readable | §7 |
| T5 | A2/A3 reads `reads.jsonl` to learn what the user looked at | **Not mitigated** (same directory, same permissions) | §7 |
| T6 | Denial of service: hold the write lock forever | **Partially mitigated**: `LockTimeout` after the configured wait (exit 3), and the lock is released when the handle closes, so a crashed process cannot wedge the graph | `store.py` |
| T7 | Crash during write leaves a half-written graph | **Mitigated**: full write to a temp file + `fsync` + `os.replace`, so a reader sees old or new, never a mix | `store.py::_atomic_write` |
| T8 | Dangling/duplicate writes corrupt structure | **Mitigated**: `check` (IR-1..IR-4) and the write gates reject them before commit | `protocol.py`, `gate.py` |

### Evidence authenticity is declared, not proven (v0.20.0)

`content_sha256` is supplied by the caller; the write gate checks its shape (64 lowercase
hex) and nothing else. A fabricated hash is accepted, yields `anchor_state: "present"`,
and that is the first retrieval sort key — reproduced in the public package
(`issue.mem-arch-evidence-sha-forgeable`, severity high). Two-part response, both
shipped: **disclosure** here and in `docs/API.md` (`present` = *declared*), and an
**observation mechanism**, `amg verify-evidence`, which re-hashes `path:` locators and
exits 1 on mismatch. Deliberately not fixed: no per-read verification (I/O on the hot
path, and referenced files legitimately move); no `anchor_state` split into
`verified`/`claimed` (without a persisted verification result that would be a label, not
a measurement); `cmd:`/`url:`/`sha256:` evidence cannot be checked offline and is
reported `unverifiable`, never a pass. Treat `--strict` as "anchored as declared".

## 5. Read-only mode: what it guarantees

`amg mcp <dir> --read-only` (and `Memory.open(dir, read_only=True)`) provides:

1. **Tool refusal before dispatch.** `memory_add`, `memory_status` and
   `memory_supersede` raise `E_READ_ONLY` and are reported to the client as
   `isError: true`. The call never reaches the `Memory` method.
2. **Commit refusal as a backstop.** A read-only `Memory` raises `E_READ_ONLY`
   in `_commit()`, the single function every mutation funnels through. This is
   the layer that matters: a future mutating method cannot forget the check, and
   a tool added later without being classified is still blocked here.
3. **No write tools advertised.** `tools/list` returns the five read tools only,
   and `initialize` carries a `read-only` instruction string so an agent client
   is told the constraint instead of discovering it by failing.
4. **No bytes written.** Tested by hashing `graph.json` before and after a
   session that attempts every write tool, and after calling `add_node`,
   `set_status`, `supersede` and `expire(apply=True)` directly.

What read-only mode is **not**:

- It is not authentication. It does not identify the client, and it cannot stop
  a client from launching a second `amg mcp` **without** the flag. It reduces
  the blast radius of one session; it does not deprive the OS user of authority.
- It is not a sandbox. `A2` can still `open("graph.json","w")`.
- It does not block disclosure: all read tools keep working, by design.
- It does not cover the legacy `amg adopt`/`amg migrate` entry points, which are
  writes by nature and take no read-only flag.

Honest summary: **`--read-only` protects the graph from the process it was
started in, and from the agent driving that process. Nothing more.**

## 6. Why MCP cannot bypass the write discipline

The MCP layer adds no validation and no write path of its own. Every tool calls
the same `Memory` method the CLI calls, so:

- evidence format and the conclusion gate (`E_EVIDENCE_MISSING`,
  `E_EVIDENCE_FORMAT`) fire identically over MCP;
- `IR-2` (real source) and `IR-4` (conclusion-`done` needs evidence) are enforced
  in `Memory._make_node`, below the transport;
- a rejected write returns `isError: true` with the protocol code in the text,
  never a success frame.

`tests/test_mcp.py` asserts the error comes back as a tool error; `tests/test_readonly.py`
asserts the same for read-only refusals.

## 7. Accepted risks (not bugs to report)

- **Same-user file access.** Anyone who can run a process as the user can read
  and rewrite the graph. The only defence is OS permissions, disk encryption, or
  keeping the file out of shared locations.
- **No tamper evidence inside the file.** `changes[]` is append-only *by the
  API*, not cryptographically. A process with file access can rewrite it.
  `amg fingerprint` / `amg verify` (§7a) detect accidental corruption and edits
  that leave state and history inconsistent, but the digest can be recomputed by
  the same attacker. Real evidence requires an external witness: commit the
  fingerprint into git, a CI log, or another host, and compare out of band.

### 7a. What `amg verify` does and does not buy

`amg fingerprint` emits `state_sha256` (nodes+edges, order-independent) and
`history_sha256` (`changes[]`, in order). `amg verify --expect FILE` exits 1 when
either differs from the recorded value.

| Situation | Detected? |
|---|---|
| Bit rot, partial write, truncated file | yes (state digest) |
| A node edited in the file with no change record | yes — state moves, history does not |
| A change appended without touching nodes | yes — history moves, state does not |
| An attacker who rewrites state **and** history and recomputes the digest | **no** — only an external witness catches this |
| An attacker who also rewrites your copy of the fingerprint | **no** |

This is why the project does not ship an in-file hash chain over `changes[]`: it
looks stronger than it is (the attacker regenerates the chain in one pass) while
costing a schema migration, and it invites people to trust it.

### 7b. Checking that the boundary still holds

Because permissions *are* the boundary, `amg doctor` checks the conditions under
which the boundary stops existing: `SEC_WORLD_WRITABLE`,
`SEC_GROUP_WRITABLE` (info), `SEC_NETWORK_PATH` (SMB/NFS/UNC — the advisory lock
is not reliable there), `SEC_GRAPH_SYMLINK`. `amg doctor --strict` exits 1 on a
warning (`E_INSECURE_GRAPH`); `amg mcp` prints the warnings to stderr at startup
and keeps serving.

It is a check, not a sandbox: it cannot make a shared filesystem safe, only
refuse to be quiet about it.
- **Read tools are unlimited.** `memory_digest` accepts `max_bytes`; the others
  have no output bound beyond `k`. A client can read everything available.
- **`reads.jsonl` is a plain-text log** of query text for high-risk reads. Do not
  treat it as a secret store (see SECURITY.md).
- **Timing/resource limits.** A very large graph makes `audit`/`digest` slow; the
  tool has no per-request timeout.

## 8. Authorization: decided out of scope, and what to do instead

Earlier versions of this file listed "authentication and multi-tenancy" as
pending work. That was a deferred decision, not a plan. It is now decided:
**this project will not implement authentication or per-caller authorization.**

The reasoning is not "it is hard". It is that, in this architecture, app-level
authentication is bypassable in one step:

1. The memory is one file the caller can open. A process that can run `amg` can
   also `open("graph.json", "w")`. A token check inside `amg` therefore proves
   only that the caller *has the file* — which they already needed.
2. Single-user file stores typically end up with the token in a config file
   readable by that same user, so the check becomes decoration that costs code,
   tests and maintenance while changing no capability.
3. Anything that *would* hold — separate users, containers, read-only mounts,
   filesystem ACLs — is enforced below us by the OS. Re-implementing it above the
   file would be a weaker copy.

So the boundary is explicit and the work moves to where it actually holds:

| Need | What to do |
|---|---|
| Two people, one graph, different rights | two OS users + a group; make the file group-readable and directory group-writable only if you accept shared write |
| An agent that must never write | `amg mcp --read-only` (blast radius for this session) **and** start that process as a user with no write permission on the file |
| Several projects, no leakage between them | one graph directory per project; separate mounts if the projects have different trust levels |
| Read-only dashboards / audits | serve a copy, or mount the directory read-only for that user |
| Untrusted plugins or code | container or VM; not a flag |

What *is* implemented in this area: `--read-only` (one session), `amg doctor
--strict` (refuses to stay quiet when the permission boundary does not hold: see
§7b), and `amg fingerprint` / `verify` (tamper *detection*, §7a).

### What would change this decision

Three things, each of which invalidates the reasoning above rather than merely
making auth more attractive:

- a network transport (then identity is unavoidable — and should be built by
  whoever ships the transport, not bolted on here);
- multi-writer concurrency beyond the advisory lock (then "who wrote this" stops
  being answerable from the process);
- a hosted or multi-tenant deployment (then tenant separation must be structural,
  i.e. separate stores, not a column in a shared file).

## 9. How to verify the claims above

```bash
# 1. read-only refuses write tools, and the file does not move
BEFORE=$(sha256sum "$D/graph.json")
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory_add","arguments":{"id":"x","type":"task","label":"x","source":"t","note":"n"}}}' \
  | PYTHONPATH=src python3 -m amg.cli mcp "$D" --read-only
AFTER=$(sha256sum "$D/graph.json"); [ "$BEFORE" = "$AFTER" ] && echo "no bytes written"

# 2. the backstop holds even below the tool layer
PYTHONPATH=src python3 -c "
import sys; sys.path.insert(0,'src')
from amg import Memory, ProtocolError
m = Memory.open('$D', read_only=True)
try: m.add_node(id='y', type='task', label='y', source='t', note='n')
except ProtocolError as e: print(e.code)   # E_READ_ONLY
"

# 3. no listener exists while the server runs
lsof -nP -iTCP -sTCP:LISTEN | grep -c python3 || echo "no listening python socket"
```

The unit tests run the first two as assertions in CI:
`tests/test_readonly.py` (12 tests, including the digest-unchanged check).
