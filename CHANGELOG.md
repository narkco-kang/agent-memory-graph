# Changelog

All notable changes to this project are documented here.
The format follows Keep a Changelog, and this project adheres to SemVer.

## [0.35.0] — 2026-10-31

The evaluation corpus is frozen, and the ranking rule says what it does when scores tie.

### Added

- `docs/RANKING.md` states the ranking rule instead of leaving it in a lambda: anchored hits first,
  then the displayed score (three decimals), then **node id descending** — which means that when two
  hits round to the same score, the order is alphabetical, not relevance. The key is now a single
  named function (`retrieval.rank_key`) rather than an inline expression.
- The tie surface is measured, not assumed: every arm in `result.json` carries `tie_surface` (how many
  queries have a tie at the k=5 and k=10 boundary, with their ids), and every `ledger.json` row carries
  `boundary_tie_at_5` / `boundary_tie_at_10`. At the pinned corpus that is realtext **10/26** at k=5,
  n2 10/26, control 5/26.
- The corpus is frozen as data: `experiments/retrieval_noise_realtext/corpus_src/` holds the 71 source
  documents with a `manifest.json` (per-file sha256), and the pin records `source_sha256` over their
  concatenation **in `files[]` order** as well as `extracted_sha256` over the paragraph text. A test
  re-derives both, so the two copies cannot drift apart silently.
- `result.json` must declare `representativeness`: that this corpus measures lexical retrieval over this
  repository's own prose, that its distractors are drawn from the same documents as the answers, and
  what that does and does not license. The validator raises if the block is missing or incomplete, so it
  is a gate rather than a paragraph in a README.
- `corpus_version` (currently `v2`) in both the pin and the result, so a change of corpus is a visible
  event instead of a silent shift in every quoted number.

### Changed

- `--check-corpus` is an audit, not a gate. It reports how many documents differ from the frozen set and
  how old the pin is, and **never fails**: the project's own documentation changes with every release, so
  a check that fails whenever `docs/` moves would be permanently red and would be turned off. What CI
  asserts instead is internal consistency — the committed numbers must reproduce from the pinned corpus.
- Refreshing the corpus is a deliberate version bump (`--refresh-corpus`, formerly `--rebuild-corpus`),
  not a routine command: **every number quoted anywhere has to be restated when it runs**.
- `tools/check_dist.py` requires `corpus_src/manifest.json` and `corpus_pin.json` in the artifacts, and
  the documentation-size budget keeps scanning only `README.md` + `docs/`, so the frozen fixtures are a
  fixture and not a document.

### Notes

- Nothing measured moved: at corpus v2 fractional r@5 **0.692**, r@1 0.615, MRR 0.688, competing share
  0.492, hit-or-miss **0.7308**, ceiling 0.8462 — identical to v1. Freezing the input is not a change to
  the measurement.
- **The corpus is a same-domain regression set, not an independent validation set.** 20 of 20 rare terms
  of the gold nodes (df ≤ 1 in the 27-node corpus) appear in the evaluation prose, because both describe
  this same product, and 12.8% of its paragraphs are the project's own writing about retrieval evaluation
  — including the decision entries some gold nodes point at. Freezing that corpus preserves the property;
  it does not remove it. No external claim may cite realtext as evidence of real-world retrieval ability.
- The 0.70 target remains attached to N2, remains **unmet** at 0.538, and the realistic corpus is reported
  as its own measurement. Decoupling changed which number is comparable, not whether the target is met.

## [0.34.1] — 2026-10-31

A checkout's line ending is not corpus content.

### Fixed

- CI `windows-latest` failed on the corpus pin added in v0.34.0: the pin hashed raw file bytes, so the
  same text produced `7ff0987a…` on an LF checkout and `ecf06ff9…` on a CRLF one and a clean Windows run
  reported *stale corpus*. CRLF is now folded to LF before hashing, for the per-file digests and for
  the extracted-text digest, and a regression test asserts the fold is not vacuous (raw hashing must
  differ). Numbers are unchanged: fractional 0.692, hit-or-miss 0.7308, out-of-reach still
  {q06, q08, q10, q18}.
- Fixed as an L0 hotfix (CI red, mechanical, reversible) and reported for review by Mini仔, the author
  of the pin, and Hermes仔 for independent verification.

## [0.34.0] — 2026-10-31

The evaluation harness is pinned, and the numbers it produces can be reproduced byte for byte. This
release also carries the correction that prompted it — commit `390c942` was tagged "v0.33.6" in its
message but never got a version bump, a changelog entry or a release; it is recorded here instead of
being rewritten, because a version that only exists in a commit message is not a release.

### Fixed

- **The real-text corpus is data, not a live read.** `experiments/retrieval_noise_realtext/` used to
  build its distractors from `README.md` and `docs/**` at run time, so a docs edit silently changed a
  published number (whole paragraphs r@5 **0.673 → 0.654**) with nothing failing. `corpus_pin.json`
  now freezes the 623 extracted paragraphs (223 KB), `result.json` records per-file `sha256` for all 70
  corpus files plus an `extracted_sha256`, and `--check-corpus` exits 1 on drift instead of quietly
  recomputing.
- **I ruled that the independent verifier had misread a column, and that ruling was wrong.** He had
  re-run the harness and seen the drifted corpus; the committed artefact was the outlier.
  DECISIONS #52 carries the retraction on the page, then the pinned re-measurement.

### Added

- `ledger.json` — 26 per-query rows with `rank_base: 1`, `best_gold_rank`, matched tokens and the
  out-of-reach set, plus **both** metric conventions: `fractional_r5` **0.692** and `hit_or_miss`
  **0.7308 (19/26)**. The two disagree about the 0.70 target and both are now published.
- `paired_test.py` — a paired **falsifier**: pass means zero regressions and reports integer pairs;
  `significance_claimed: false`, because at n=26 no p value is evidence. Held-out splitting was cut
  (structurally cannot reach p<0.05 at 13/13); single-arm comparisons need no correction, multi-arm
  forces Holm.
- `tests/test_realtext_artifacts.py` — 391 tests total; asserts both metric conventions recompute to
  the stored values, that the out-of-reach set stays {q06,q08,q10,q18} with ceiling 22/26, and that a
  corpus digest mismatch reports `stale corpus` rather than a new number.

### Not changed

- No `src/amg/` change. The 0.70 target stays attached to **N2** and stays **unmet** (0.538); the
  realistic corpora are reported as their own measurements with both conventions, never as the target
  being met.

## [0.33.5] — 2026-10-31

The group-authority rule the user stated twice is now a mechanical gate, not a promise.

### Added

- DECISIONS **#54**: a decision page numbered above it must carry a `**Discussed:**` line naming at
  least **two distinct members** and at least one evidence path — one proposed a variant or an attack,
  one verified it independently; the CEO signs and writes the page.
- `tests/test_group_authority_gate.py` enforces that on every later page, and the rule function is
  itself tested against four synthetic bodies (missing line / one name / two names without a path /
  valid), so the gate cannot pass by being vacuous.
