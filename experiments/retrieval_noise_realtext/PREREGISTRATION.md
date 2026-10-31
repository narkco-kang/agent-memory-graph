# Pre-registration: a noise corpus built from real text

DECISIONS **#51** rejected the first calibration attempt and fixed the next design: distractor text
must come from **real prose**, not token soup, and the corpus must pass a calibration check on the
*competing* subset **before** any recall number is reported. This is that design, written before the
run.

## Why a real-text corpus

N2's distractors are six tokens drawn from the queries' own vocabulary; #49, #50 and #51 established
that this construction makes the corpus a near-duplicate filter (91.8% of competing distractors reach
a quarter of the query, against 14.4% for real nodes) and that a token-count mix cannot reproduce the
real rate because the top-100 is selected by the very quantity being calibrated.

The remaining question is empirical, not statistical: **what does the shipped scorer do when the
competing notes are real prose?** If a corpus of real sentences is easy, the 0.70 target on N2 is a
statement about adversarial robustness, and should be published as one.

## Construction (fixed here)

Pool: every paragraph of at least six words from `README.md`, `docs/*.md` and `docs/decisions/*.md`
of this repository — 593 paragraphs of real English prose about this project. That pool is fixed by
the repository's own content, not chosen to make the corpus hard or easy.

For each of 10,000 synthetic nodes: pick a paragraph with `random.Random(20261031)`, take a
contiguous window of **8 words** starting at a seeded offset, and use it as the node's label (first
three words) and note (the rest), with the same `bench.make_node` scaffolding N2 uses. No token is
invented, reordered or drawn from a vocabulary list; the word *distribution*, including function
words and co-occurrence, is the documentation's own.

Reported alongside: control (27), n1, n2, n3, all rebuilt the same way as the earlier rounds.

## Checks and criteria (fixed before the run)

* **Q2' calibration, reported first**: competing-distractor share ≥ 0.25 for this corpus. It must be
  reported *before* Q1, and it must land **strictly below N2's 0.918** for the corpus to be accepted
  as "real text". It is not required to match control's 0.144 — a larger pool of real prose is
  allowed to compete more than 27 hand-written nodes.
* **Q1 recall**: shipped `recall@5` on this corpus. Pre-registered prediction: **≥ 0.75**.
* **Q3 ordering**: N2 < this corpus < control.
* **Q4 no target inflation**: the 0.70 target stays attached to **N2** and is reported **unmet**. A
  higher number on this corpus is reported as a *separate* measurement, never as the target being met.

### Predictions

1. competing share ≥ 0.25 between 0.15 and 0.45 (below N2's 0.918, plausibly above control's 0.144).
2. shipped `recall@5` ≥ 0.75 (Q1), and above N2's 0.538.
3. ordering N2 < real-text < control (Q3).
4. the corpus is not trivially easy: at least one query still fails at top-5, because real prose about
   the project can still be lexically closer to a query than the true answer.

## Outcome

Run on 2026-10-31, `run_realtext.py` (≈10 s), then the post-hoc `sensitivity_window.py`.
Machine-readable in `result.json` and `sensitivity_window.json`.

**Calibration first, as the pre-registration requires:** the competing-distractor share ≥ 0.25 on
this corpus is **0.476** — below N2's 0.918 (Q2' passes) and above control's 0.144.

| corpus | r@1 | r@5 | r@10 | MRR@10 | ceiling | competing share ≥ 0.25 |
|---|---|---|---|---|---|---|
| control (27) | 0.731 | 0.865 | 0.865 | 0.821 | 0.885 | 0.144 |
| n1 | 0.731 | 0.865 | 0.865 | 0.815 | 0.885 | — |
| **n2** | 0.481 | **0.538** | 0.577 | 0.543 | 0.846 | 0.918 |
| n3 | 0.731 | 0.865 | 0.865 | 0.821 | 0.885 | — |
| **real text (window 8)** | 0.558 | **0.692** | 0.731 | 0.650 | 0.846 | **0.476** |

**Verdict: Q2' passes, Q1 fails (0.692 < 0.75), Q3 holds (0.538 < 0.692 < 0.865), Q4 holds by
construction.** The headline is not the miss: it is that a corpus made of **real prose** — no invented
tokens, no vocabulary sampling, function words and co-occurrence straight from this repository's own
documentation — still leaves the shipped scorer at **0.692**, i.e. **below the published 0.70 target
by 0.008**.

### Predictions scored

| # | prediction | result |
|---|---|---|
| 1 | competing share between 0.15 and 0.45 | **wrong** — 0.476, just outside the band |
| 2 | shipped r@5 ≥ 0.75 | **wrong** — 0.692 |
| 3 | ordering N2 < real text < control | **correct** |
| 4 | at least one query still fails at top-5 | **correct** |

### Post-hoc sensitivity: is it the 8-word window?

Real notes are longer than 8 words (this repository's paragraphs have a median of 37), so the
pre-registered number could be a statement about *short* notes. Re-running the same construction at
three lengths:

| distractor length | competing share ≥ 0.25 | r@1 | r@5 | MRR@10 |
|---|---|---|---|---|
| 8 words (pre-registered) | 0.476 | 0.558 | **0.692** | 0.650 |
| 20 words | 0.589 | 0.538 | **0.692** | 0.618 |
| whole paragraph (median 37 words) | 0.827 | **0.654** | **0.673** | 0.695 |

Length does not rescue it: the longer and more realistic the distractors, the *harder* recall@5 gets
(0.692 → 0.673) even though r@1 improves. The pre-registered number is therefore not an artifact of
window length.

### What this settles

1. **The 0.70 target is missed under realistic noise too.** N2 at 0.538 is a worst case; a corpus of
   real documentation prose lands at 0.673–0.692. The shortfall is not explained by N2's construction.
2. **N2 still overstates the gap** — 0.538 vs 0.673–0.692 — so publishing both is the honest choice:
   N2 as the adversarial robustness corpus, the real-text corpus as the realistic measure.
3. **The remaining realistic gap is small** (0.008–0.027), unlike N2's 0.162. That is a different
   problem worth its own pre-registration (tokenisation of adjacent words, phrase handling), and it is
   not addressed by this round.
4. Nothing in `src/amg/` changed; the target stays **unmet** and stays attached to N2.
