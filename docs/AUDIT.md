# Auditing and reading: the evidence base

This is the owning document for `amg audit --verify`, `amg search --root` and the
`evidence_state` each hit carries. `docs/API.md` keeps the command list and a pointer
here, because the API page is at its size budget and details belong in one place.

## The evidence base is stated, never guessed

`path:` evidence is resolved against a **base directory**, and the base is not always
the graph directory. Measured on one graph, one build, one command, changing only the
base:

| evidence base | `evidence_unverifiable` |
|---|---|
| the graph directory | **232** |
| the directory the locators were written against | **24** |

A wrong base does not fail — it returns a larger number that reads like a finding. So
both `audit --verify` and `search` require `--root`:

```
$ amg search <dir> "query"
E_EVIDENCE_ROOT_REQUIRED: pass --root <dir>, the base that evidence locators are
resolved against. It is not inferred from `dir` ...
$ echo $?
2
```

No report is printed when the base is unknown. `audit --verify` additionally refuses a
base that carries none of the structure anchors (`README.md`, `docs`,
`agent-memory-graph`, `src`, `tests`) with `E_EVIDENCE_ROOT_SUSPECT`; `--force-root`
overrides it and the report then records `anchors.suspect: true`.

Every `--verify` report echoes the base and its physical identity:

```json
"evidence_root": {
  "path": "/…/workspace",
  "source": "--root",
  "identity": {"dev": 16777229, "ino": 24188727},
  "anchors": {"found": ["docs", "tests"], "suspect": false}
}
```

`(st_dev, st_ino)` is reported because a path string cannot identify a directory: on a
case-insensitive filesystem one directory has several spellings, and a hard link gives
one file two names with two different `realpath` results. It is a **report field, not a
rejection rule** — anyone who can choose the base can choose one that passes, so
treating it as enforcement would promise more than it can keep (decision #56).

## Three buckets, not one number

`amg audit <dir> --root <base> --verify` splits every `done` node into exactly one of:

| bucket | meaning |
|---|---|
| `evidence_absent` | the evidence list is empty |
| `evidence_unverifiable` | locators exist, none can be observed (dead pointer, escaping path, digest mismatch, or prose/`cmd:`/`url:` only) |
| `evidence_resolvable` | a locator resolved **and** its declared digest matched — the only passing state |
| `evidence_declared_uncheckable` | legacy bare-string declarations: the file may exist, but no digest was declared, so existence is all that can be shown |
| `known_limitation` | reserved for the registry (P1); always 0 in this build |

Without `--verify` the old single `done_no_evidence` count is returned unchanged, so
callers that never asked for the split see no difference.

## `evidence_state` on search hits

`amg search <dir> --root <base> "query"` tags every hit:

| state | meaning |
|---|---|
| `verified` | an object locator resolved and its digest matched |
| `declared` | something was recorded; nothing checkable was checked |
| `missing` | every path-shaped locator resolves nowhere |
| `absent` | nothing was recorded |

`anchor_state` is **not** this. It answers only "is the list non-empty", and rendering
it beside a bare-string declaration shows a claim as if it were a result. The plain-text
output prints `evidence=<state>` and never `anchor=present`.

Measured on the team graph (545 nodes): `declared` 309, `absent` 187, `missing` 25,
`verified` **0** — every stored conclusion is a declaration, not a verified fact.

## Write-time verification

The same proof is required when concluding, not only when reading:

```
$ amg add <dir> --id x --type artifact --label x --source s --status done \
      --evidence "path:proof.md|aaaa…(64 hex)|2026-11-01T00:00:00Z"
E_EVIDENCE_VERIFY_FAILED: x: declared evidence does not match what can be observed;
  evidence[0] path:proof.md: declared aaaa… but the file hashes to f6ed42a9…
```

Rules: the declared digest must equal the digest of the bytes; a `path:` locator must
stay inside the evidence root (an escaping locator is refused, not skipped — skipping
would make the check its own bypass); a missing file is a failed claim. `open` and
`in_progress` nodes are not gated: evidence constrains concluding, not recording.

## Read-side audit log (opt-in, v0.3)

`--audit-read` on `search` / `related` writes a JSONL event to `<graph>/reads.jsonl`
only when the read is **high-risk**: `--layer L4` (rule access), `--strict` queries, or
results that include `superseded` nodes. Default reads stay zero-cost and are not
logged.

- Not written into `changes[]`: read events would drown the write ledger, and
  `changes[]` is append-only so it could never be rotated.
- Bounded and rotated: 1 MiB per segment, one older segment kept (`reads.jsonl.1`).
- `reads.jsonl` contains query text — treat it as data, not as a secret store.

## `check --baseline`: debt with a name, not an exemption (v0.38.0)

`amg check --strict` on the team graph reports 1011 errors. All but five are legacy
nodes written before the amg schema existed; none can be fixed without fabricating
evidence, and all are real. A check that is permanently red carries no information.

```
amg check <dir> --strict --baseline FILE                    # excuse only what is registered
amg check <dir> --strict --baseline FILE --write-baseline   # register the current set
amg check <dir> --strict --baseline FILE --prune-baseline   # drop entries that no longer fire
```

Five rules, each with a test that fails if it is broken:

1. **Registered by node id, not by count.** A baseline reading "1006 known" would
   accept 1006 of anything. A baseline that names nodes cannot: a violation on an
   unregistered node is new.
2. **Compared by problem kind, not by node.** A registered node that grows a second
   kind of problem returns to the report in full — its old registration no longer
   describes it. A node whose identical messages were merely recounted stays known.
3. **Document-level errors are never excused.** `schema mismatch` and duplicate edges
   belong to no node, so they cannot be registered. On the team graph these are the
   five that stay red after a baseline is written — deliberately.
4. **`--write-baseline` refuses to grow an existing baseline** (`E_BASELINE_GROW`).
   A baseline may shrink; a new violation has to be argued for, not swept in by
   re-running a command.
5. **A plain check never rewrites the baseline.** Every excused violation is counted
   and printed on each run: "1006 known" is not the same claim as "clean".

What it is not: it does not verify anything, does not make the graph good, and is not
an exemption registry. It is a filing cabinet — the debt keeps its size and its names.
