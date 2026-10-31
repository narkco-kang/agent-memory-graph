# Decision #53

[← decision log](../DECISIONS.md) · status: active

**The +0.077 arm was a vocabulary filter, not content-word weighting — and #48's named direction was
inferred from it.** Independent verification of v0.33.0–v0.33.2 reproduced every published number and
then found one description that does not match its implementation.

#48 says: "Restricting coverage to content words only returns N2 to 0.615 (+0.077, the first arm to
pass C2's +0.05) … the next direction is **content-word weighting or stop-word stripping**". The
script behind that arm (`/tmp/re8/attack_coverage_mechanism.py`, reproduced here) does:

    orig_vocab = frozenset(tokens of the original 27-node corpus)
    qt_eff = qt & orig_vocab                      # counted query tokens
    cov = len(qt_eff & node_tokens) / len(qt)     # denominator stays the full query length

That is a **vocabulary filter** — it counts only query tokens that exist in the original corpus's own
vocabulary — not a part-of-speech filter. Re-running the arms reproduces the numbers exactly: A −0.057,
B −0.057, C **+0.077**, and the mechanism #48 records (distribution mismatch, `q04` pushed from rank 1
to 79) stands. What does not stand is the inference.

Two consequences, both now recorded:

1. **The +0.077 was never an estimate for content-word weighting.** The filter knows which vocabulary
   is "original", so it encodes information a shipper would not have; it is partly oracle, and it is
   closer to the sentence #47 proposed ("separate source tokens from injected ones") than to the
   direction #48 named. Anyone reading #48 as "content-word weighting is worth about +0.08" would be
   reading a number that does not measure that.
2. **The direction was tested properly afterwards and failed.** #49's pre-registered round implemented
   real content-word coverage — stopword stripping with the denominator over content tokens — and every
   arm lost recall (0.442 / 0.404 / 0.481 against 0.538). So the error was in the *label*, not in the
   conclusion that closed the family: the family is closed for a stronger reason than the one #48
   offered.

The page is not rewritten: the published sentence stays, with a dated correction appended that points
here (a corrected claim is marked, never deleted). A test asserts that both the original sentence and
the correction are present, so a later cleanup cannot quietly drop either.

Decisions: **(a)** experiment arms are described by their implementation, not by the idea they
resemble — an arm name may not name a mechanism its code does not implement; **(b)** a correction to a
published page requires a dated block on that page plus an entry here, and the original text stays;
**(c)** #49's conclusion is unchanged and un-weakened: the lexical family is closed for N2.

Cost: one independent verification caught a mislabelled arm two releases after publishing; the cost of
not catching it would have been a future round implementing "content-word weighting" and quoting +0.08
as its prior.
*Signed 2026-10-31; `docs/memory-arch/VERIFY-V033X.md`; v0.33.4.*
