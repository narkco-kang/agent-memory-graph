# Decision #56

[← decision log](../DECISIONS.md) · status: active
**The evidence root is stated, never guessed; a path string is not an identity.**

## The problem

`amg audit <dir>` used one argument for two different things: where `graph.json`
lives, and what `evidence` locators resolve against. Those coincide in the simple
layout and diverge in every real deployment, because the team writes group graphs
to `graphs/<group>.json` while the evidence strings are relative to the workspace
root (`docs/...`, `src/...`).

Measured on one graph, one build, one command — only the base changed:

| evidence base | `evidence_unverifiable` |
|---|---|
| `knowledge-graph/live` (the graph directory) | **232** |
| workspace root (where the locators point) | **24** |

A wrong base does not fail. It returns a **larger number that reads like a finding**.
Nothing in the output said which base had been used, so the same graph supported
two contradictory debt figures depending on where it was run.

## Decision

**1. The base is required, not inferred.**

```
$ amg audit <dir> --verify
E_EVIDENCE_ROOT_REQUIRED: pass --root <dir>, the base that evidence locators are
resolved against. It is not inferred from `dir`: ...
$ echo $?
2
```

No report is printed when the base is unknown. Guessing one of the two numbers and
presenting it as the result is worse than refusing.

**2. A base with no structure anchors is refused.**

Before any bucket is computed, the base is checked for the markers of the tree the
team works in (`README.md`, `docs`, `agent-memory-graph`, `src`, `tests`). None of
them means the base almost certainly is not that tree:

```
E_EVIDENCE_ROOT_SUSPECT: ... holds none of the structure anchors (...) — refusing to
report evidence buckets from a base that does not look like the tree the locators
were written against.
```

`--force-root` overrides the refusal, and the report then records
`anchors.suspect: true`. Forcing does not make a wrong base right; it makes the
choice visible.

**3. The report carries the base and its physical identity.**

Every `--verify` report includes:

```json
"evidence_root": {
  "path": "/…/workspace",
  "source": "--root",
  "identity": {"dev": 16777229, "ino": 24188727},
  "anchors": {"found": ["docs", "agent-memory-graph", "tests"], "suspect": false}
}
```

`(st_dev, st_ino)` is reported because **a path string cannot identify a
directory**. Measured on this platform:

- a case-insensitive filesystem gives one directory several spellings, and
  `realpath` returns a different string for each (`…/workspace` vs `…/Workspace`);
- a symlink to a directory is collapsed by `realpath`, but a hard link is not —
  two names, one inode, two `realpath` results.

`(dev, ino)` collapses all of them. It is a **report field, not a rejection
condition**, and that is deliberate.

## Why it is not enforced

Anyone who can choose `--root` can choose one that passes. Turning the identity
into a gate would promise a guarantee this design cannot keep: there is no
out-of-band trusted anchor, and the project's own `fingerprint.py` records the same
limit — a fingerprint stored inside a file proves nothing against someone who can
edit that file.

So the honest statement, recorded in the threat model:

> This build does not defend against deliberate root selection by someone who has
> write and command-line access. It defends against **reading a number whose base is
> unknown**, which is the failure that actually occurred: two people quoting 232 and
> 24 about the same graph, both believing they were quoting the debt.

## Consequences

- Existing invocations of `audit --verify` now fail loudly instead of reporting a
  base-dependent number. That is the intended break.
- `--graph <file>` (decision #57) separates *which file* from *which base*; a graph
  shared with another writer keeps its own layout and still names its base.
- The bucket names from `--verify` are unchanged: `evidence_absent`,
  `evidence_unverifiable`, `evidence_resolvable`, `evidence_declared_uncheckable`,
  `known_limitation`.
- Still unmeasured here: bind-mount identity (a bind mount can present one directory
  under two device numbers, which `(dev, ino)` cannot collapse).

## Rejected alternatives

- **Auto-ascend** to an ancestor that resolves the evidence: silent. Measured to
  return nothing at all under `/tmp`, leaving the caller with a default nobody chose.
- **Declare the base in graph metadata**: moves the power to choose from the caller
  to the writer. The writer already has it. Measured: the field is accepted on load,
  preserved across writes, and editable by anyone who can edit the file.
- **Compare report base strings across runs**: a symlink, a hard link, or a different
  spelling produces different strings for the same directory, so the comparison
  answers a question nobody asked.

**Discussed:** 记忆架构开源 @ 2026-11-01 by Glm仔,Hermes仔 — Hermes仔 measured the 232-vs-24 split and the symlink/hardlink/case variants (`knowledge-graph/graphs/记忆架构开源.json`); Glm仔 independently confirmed that `realpath` does not collapse case variants. Chief signed the downgrade from enforcement to a report field.

*Signed 2026-11-01; group notice rule #8; v0.37.0.*
