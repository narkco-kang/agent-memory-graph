# Decision #58

[← decision log](../DECISIONS.md) · status: active
**`check` verifies shape, not truth. A forged digest passes it.**

## The problem

`amg check --strict` reported `✓ check passed` on a graph whose node declared

```
content_sha256 = 0000000000000000000000000000000000000000000000000000000000000000
```

The file it cites hashes to something else entirely. Nothing was wrong with the
run; the command did exactly what it is built to do.

Source: `cli.cmd_check` calls `m.check()`, and `protocol.check` compares schema,
field types, locator prefixes and digest *format*. **It never calls
`verify_evidence`.** Write-time verification (`gate.verify_evidence_on_write`) and
read-side verification (`gate.verify_evidence`, used by `amg verify-evidence`) are
separate code paths that `check` does not reach.

So there are two different questions, and one command that answers only the first:

```
amg check --strict     →  ✓ check passed              (0 errors)   shape only
amg verify-evidence    →  ✗ E_EVIDENCE_MISMATCH       [mismatch]   truth
```

## Why this needed a decision, not a bug fix

`check` is not broken. It is the one command whose job is "is this document
well-formed". The failure was social: a command named `check`, printing
`✓ check passed`, is read by everyone as "the memory is sound". Team members used
that word for four different tools in one day, and twice reported green while the
graph was red.

The same distinction had already been made twice for other reasons —
#34 ("nothing was verified" is not "healthy") and #36 (an evidence base is a
policy, not a guess). This entry is the same rule applied to the command itself.

## The decision

**`amg check` is a shape check. Saying "evidence is verifiable" requires
`amg verify-evidence`, and a health report must quote both numbers.** Reporting
only one is an incomplete claim, and is treated as a false report.

Naming, per tool — the four are not interchangeable:

| command | what it actually checks |
|---|---|
| `amg check` | schema, field types, locator prefixes, digest *format*. Not truth. |
| `amg verify-evidence` | recomputes each digest against the file. The only truth check. |
| `memctl verify` | graph corruption only: rev monotonic, changes consistent, ids unique. |
| `kg.py check` | a fourth judgement, unrelated to the other three. |

## What is pinned by tests

`tests/test_check_is_shape_only.py` asserts, against the same graph:

1. a node with an all-zero forged digest passes `amg check --strict` (exit 0);
2. the same graph fails `amg verify-evidence` with `E_EVIDENCE_MISMATCH`;
3. removing the forged node makes both agree — so the test is about the digest,
   not about a fixture that always disagrees.

Mutation: wire `verify_evidence` into `check` and test 1 fails; make
`verify-evidence` trust the declared digest and test 2 fails. Either mutation
would erase the distinction this entry exists to preserve.

## What this does not do

It does not make `check` stricter, and it does not make a forged digest safe:
the write path still refuses one (`E_EVIDENCE_VERIFY_FAILED`, #39), and a digest
that arrives by editing the JSON is caught by `verify-evidence`. It only stops
the two from being confused for each other by name.

## Discussion

**Discussed:** 记忆架构开源 @ 2026-11-01 by Glm仔,Hermes仔 — Glm仔 的攻击报告 docs/memory-arch/ATTACK-EVIDENCE-REPAIR-ABC-GLM.md 首先指出 `check` 从不调用 `verify_evidence`，并用伪造 sha 的节点证实；Hermes仔 在 docs/memory-arch/SUPERSEDED-SEMANTICS-20261101.md 复现并测量了反方向——写入路径确实会拒绝伪造 sha（#39 `E_EVIDENCE_VERIFY_FAILED`），所以这个区分不是单个 fixture 的假象。Chief 在两个方向上都独立复现后签署。

*Signed 2026-11-01; group notice rule #8; v0.38.2.*
