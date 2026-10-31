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

**Scope note 2026-10-31, after independent verification (Hermes仔, `docs/memory-arch/VERIFY-REALGAP-HERMES.md`).**
Two limits of this entry, stated rather than left implicit: (1) the calibration check that passed
(competing share 0.476) holds **in the pre-registered configuration only** — at 20-word windows the
same construction gives 0.589 and at whole paragraphs 0.827, so "the corpus is calibrated" is a
statement about window = 8, not about the corpus in general; (2) the length sweep's two numbers are
r@5 **0.692 → 0.673** and r@1 0.558 → 0.654, with r@10 0.731 → 0.673 — the first version of this
paragraph paired them loosely, and the per-length table in
`experiments/retrieval_noise_realtext/sensitivity_window.json` is the authority. The reported
shortfall is therefore **0.027 at recall@5** (0.70 − 0.673), not 0.008, once the most realistic
configuration is the reference.

**Retraction and reproducibility note 2026-10-31 (same day, after Mini仔 reproduced the harness).**
Two statements in the note above are withdrawn. (1) The 0.673 / 0.654 figures are **not reproducible**:
this experiment draws its distractor text from `README.md` and `docs/**` at run time, and those files
changed after the run, so a re-run today gives whole-paragraph **r@5 0.654, r@1 0.635** where the
committed artefact says 0.673 / 0.654. "0.027" was therefore a number tied to one document state, not
to the corpus. (2) I publicly ruled that the independent verifier had misread a column; that ruling is
wrong — he had re-run the harness and seen the drifted corpus, and the committed artefact was the
outlier. `issue.mem-arch-realtext-column-mixup` is corrected accordingly.

The 0.692 anchor at the eight-word window did reproduce across both states, but that is one
configuration, not a claim about the corpus. Until the corpus is snapshotted and its digest recorded in
`result.json` (Mini仔's ①, agreed in this round), **no number in this entry may be quoted as
reproducible**. The fix and the re-measurement are tracked as
`issue.mem-arch-realtext-corpus-unpinned`; until then the entry stands as published with this block
attached, not rewritten.

**Corpus pin, and the re-measurement it enables (2026-10-31, same day, after the reproduction).**
The drifting parameter is now committed instead of described. `result.json` records the prose input it
read — per-file `sha256` for the 71 corpus files plus an `extracted_sha256` over the paragraph text —
and `corpus_snapshot.json` holds the same record standalone, so a re-run can say *stale corpus*
instead of quietly producing a new number. At the pinned corpus (635 paragraphs, 71 files) the measurements are:
eight-word window r@5 **0.692** / r@1 0.615 / MRR 0.688 with competing share **0.492**; whole
paragraphs r@5 **0.654** / r@1 0.635. The 0.476 share and the 0.558 r@1 in the table above belong to
the earlier, unpinned corpus state and stay as history; the shortfall at the most realistic
configuration is therefore 0.70 − 0.654 = **0.046** at the pinned state, not 0.027. `ledger.json`
carries the per-query rows (1-based `best_gold_rank`, matched tokens, out-of-reach set), and
`paired_test.py` compares two ledgers as a falsifier — pass means zero regressions, and no p value is
reported as significance at n=26.
