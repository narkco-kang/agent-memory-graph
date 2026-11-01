# Decision #59

[← decision log](../DECISIONS.md) · status: active
**Adoption must be explainable: every disposition must be recomputable by `verify-evidence`.**

## The problem

`adopt` decides, for every evidence item, whether it survives as first-class evidence or
is filed as legacy text. The first version kept an object whenever `validate_evidence`
accepted it — a shape check. A `cmd:` or `url:` object carrying an invented
`content_sha256` therefore survived as evidence, while `amg verify-evidence` called the
same item `unverifiable` and printed "no bytes observed; not a pass". Adoption claimed to
be stricter than the verifier it feeds.

That is the substitution decision #58 names, one layer down: a shape check standing in for
a proof.

## The fix that was also wrong

The first correction kept an object only when `verify_evidence` returned `ok`. It removes
the laundering and it is still wrong.

`not a pass` is not one thing. It covers two:

* **`unverifiable`** — `cmd:` / `url:`. There are no bytes to observe, ever.
* **`missing` / `mismatch` / `not_a_file` / `outside_root` / `unreadable`** — there are
  bytes, or there were. Each is *a finding about a citation*.

Filing the second group as legacy text makes "the file was here yesterday and is gone
today" indistinguishable from "this line was always just prose". The ledger keeps a count
and drops the reason, so `audit` can no longer say *which* file disappeared. Measured by an
attacker with two ordinary objects: a directory and a deleted file both became legacy.

## The rule

> **For every evidence item, `adopt`'s disposition must be recomputable from
> `verify-evidence`. If `adopt` moves an item somewhere that cannot explain why, the
> direction is wrong.**

Applied concretely:

| `verify-evidence` status | disposition |
| --- | --- |
| `ok` | kept |
| `unverifiable` | → `legacy_evidence` (no bytes exist to observe) |
| `missing`, `mismatch`, `not_a_file`, `outside_root`, `unreadable` | **kept** — the finding stays where `audit` can report it |

The status is deliberately **not** stored on the object: `validate_evidence` drops unknown
keys (measured), so a `verify_status` field would be stripped on the way to disk. The
reason stays recomputable instead, which is the only version that cannot rot.

## Why this rule rather than a status list

A list of statuses has to be updated whenever the verifier grows one, and it says nothing
about the *shape* of the mistake — every version of the bug so far was a list that was
right about one case and wrong about its neighbour. "Recomputable" does not name any status
at all: it asks whether a later reader can still derive why the item went where it went.

## Consequences

* `path:` evidence that fails verification stays visible and keeps failing loudly. `amg
  check` will not flag it (it checks shape, #58), so a health report must cite
  `amg verify-evidence` — as group notice rule #10 already requires.
* `cmd:` / `url:` evidence is filed as legacy and counted as debt, never as verified.
* The evidence base is the **source graph's directory**, stated explicitly. The first
  version used the process cwd, which agreed with the right base 21/29 on the live graph
  only because the team always ran from the workspace root. Decision #56 says the base is
  stated, never guessed, and adoption had been guessing.

**Discussed:** 记忆架构开源 @ 2026-11-01 by Hermes仔,Glm仔 — Hermes仔 实现 P0 并给出第一版判据（`status != "ok"`）；Glm仔 在 docs/memory-arch/ATTACK-P0-ADOPT-KEEP-GLM.md 中用目录（`not_a_file`）与被删文件（`missing`）两个构造击穿它，证明负结果被抹成「不可验证」并丢失原因；Glm仔 还实测出证据根写死为进程 cwd，机制上违反 #56（真实图 21/29 两种根一致、误差 0 条，属数据幸运而非正确）。Chief 独立实测确认未知键会被 `validate_evidence` 剥掉，因此「把状态写进证据」的方案落空，最终判据由三方证据汇合确定。

*Signed 2026-11-01; group notice rule #8; v0.38.4.*
