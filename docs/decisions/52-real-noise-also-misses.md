# Decision #52

[← decision log](../DECISIONS.md) · status: active

**The 0.70 target is missed under realistic noise too — N2 is a worst case, not the explanation.** #50
and #51 established that N2's distractors are built from the queries' own vocabulary (91.8% of
competing distractors reach a quarter of the query, against 14.4% for real nodes) and that calibrating
a synthetic pool to the real rate fails, because the top-100 is selected by the quantity being
calibrated. #51's way out was to stop inventing distractors and use real prose.

A pre-registered corpus did exactly that: 10,000 nodes whose text is a seeded 8-word window of a real
paragraph from this repository's own documentation — no token drawn from a vocabulary list, function
words and co-occurrence straight from the prose.

| corpus | r@1 | r@5 | MRR@10 | competing share ≥ 0.25 |
|---|---|---|---|---|
| control (27) | 0.731 | 0.865 | 0.821 | 0.144 |
| **n2** | 0.481 | **0.538** | 0.543 | 0.918 |
| **real text (8-word window)** | 0.558 | **0.692** | 0.650 | 0.476 |
| real text, whole paragraphs (median 37 words) | **0.654** | **0.673** | 0.695 | 0.827 |

The calibration check passed (0.476, below N2's 0.918) and the ordering held (0.538 < 0.692 < 0.865),
so the corpus stands — and it lands **below the published 0.70 target by 0.008**. A post-hoc length
sweep shows this is not a short-note artifact: longer, more realistic distractors make recall@5
slightly *worse* (0.692 → 0.673) while r@1 improves to 0.654.

Decisions: **(a)** the project publishes **two** noise corpora — N2 as the adversarial worst case and
the real-text corpus as the realistic measure — with their numbers side by side; **(b)** the 0.70
target stays attached to N2 and stays **unmet** (0.538), and the realistic number is reported as its
own measurement (0.692 / 0.673), never as the target being met; **(c)** N2's construction is recorded
as *overstating* the gap by roughly 0.13–0.15 recall@5, which is what #50 suspected, but the conclusion
#50 hinted at — "the target may only measure an artifact" — is **wrong**, and is recorded as wrong
here; **(d)** the remaining realistic shortfall (0.008–0.027) is a different problem from N2's 0.162
and needs its own pre-registration (tokenisation, phrase adjacency), not another noise model.

Cost: one pre-registration and two 10-second runs, to replace a hypothesis with two numbers and to
correct the direction the previous two decisions were leaning.
*Signed 2026-10-31; `experiments/retrieval_noise_realtext/`; v0.33.3.*
