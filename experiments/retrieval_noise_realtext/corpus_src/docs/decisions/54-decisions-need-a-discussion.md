# Decision #54

[← decision log](../DECISIONS.md) · status: active

**A decision entry must name the group discussion that produced it; the CEO signs, the CEO does not
author the plan.** The user required this twice (2026-10-31), the second time as an execution-layer
rule rather than a preference. The measured failure: v0.33.0–v0.33.4 and entries #49–#53 were
authored, run and signed by one agent, with the group informed afterwards. Every number in them
reproduced under independent verification, and the process was still wrong — an organisation that
cannot tell "verified" from "self-verified" has no verification.

The rule, as enforced: a decision page numbered above this one must carry

    **Discussed:** <member> — <evidence path>; <member> — <evidence path>

naming at least **two distinct members** and at least **one evidence path**. One of them proposed a
variant or an attack; the other independently verified it; the CEO decides and signs, and writes the
page. A page that cannot name them is not a decision but one agent reasoning in public.

`tests/test_group_authority_gate.py` enforces it mechanically, and the rule function is itself tested
against four synthetic page bodies (missing line, one name, two names without a path, and a valid
line), so the gate cannot pass by being vacuous. Entries #49–#53 stay published as **pre-rule** with a
pointer to their verification reports; they are not retro-written, and the gate does not demand it —
a corrected or superseded claim is marked, never deleted.

What this costs: a decision can no longer be made in one turn, and a release can be blocked by a
member who has not yet verified it. That is the point — the block is the control.

**Discussed:** the user's directive (group notice rule #8, stated twice on 2026-10-31) — `docs/memory-arch/VERIFY-V033X.md`; Hermes仔's independent verification of v0.33.0–v0.33.4 — `docs/memory-arch/VERIFY-V033X.md`.

Decisions: **(a)** the gate above is mandatory for every entry after #54; **(b)** a release that
contains such an entry cannot be signed while the gate fails; **(c)** the CEO's own work is not exempt
— the five entries that motivated this rule are listed here as the counter-example, not as precedent.
*Signed 2026-10-31; group notice rule #8; v0.33.5.*
