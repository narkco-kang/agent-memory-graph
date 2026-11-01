# Decision #57

[← decision log](../DECISIONS.md) · status: active
**Two writers open one physical file; a symlink bridge splits the graph.**

## The problem

Two tools write the same team memory and each had decided its own layout:

- `kg.py` writes `knowledge-graph/graphs/<group>.json` and chooses that filename
  itself (from the graph's `group` field, not from the argument);
- `amg` opens `<dir>/graph.json`.

Neither can dictate the other's layout, so the two obvious bridges were tried and
both fail:

**Bridge with a symlink — measured to SPLIT THE GRAPH.**

```
graphs/graph.json -> graphs/测试群.json        (symlink)
$ amg add <graphs> --id a4 ...
added a4 [task/open]                          ← reports success

after:  测试群.json     4 nodes  rev 4        ← unchanged, zero bytes written
        graph.json      5 nodes  rev 5        ← now an ordinary file, holds a4
```

Cause: `Store._atomic_write` ends in `os.replace(tmp, self.file)`, and `os.replace`
replaces **the link**, not the link target. Every write path (`add`, `status`) did
this; only reads (`search`) left the link intact — which is why a read-only check
looked perfectly healthy while writing silently forked the data.

**Make one tool move** — rejects the premise: relocating `kg.py`'s graphs breaks
`kg.py`, and relocating `amg`'s expectations breaks every existing invocation.

## Decision

Both tools open **the same physical file**. `amg` gained `--graph <file>`:

```
$ amg add knowledge-graph/graphs --graph knowledge-graph/graphs/测试群.json \
      --id ACCEPT1 --type task --label 验收节点 --source probe --status open
$ python3 knowledge-graph/kg.py check 测试群
[kg] 节点 3 / 边 0 / 变更 3   ✓ 结构校验通过
```

- `--graph` names the exact file; the lock (`.lock`) is created **next to that
  file**, so both writers contend on the same lock rather than two separate ones.
- The flag is added to every dir-taking sub-command in one loop, so a new
  sub-command cannot silently miss it (a test asserts this).
- `--graph` and `--root` are separate concerns: `--graph` says *which file*,
  `--root` says *which evidence base* (decision #56).
- Without `--graph`, the old `<dir>/graph.json` layout is unchanged.

## Consequences

- `kg.py` keeps its naming and its directory; nothing has to move.
- The write path is now shared, so **the lock must be shared too**. `amg` uses
  `flock` on `<graph dir>/.lock`; `kg.py` uses its own stale-by-mtime lock. These are
  **not the same lock**, so concurrent writers from the two tools can still lose an
  update. That is recorded as an open risk, not fixed here — the two locking schemes
  need their own decision.
- Sequential alternation is safe and was measured: `kg → amg → kg` produced
  `changes[].rev = [1, 2, 3]`, contiguous, no duplicates, no losses.

## Rejected alternatives

- **Symlink bridge**: splits the graph on the first write, silently.
- **Copy-on-write or periodic sync**: two files again, and the divergence becomes a
  merge problem nobody asked for.
- **Make `kg.py` write `<dir>/graph.json`**: `kg.py` derives the filename from the
  graph's own `group` field; overriding that is how a test node was once written into
  a real group graph.

**Discussed:** 记忆架构开源 @ 2026-11-01 by Hermes仔,Glm仔 — Hermes仔 measured the symlink split (`os.replace` swaps the link) against `src/amg/store.py` and `knowledge-graph/graphs/`; Glm仔 attacked the two-lock risk that the shared file still leaves open.

*Signed 2026-11-01; group notice rule #8; v0.37.0.*
