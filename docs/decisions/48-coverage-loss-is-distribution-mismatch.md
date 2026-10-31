# Decision #48

[← decision log](../DECISIONS.md) · status: active · amends #47

**The coverage loss is distribution mismatch, not anti-correlation.** #47 explained its own
result by saying coverage "points away from the answer" because N2 injects distractors from the
query vocabulary. An attack falsified that in four arms. (a) Same corpus, same seed, distractors
rewritten with 78 foreign words of comparable length (asserted disjoint from the query
vocabulary): the loss is **-0.057, identical** to N2's, so the damage does not depend on the
distractors being query words at all. (b) Gold coverage averages **0.610 against the distractors'
0.376** — positively correlated, the opposite of what #47 claimed. (c) The real driver is the
shape of the two distributions: gold is bimodal (7 of 22 queries fully covered, 8 of 22 at or
below 0.33) while distractors cluster (64% between 0.25 and 0.5). Query `q04`: gold
`task.windows-lock` matches one content word (coverage 0.12) while a distractor matches three
*function* words (coverage 0.38), and alpha=1 pushes gold from rank 1 to **rank 79**. (d) Restricting
coverage to content words only returns N2 to 0.615 (+0.077, the first arm to pass C2's +0.05) with
reversals falling 9 → 3 — but it is a selective construction, so it is a candidate for a fresh
pre-registration, not a result. Corrected conclusion: coverage is positively associated with the
answer and loses recall because a partial-content-word answer is scored as a poor answer; the
next direction is **content-word weighting or stop-word stripping**, not "separating source tokens
from injected ones" (#47's sentence). Cost: a signed explanation replaced two rounds after it was
published, which is the point of writing mechanism claims down where an attacker can reach them.
*Signed 2026-10-31; `docs/memory-arch/ATTACK-COVERAGE-MECHANISM-GLM.md`; v0.32.7.*

**Correction 2026-10-31, after independent verification (DECISIONS #53).** The arm this page calls
"coverage to content words only" was implemented as a **vocabulary filter**, not a part-of-speech one:
`/tmp/re8/attack_coverage_mechanism.py` restricts counted query tokens to `orig_vocab` — the
vocabulary of the original 27-node corpus — with the denominator left as the full query length.
Every number here reproduces, and the mechanism conclusion stands; what does not stand is reading the
**+0.077 as an estimate for content-word weighting**. It is a filter that knows which vocabulary is
"original", so it is partly oracle, and it is closer to the sentence #47 proposed than to the
direction this page named. The sentence above stays as published; the correction is that its named
next direction was inferred from the wrong arm. DECISIONS #49 then tested content-word weighting
itself and it failed.
