# Decision #22

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31.*

**One source of truth for audit output: structured findings, human strings
    derived.** `audit` used to build display strings directly, so any consumer that
    wanted the node or the owner had to parse them. Now each finding is recorded once
    as a dict (severity, kind, detail, node/edge/owner/age) and the `conflicts` and
    `hints` lists are generated from it, which makes drift between text and `--json`
    impossible by construction rather than by discipline. The string lists stay, in
    the same order, because they are the existing contract; `findings` is additive.
    A test asserts the two views match exactly.
    *Signed 2026-10-31.*
