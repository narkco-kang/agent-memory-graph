# Decision #55

[← decision log](../DECISIONS.md) · status: active

**Anchoring is a tie-breaker, not a gate.** Entry #3 said anchored hits come first and that the
anchor filter "degrades, never hides". The second half described the *filter* (`--strict`); neither
half described the *ranking*. As `rank_key`'s first component, anchored-ness was not a preference —
it outranked every score.

Measured on the team's own graph (474–478 nodes, 296–300 anchored), 40 stratified queries per
stratum, three seeds: under the old key, anchored nodes reached their own label **40/40** and
unanchored nodes **0/40**, with `rank@50 = None` — an unanchored node could not appear in the top 50
at all, whatever it scored. The sharper pair is not a rate: an anchored node scoring **1.313**
outranked an unanchored node scoring **3.527**. That is the difference between "degrades" and
"hides", and it is #3's sentence that was wrong, not the measurement.

v0.36.0 moves anchored-ness from the first key to the second:
`(round(raw, 3), anchored, node_id)`. Re-measured on the same strata and seeds: anchored **40/40**,
unanchored **40/40**.

What this does **not** license: the four synthetic arms move by exactly **0** on every metric
(control 0.8654, n1 0.8654, n3 0.8654, n2 0.5385, realtext 0.6923), and that is *structural*, not
reassurance — those corpora declare evidence uniformly, so an anchor key cannot reorder them. The
safety evidence is the stratified re-measurement above, never the delta.

What stays: every hit still carries `anchor_state`, and `--strict` still returns anchored-only
results. What changes: rank position no longer tells the reader *which* hits are evidenced. Read
`anchor_state`, or use `--strict`; do not infer evidence from order.

The guards for this change were themselves defective on first delivery: of four new tests, three
still passed under the old key, so the change shipped with decorations rather than guards. Glm仔
found that by mutating `rank_key` back inside an isolated worktree. Three tests now fail under the
old key, and `tools/glm-mutation-check.py` re-runs that acceptance as a command, not a claim.

**Discussed:** Glm仔 — knowledge-graph/graphs/记忆架构开源.json (issue.mem-arch-v036-new-tests-do-not-catch-mutation: independent-worktree mutation of the old key, 1.313 vs 3.527 fixture, 3 red); Hermes仔 — knowledge-graph/graphs/记忆架构开源.json (task.mem-arch-v036-tests-fix-hermes: three test fixes landed, mutation self-check, 3 red under the old key).

*Signed 2026-10-31; group notice rule #8; v0.36.0.*