- The five entries that motivated the rule (#49–#53) stay published as pre-rule with their
  verification reports; they are not retro-written, and the gate does not ask them to be.

### Not changed

- No retrieval code, no numbers. `src/amg/` untouched; N2 stays 0.538 and the 0.70 target stays unmet
  on both corpora. The next technical candidate is under group discussion and is **not** decided here.

## [0.33.4] — 2026-10-31

Independent verification of v0.33.0–v0.33.2 reproduced every published number and caught one arm whose
name does not match its code.

### Verified

- **v0.33.1**: all twelve semantic-arm values reproduce (control 0.865/0.865/0.981/0.923, n1
  0.865/0.865/0.962/0.904, n2 0.538/0.577/0.577/0.577, n3 0.865/0.865/0.904/0.942), including the
  load-bearing "n2 ceiling 0.846 = shipped ceiling". Cache hits read the same vectors (keyed by text
  digest + model digest); a cold re-embed was **not** run and is listed as unverified.
- **v0.33.2**: 0.144 / 0.918 / 0.606 and the probe ladder 0.537 / 0.516 / 0.497 all reproduce, with
  `Q1/Q2 = False, Q3 = True`.
- **v0.33.0**: all nine lexical arms are negative; attribution clarified — 0.481 is `s3_compact@0.5`,
  and the earlier coverage experiment's N2 arm also happened to land on 0.481 (different experiment).
- Five mutation classes were injected (result.json number, page number, `rejected` → `delivered`,
  `rejected` → `blessed`, `Q2 = True`) and all five failed, so the new tests can catch a forged result.

### Corrected

- **DECISIONS #48's "content words only" arm was a vocabulary filter.** The code restricts counted
  query tokens to `orig_vocab` — the original 27-node corpus's vocabulary — with the denominator still
  the full query length. Numbers reproduce; the **+0.077 is not an estimate for content-word
  weighting**, and #48's named next direction was inferred from it. A dated correction is appended to
  #48 (original sentence kept) and DECISIONS **#53** records the rule: an arm is described by its
  implementation, not the idea it resembles.
- #49's conclusion is unchanged: content-word weighting was tested properly there and failed.

### Not changed

- `src/amg/` untouched; N2 stays 0.538 and the 0.70 target stays unmet on both corpora.

## [0.33.3] — 2026-10-31

The question #50 and #51 were leaning toward — "the 0.70 target may only measure an artifact of N2's
construction" — was tested with real prose and answered **no**.

### Measured

- A pre-registered corpus of 10,000 distractors built from **real documentation prose** (seeded
  8-word windows of paragraphs in this repository, no vocabulary sampling) passes the calibration
  check (competing share 0.476 against N2's 0.918) and lands at recall@5 **0.692** — **below the
  published 0.70 target**, with N2 at 0.538 and the real corpus at 0.865.
- A post-hoc length sweep shows it is not a short-note artifact: 20-word windows give 0.692, whole
  paragraphs (median 37 words) give **0.673** with r@1 rising to 0.654.
- Ordering holds throughout: N2 < real text < control. n1 / n3 stay 0.865.

### Added

- DECISIONS **#52**: publish two noise corpora — N2 as the adversarial worst case, real text as the
  realistic measure; the 0.70 target stays attached to N2 and stays **unmet**; N2 is recorded as
  overstating the gap by roughly 0.13–0.15 recall@5, and #50's suspicion that the target measures only
  an artifact is recorded as **wrong**.
- `experiments/retrieval_noise_realtext/` — pre-registration, runner, post-hoc length sweep,
  machine-readable outputs.
- `tests/test_realtext_noise.py` pins the page to the result files, including the calibration-first
  ordering and the recorded wrong prediction.

### Not changed

- `src/amg/` untouched. The remaining realistic shortfall (0.008–0.027) is a separate problem and is
  not claimed as fixed.

## [0.33.2] — 2026-10-31

An attempt to answer #50's open question failed its own pre-registered check. The failure is the
finding.

### Measured

- On the candidates that actually compete (top-100, gold excluded), a quarter of the query is
  reached by **14.4%** of the real corpus's distractors against **91.8%** of N2's — the 6.4× contrast
  #50 assumed is real and now measured.
- A pre-registered `N2-cal` corpus tried to reproduce the real 14.4% by drawing each node's
  query-token count from the per-pair coverage distribution. It produced **60.6%**, missed the ±0.10
  tolerance, and by the rule fixed beforehand was **rejected** — its `recall@5` of **0.654** is a
  rejected-run diagnostic, not a result.
- Probing an explicit token-count mix shows the base rate cannot repair it: 0.55/0.43/0.02 → 0.537,
  0.70/0.28/0.02 → 0.516, 0.80/0.19/0.01 → **0.497**. With ~2,000 nodes carrying two query tokens,
  those nodes own the top-100 however rare they are: the pool is selected by the quantity being
  calibrated.
- n1 and n3 are unchanged (0.865 each), so their generators are untouched.

### Added

- DECISIONS **#51**: synthetic noise corpora must be calibrated and checked **on the competing
  subset**, with that check run before any recall number is reported; the next design samples
  distractor text from real notes instead of token soup.
- `experiments/retrieval_noise_representativeness/` — pre-registration (with the two preliminary
  scans disclosed), the rejected run, and the probe ladder, all with machine-readable output.
- `tests/test_noise_calibration.py` pins the page to `result.json` and `probes.json`, and requires
  the rejected recall to stay labelled as such.

### Not changed

- N2 stays the hardest corpus, the shipped number stays **0.538**, and the 0.70 target stays
  **unmet**. `src/amg/` untouched.

## [0.33.1] — 2026-10-31

The direction #49 left open was measured and closed, with its failed predictions on record.

### Measured

- A pre-registered semantic arm (`experiments/retrieval_semantic/`) with a local embedding daemon
  (`nomic-embed-text`, digest pinned) tested three shapes — RRF rerank of the shipped top-100, pure
  full-corpus semantic retrieval, and their union. On the **real** corpus the same model lifts
  recall@5 **0.865 → 0.981**, and on the two non-adversarial noise corpora to 0.962 / 0.942.
- On **N2** all three land on **0.577** (+0.039 against the shipped 0.538), missing the
  pre-registered +0.05 by 0.011; the 0.70 target is not approached. Every regression gate passes, so
  the miss is specific to the target corpus, not a broken backend.
- The informative miss is the candidate ceiling: semantics was predicted to find the four gold nodes
  lexical search never reaches, and the semantic ceiling on N2 is **0.846 — identical to the
  shipped one**. N2's distractors are built from the queries' own vocabulary in `label` and `note`,
  so they are near-duplicates under any bag-of-vectors similarity; cosine is no more adversarial to
  that construction than `df` was.
- The aggregate hides churn: the three arms tie at 0.577 while fixing `q05`/`q26`/`q16`/`q24` and
  breaking `q04` (2 → 23 or beyond 100) and `q14` (1 → 5 or 27). Six queries cross the top-5
  boundary in opposite directions; the per-query table ships with the experiment.

### Added

- DECISIONS **#50**: the similarity family (lexical #49, semantic here) is closed for N2; the open
  question moves from *which model* to *whether N2 is the noise a memory graph faces*, which is a
  separate, measurable decision (`issue.mem-arch-n2-representativeness`).
- `tests/test_semantic_arm.py` pins the page to `result.json` and the post-hoc diagnostic.

### Not changed

- `src/amg/` untouched; embeddings stay optional-only (274 MB model + daemon are outside the
  zero-dependency default path). N2 stays **0.538** and the 0.70 target stays **unmet**.

## [0.33.0] — 2026-10-31

The direction #48 named is tested and closed in one round, with its failed predictions on record.

### Measured

- `experiments/retrieval_lexical_ceiling/` pre-registered **three** signals that are not document
  frequency — content-word coverage (stopwords stripped, #48's named direction), title coverage and
  compactness — reranking the shipped top 100 on the same four corpora. **All nine arm/alpha
  combinations lose N2 recall**: the best (compactness, alpha 0.5) is **0.481** against the shipped
  **0.538**, and each arm also harms at least one non-target corpus (title coverage costs control
  0.057 and n3 0.115; compactness costs n1 0.057). Nothing ships; `src/amg/retrieval.py` untouched.
- The pre-registered diagnostic is what explains it. Pooled separability (AUC, gold vs non-gold
  inside the top 100) looked usable — 0.665 for content coverage, 0.610 for compactness — but
  splitting by whether the shipped ranking already solved the query shows the mean was carried by
  the solved half: **0.779 / 0.515 / 0.767 on the 15 solved queries against 0.421 / 0.258 / 0.275
  on the 11 failing ones.** On the queries that need repair, every lexical signal is at or below
  chance.
- **Two limits stay open, as recorded**: the 0.70 target is not shown impossible — the candidate
  ceiling (gold inside the top 100) is **0.846**, above 0.70, so a perfect reranker could pass; and
  **4 of 26 queries have gold beyond the top 100**, so a semantic arm must be judged on candidate
  generation as well as reordering.

### Added

- DECISIONS **#49** closes the lexical rerank family for query-vocabulary noise and records the
  general hazard behind the pooled number: an AUC averaged over a candidate set the scorer already
  orders correctly measures the solved queries and hides the failures.
- `tests/test_lexical_ceiling.py` pins the page to `result.json` and `diagnostic_by_solved.json`, and
  asserts the three failed predictions stay visible in the pre-registration.

### Not changed

- N2 stays **0.538** against the published 0.70 target; the target remains **unmet** and no
  published claim says otherwise.

## [0.32.7] — 2026-10-31

A mechanism claim published two days* ago was falsified by an attack, and is corrected.

\* same calendar day, two releases apart.

### Corrected

- **#47's explanation was wrong.** It said coverage reranking loses recall on query-vocabulary noise
  because the feature becomes *anti-correlated* with the answer. An attack tested that with four
  arms and falsified it: rewriting the distractors with 78 **foreign** words of comparable length
  (same corpus, same seed, asserted disjoint from the query vocabulary) produces the *same* loss,
  **−0.057**, so the damage does not depend on the distractors being query words; gold coverage
  averages **0.610 against the distractors' 0.376**, i.e. positively associated.
- **#48 records the corrected mechanism**: the loss follows the *shape* of the two distributions.
  Gold is bimodal (7 of 22 queries fully covered, 8 of 22 at or below 0.33), distractors cluster
  (64% between 0.25 and 0.5), and the failing case is a true answer matching one content word while
  a distractor matches three function words (`q04`: gold pushed from rank 1 to 79; `q26`: 77
  places). `#47` is now `amended` by `#48`, and the experiment README states the corrected
  explanation with the wrong one preserved in the decision log.
- The next direction is therefore **content-word weighting or stop-word stripping**, not
  "separating source tokens from injected ones". The attacker's content-word-only arm returned N2
  to **0.615 (+0.077)**, which would be the first arm to pass the +0.05 criterion — but it is a
  selective construction, so it is a candidate for a fresh pre-registration and is **not** recorded
  as a result.

### Not changed

- `src/amg/retrieval.py` untouched; N2 remains 0.538 in the shipped scorer and its 0.70 target
  remains unmet.

## [0.32.6] — 2026-10-31

Next attempt at query-vocabulary noise, rejected — with the mechanism recorded.

### Measured

- The shipped scorer leaves N2 (query-vocabulary noise) at recall@5 **0.538** against a 0.70
  target, and #28 explained why IDF cannot move it. `experiments/retrieval_beyond_df/`
  pre-registered a signal outside the frequency family: rerank the top 100 by **query coverage**
  (`score × coverage**alpha`), with `alpha = 0` as a control arm that must reproduce the shipped
  metrics.
- Result: it makes every corpus worse — N2 **0.538 → 0.481**, control 0.865 → 0.846, unrelated
  noise 0.865 → 0.808, frequent noise 0.865 → 0.808. All four pre-registered criteria failed;
  no ship, no retuning (DECISIONS #47).
- **The mechanism is the finding**: N2 injects distractors from the query's *own vocabulary*, so
  coverage counts the injected tokens and a distractor absorbing three of them outranks the gold
  node — the feature points away from the answer, which is why the harm is larger on N2 (−0.057)
  than where it merely dilutes (−0.019 on control). Next candidate must separate source tokens
  from injected ones (term proximity inside one field), not aggregate over query tokens.
- All four predictions were wrong and are recorded as wrong.

### Fixed (in the harness, before drawing any conclusion)

- The first version broke ties by id, which moved n1 recall@5 from 0.865 to 0.827 with no signal
  involved. It now breaks ties by the scorer's own order and asserts that `alpha = 0` reproduces
  the shipped metrics on all four corpora (`tests/test_retrieval_beyond_df.py`). A reranker that
  cannot reproduce its baseline is measuring its own tie-break.

### Not changed

- `src/amg/retrieval.py` is untouched. N2 remains 0.538 and its target remains unmet; the
  frozen 27-query baseline remains 0.865.

## [0.32.5] — 2026-10-31

Test tightening: the provenance check now pins *which* id is which.

### Changed

- v0.32.4's `test_every_row_names_a_run_and_a_job` only required two long numbers to appear
  anywhere in a row, so a job id pasted into the run column would still have passed — the
  verifier reported it as a loose criterion. It now parses the row shape: **column 1 is the run
  id**, **the parenthesised number beside the platform is that platform's job id**, a run id and
  its job id can never be the same number, job ids are unique, and **each run appears exactly
  once per platform (three rows)**.
- Mutation-tested: swapping a run id with its job id now fails with
  `run 124431735505 should cover three platforms, has ['ubuntu']`; the unmutated table passes.

### Not changed

- No document text and no product code. The table it guards was verified cell by cell against
  the CI logs (nine cells, three runs, 0.5% tolerance) and that verification is unchanged.

## [0.32.4] — 2026-10-31

v0.32.3 published a performance table that could not be traced to any run, and the index's
status column and its page records could drift apart. Both were found by verification, not by
tests.

### Fixed

- **The nine-cell tail table in `docs/CONCURRENCY.md` named no run.** Its numbers came from one
  CI run (41165056624) that the document never named; the independent verifier read the job logs
  and found not one cell reproducible on the following runs. Rewritten as a **three-run table
  where every row names its run id and job id**, and the conclusion is cut back to what repeats:
  the worst lock wait is stable (ubuntu 10.46–11.01 s, macOS 6.16–7.26 s, Windows 5.58–12.36 s)
  and macOS is consistently the mildest; **p95 is not a statistic to quote here** — at 80 samples
  it sits between the 76th and 77th value, and the same command measured 164 ms and 2,897 ms on
  ubuntu in two runs.
- **`#45`'s headline claim is withdrawn.** "Windows is materially worse" rested on a single p95
  (1,672 ms); over three runs Windows measured 1,672 / 2,568 / 6,588 ms, so the platform ordering
  the decision asserted does not survive repetition. `#45` is `amended` by **#46**, which states
  the rule the rest of the project already follows (#44): a number without the run that produced
  it is not evidence.
- **The index and the page records could drift separately.** The `amended (#N)` test read
  `manifest.json`, so editing only the index row — the copy a human reads — passed everything.
  New `test_index_status_matches_manifest` asserts status and slug agreement for all 46 rows
  (DECISIONS #22, one source of truth, applied to the decision log).

### Tests

- 355 tests: +1 index/manifest cross-check, +2 in `tests/test_concurrency_doc.py` (every table
  row carries a run id and a job id; the section still states what was not measured).
- 62 documents.

## [0.32.3] — 2026-10-31

The lock tail is measured on three operating systems, and the index's hand-written column was
checked by an attacker (and lost one row).

### Measured

- **Windows tail latency, previously "not measured" since v0.15.0.** New
  `experiments/concurrency/tail_latency.py` runs the same measurement in CI on ubuntu, macOS and
  Windows (5,000 nodes, 8 x 10 burst). Worst lock wait: 10.46 s / 6.16 s / 10.49 s; all three
  kept 80/80 writes with `check` clean. The finding: **Windows p95 is 1.67 s against 0.09–0.15 s
  on the other two**, while its worst wait matches Linux's — the distribution, not the maximum,
  is what a Windows caller feels. Fairness stays unbuilt per #15's trigger; the 10k Windows
  number is still unmeasured and the document still says so. DECISIONS #45.
- First CI run of the new script failed on all three platforms with `LockTimeout after 5.0s`:
  the documented default (a 5 s timeout covers `writers x writes x per-write cost`, #26) working
  as designed on slow runners. The burst now runs with `AMG_LOCK_TIMEOUT=180`, which decides
  when a run stops, not what a waiter waited; the script reports the value it used.

### Fixed (found by an attack on the new index)

- `#17` was marked `amended (#24)`, but #24 never mentions a sidecar, history or compression —
  the two decisions are parallel, not corrective. It is `active` again (DECISIONS #42-adjacent
  reasoning: a status that is not backed by the cited page is a claim without evidence).
- `#3` (via #31) and `#25` (via #28) are genuinely amended, but the amending pages did not say
  so. Their headers now do, and a test requires that any `amended (#N)` claim is declared by
  page N.
- The index preamble said the cost-keyword match "hits 8 of the 34"; a stem match finds **11**
  (9, 11, 14, 16, 17, 24, 25, 26, 27, 28, 29). The old count used a pattern with a word boundary
  after `cost`, so `costs` never matched. It now states 11 and a test asserts the number, because
  a hand-maintained fact drifted the first time anyone checked it.

### Tests

- `tests/test_decisions_log.py` (10 tests): adds the two column checks above, and catches a
  bare `DECISIONS #15` that this release's own new prose introduced.
- 352 tests; 62 documents.

## [0.32.2] — 2026-10-31

Documentation patch: a reference now lands on the decision, not on the index.

### Changed

- The shipped documentation referenced decisions as bare text (`DECISIONS #20`,
  `` `DECISIONS.md` #24 ``), so reading one meant opening the index and clicking again. All
  eleven such references in `README.md` and `docs/*.md` are now links straight to
  `docs/decisions/NN-slug.md`, including the one the independent verifier flagged
  (`docs/API.md` ended with "[DECISIONS.md](DECISIONS.md) for why", pointing at the index).
- `docs/DECISIONS.md`'s reference paragraph now says what is true after the change: shipped
  docs link directly; `CHANGELOG.md` and `RELEASE.md` keep bare numbers because they are
  append-only logs.

### Tests

- `tests/test_decisions_log.py` gains two assertions: every `[DECISIONS #N](…)` link resolves
  to a file whose name starts with that number, and no bare `DECISIONS #N` remains in the
  shipped documents. The index's promise ("references resolve by number") is now machine-checked
  instead of stated.
- 350 tests.

## [0.32.1] — 2026-10-31

v0.32.0's sdist was incomplete; the artifact check could not see it.

### Fixed

- `docs/decisions/manifest.json` — the file `tests/test_decisions_log.py` reads — was not in
  the sdist: `MANIFEST.in` shipped `recursive-include docs *.md`, and the manifest is JSON. The
  sdist's own test suite failed with five `FileNotFoundError`s on the only job that unpacks it
  (ubuntu-latest / 3.12); the four other `package` jobs printed a green artifact check, because
  `tools/check_dist.py` derived its "what the sdist must contain" list with one `listdir`
  **filtered to `.md`** — the same shape as the documentation gates before v0.30.0/v0.31.0.
- Both are fixed at the source of the assumption: `MANIFEST.in` ships every `docs/` file type
  the working tree has (`*.md *.json`), and `expected_docs()` now walks `docs/` recursively with
  no suffix filter, so a file added for the tests must be shipped or the build fails. The
  checker reports "sdist has all 61 documents" derived from the tree (16 documents + 44
  decision pages + the manifest), not from a hand list.
- DECISIONS **#44** records it: this is the fourth appearance of one failure shape (#18, #19,
  #40/#41), which is why it is written down instead of assumed fixed.

### Not shipped

- v0.32.0's tag still exists and its sdist is still incomplete; v0.32.1 supersedes it and is the
  version to install. No GitHub release was published for v0.32.0.

## [0.32.0] — 2026-10-31

The decision log is an index plus one page per decision — and the seven versions of
decisions it had no room to record are backfilled.

### Changed

- `docs/DECISIONS.md` (24,569/24,576 B, 7 B of headroom) is now the **index**: number,
  decision, status, signature, link. Each decision lives on its own page under
  `docs/decisions/`, cut mechanically from the old file with a reconstruction check
  (`preamble + entries == the original bytes`, sha256 compared) and a per-entry
  byte-for-byte assertion. Bodies are copied, never retyped.
- The 24 KiB budget now applies **per page** instead of to the whole log, so capacity grows
  with the number of decisions. That is stated in the index rather than left to be
  discovered: the old single file could hold 34 decisions and then stopped, which is
  exactly what happened.
- The index carries a hand-maintained `status` column (`active`, `amended (#N)`,
  `superseded`, `archived` — nothing is superseded or archived yet). Three entries are
  `amended`: #3 by #31, #17 by #24, #25 by #28. The column is human judgement per entry;
  nothing in the prose is structured enough to derive it, and the index says so.

### Fixed (a gap this split uncovered)

- **Decisions v0.25.0–v0.31.0 were made, shipped and never logged.** With 7 B left, entry
  #34 was the last one writable, so nine rounds of decisions — coverage denominators, an
  explicit evidence base, thin anchoring, the bridge's full-anchoring rule, a forged digest
  as failure, recursive gates, directory-scoped gates — had no record. Entries **#35–#43**
  are backfilled in this release, each with the evidence it was made on and its cost.
- Entries **#1–#8** have no per-entry `*Signed …*` line (26 of 34 do). Their only signature
  is the log's preamble, so their pages say exactly that and the index marks them
  `preamble`. No signature was invented, and DECISIONS #42 records the fact.

### Documentation

- The four places in `docs/README.md` that described `DECISIONS.md` as the single signed
  record now describe the index-and-pages structure; all 27 `DECISIONS #N` references in the
  repository are bare numbers and resolve through the index.
- `docs/decisions/manifest.json` records each page's body hash and size, so "the cut lost
  nothing" is checkable after the fact, not only during the cut.

### Tests

- `tests/test_decisions_log.py` (6 tests): one page per number with no gaps or repeats, body
  hashes matching the manifest, every index link resolving on disk, status values in the
  allowed set, #1–#8 claiming the preamble and no invented signature, and every page inside
  both documentation gates.
- 348 tests; the gates now cover 59 documents (16 + 43 pages).

## [0.31.0] — 2026-10-31

The documentation gates select documents by **directory**, not by `.md` suffix.

### Fixed

- Both gates filtered the walk with `name.endswith(".md")`, so renaming a page was a
  complete bypass. Measured on v0.30.0 by the independent verifier (exit codes read off
  the process, not off a pipe): `docs/n/A.markdown`, `docs/n/B.txt` and `docs/n/NOEXT`
  at 30,000 B each all passed the size gate, and a 30 KB `.markdown` page documenting
  `amg teleport` — a command that does not exist — passed the symbol gate with exit 0.
  The suffix was the only difference from a page the gates would have failed.
- Scope now lives in one place, `tools/doc_scope.py`: `README.md` plus **every regular
  file under `docs/`**, recursively, whatever it is named at any depth. Both gates
  import it, because the v0.30.0 bug was one walk copied into two files; the fix is one
  implementation used twice, and `test_both_gates_see_the_same_files` fails if either
  gate stops using it.
- `tools/check_doc_symbols.py` resolves its targets against the repository root instead
  of the process working directory. Run from anywhere but the root, every default
  target used to print `skip (missing)` and the gate exited 0: a green run that checked
  nothing. The size gate already resolved against the root, so this also makes the two
  agree.
- `scan()` decodes with `errors="replace"`, so a file under `docs/` that is not UTF-8
  text cannot crash the gate; replacement characters cannot spell a documented symbol,
  so decoding damage cannot hide a phantom command either.

### Not shipped in 0.31.0 (do not assume)

- `docs/DECISIONS.md` is **still not split**: it holds all 34 entries at 24569/24576 B.
  This round only makes the gates safe for the pages the split will create.
- The gate-scope rule is recorded as DECISIONS **#35** and will be written when the
  split lands (there are 7 B of headroom in the file today, so it cannot be written
  now). Until then its statement lives here and in `docs/OPERATIONS.md` §1.

## [0.30.0] — 2026-10-31

A document in a subdirectory no longer escapes the documentation gates.

### Fixed

- Both documentation gates derived their file list with one `os.listdir(docs)` level, so
  `docs/decisions/…` would have been invisible to the size budget **and** to the
  code-symbol gate — the exact "a hand-written list is a claim about the past" failure
  DECISIONS #18 exists to prevent, reappearing one level down. Both now walk the
  directory tree recursively (`README.md` plus every `docs/**/*.md`), with tests that
  place documents in nested directories and assert they are covered.
- This is the prerequisite for splitting `docs/DECISIONS.md` (24569/24576 B of a 24576 B
  budget): the split is only safe if new pages cannot silently drop out of the gates.

### Not shipped in 0.30.0 (do not assume)

- `DECISIONS.md` itself is **not** split yet: it still holds every entry and has 7 B of
  headroom. The split is a separate round, with the attackers reviewing the plan first.
- No change to what the gates enforce, only to which files they see.

## [0.29.1] — 2026-10-31

Documentation-only patch: `--strict` is an acceptance mode, not an inspection mode.

### Changed

- `docs/OPERATIONS.md` states what the v0.29.0 re-attack made obvious: on a store with
  any debt, `--strict` always fails — even a 100%-anchored graph, because ten stale work
  items are ten failures under it (measured: `healthy` without the flag, `NEEDS
  ATTENTION` with it). Daily inspection uses the plain run, which prints the debt;
  `--strict` is for signing off when the debt must be zero.
- It also records that a run is a snapshot: the numbers describe the graph at that
  moment, so compare against the same file digest, not against yesterday's line.

### Not shipped in 0.29.1 (do not assume)

- No code change: verdicts, exit codes, counts identical to 0.29.0.

## [0.29.0] — 2026-10-31

A forged legacy digest fails the run, and one ruler counts evidence everywhere.

### Fixed

- A legacy string `path:x#sha256:h` whose file does **not** hash to `h` only lowered the
  verified count: the bridge exited 3 ("nothing verified"), the same code as "no digest
  was ever declared", and only `--strict` promoted it. A declared proof that fails is a
  violation, exactly as it is for an evidence object, so it is now a **problem** (exit 1,
  `NEEDS ATTENTION`). A malformed `#sha256` is reported as a warning
  (`issue.mem-arch-legacy-mismatch-not-problem`, Glm仔 N4).
- `done` and `conclusions` disagreed about the same node: `conclusions` counted a
  verified legacy string as evidence while `done` counted only `evidence[]`, so a node
  read as "verified" on one line and "carries no evidence" on the next (Glm仔 N6). Both
  use the same ruler now; on the project's own graph `done without evidence` drops from
  292 to 108 because legacy declarations are real declarations.
- The bridge's text also prints the `done nodes:` line, so the two rulers can be compared
  in one look.

### Added

- 3 tests: a forged legacy digest exits 1 without `--strict`; done-vs-conclusions agree on
  a legacy-verified graph; the conclusions field stays `unanchored_conclusions`.

### Not shipped in 0.29.0 (do not assume)

- A malformed `#sha256` is a warning, not a failure: it declares nothing verifiable, so
  it is debt, not a violation.
- No change to `healthcheck`'s debt policy or to any verdict/exit code it already had.

## [0.28.1] — 2026-10-31

Patch: the bridge's report says what it means.

### Fixed

- The `partially_verified` verdict printed `PARTIALLY VERIFIED (no conclusion
  anchored)` even when one conclusion *was* anchored (1/20). The parenthetical is gone;
  the `conclusions:` line carries the numbers.
- The bridge's `conclusions:` line omitted unobservable evidence, so a graph with 165
  declared-but-unobservable conclusions printed only `41 unanchored`. It now prints
  `0/206 verified (0%), 41 unanchored, 165 unobservable`, matching the warnings.
- With no `path:` evidence at all the base line read `files found 0/0`; it now reads
  `no path: evidence rows`.

### Not shipped in 0.28.1 (do not assume)

- No behaviour change: verdicts, exit codes and counts are identical to 0.28.0.

## [0.28.0] — 2026-10-31

The snapshot bridge stops having a private green light, and legacy observations count
where they belong.

### Fixed

- The bridge's verdict ignored anchoring: one verified legacy string turned a graph
  whose own report said `0/20 verified, 20 unanchored` into `healthy`, exit 0, while
  `healthcheck --strict` on the same graph exited 1 (Glm仔 N3, Hermes §2). The bridge now
  calls the shared `verdict_of` with `require_full_anchoring=True`: `healthy` means every
  `done` conclusion is anchored; anything less is `partially_verified` (exit 3). Two
  postures, one implementation, both documented — a store owner keeps the debt policy,
  a verification of someone else's graph does not get to call 5% anchoring healthy.
- The bridge counted only `evidence` for anchoring, so adopted graphs always read
  `0/N` even when their legacy `path:x#sha256:h` strings verified. Those observations now
  count: `1/20 verified (5%), 19 unobservable` instead of `0/20 verified, 20 unanchored`.
- `--strict` is now available on the bridge too (it was missing entirely): it fails on
  debt (unanchored/unobservable conclusions) and never turns a failed check into a pass.

### Added

- 3 tests: the N3 graph is `partially_verified` exit 3 with honest numbers; a graph with
  zero anchored conclusions is `partially_verified`; `--strict` fails on debt while
  breakage still outranks it.
- `docs/OPERATIONS.md` verdict table gains `partially_verified`, and the bridge section
  states why it is stricter than `healthcheck`.

### Not shipped in 0.28.0 (do not assume)

- `healthcheck` keeps its debt policy: 5% anchoring on the owner's own store is a
  warning, not a failure, unless `--strict`.
- No automatic base detection, no write-back of verified legacy digests, no `kg.py`
  schema change.

## [0.27.0] — 2026-10-31

Thin anchoring cannot pass silently, and "did not look" stops printing a percentage.

### Fixed

- A graph with one verified anchor and nineteen `cmd:`-only conclusions printed
  `healthy`, exit 0, **zero warnings**: the verdict keyed on "at least one verified" and
  never looked at the ratio. `conclusions` now carries `unobservable` (evidence declared
  but not observable), the text line reads `1/20 verified (5%), 0 unanchored,
  19 unobservable`, and it raises a warning — `--strict` fails it
  (`issue.mem-arch-cmd-ratio-healthy-threshold`, Glm仔's re-attack of v0.25.0, case X1).
- With `--no-evidence` the `conclusions` line still printed `0/1 verified (0%)`, i.e.
  "did not look" shown as "looked and found zero". It now prints
  `conclusions: not checked (evidence hashing skipped)` and the JSON reports
  `verified: null`, `anchor_coverage: null` (`issue.mem-arch-notchecked-conclusions-zero`).

### Added

- 2 tests: the 1-real-19-`cmd:` graph must warn and fail `--strict`; `--no-evidence`
  must not print a percentage.
- `docs/OPERATIONS.md` documents the bridge's boundary: it accepts **legacy-schema
  sources only** — an `amg/v1` graph is refused with `E_ALREADY_AMG`, because it is
  already under the gate and belongs to `healthcheck`, not to the bridge.

### Not shipped in 0.27.0 (do not assume)

- No hard floor on anchoring: a low ratio is a **warning**, not a failure, because a
  curated graph legitimately cites `cmd:`/`url:` evidence. `--strict` is the switch.
- The bridge still cannot write verified legacy digests back into the store.

## [0.26.0] — 2026-10-31

The bridge states its evidence base, verifies declared digests in legacy strings, and
`--no-evidence` can no longer slip past a `--strict` run.

### Fixed

- `not_checked` (from `--no-evidence`) is now also a **warning**, so `--strict` fails on
  a run that did not look. Before, a scheduler keying only on the exit code — which
  `OPERATIONS.md` invites — saw `0` and called it a pass (Hermes v0.25.0 re-test).
- JSON field `conclusions.unanchored` renamed `unanchored_conclusions`: it counts
  conclusion-typed nodes only, and sitting next to the `done nodes` line it read as
  "there are no unanchored nodes".

### Added

- `tools/verify_snapshot.py --evidence-root DIR` — the directory the source's `path:`
  locators are relative to, stated not guessed. Each run prints
  `evidence base: … (files found N/M, P%)`. Measured why it must be explicit: this
  project's own graph answers 0/240 under `graphs/`, 113/240 under the workspace root,
  89/240 under the repository root — the same file, three answers.
- Legacy `path:<rel>#sha256:<hex>` strings are verified read-only and counted
  (`N with #sha256, V verified, M mismatched, X malformed`); a malformed digest is
  reported, never repaired; every other string stays a citation. A graph whose only
  observations come from such strings can now reach `healthy` instead of `unverified` —
  without writing into the store and without fabricating a hash.
- 5 tests: `--evidence-root` changes the answer and is reported; legacy digest verified;
  mismatch and malformed reported; `not_checked` warns and `--strict` fails; the renamed
  field.

### Not shipped in 0.26.0 (do not assume)

- No automatic evidence-base detection, on purpose: a wrong guess reads as a false
  alarm, which is how two rounds of this attack started.
- No write-back of verified legacy strings into the store: the bridge remains read-only.
- Migrating `kg.py` writers to `amg/v1` is still not shipped (decision B+: gate boundary
  is documented, not enforced).

## [0.25.0] — 2026-10-31

The health report stops lying about coverage, and a graph another tool wrote can now be
verified without pretending it is gated.

### Fixed

- **Coverage had the wrong denominator.** v0.24.0 printed `1 declared, 1 verified (100%)`
  for a graph where ten other `done` nodes carried no evidence: the denominator was
  *evidence rows that exist*, not *knowledge that should be anchored*. The report now
  prints three numbers — `evidence rows` (declared/verified), `conclusions` (done
  conclusion-typed nodes, how many carry verified evidence, how many are unanchored) and
  `done nodes` (all finished nodes, how many carry no evidence) — and adds a warning for
  each unanchored group (`issue.mem-arch-coverage-denominator`,
  `REATTACK-HEALTHCHECK-V0240.md`).
- **`--no-evidence` read as `healthy`.** A report that did not look must not read like
  one that looked and found nothing: its verdict is now `not_checked` (exit 0), and JSON
  carries `verdict: "not_checked"`, `healthy: false` (`issue.mem-arch-no-evidence-verdict-green`).
- `--allow-unverified` now records `unverified_accepted: true` in JSON, so a log can
  tell "verified" from "exempted"; and `strict_scope` states what `--strict` covers
  (audit conflicts + unanchored done nodes) and that it is **not** evidence verification.

### Added

- `tools/verify_snapshot.py <graph.json> [...] [--json] [--allow-unverified] [--keep]` —
  the verification bridge for graphs another tool wrote (our `kg.py` graphs are
  `group-kg/v1` and are **not** under `amg`'s write gate). It adopts a copy into a temp
  directory, resolves `path:` evidence against the original graph's directory (a temp
  copy has no evidence files, so hashing against it would report every real file as
  `missing`), and runs the same report the health check runs. Exit `0` pass / `1`
  problem / `2` usage / `3` nothing verified. It never writes the source and it inherits
  the coverage and anchoring numbers, so a fix to the report applies here too.
- 11 tests: 4 for the new health-report semantics (denominator, unanchored-debt vs
  `--strict`, `not_checked`, `unverified_accepted`, `strict_scope`) and 7 for the bridge
  (pass, evidence-root resolution, tampered evidence, bare strings = exit 3,
  `--allow-unverified` relaxes only the code, usage, JSON shape).
- Measured on the project's own graphs through the bridge: `记忆架构开源` (316 nodes)
  `conclusions: 0/194 verified (0%), 194 unanchored`; `C仔指挥部` (1298 nodes)
  `0/610 verified (0%), 610 unanchored`; both `verdict: UNVERIFIED`, exit 3 — the honest
  number for evidence that is citations rather than hashed files.

### Not shipped in 0.25.0 (do not assume)

- The bridge observes; it does **not** block. `kg.py` writes are still not gated, and no
  document may claim they are.
- Exit 0 from the bridge is not a claim that content is correct, and not a claim that
  every evidence item is verifiable.
- No `path:<rel>#sha256:<hex>` evidence syntax yet: it is the agreed direction, not a
  shipped feature.

## [0.24.1] — 2026-10-31

Documentation round: "successful adoption" now has six observable criteria, and the
wrong criterion is named as wrong.

### Changed

- `docs/ADOPTION.md` gains **What counts as a successful adoption**: six checks that
  must all be observed on the adopted copy — `check` errors `0`; the printed counts add
  up (`nodes N→N`, `edges M→M−merged`, `changes[]` accounted for); no fabricated
  evidence (`legacy_evidence` keeps the locator strings, `evidence` claims nothing
  adoption could not observe); the pin is self-consistent and recomputable
  (`pin.match: true` on a second run); the pin is forward-only and uncovered nodes are
  reported as unanchored (measured 887/1063 after adoption vs 647/782 before); the
  source file is byte-identical afterwards.
- It also states what the criterion is **not**: `audit --pin`'s exit code. A real graph
  carries genuine stale work, so `audit --pin` exits `1` with `pin.match: true`, and
  requiring exit `0` would push an operator to close live items or widen the staleness
  threshold to manufacture a clean report. Remaining conflicts are the graph owner's
  tasks, not migration failures.
- A corollary records which gate governs which graph: an adopted graph is under `amg`'s
  write gate and evidence verifier; a graph still written by another tool (ours:
  `kg.py`, `group-kg/v1`) is not, and no document may imply otherwise.

### Added

- 3 tests in `tests/test_adopt.py` pin the definition: the section exists, it has six
  numbered criteria, each criterion is named, and the "do not use the exit code"
  sentence with `pin.match: true` is present.

### Not shipped in 0.24.1 (do not assume)

- No code change: `adopt`, `audit`, `--pin` and the pin format are byte-for-byte what
  0.24.0 shipped.
- No gate that the project's own group graph is under `amg`'s write gate — that is an
  open A/B decision, not a shipped capability.

## [0.24.0] — 2026-10-31

The health report stops calling "nothing was verified" healthy.

### Fixed

- `tools/healthcheck.py` classified `unverifiable` evidence (`cmd:`/`url:`/`sha256:`
  locators, which carry no local bytes) as neither a problem nor debt. A store with
  **zero** verifiable evidence — an `adopt`ed graph, whose evidence layer is emptied by
  design, or a `cmd:`-only graph — printed `verdict: healthy` and exited `0`, and
  `--strict` could not catch it: a dashboard said "fine" about "unknown". The report now
  carries a third verdict `unverified` with its own exit code `3`, counts coverage
  (`declared` / `verified` / `coverage` / `coverage_state` = `full|partial|none|not_checked`),
  and the text line reads `N declared, M verified (P%)`.
- Evidence that cannot be confirmed is a problem, not silence: `missing` (the declared
  file is gone), `not_a_file` (a directory) and `unreadable` (permission/IO) now fail the
  report the same way `mismatch` and `outside_root` already did.
- `--allow-unverified` accepts an unprovable store (exit `0`) for stores whose evidence
  is intentionally remote — the verdict still says `unverified`, and `--json` keeps
  `healthy: false`; only the exit code is relaxed, so `healthy` never describes an
  unproven store. `--no-evidence` prints `evidence: skipped (--no-evidence) - NOT
  VERIFIED` and never claims verification; it does not force `unverified` because the
  operator explicitly chose not to look.

### Added

- 8 tests for the new semantics (16 in `tests/test_healthcheck.py`): nothing verifiable
  is `unverified`, an empty graph is `unverified`, `--allow-unverified` relaxes only the
  exit code, partial coverage is reported and still `healthy`, `missing` and `not_a_file`
  evidence fail, `--no-evidence` says it did not look, and breakage outranks
  `unverified` (exit `1`, not `3`).
- Measured on the project's own graph through `amg adopt` (302 nodes / 278 edges, 334
  legacy evidence strings moved out): before the fix `verdict: healthy`, exit `0`; after,
  `evidence: 0 declared, 0 verified (0%)`, `verdict: UNVERIFIED`, exit `3`. An `amg init`
  store with nothing written: exit `3` instead of `0`.

### Not shipped in 0.24.0 (do not assume)

- `healthy` still does not mean the *content* is correct: it means the invariants this
  report checks hold, and the report prints what it could not observe.
- No automatic repair and no change to `check`/`audit` semantics; `--strict` still means
  "stale work fails", not "everything is verified".
- No gate that the project's own group graph (`group-kg/v1`, written by `kg.py`) is
  covered by `amg`'s write gate — that is an open decision, not a shipped capability.

## [0.23.1] — 2026-10-31

Patch: the health report survives a legacy Windows console code page.

### Fixed

- `tools/healthcheck.py` printed `✗` and `—`. On `windows-latest` (cp1252 stdout) the
  first such line raised `UnicodeEncodeError`, so the report stopped after the archive
  line, dropped every problem and the verdict, and still exited 1 — a failing store
  looked like a silently truncated report. Output is now ASCII and the stream is
  reconfigured where the interpreter allows it; a regression test runs the tool with
  `PYTHONIOENCODING=cp1252` and asserts the problem line and verdict are present.

### Not shipped in 0.23.1 (do not assume)

- No change to what the report checks or how it classifies problems versus debt.

## [0.23.0] — 2026-10-31

Operational readiness: a one-page health check and the runbook that says what to run on
a live store, how often, and what a bad answer means.

### Added

- `tools/healthcheck.py <dir> [--json] [--strict] [--no-evidence]` — read-only report
  combining `check`, `audit`, real evidence hashing (the gate's `verify_evidence`) and
  `archive_verify`. Exit `0` healthy / `1` problem / `2` usage. Debt is separated from
  breakage: stale work items and legacy unanchored nodes are printed, and only
  `--strict` fails on them. Mismatched evidence and evidence paths outside the graph
  root are always problems.
- `docs/OPERATIONS.md` — runbook: schedule (daily/nightly/weekly), backups and restore
  with a fingerprint, large-graph sizing from measured write costs, upgrade steps, and a
  table mapping each error to its first action. Excess and limits are stated: single
  user, no auth, no external cold-start evidence, Windows latency unmeasured, 10k
  numbers synthetic.
- 7 tests for the health-check report (healthy, tampered evidence, outside-root path,
  structural error, debt-vs-problem split, JSON shape, usage error).

### Not shipped in 0.23.0 (do not assume)

- No new CLI subcommand: the report is a repository tool, so the API surface stays as
  documented.
- No promise that "healthy" means correct content: it means the invariants it checks
  hold, and it prints which evidence it could not observe.

## [0.22.0] — 2026-10-31

One canonical `changes[]` shape after migration, a `check` that stops advising a no-op,
and documentation moved where it belongs to restore budget headroom.

### Fixed

- `amg migrate` folds the legacy `detail` key into `note` (moved, never dropped) and
  reports `folded_detail` plus any `non_canonical_shapes` left, so the three legacy
  `changes[]` shapes collapse to the canonical one (`changes-key-shapes`).
- `amg check` no longer prints "run `amg migrate`" for a `rev` that `migrate` left null on
  purpose; it reports the rev as unknown by design. The previous advice was a loop that
  could not help.
- **Documentation budget**: the adoption guarantee list moved from `docs/API.md` to
  `docs/ADOPTION.md`, and decisions #9/#10 detail to their owning docs. Both caps were
  1–9 bytes from failing `check_doc_sizes`; API now has 553 B and DECISIONS 33 B of room.

### Tests

293 tests (+3): `detail` folded not dropped and shapes canonical, post-migrate hint
wording, migrate idempotent.

## [0.21.0] — 2026-10-31

Three boundary defects in shipped behaviour, found by the post-release review and fixed
together: two in v0.20.0's verifier, one in `--include-archive` since v0.15.0.

### Security

- **`verify-evidence` no longer reads outside the graph root.** `path:` evidence with an
  absolute path, `..` or a symlink escape resolved to any file on the host, so a public,
  unauthenticated store could be used to hash files it does not own
  (`issue.mem-arch-evidence-locator-out-of-tree`). Paths must resolve inside the root;
  escapes are reported `outside_root`, never opened, and exit 1.

### Fixed

- **`--strict` and JSON no longer fake green**
  (`issue.mem-arch-verify-strict-unverifiable`, `...verify-evidence-boundaries`): `--strict`
  ignored `unverifiable`, and `--json` printed `ok: true` on a strict exit 1. The report
  now separates `ok` (nothing violated) from `all_verified` (every item matched);
  `--strict` requires the latter, and `not_a_file`, `unreadable` and an empty check are
  explicit outcomes instead of passes or crashes.
- **`--include-archive` is no longer starved by `k`** (`issue.mem-arch-archive-k-starve`):
  archived records are older by construction, so a time-ordered merge cut to `k` returned
  **zero** archived hits whenever `k` live records matched — the flag silently did
  nothing. From `k >= 5` the archive keeps `max(1, k // 5)` slots, one per archive file
  first, then recency; below 5 the previous order stands, so live-only searches are
  unchanged.

### Tests

290 tests (+10: 7 verifier boundary cases, 3 archive reservation cases), nine
CI jobs, `tools/verify.py` green.

### Not shipped in 0.21.0 (do not assume)

- No anchored "verified" state is persisted on nodes; `anchor_state: "present"` still
  means *declared*.
- No per-read verification, no search cache, no `verified`/`claimed` split.
- The archive reservation is a floor, not a guarantee that every archived file fits when
  more files than slots have matches.

## [0.20.0] — 2026-10-31

Closes the evidence-authenticity finding from the retrieval attack brief (E1 / `R3`):
declared evidence hashes become observable, and the limitation that stays is written down.

### Added

- `amg verify-evidence <dir> [--id ID] [--strict] [--json]` — hashes `path:` evidence
  locators (resolved against the graph directory unless absolute) and compares them with
  the declared `content_sha256`. Exit 1 on `E_EVIDENCE_MISMATCH`; `--strict` also fails
  on missing paths; `cmd:` / `url:` / `sha256:` locators are reported `unverifiable` and
  never count as passes. This is the first caller of `gate.sha256_of_file`, which existed
  unused since v0.1.
- `tests/test_evidence_verify.py` — 11 cases, including the original attack as an
  executable record: a fabricated hash is accepted by the write gate, still shows
  `anchor_state: "present"`, and is caught by `verify-evidence`.

### Disclosed, not fixed

- `content_sha256` is still **caller-declared**: the write gate validates shape, not
  bytes, so a fabricated hash still wins the retrieval sort key. `docs/API.md` and
  `docs/THREAT-MODEL.md` now state that `present` means *declared*.
- Not shipped: per-read verification (I/O on the hot path; referenced files move), an
  `anchor_state` `verified`/`claimed` split (a label without persisted verification), and
  any claim that `--strict` means verified.
- `cmd:` / `url:` evidence remains unverifiable offline — reported as such, never a pass.

## [0.19.1] — 2026-10-31

Patch: the documentation size gate measures content, not the checkout's line endings.

### Fixed

- `tools/check_doc_sizes.py` folds CRLF to LF before counting. v0.19.0's
  `windows-latest` job failed on `docs/DECISIONS.md` (24,450 B of content, ~300 B larger
  in a CRLF checkout) while the same tree passed on Linux and macOS — a red CI caused by
  `core.autocrlf`, not by length. Regression test: a CRLF document whose LF content is
  inside budget now passes on every platform (`tests/test_doc_sizes.py`).
- No document was trimmed to work around it, and the budgets are unchanged.

### Not shipped in 0.19.1 (do not assume)

- No product change; no document content change; identical behaviour to v0.19.0.

## [0.19.0] — 2026-10-31

Defect round for the two retrieval issues the attack brief registered (`R1`, `R2`):
**scores become bounded and labelled, and the change is measured to move no rank.**

### Changed

- `src/amg/retrieval.py`: IDF divided by `ln(1 + N)`, so each matched (field, term)
  contributes at most its field weight and a score is in `(0, 7.0 × terms]` instead of
  growing with graph size. Ordering uses the value before the common divisor, so the
  normalization cannot reorder anything.
- Every hit gains **`score_kind`**: `idf` (L1/L3/L4), `recency` (L2 — the 1.0 constant,
  ordered by `at`; not a match score), `expansion` (`--expand` neighbours). Additive;
  docs and the MCP tool description now forbid comparing scores across kinds.

### Verified

- `experiments/score_scale/`: **every ranked id list and every metric identical** to
  v0.18.0 on all four corpora (control, N1, N2, N3).
- Bounded: worst frozen score 8.716 (bound 7.0 × terms). Residual 27→10k drift on one
  gold is 1.375× against v0.18.0's 3.799× — *bounded, not invariant*, and published as
  such; `issue.mem-arch-idf-live-df-drift` stays open with that wording.
- 268 tests (+7), nine CI jobs, `tools/verify.py` nine steps.

### Not shipped in 0.19.0 (do not assume)

- No ranking change; recall is identical by construction and by measurement.
- No search cache; no evidence-content verification (`R3` is the next round).
- Scores are not probabilities and are not comparable between different queries.

## [0.18.0] — 2026-10-31

The IDF round that 0.17.0 named: **rarity-aware scoring ships, and it is measured to fix
the realistic noise model but not the adversarial one.**

### Changed

- `src/amg/retrieval.py`: a matched term contributes `WEIGHTS[field] × idf(term)`,
  `idf = ln(1 + N/(1+df))` over the visible nodes, instead of a constant field weight.
  Field weights, matchers, hard filters, anchor rule and ordering are unchanged; a query
  token repeated twice counts once. `_match_fields()` keeps the matches from the existing
  scan, so this is bookkeeping, not a second pass over the graph.

### Measured (26 frozen queries, both scorers in one process)

| corpus | baseline r@1 / r@5 | shipped r@1 / r@5 |
|---|---|---|
| control 27 | 0.654 / 0.808 | **0.731 / 0.865** |
| N1 unrelated 10k | 0.654 / 0.808 | **0.731 / 0.865** |
| N2 query-vocabulary 10k | 0.481 / 0.538 | 0.481 / 0.538 (r@10 0.538 → 0.577) |
| N3 frequent-vocabulary 10k | 0.654 / 0.712 | **0.731 / 0.865** |

- **The N2 `recall@5 ≥ 0.70` target was missed (0.538)** — predicted before the run:
  N2 samples distractor tokens uniformly from the query vocabulary, so `df` is the same
  for every query term and IDF has nothing to weight. Deep ranks improve (q05 42→9,
  q16 99→46); the top-5 does not move.
- Cost: p50 +3.0 ms at 10k (+4%); +6 tests pin the mechanism (261 total).

### Added

- `experiments/retrieval_idf/` — pre-registration, frozen v0.17.0 baseline, harness, a
  fourth corpus (N3 frequent-vocabulary noise), `result.json`, and a README that records
  the two wrong predictions.

### Not shipped in 0.18.0 (do not assume)

- **N2 is not fixed**: the same 11 queries miss at 5, and 3 of them are word-level gaps
  (q06, q08, q10) that no ranking weight can close.
- No real-graph 10k retrieval; every noise model here is synthetic.
- No phrase/proximity matching and no id/type priors — those are the named next
  candidates, each needing its own pre-registration.

## [0.17.0] — 2026-10-31

Second half of the 10k gap: **retrieval recall at 10,000 nodes is measured**, and the
result inverts the obvious guess.

### Added

- `experiments/retrieval_10k/` — pre-registration (with predictions, an amendment for a
  second noise model, and an outcome table), harness, `result.json`, README.
- Two noise models on the same frozen 26 queries: **N1** unrelated distractors
  (bench generator), **N2** distractors built from the queries' own tokens (seeded).

### Measured

| run | nodes | recall@1 | recall@5 | recall@10 | MRR@10 | p50 |
|---|---|---|---|---|---|---|
| control | 27 | 0.654 | 0.808 | 0.865 | 0.763 | — |
| N1 unrelated | 10,000 | 0.654 | 0.808 | 0.865 | 0.763 | 74.3 ms |
| N2 query-vocabulary | 10,000 | **0.481** | **0.538** | 0.538 | **0.515** | 92.5 ms |

1. **Size alone costs nothing** (370× more unrelated nodes, identical metrics).
2. **Vocabulary overlap costs 0.27 recall@5, and the cause is scoring**: 7 of the 11
   misses are beyond rank 100. `WEIGHTS` in `src/amg/retrieval.py` has no IDF, so a note
   repeating common query words outscores the node that answers.

### Fixed

- The README no longer says "retrieval recall at 10k is unmeasured"; it states both
  halves of the 10k question, with the weakness named. `docs/API.md`'s retrieval rules
  now warn that scoring has no IDF and point at the numbers.

### Not shipped in 0.17.0 (do not assume)

- **No IDF, no re-ranking change, no code touched at all** — criterion C4 of the
  pre-registration forbade tuning in the same round. IDF weighting is the next candidate
  with its own pre-registration.
- No real-graph 10k retrieval numbers: this is synthetic noise on a frozen corpus.
- No semantic recall; no claim that a bigger graph is "fine" — only that *unrelated*
  size is, and that *related* noise is not.

## [0.16.0] — 2026-10-31

Removed a documented gap: **concurrency at 10,000 nodes is measured**, and the naive
configuration fails there — which is the useful part.

### Added

- `experiments/concurrency/PREREGISTRATION-10k.md` — criteria and predictions written
  before the run, plus an outcome section that records two **wrong** predictions.
- `experiments/concurrency/build_10k.py` and two artifacts: `result-10k.json` (the run
  that completed) and `result-10k-run1-timeout.txt` (the run that died). Both are in
  the repository, including the failing one.
- `docs/CONCURRENCY.md` §"At 10,000 nodes": 86.2 ms per write at 10k (the extrapolation
  held), 200 writes = ~17.2 s of work, burst window 17.95 s, worst lock wait 13.52 s,
  p50 85.8 ms / p95 112.3 ms contended against 86.2 ms serial — **throughput is
  write-cost bound, not lock-bound** (11.1/s vs 11.3/s).

### Fixed

- **A false confidence, not a bug**: the default 5 s lock timeout *does not* survive
  8 × 25 writes at 10k (run 1 died with `LockTimeout`). The default is kept on purpose
  (DECISIONS #26); what changed is that the limit is now measured and the sizing rule
  is written down (`timeout ≥ writers × writes × per-write cost`, here ≥ 18 s).
- `docs/BENCHMARKS.md` now carries the measured 10k write cost next to the 5k
  extrapolation, instead of leaving the 10k number as a projection.

### Not shipped in 0.16.0 (do not assume)

- No 10k **retrieval** recall numbers, no 10k Windows run, no multi-host or network
  filesystem numbers.
- No fairer lock: the 13.5 s wait with 821 polls is a starvation *symptom*; attributing
  it to unfairness needs the counter experiment that DECISIONS #15 keeps unbuilt.

## [0.15.0] — 2026-10-31

New: the archive is reachable over MCP. Fixed: two "not implemented" claims that were
false — in the direction that made the project look less verified than it is.

### Added

- **`memory_search` accepts `include_archive`** (MCP, `layer: "L2"` only). Archived
  hits come back marked `archived: true` with their `archive_file`, exactly as from the
  CLI; any other layer returns `E_ARCHIVE_LAYER` as `isError: true`. The tool list stays
  at eight — this is a search option, not a ninth tool, and a test pins both facts.
  `docs/ARCHIVE.md` no longer says the archive is invisible over MCP.

### Fixed

- **Two stale "not implemented" entries were wrong, and are corrected in the honest
  direction.** The README listed "Windows file-locking verification" and "any benchmark
  above 1,289 nodes" as not done. Both were false: `test_lock.py` and
  `test_concurrency.py` run and pass on `windows-latest` in CI (cross-process
  exclusivity, serialised writes, concurrent writers losing nothing), and
  `docs/BENCHMARKS.md` has synthetic 1k/5k/10k measurements. What is still true is
  narrower and is what the list now says: the **Windows latency tail is unmeasured**
  (burst timing is macOS-only), and **concurrency and recall are not measured at 10k**.
  `src/amg/store.py`'s module docstring said "Windows locking is NOT verified" for the
  same reason and now states the real coverage.

### Not shipped in 0.15.0 (do not assume)

- No MCP tool archives anything: `amg archive` remains a CLI/library operation, because
  a write that moves history should be an explicit, leased decision, not an agent tool.
- No Windows burst/latency measurement; no 10k-node concurrency or retrieval numbers.

## [0.14.0] — 2026-10-31

Changed behaviour: **lexical matching is word-aware**, so queries that cannot
distinguish anything stop returning answers — and the recall that costs is published,
not absorbed.

### Changed

- **ASCII matches a whole word or its regular inflection**, never a raw substring:
  `rank` finds `ranking`, `searched` finds `search`. A one-character ASCII token is
  dropped. Before this, `a` matched `archive` and nearly everything else: on the real
  1,289-node graph, `a`/`e`/`i`/`x` each returned the full `k=10`.
- **A query containing `.` `:` `/` `_` is an identifier lookup.** `task.a` asks for
  that id instead of splitting into every `task` plus the letter `a`, which used to
  return ten unrelated `task.*` nodes for an id that does not exist. Word separators
  (`-`, `.`, `_`, `/`) still allow prefix lookups (`task.read` → `task.read-audit`).
- **CJK is unchanged** (substring; a character is a word), and single CJK characters
  remain searchable.

### Measured (`experiments/retrieval_precision/`, pre-registered)

| measurement | before | after |
|---|---|---|
| one-letter queries, real graph, `k=10` | 10 hits each | **0** |
| nonexistent identifier (`task.a`, `issue.zzz`, `missing.node`) | 10 hits each | **0** |
| identifier lookups naming a live node, top-1 | — | **20/20** |
| frozen-eval keyword recall@5 | 0.938 | **0.969** |
| frozen-eval MRR@10 | 0.744 | **0.763** |
| frozen-eval overall recall@5 | 0.865 | **0.808** |
| frozen-eval overall recall@1 | 0.654 | 0.654 |

The overall drop is analysed per query, not explained away: two of 26 eval queries were
reached only through substrings **inside other words** (`i` in `high-risk`, `one` in
`gone`), one was a genuine inflection case and is recovered, one improved. Both the
pre-registration criteria that failed and the override are recorded (DECISIONS #25,
`experiments/retrieval_precision/PREREGISTRATION.md` §Outcome).

### Not shipped in 0.14.0 (do not assume)

- **No stemmer and no synonyms.** A 14-entry English suffix table, no dependency;
  other languages get word-boundary matching only.
- **No stopword handling**: a query made only of common words (`the if do`) still
  matches loosely, because those words are words.
- **No semantic matching.** Paraphrase recall is unchanged at 0.55 in this eval; the
  embedding candidate remains rejected for the default path.

## [0.13.0] — 2026-10-31

New capability: **the history that was moved out stays searchable**, on request and
labelled as history.

### Added

- **`amg search <dir> "q" --layer L2 --include-archive`** and
  `Memory.search(..., include_archive=True)`. The cold archive
  (`archive/changes-*.json`) is read with no index and no second store — it is plain
  JSON, and `archive.load_records()` returns the records with the file they came from.
  Every archived hit carries `archived: true` and `archive_file`, so an old record can
  never be mistaken for a current one; `k` applies across live and archived records
  together, newest first; archived hits keep their original `at` and `rev`.
- **The flag is refused on node layers** (`E_ARCHIVE_LAYER`, exit 2) instead of being
  silently ignored: an L3 result set cannot contain ledger records, and a success that
  changed nothing would be a lie about what was searched.
- Default L2 behaviour is unchanged, and there is a test that asserts it: moving
  history must not change what a plain search answers.

### Why this closes a documented gap

0.11.0 shipped the archive with "`L2` search sees live history only" written into
`docs/ARCHIVE.md` and the CHANGELOG. That was honest but inconvenient: the first
question after "I moved my old history out" is "can I still find it?". Now the answer
is yes, with the provenance attached. The docs, the example
(`examples/archive.sh`, in CI) and the not-shipped list are updated together.

### Not shipped in 0.13.0 (do not assume)

- **No index** over the archive: a search reads the archive files. Fine at old-history
  sizes; unmeasured on a graph with years of history, and said so.
- No cross-file rank normalisation beyond `(at, rev)`, no archive pruning, no
  `--include-archive` for node layers.

## [0.12.0] — 2026-10-31

New contract: **documentation size budgets**, and the README restructured to fit one.

### Added

- **`tools/check_doc_sizes.py`** — the budget gate: `README.md` and `docs/README.md`
  ≤ 12 KiB, every other `docs/*.md` ≤ 24 KiB. It fails with the exact overshoot, and
  runs in CI next to the symbol gate and in `tools/verify.py`. The rule is adapted from
  the same public workbench as the handover card (`docs/PRIOR-ART.md`), where a file
  over the line is defined as one a reader skips. `CHANGELOG.md` and `RELEASE.md` are
  out of scope **in words** — append-only logs, where a cap would mean deleting
  history — not silently exempted.
- **`docs/ADOPTION.md`** — the adoption contract (nothing fabricated, nothing
  overwritten) and the measured before/after table on a real 1063-node graph, moved
  out of the README. The README keeps a three-line summary and links.
- **`docs/PRIOR-ART.md`** gains an "At a glance" list of the six systems this project is
  measured against, and the two `grep` commands that re-check the two commitments it
  does **not** ship (hard authorization, risk-scaled evidence).

### Changed

- **README.md 20,315 → 10,552 bytes**, and nothing was deleted: duplicated material
  moved back to the document that owns it (adoption → `ADOPTION.md`, prior art →
  `PRIOR-ART.md`, MCP tools → `API.md`, handoff/archive detail → `HANDOFF.md` /
  `ARCHIVE.md`). A README that restated the docs was a second source of truth that
  could drift; the budget makes the drift expensive.
- `docs/README.md` states the budgets as a contract and says what to do when a
  document reaches one: move detail to the owning document, do not delete it.

### Not shipped in 0.12.0 (do not assume)

- No automatic document splitting, no word-count or reading-time metric, no per-file
  budget overrides: one entry budget, one reference budget, no escapes.

## [0.11.1] — 2026-10-31

### Fixed

- **A false alarm on legacy ledgers.** `amg archive`'s rev-contiguity check treated a
  record without an integer `rev` as a failure, so a graph written before
  `amg migrate` existed refused to archive and rolled back (`E_ARCHIVE_VERIFY`) —
  safe, but wrong: contiguity is *unknowable* when numbers are missing, not violated.
  The check now reports `rev_contiguous: null` with `rev_unnumbered: N` and lets the
  move through; `amg archive --verify` reports `rev_continuity: null` the same way.
  Duplicate rev numbers are still hard evidence and still fail. `amg migrate` numbers
  the records and makes the check enforceable. Found by probing the edge case before
  calling 0.11.0 done; `tests/test_archive.py` covers it.

## [0.11.0] — 2026-10-31

New capability: **cold archiving of the change ledger** — move old history out of the
live file and prove on every run that nothing was lost.

### Added

- **`amg archive <dir>`** (`--older-than-days N`, `--apply`, `--verify`, `--json`) and
  `Memory.archive(days=..., apply=...)` / `Memory.archive_verify()`. A cold **prefix**
  of `changes[]` moves into `archive/changes-r<rev>-<stamp>.json`, leaving one pointer
  record; a record without a parseable `at` stops the prefix, and an old record behind
  a newer one is counted as `deferred_behind_newer` rather than taken out of order.
  Dry-run by default; nothing is written without `--apply`.
- **A proof, not a checksum of our own output.** Every `--apply` snapshots the file to
  `archive/snapshots/`, then verifies five independent things: the archive file
  re-read from disk reproduces the moved records, the live ledger is exactly
  remainder + one pointer, `state_sha256` is unchanged (nodes and edges untouched),
  `check()` still passes, and rev numbers are contiguous across the boundary. A failed
  proof writes the snapshot back and exits 1 with `E_ARCHIVE_VERIFY`.
- **`amg archive --verify`** re-runs the proof later from disk only: it recomputes each
  payload digest and requires every rev number to appear exactly once across archives
  plus live history, so a dropped record shows up as a hole rather than as silence.
- **`docs/ARCHIVE.md`** — the rule and its credited source, what qualifies, the five
  checks, measured before/after numbers on two real graphs, recovery commands, and the
  list of what it deliberately does not do. `examples/archive.sh` runs the whole cycle
  (dry-run, apply, verify, tamper rejection) in CI.
- **`benchmarks/archive_cost.py`** — re-runnable pricing: adopts a legacy graph into a
  temporary directory and reports file size, ledger share, eligible records, bytes
  after, single-write latency before/after and verification cost, aggregates only.
- `AMG_ARCHIVE_DAYS` (policy, not constant: `0 < x <= 3650`, invalid values fall back
  to 30 — never to 0), same ruling as `AMG_STALE_DAYS`.

### Measured (macOS, 1-minute load ≈ 3.4, re-runnable with the benchmark)

| graph | file | ledger share | archive @1 d | file after | single write |
|---|---|---|---|---|---|
| 15.7 MB real team graph | 1289 nodes / 2604 changes | 79.0% | 2275 records | 5.9 MB (−62.2%) | 226.1 → 72.7 ms |
| this project's own graph | 198 nodes / 454 changes | 48.8% | 265 records | 337 KB (−32.3%) | 7.7 → 5.5 ms |

At the default 30-day cutoff **0 records qualify** on both graphs (they are 8 days
old). That is stated rather than worked around.

### Not shipped in 0.11.0 (do not assume)

- **No node archiving.** Edges cross the boundary; moving cold *nodes* is a different
  design that this release does not pretend to have.
- **`L2` search sees live history only.** Archived records are not searched; `grep` or
  `--verify` is how you inspect them.
- **No compression and no dependencies** — the archive is plain JSON.
- **Not exposed over MCP**, and **not automatic**: no background job prunes history.
- **Snapshots are kept, one full graph copy per run**, and never cleaned up
  automatically.

## [0.10.0] — 2026-10-31

New capability: **handoff cards** — a bounded, superseding record of where the work
stands, so a new session reads one thing instead of searching.

### Added

- **`handoff` node type and `amg handoff <dir>`** (`--by`, `--owner`, `--note -`,
  `--json`). Exactly one card is active: writing a new one supersedes the previous
  through the normal supersede path, so the history stays in the ledger. The card is
  capped at **4,096 bytes**; an empty or oversized card is refused
  (`E_BAD_HANDOFF`, `E_HANDOFF_TOO_LARGE`, exit 2) and writes nothing.
  `Memory.write_handoff()` / `Memory.handoff()` are the same operations in Python.
- **`audit` enforces the invariants a hand-edited graph can break**:
  `handoff_over_budget` and `multiple_active_handoffs` are conflicts, so the limit is
  not merely advisory. Handoff nodes are registrations, not work items, so they are
  exempt from staleness (same class as DECISIONS #20).
- **`docs/HANDOFF.md`** — the four questions a handover answers, the three rules it
  follows, and what this project adds over the pattern's source; `examples/handoff.sh`
  runs the whole cycle in CI.
- Pattern credit: the handover discipline (`§〇 交接`: overwrite, ≤4 KB, pointers not
  transcripts) is taken from
  [mashanglinyu/luanyujia-workbench](https://github.com/mashanglinyu/luanyujia-workbench)
  (MIT) and recorded in `docs/PRIOR-ART.md`; this is an adaptation, not an invention.
  The node-typed form, supersede-on-write and the double enforcement are ours.

### Fixed

- **A misleading audit hint**: `valid_time_known=false` counted registrations
  (group/env/member) and said "migrated validity time is unknown" even on a fresh
  graph written today. Registrations are not TTL candidates and are no longer counted;
  the wording now states the actual reason (no fact time recorded).

### Not shipped in 0.10.0 (do not assume)

Unchanged: no authentication / authorization / multi-tenancy (out of scope by
decision), no vector retrieval in the default path (measured, rejected), no tamper
*proof*, no TTL scheduler, no encryption at rest, no lock fairness, and history
compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.9.0] — 2026-10-31

Additive: `audit` now returns structured findings alongside its strings, so a reader
(or an agent) can tell who is responsible without parsing a sentence.

### Added

- **`audit()["findings"]`** — one entry per conflict or hint, derived from the same
  record as the human string, in the same order: `severity` (`conflict`/`hint`),
  `kind` (`done_without_evidence`, `stale_work_item`, `expired_but_active`,
  `dangling_edge`, `pin_changed`, and five hint kinds), the `detail` string, plus the
  node, its type/status/owner, and `age_days`/`limit_days` where relevant; dangling
  edges carry the `edge` object. `conflicts` and `hints` are unchanged, so existing
  consumers see no difference. Measured on the first live graph: 3 conflict findings
  and 602 hint findings, with the string lists matching the findings exactly.
- The human lists are now **generated from** the findings instead of being built
  separately, so text and `--json` cannot diverge by construction (DECISIONS #22); a
  test asserts the two views stay identical.

### Not shipped in 0.9.0 (do not assume)

Unchanged: no authentication / authorization / multi-tenancy (out of scope by
decision), no vector retrieval in the default path (measured, rejected), no tamper
*proof*, no TTL scheduler, no encryption at rest, no lock fairness, and history
compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.8.0] — 2026-10-31

**A new capability, not a fix**: the staleness threshold is now policy, because the
right value is a property of the team's cadence rather than of the tool.

### Added

- **`AMG_STALE_DAYS`** (integer days, `0 < x <= 365`, invalid values fall back to 3)
  and **`amg audit --stale-days N`** for one run. Measured on the first live graph,
  the same three work items produce **3 conflicts at 3 days, 1 at 7, 0 at 14** — a
  weekly-sync team sees false alarms at the default, a monthly team none. Default
  stays 3 (the original rule), so existing users see no change. Fallback rather than
  disable: a typo must not silently turn the check off, same rule as
  `AMG_LOCK_TIMEOUT` (DECISIONS #21).
- **`Memory.audit(stale_days=...)`** for callers that do not want a process-wide
  environment variable.

### Not shipped in 0.8.0 (do not assume)

Unchanged: no authentication / authorization / multi-tenancy (out of scope by
decision), no vector retrieval in the default path (measured, rejected), no tamper
*proof*, no TTL scheduler, no encryption at rest, no lock fairness, and history
compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.7] — 2026-10-30

**A behaviour change, and the first library change since 0.6.0**: `audit` no longer
reports long-lived registration nodes as stale.

### Fixed

- **Staleness now applies to work, not to registrations.** The rule "an `in_progress`
  or `blocked` node untouched for 3 days is stale" assumed every node is a
  short-lived work item. On the first live graph it flagged a `group` node
  `in_progress` for 7 days — correct by the letter, noise in practice: a group
  registration is long-lived, and its `updatedAt` does not move when its children
  change. `group`, `env` and `member` are exempt (`LONG_LIVED_TYPES`); **an unknown
  type is still checked**, so a new kind of work cannot become invisible by omission.
  Measured on that graph at rev 2,610: `audit --pin` **4 → 3 conflicts**, pin still
  matches. The three remaining are real work items (`task`/`issue`/`decision`
  untouched 3–7 days) and stay reported. DECISIONS #20; four tests in
  `tests/test_audit.py`, including one that a `question` node is still checked.

### Not shipped in 0.7.7 (do not assume)

Unchanged from 0.7.6 — no authentication / authorization / multi-tenancy (out of
scope by decision), no vector retrieval in the default path (measured, rejected), no
tamper *proof*, no TTL scheduler, no encryption at rest, no lock fairness, and
history compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.6] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. Two numbers
that were quoted without context now have it: the stale-conflict count, and the
conditions the timings were taken under.

### Added

- **`docs/REAL-WORLD.md` breaks down the pinned conflicts.** On the first live graph
  all four are staleness, but not one kind: three are work items (`task`/`issue`/
  `decision`) untouched 3–7 days with owners and notes — real debt, left visible on
  purpose — and **one is a `group` node**, which is long-lived by nature and flagged
  by a rule that assumes a short-lived work item. That false-positive class is
  recorded as a finding; changing which types the rule covers changes `audit` output
  for existing users, so it needs a decision and a test, not a quiet patch.
- **`benchmarks/real_graph.py` prints the load average** and flags runs above 2.0 as
  inflated, because the effect is large: the same `adopt` of the same 15.4 MB file is
  **140–142 ms idle and 1,055 ms at load 24.8**, and CLI startup goes **48 ms → 552
  ms**. `docs/REAL-WORLD.md` records this as a measurement-condition table, so its
  numbers are not compared across conditions.

### Not shipped in 0.7.6 (do not assume)

Unchanged from 0.7.5 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, no change to the audit rules, and history
compression remains a design (`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.5] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. It turns the
real-world measurement into a re-runnable script and adds a second live graph, so the
published numbers are no longer one graph's anecdote.

### Added

- **`benchmarks/real_graph.py`** — runs the whole `REAL-WORLD.md` measurement against
  any `group-kg/v1` graph: adopt, check, audit (with and without the pin), expire,
  fingerprint, doctor, search, digest, related and one write, then prints the table.
  In-process timings, matching the published run; CLI startup (~48–51 ms) is measured
  and reported separately so the two are never mixed. It verifies the source
  `sha256` before and after and prints **aggregates only** — no ids, labels, notes or
  query strings.
- **A second live graph in `docs/REAL-WORLD.md`**: this project's own bookkeeping
  graph, 187 nodes / 152 edges / 429 changes / 0.44 MB, chosen because its shape is
  different — 172 of 187 `done` nodes carry legacy evidence, no node has a validity
  window, and it is 35× smaller. Adopt 6 ms, check 0 errors in 0.4 ms, audit 172
  conflicts → **0** with the pin, one write **4 ms**.

### Changed

- **`docs/REAL-WORLD.md` records that its numbers move, with evidence.** Re-running
  the script on the first live graph a few hours later (rev 2,570 → 2,604) gives
  1,282 nodes, adopt 142 ms, one write 153 ms, and **pinned conflicts 3 → 4** — time
  passed, so staleness grew. A tool reporting a constant there would be reporting
  the wrong thing.
- The page now states which numbers are **shape-dependent** (IR-4 conflict count
  tracks legacy evidence format, write cost tracks file size at ~10 ms/MB) and which
  are flat (single-digit-millisecond reads on both graphs).

### Not shipped in 0.7.5 (do not assume)

Unchanged from 0.7.4 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.4] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. It makes the
project's own checks one command, and turns the resource-leak cleanup of 0.7.3 into
something CI enforces.

### Added

- **`tools/verify.py`** — runs every self-check in one command and prints one table:
  unit tests (with `ResourceWarning` promoted to an error), the documentation↔code
  gate, both end-to-end examples, the MCP client, and the artifact check when
  `dist/` exists. A skipped step is printed as skipped and never counted as a pass.
  `docs/README.md` now leads with it instead of listing six commands with no order.

### Changed

- **CI promotes `ResourceWarning` to an error** in both the platform test matrix and
  the suite run from inside the sdist. The leaks were cleaned in 0.7.3 (90 warnings
  per Windows run → 0); this keeps them from returning, and it is the same flag
  `verify.py` uses, so CI and a local run check the same thing.

### Not shipped in 0.7.4 (do not assume)

Unchanged from 0.7.3 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.3] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. It adds the
scenario a team actually has — several long-lived MCP processes plus a CLI command
writing one file — and records what the test can and cannot prove.

### Added

- **`tests/test_mcp_concurrency.py`**: two stdio MCP servers (5 writes each) and one
  thread running 5 `amg add` subprocesses, with a fourth thread running `amg check`
  while the writes land. Asserts on every commit and on all four test platforms:
  15 nodes for 15 writes with no duplicates, **exactly one `changes[]` record per
  write**, `check --strict` clean, and no writer *or reader* reporting an error (a
  refusal fails the test instead of being swallowed).
- **`docs/CONCURRENCY.md`** gains "Three writers over two protocols", including one
  limit measured rather than assumed: reverting `Memory.open` to the pre-v0.6.0
  unlocked read leaves the test **green on macOS**, because POSIX lets you replace an
  open file. The test is a regression guard for Windows specifically, and the doc
  says so instead of implying it is platform-neutral.

### Not shipped in 0.7.3 (do not assume)

Unchanged from 0.7.2 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.2] — 2026-10-30

**No library change**; `src/amg/` differs only in the version string. This release
adds the first end-to-end proof that another process can actually use the MCP
server, and closes the last install-matrix gap.

### Added

- **`examples/mcp_client.py`** — a working MCP client in the standard library only.
  It starts `amg mcp` twice and asserts, end to end: the handshake returns the
  server's identity; `tools/list` advertises exactly the eight documented tools; an
  evidence-free `done` write is **refused over JSON-RPC** (`E_EVIDENCE_MISSING`,
  `isError: true`) — the write gate is not a CLI feature that MCP can walk around;
  a valid write succeeds and `memory_search` finds it; a `--read-only` server
  advertises five tools and refuses the same write with `E_READ_ONLY`; and
  `amg check --strict` passes on the graph the server wrote. CI runs it on every
  push, on all four test platforms. The protocol tests check frames; this checks
  whether the thing is usable.
- **`examples/*.py` are shipped in the sdist** (previously only `*.sh`), and
  `tools/check_dist.py` now requires `examples/mcp_client.py` to be present.

### Changed

- **The `package` job now covers macOS, and the minimum Python on two platforms**:
  ubuntu / macos / windows on 3.12, plus ubuntu and windows on 3.10. Nine CI jobs.
  macOS previously had only an editable install, so the wheel had never been
  installed there either.

### Not shipped in 0.7.2 (do not assume)

Unchanged from 0.7.1 — the library gained nothing: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in the
default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.1] — 2026-10-30

A packaging release: **no library behaviour changes**. It exists because the sdist
published with 0.7.0 could not run the tests it contained.

### Fixed

- **The sdist was incomplete.** With no `MANIFEST.in`, `python -m build` shipped
  `src/` and `tests/` but not `docs/`, `tools/`, `experiments/`, `examples/` or
  `benchmarks/`. Running the shipped suite from the unpacked archive gave **17
  errors and 4 failures — every one of them file-not-found** (`docs/API.md`,
  `tools/check_doc_symbols.py`, the experiment scripts). The wheel was unaffected,
  which is why install-only verification missed it. `MANIFEST.in` now carries
  everything the tests read; the sdist goes 70 KB → 376 KB, and its own **190-test
  suite passes from inside the unpacked archive**.
- **License metadata modernised.** `license = {text = "MIT"}` is deprecated
  (PEP 639; setuptools warns that builds stop working after 2027-02-18). Now
  `license = "MIT"` with `license-files = ["LICENSE"]`, build requires
  `setuptools>=77`, and the wheel metadata carries `License-Expression: MIT`.

### Added

- **`tools/check_dist.py`** — checks the built artifacts, deriving its expectations
  from the working tree: every module in `src/amg/` must be in the wheel, the
  entry point must be `amg = amg.cli:main`, the metadata must carry an SPDX licence,
  and the sdist must contain every `docs/*.md`, the tools, examples and experiment
  scripts its own tests read. Against 0.7.0's first sdist it reports **20
  problems**; against the fixed build it is clean.
- **CI job `package`** — builds sdist and wheel, runs `check_dist.py`, installs the
  wheel into a fresh venv, then unpacks the sdist and runs its shipped test suite.

### Not shipped in 0.7.1 (do not assume)

Identical to 0.7.0 — nothing was added to the library: no authentication /
authorization / multi-tenancy (out of scope by decision), no vector retrieval in
the default path (measured, rejected), no tamper *proof*, no TTL scheduler, no
encryption at rest, no lock fairness, and history compression remains a design
(`docs/DESIGN-HISTORY.md`), not a capability.

## [0.7.0] — 2026-10-30

A small release: one operational knob, one design note, and a reading index. The
on-disk format is unchanged (`amg/v1`); nothing here needs a migration.

### Added

- **`docs/DESIGN-HISTORY.md`**: the write-cost fix, designed before it is built —
  and the obvious version of it rejected with measurements. A history sidecar would
  cut writes 147 ms → ~27 ms, but `changes[]` records are descriptions rather than
  replayable operations, so a split store gains a crash window that can only be
  detected, never repaired. The sanctioned direction is zlib-sealed history segments
  inside the single atomic file: −54% size (15.6 MB → 7.2 MB), write ~60 ms,
  11 ms to decompress on read, atomicity intact, at the cost of text-greppable
  history and an `amg/v2` format bump. Not built; DECISIONS #17 records why and the
  trigger.

- **`AMG_LOCK_TIMEOUT`** (seconds, clamped to `(0, 3600]`, nonsense falls back to
  5 s) — because the default is now known to be load-dependent rather than safe:
  on the real 15.6 MB graph a write costs ~147 ms, so 5 s covers about 34 queued
  writes and 8 writers × 5 writes times out (measured; the run aborted). The
  timeout error names the variable. Fairness would not fix it — the queue still has
  to drain — which is now stated with arithmetic in `docs/CONCURRENCY.md`.

- **`docs/README.md`**: a reading index, because a folder of measurements is worse
  than useless if the document describing a *proposal* is read as a feature.
  Every document is tagged measured / contract / proposal / decision / operational,
  and there is a reading order per intent (deciding, using, changing storage,
  auditing claims). A test fails if a document is added without being indexed.

- **The documentation↔code gate now scans every document by default**
  (`tools/check_doc_symbols.py` with no arguments reads `README.md` and every
  `docs/*.md`). CI used to pass a fixed list of two files; documents were added and
  the gate kept checking the same two, so the gate was green about a shrinking
  share of the docs. The list is now derived, and a test asserts the default covers
  every document. The success line also names the files it checked, so "12 files"
  is auditable rather than a number to trust.

### Fixed

- **A stale command count in the README.** It said `cli.py` has "16 commands";
  `COMMANDS` has had 20 since `fingerprint`, `verify` and `doctor` landed — a
  number nobody re-checked. Replaced with a pointer to `docs/API.md`, and a new
  test asserts that every command in `COMMANDS` appears in `docs/API.md`, so an
  undocumented command now fails the build. (The same class of error as the 0.3.0
  false-absence claims: green tests cannot catch a number that is merely old.)

### Not shipped in 0.7.0 (do not assume)

Unchanged: authentication/authorization/multi-tenancy (out of scope by decision),
vector retrieval in the default path (measured, rejected), tamper *proof*, TTL
scheduler, encryption at rest, lock fairness. **History compression — the subject
of `docs/DESIGN-HISTORY.md` — is not built**: it is a design with a trigger, not a
capability, and the document says so in its first line.

## [0.6.0] — 2026-10-30

### Fixed

- **Windows: a reader could make a concurrent writer fail.** `os.replace` cannot
  replace a file another process has open, and `Memory.open` read the graph without
  the lock, so one agent's startup read could turn another agent's atomic write into
  `PermissionError [WinError 5]`. `Store.read_locked()` now reads under the lock and
  `Memory.open` uses it; opening a missing graph still creates nothing
  (`LockedReadTests`). Found by the new concurrency test on Windows CI, not by a
  user.

### Changed

- **Lock retry now backs off with jitter** (`LOCK_POLL_START_S` 1 ms doubling to a
  16 ms ceiling) instead of sleeping a flat 20 ms. Measured effect on an 8-writer
  burst: throughput ~700 → ~870 writes/s, p50/p95 unchanged, **tail unchanged**
  (168–199 ms). The change is kept for the throughput, not for the tail — see the
  diagnosis in `docs/CONCURRENCY.md`.
- **The contention tail is diagnosed, not hypothesised**: `Store.lock_stats`
  (observation only) shows the worst waiter loses only ~15 polls while the other
  seven writers complete ~200 writes, and its wait matches the whole burst — i.e.
  starvation from non-FIFO `flock` wakeups, not the polling interval. Fairness was
  not implemented; the open issue records the numbers and the trigger.

### Added

- **Concurrency burst test** (`experiments/concurrency/run_stress.py`,
  `docs/CONCURRENCY.md`): 8 processes × 25 writes against one graph, three runs —
  **200/200 nodes present, 0 duplicates, 0 lost, exactly one change record per
  write, `check` clean, no lock timeouts**. Throughput is unchanged by contention
  (~700 vs ~640 writes/s) because the lock serialises the critical section, but the
  latency tail is ~240 ms against a ~1 ms median. The cause of that tail is stated
  as a hypothesis (unfair `flock` wakeups plus 20 ms polling), not a finding, and
  the counters needed to prove it do not exist yet.
- `tests/test_concurrency.py`: a 3×3 version of the same four properties runs on
  every commit, including Windows.

### Not shipped in 0.6.0 (do not assume)

Unchanged: authentication/authorization/multi-tenancy (out of scope by decision),
vector retrieval in the default path (measured, rejected), tamper *proof*, TTL
scheduler, encryption at rest, and write-path speed work (priced, deferred).
Lock **fairness** is also not implemented — the starvation tail is diagnosed and
documented, not fixed (DECISIONS #15).

## [0.5.0] — 2026-10-30

**A measurement release: no behaviour changes.** Every claim below is a number
taken on a live graph or a priced option, and nothing in `src/amg/` changed except
the version string. If you are upgrading for features, there are none.

### Added

- **Write-cost analysis** (`docs/WRITE-COST.md`): on the live 15.6 MB graph,
  `changes[]` is **79.1%** of the bytes and a write is 148 ms = parse 75 +
  render 50 + `fsync` 23. Four options are priced with measurements: cold-archive
  reclaims nothing (oldest node 6 days, 0 candidates), compact JSON saves 2.4% and
  costs git diffability, incremental writes abandon the atomicity guarantee, and a
  history sidecar would cut writes ~80% at the cost of the single-file property.
  Nothing was built: the existing trigger (p95 > 250 ms / 20 MB / 10k nodes) is
  two-thirds away and the analysis is recorded so the decision does not need
  rediscovering.

- **Real-graph measurements** (`docs/REAL-WORLD.md`): a live 1,249-node / 15.3 MB
  graph adopted in 140 ms with the source `sha256` unchanged, `check` clean in
  4.4 ms, `audit` 1,029 conflicts before the exemption pin and **3 after** (all
  genuine staleness), `audit --pin` report `match: true`, `expire` correctly inert
  (no node carries `valid_until`), reads in single-digit milliseconds, and a
  single write at **147 ms** — the number behind the cold-archive trigger, now
  measured on real data instead of projected from a synthetic benchmark.
  Aggregates only: no node ids, labels or notes are reproduced.

### Not shipped in 0.5.0 (do not assume)

Unchanged from 0.4.0 — this release added no capability:

- Authentication / authorization / multi-tenancy (out of scope by decision).
- Vector retrieval in the default path (measured and rejected; optional extra only).
- Tamper *proof* (`fingerprint`/`verify` detect; the losing cases are tabulated).
- TTL scheduler (`amg expire` is a command; no daemon).
- Encryption at rest (`graph.json` is plain text by design).
- Write-path speed work: priced in `docs/WRITE-COST.md`, deliberately not built —
  the trigger (p95 > 250 ms / 20 MB / 10k nodes) is still ahead of the live graph.

## [0.4.0] — 2026-10-30

### Notes

- Every "not implemented" claim in the docs was re-run against the code before
  this release (the rule from 0.3.0): no authentication code, no scheduler or
  thread, no socket, no encryption, no embedding in `src/amg/`. The only matches
  for `auth`/`token`/`socket` are the sentences asserting their absence and a
  tokeniser named `_TOKEN`.

### Not shipped in 0.4.0 (do not assume)

- **Authentication / authorization / multi-tenancy.** Decided out of scope with
  reasoning and alternatives (THREAT-MODEL §8, DECISIONS #13), not deferred.
- **Vector retrieval in the default path.** Measured: a local `nomic-embed-text`
  candidate lifts paraphrase `recall@5` 0.750 → 0.950, but misses the
  pre-registered bar in one stratified half and cannot ship as a dependency-free
  default. Optional extra only, and nothing is shipped.
- **Tamper *proof*.** `fingerprint`/`verify` detect edits; a determined attacker
  who can write the file and your stored digest wins (§7a, last two rows).
- **TTL scheduler.** `amg expire` is a command; no daemon.
- **Encryption at rest.** `graph.json` is plain text by design.

### Added

- **Filesystem hygiene checks**: `amg doctor` reports `SEC_WORLD_WRITABLE`,
  `SEC_GROUP_WRITABLE`, `SEC_NETWORK_PATH` and `SEC_GRAPH_SYMLINK` — the
  conditions under which this project's only boundary (file permissions) does not
  hold. `amg doctor --strict` exits 1 (`E_INSECURE_GRAPH`) on a warning; `amg mcp`
  prints the warnings to stderr at startup and keeps serving.

### Changed

- **Authorization decided out of scope** (docs/THREAT-MODEL.md §8, DECISIONS #13):
  no authentication, no per-caller authorization, no multi-tenancy. A token check
  in front of a file the caller can open proves only that they have the file; what
  would actually hold (users, containers, ACLs, read-only mounts) is enforced by
  the OS. The decision lists what to do instead, and the three conditions that
  would reopen it.
- **Semantic retrieval measured, not guessed** (`experiments/retrieval_eval/`):
  a local `nomic-embed-text` candidate (768 dims via ollama) lifts paraphrase
  `recall@5` from 0.750 to 0.950 and `recall@1` from 0.400 to 0.625 with no
  keyword regression — real, measured, and still **not adopted**: one stratified
  half gains +0.100 against a +0.20 bar, and C3 keeps a 274 MB model out of the
  default path of a zero-dependency library. An earlier claim in this repo that
  the semantic arm was "not measurable here" was wrong (a local model was already
  installed); that correction is recorded in the experiment README.
- **Prior art verified in full text** (`docs/PRIOR-ART.md`): MAP-Graph
  (arXiv:2608.10509) already implements and ablates the two ideas this project
  had listed as its own direction, so both are conceded as prior art rather than
  presented as design commitments. The check also established the boundary we may
  cite: the paper states it has "no generic supersession or conflict-resolution
  state machine", and an expiry keyword scan returns nothing. README's "task
  scope" wording was wrong for that paper and is corrected to "scoped access and
  an action-level risk gate".

### Added

- **`amg fingerprint` / `amg verify`**: canonical `state_sha256` (nodes+edges,
  order independent) and `history_sha256` (`changes[]`, in order), plus a verify
  command that exits 1 on mismatch. Keeping them separate is what makes a silent
  edit visible: changing a node in the file moves state and leaves history alone.
  Read-only — `verify` writes nothing, proven by comparing file bytes.
- `docs/THREAT-MODEL.md` §7a states the exact limits, including the row where a
  determined attacker wins, and DECISIONS.md #11 records why there is no in-file
  hash chain over `changes[]` (it would look stronger than the external digest
  while being weaker, because the attacker regenerates it in one pass).

## [0.3.0] — 2026-10-30

### Added

- **MCP server over stdio** (`amg mcp <dir>`): eight tools over newline-delimited
  JSON-RPC 2.0, no network listener, no authentication (stated plainly). Every
  tool reuses the library entry points, so the evidence gate applies unchanged.
- **Opt-in read-side audit**: `--audit-read` records high-risk reads (L4 rules,
  strict queries, results touching superseded nodes) to a bounded, rotated
  `reads.jsonl` — deliberately not in `changes[]`.
- **Windows and macOS are tested, not assumed**: CI runs the suite on
  `ubuntu-latest`, `macos-latest` and `windows-latest`; the lock has a `msvcrt`
  implementation with a cross-process exclusivity test.
- **Read-only mode** (`amg mcp <dir> --read-only`, `Memory.open(dir, read_only=True)`):
  write tools are refused with `E_READ_ONLY` before dispatch, only the five read
  tools are advertised, and the underlying `Memory` refuses every commit, so the
  guarantee does not depend on the tool list staying correct. Verified by a
  digest-before/after test that attempts every write tool.
- `docs/THREAT-MODEL.md`: assets, trust boundaries, actor model, threat table,
  what read-only does not cover, and the accepted risks (no tamper evidence,
  read tools unthrottled, same-user file access).
- **Pre-registered retrieval evaluation** (`experiments/retrieval_eval/`): 27-node
  corpus, 26 labelled queries, measured baseline (overall `recall@5` 0.865;
  paraphrase bucket 0.750) and a written acceptance bar a vector retriever must
  clear before it may ship. Buckets are computed from measured token overlap, not
  from declared intent; `tests/test_retrieval_eval.py` locks the baseline numbers.
- **Two zero-dependency retrievers measured and rejected** (`bm25`, `hashed-vec`).
  Both lose to the shipped substring scorer on paraphrase `recall@5`
  (0.750 baseline vs 0.450 / 0.550) and `bm25` also trips the keyword-regression
  guard, so neither ships. The purpose of the experiment was to make that
  rejection possible; the shipped retriever is unchanged and still lexical only.
  A semantic candidate could not be measured here: the available embedding API
  answers `429 {"code":"1113"}` (no covered resource) and no local model is
  installed.
- `docs/SCHEDULING.md`: cron/systemd usage, rollback, and why there is no daemon.

### Fixed

- Windows: cp1252 console crashed on status glyphs; directory `fsync` raised
  `PermissionError` on non-POSIX filesystems.

### Notes

- `E_READ_ONLY` is classified as exit `2` (wrong call), not `1` (bad content):
  the same class as `E_ALREADY_AMG`. The exit-code table has no default, so an
  unclassified code still fails loudly.
- README corrections: it still said read-side audit and read-only were not
  implemented, and used a `grep risk` "no matches" proof that stopped being true
  when read-audit added `is_high_risk`. Both now describe the shipped state, and
  the remaining design-only claims carry commands that were actually run.
- Changelog correction: two bullets (Windows CI, read-side audit) had been
  inserted into the already-released **0.2.0** section by mistake. Both features
  landed after the `v0.2.0` tag, so they belong to 0.3.0 only; the 0.2.0 section
  now matches what that tag actually contained.

### Not shipped in 0.3.0 (do not assume)

- **Vector / embedding retrieval.** Two zero-dependency candidates were measured
  and both were **rejected** (paraphrase `recall@5` 0.450 / 0.550 against the
  lexical baseline 0.750). A semantic candidate was not measurable here: the
  available embedding API answers `429 {"code":"1113"}` and no local model is
  installed. Retrieval is still lexical only.
- **Authentication and multi-tenancy.** Read-only mode limits one session's blast
  radius; it does not authenticate anyone, and there is no per-caller
  authorization or tenant separation.
- **Tamper-evident history.** `changes[]` is append-only by API, not
  cryptographically. A process with file access can rewrite it undetected.
- **TTL scheduler.** `amg expire` is an explicit command; there is no daemon and
  no background thread.
- **Encryption at rest.** `graph.json` is plain text by design.

See `docs/THREAT-MODEL.md` section 8 for the reasoning behind the last three.

## [0.2.0] — 2026-10-30

Adds explicit fact time, opt-in expiry, batch ingest, a CLI for `supersede`, and
edge traversal. Every claim below is measured or covered by the test suite;
capabilities that are absent stay under **Not yet**.

### Added

- **Explicit fact time**: `amg add --valid-from ISO8601 [--valid-until ISO8601]`
  and `Memory.add_node(valid_from=…, valid_until=…)`. Values are stored verbatim;
  `valid_time_known` is true only when `valid_from` was supplied.
- **`amg expire <dir> [--apply]`**: opt-in expiry. Dry-run by default, supersedes
  instead of deleting, idempotent, skips nodes with unknown validity and counts
  them, so a migrated graph has zero eligible nodes. No background scheduler.
- **Batch ingest**: `amg import <dir> --from FILE.json` and
  `Memory.add_many(nodes, edges)`. All-or-nothing: every node and edge passes the
  same gates before the file is written; a single bad record leaves the graph
  byte-identical. 10,000 nodes in 0.10 s (previously computed at 6–7 minutes one
  by one).
- **`amg supersede <dir> OLD NEW --note`**: the core protocol operation is now
  reachable from the CLI, not just the library.
- **Edge traversal**: `amg related <id> [--depth N] [--kind K]` and
  `search --expand` (1-hop neighbors marked `expanded_from`, with `--strict`
  still applying). `depends_on` / `supersedes` must form a DAG — a cycle is a
  `check` error; other edge kinds may cycle and are only counted as a hint.
- `docs/BENCHMARKS.md`: read paths at 1k/5k/10k, per-write scaling, batch ingest,
  and traversal latency on a 10k-node / 10k-edge graph.
- `CONTRIBUTING.md`, `SECURITY.md`, and a public roadmap as GitHub issues.

### Changed

- **`valid_from` no longer defaults to the write time.** Omitting it means
  unknown (`null`, `valid_time_known: false`). The transaction-time proxy was
  measured to mis-date lagged facts by exactly the writing lag (20/20 records by
  more than a day) — see `experiments/valid_from_bias/`.
- `digest` header reports both exclusion counts
  (`superseded excluded: N, not yet valid excluded: M`).
- Nodes written by 0.1.0 keep their stored `valid_from`; the new rule applies to
  new writes.
- CLI: 16 commands, exit codes 0/1/2/3 from an explicit table with no default
  branch (an unclassified error raises instead of guessing).

### Fixed

- Retrieval and digest returned `superseded` nodes. Now hard-filtered in L1/L3/L4
  and in the digest; history stays reachable through L2.
- Missing-graph errors returned exit code 1 instead of the contractual 2, and
  unknown-enum errors were classified inconsistently. Both now follow the table.
- `evidence.grade` accepted booleans (a subclass of `int`), which landed `true`
  on disk instead of a grade.

### Enforced, not just documented

- Expiry requires a **known** validity window (`amg.audit.expiry_eligible`); an
  unknown window is a hint, never an automatic expiry.
- `amg adopt` still refuses to infer validity time.
- The documentation↔code gate fails the build when a documented capability has no
  symbol, or when a new error code is not classified; both are mutation-tested.

### Measured

- 119 unit tests, examples (`quickstart.sh`, `lifecycle.sh`) and the symbol gate
  run in CI on Python 3.10 / 3.12.
- Read paths at 10,000 nodes / 10,000 edges: `check` 65.5 ms, `audit` 63.2 ms,
  `search` 83.5 ms, `digest` 62.9 ms. `related` depth 1: 8.1 ms.
- Batch ingest: 10,000 nodes in 0.10 s. Single writes remain O(n) per write.

### Not yet (do not assume)

- Vector / embedding retrieval (lexical only).
- MCP server, authentication, multi-tenancy, read-side audit logging.
- Background expiry scheduling. `valid_until` is only acted on by `amg expire`.
- Concurrency stress beyond the advisory lock; graphs above 10,000 nodes.
- Python 3.10/3.12 are exercised in CI only; local runs used 3.15.

## [0.1.0] — 2026-10-29

First public release.

- Append-only single-file store: advisory lock, full-graph write, atomic replace.
- Four enforced invariants (IR-1..IR-4) including "a conclusion-typed node cannot
  be `done` without evidence objects".
- Evidence contract with real `content_sha256`; bare strings rejected.
- Bi-temporal `supersede` (old node kept, validity window stamped).
- Lexical L1/L2/L3/L4 retrieval with `anchor_state` and `--strict`.
- Pointer-only bounded digest; audit with legacy coverage pin.
- `amg adopt` for migrating legacy graphs without fabricating evidence.
- 13 CLI commands, 73 tests, documentation↔code symbol gate.
