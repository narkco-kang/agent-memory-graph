# Decision #60

[← decision log](../DECISIONS.md) · status: active
**A tie is reported, not explained away. No secondary key was shipped.**

## The problem

`rank_key` returns `(score, anchor, id)` and the sort is `reverse=True`, so among equal
scores the alphabetically larger node id decides the order. That is reproducible, and it
is not a judgement about relevance — but four adjacent hits look like four ranked results.

Measured exposure (v0.38.6, frozen corpus): **5 of 26 queries (19.2%)** have the 5th and
6th results on the same score; the corpus has 26 tie groups / 34 adjacent positions inside
top-10. On the team graph the same measurement is 3 of 120 (2.5%). So r@5 carries a block
of order that no relevance model chose — small on the live graph, large on the published
benchmark.

## Direction A, implemented and rejected

"At equal score, prefer the hit that matched more distinct fields." The reasoning is
sound — the alphabet carries no information — and the measurement kills it:

```
score = sum(weight x idf) over matched fields
=> equal score ALREADY implies equal field composition
=> a key that is equal for every member of a tie cannot break that tie
```

```
official corpus   26 tie groups   separable by field count:  0  (0%)
team graph        120 queries     top-5 membership changed:   0  (0%)
```

Two independent measurements (mine and the CEO's, different harnesses) produced the same
zero. It was not merely inert: field count rose with verbosity, so in the only place it
could act it favoured whichever node repeated the term across more fields. Verbosity is not
relevance, and a no-op tie-break is worse than none — it looks like the alphabet is gone
while the alphabet still decides.

The implementation was removed, not left behind a flag. `rank_key` takes exactly
`(raw, anchor_present, node_id)`, and a test asserts that signature so a fourth component
cannot be added quietly.

## Direction B, shipped

Every hit now carries `tie_size` (how many results in the returned window share this exact
score) and `tie_group` (a number for groups of 2+, `null` for a group of one). The order is
unchanged. A reader who sees `tie_size: 7` knows those seven positions are not a ranking
judgement.

Three rules, each with a test that fails if broken:

1. **A tie is never a hit.** A gold answer ranked 6th and tied with the 5th is a miss. The
   fixture makes every node score identically and asserts position-based recall is 0.
   Mutation: make search widen `k` across a tie and this fails.
2. **`tie_size` never enters an r@5 numerator.** Same test; the metric stays tie-blind.
3. **The published baseline does not move.** r@5 recomputed from the frozen corpus must
   equal 0.865 (macro-average over queries). A "harmless" ordering edit that shifts it
   fails here before release.

## What this does not do

It does not make ties meaningful, and it does not remove the alphabet — 100% of corpus
ties and 79% of team-graph ties are still ordered by id. What changed is that the
ambiguity is now visible instead of being read as a result.

*Signed 2026-11-01; group notice rule #8; v0.38.7.*

**Discussed:** 记忆架构开源 @ 2026-11-01 by Glm仔,Hermes仔 — Glm仔 attacked both directions in docs/memory-arch/ATTACK-TIE-BREAK-DIRECTIONS-GLM.md with the field-count {0,1,2} argument and the "tie_size becomes an excuse for passing" risk; Hermes仔 reproduced the 19.2% corpus figure and the 0-of-34 separability independently with a different harness, measured the micro-vs-macro denominator difference (0.839 vs 0.865) before pinning the baseline, and removed direction A rather than shipping it behind a flag.
