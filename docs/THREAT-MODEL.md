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
- **No tamper evidence.** `changes[]` is append-only *by the API*, not
  cryptographically. A process with file access can rewrite it and no check can
  tell. If you need tamper evidence, keep the graph in git (each commit is an
  external witness) or hash it into a system you control and compare out of band.
- **Read tools are unlimited.** `memory_digest` accepts `max_bytes`; the others
  have no output bound beyond `k`. A client can read everything available.
- **`reads.jsonl` is a plain-text log** of query text for high-risk reads. Do not
  treat it as a secret store (see SECURITY.md).
- **Timing/resource limits.** A very large graph makes `audit`/`digest` slow; the
  tool has no per-request timeout.

## 8. Out of scope for v0.3.0 (tracked as issue #4b)

- Client identity, tokens, per-caller authorization, multi-tenant separation.
- Any network transport (that decision belongs to whoever builds one; this
  project will not ship one, see §2).
- Tamper-evident history (signatures / HMAC with key management).
- Encrypted-at-rest storage.

These are listed so that "the docs did not mention it" cannot be read as "it is
handled".

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
