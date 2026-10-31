# Decision #51

[← decision log](../DECISIONS.md) · status: active

**A synthetic noise model must be calibrated on what competes, not on what exists.** #50 left one
question open: whether N2 — whose distractors are six tokens drawn from the queries' own vocabulary —
represents the noise a long-lived memory graph meets. An attempt to answer it failed its own
pre-registered calibration check, and the failure is the decision.

Measured on the candidates that actually compete (top-100, gold excluded), the contrast is real:

| corpus | pairs | mean coverage | median | share ≥ ¼ of the query |
|---|---|---|---|---|
| control (27 real nodes) | 146 | 0.147 | 0.167 | **0.144** |
| n2 (query-vocabulary noise) | 2,578 | 0.415 | 0.400 | **0.918** |

The pre-registered plan was to build `N2-cal` whose competing distractors reproduce control's 0.144,
by drawing each node's query-token count from control's per-pair coverage distribution. It produced
0.606, missed the ±0.10 tolerance, and by the rule fixed beforehand the corpus was rejected — so its
`recall@5` of 0.654 is a rejected-run diagnostic, not a result. Probing an explicit token-count mix
showed why the base rate cannot repair it: 0.55/0.43/0.02 gave 0.537, 0.70/0.28/0.02 gave 0.516, and
0.80/0.19/0.01 gave 0.497. **With two thousand nodes carrying two query tokens, those nodes own the
top-100 however rare they are** — the pool is selected by the very quantity being calibrated, so a
per-pair rate mapped into a 10k pool overstates competition by construction.

Decisions: **(a)** synthetic noise corpora in this project must be calibrated and checked on the
*competing* subset, with the check run before any recall number is reported (the Q2 rule, now
standing); **(b)** this attempt is recorded as a failure with its numbers and its probe ladder, not
tuned until it agreed; **(c)** the next design samples distractor text from **real note text** (the
team's graph holds 410 notes) instead of token soup, because the failure is in the generator's shape,
not its parameters; **(d)** nothing about the published results moves — N2 stays the hardest corpus,
`0.538` stays the shipped number, and the 0.70 target stays **unmet**.

Cost: one pre-registration, two 3-second corpus builds and a probe ladder, to replace "N2 might be
unrepresentative" with a measured ratio (6.4×) and a concrete reason why the obvious re-calibration
does not work.
*Signed 2026-10-31; `experiments/retrieval_noise_representativeness/`; v0.33.2.*
