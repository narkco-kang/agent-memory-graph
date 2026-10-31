# Design decisions

Each entry states the decision, the evidence behind it, and what it costs. Entries #1–#34
were written into this one file from 2026-10-29 to 2026-10-31; at #34 it had 7 B of headroom,
so decisions went unrecorded for seven versions. Since v0.32.0 **this file is the index** and
every decision has its own page (DECISIONS #43).

**How to read a reference.** `DECISIONS #N` means entry N in the table below. In the
shipped documentation every reference is a link straight to that decision's page, and a test
asserts that a link labelled `#N` resolves to the page numbered N (`CHANGELOG.md` and
`RELEASE.md` keep bare numbers: they are append-only logs, not reading material).

**Status.** `active` = still the rule. `amended (#N)` = the rule stands but a later entry
changed part of it. `superseded` = replaced (none yet). `archived` = kept for history only
(none yet). The column is judged by hand, because nothing in the prose is structured enough to
derive it — so two things are enforced by test instead: the page that amends (#N) must say so
in its header, and the count above must match measurement. The first hand-written version of
this column marked #17 as amended by #24 when #24 never mentions it; an attack found that, and
the status is `active` again.

**Signature.** 26 of the 34 original entries carry a `*Signed …*` line; the eight without
one are #1–#8, signed only by this log's preamble (DECISIONS #42), marked `preamble` here.
No signature was invented during the split.

**Cost.** Not every entry prices itself: a stem match for `cost*`, `price*` or `pay/pays/paid`
hits **11 of the 34** original entries (9, 11, 14, 16, 17, 24, 25, 26, 27, 28, 29); the other
23 state the decision and its evidence without a numbered cost. An earlier revision of this
paragraph said 8 — the pattern it used required a word boundary after `cost`, so `costs`
did not match. The number is now asserted by a test, because a hand-maintained count drifted
the first time it was checked.

**Budget.** The 24 KiB documentation budget applies per page here, not to this file as a
whole, so the log's capacity grows with the number of decisions. That is the point of the
split: the previous single file could hold 34 decisions and then stopped.

| # | Decision | Status | Signed |
|---|---|---|---|
| [1](decisions/01-write-gate-forward-only.md) | Write gate is forward-only. | active | preamble |
| [2](decisions/02-conclusion-typed-gate.md) | Gate triggers on conclusion-typed content, not on status. | active | preamble |
| [3](decisions/03-anchor-filter-degrades.md) | Anchor filter degrades, never hides. | amended (#31) | preamble |
| [4](decisions/04-no-shared-field-semantics.md) | Two different things never share one field. | active | preamble |
| [5](decisions/05-bi-temporal-minimal.md) | Bi-temporal, minimally. | active | preamble |
| [6](decisions/06-semantic-gates-may-not-reject.md) | Semantic gates may not reject. | active | preamble |
| [7](decisions/07-consolidation-pointers-only.md) | Consolidation keeps pointers only. | active | preamble |
| [8](decisions/08-docs-equal-reality.md) | Documentation must equal reality. | active | preamble |
| [9](decisions/09-adoption-never-fabricates.md) | Adoption never fabricates evidence. | active | ✓ |
| [10](decisions/10-unknown-validity-never-auto-expired.md) | Unknown validity time can never be auto-expired. | active | ✓ |
| [11](decisions/11-tamper-evidence-outside-file.md) | Tamper evidence lives outside the file, not inside it. | active | ✓ |
| [12](decisions/12-prior-art-verified-in-full-text.md) | Prior art is verified in full text, and our two "design commitments" are  conceded. | active | ✓ |
| [13](decisions/13-no-auth-no-multitenant.md) | No authentication, no authorization, no multi-tenancy — decided, not  deferred. | active | ✓ |
| [14](decisions/14-write-cost-measure-first.md) | Write cost: measure the bytes before optimising, and do not trade atomicity  for 20 MB. | active | ✓ |
| [15](decisions/15-lock-retry-backoff.md) | Lock retry backs off; lock fairness is not implemented. | active | ✓ |
| [16](decisions/16-lock-timeout-policy.md) | The lock timeout is a policy knob, not a constant — and fairness is not the  fix for bursts. | active | ✓ |
| [17](decisions/17-history-sidecar-rejected.md) | History sidecar: rejected. Segmented compression: the sanctioned direction, not yet built. | active | ✓ |
| [18](decisions/18-coverage-gate-derives-scope.md) | A coverage gate must derive its own scope; a hand-written list is a claim about  the past. | active | ✓ |
| [19](decisions/19-artifact-is-a-claim.md) | The artifact is a claim: build it, inspect it, and run the tests inside it. | active | ✓ |
| [20](decisions/20-staleness-applies-to-work.md) | Staleness applies to work, not to registrations. | active | ✓ |
| [21](decisions/21-staleness-threshold-policy.md) | The staleness threshold is policy, not a constant. | active | ✓ |
| [22](decisions/22-one-source-of-truth-findings.md) | One source of truth for audit output: structured findings, human strings  derived. | active | ✓ |
| [23](decisions/23-handoff-borrowed.md) | Handover discipline is borrowed, credited, and adapted — not reinvented. | active | ✓ |
| [24](decisions/24-archive-ledger-not-nodes.md) | Archive the ledger, not the nodes — and prove the move on every run. | active | ✓ |
| [25](decisions/25-word-aware-matching.md) | Lexical matching is word-aware; the recall it costs is recorded, not hidden. | amended (#28) | ✓ |
| [26](decisions/26-lock-timeout-stays-5s.md) | The 5 s lock timeout stays; the 10k burst is documented, not papered over. | active | ✓ |
| [27](decisions/27-scale-does-not-dilute.md) | Scale does not dilute lexical recall; vocabulary overlap does, and the scorer is  why. | active | ✓ |
| [28](decisions/28-idf-term-weights.md) | IDF term weights ship — and they do not fix query-vocabulary noise. | active | ✓ |
| [29](decisions/29-field-df-rejected.md) | Field-specific document frequency is rejected: the noise gain is paid for by  note-only queries. | active | ✓ |
| [30](decisions/30-bounded-scores-labelled.md) | Scores are bounded and labelled; the normalization changes no rank. | active | ✓ |
| [31](decisions/31-evidence-hashes-declared.md) | Evidence hashes are declared, not proven — disclose and make them observable. | active | ✓ |
| [32](decisions/32-verifier-root-and-starvation.md) | v0.20.0's verifier leaked the graph root; `--include-archive` starved. | active | ✓ |
| [33](decisions/33-migrate-folds-detail.md) | `amg migrate` folds legacy `detail` into `note`; `check` stops advising a no-op. | active | ✓ |
| [34](decisions/34-nothing-verified-is-not-healthy.md) | "Nothing was verified" is not "healthy". | active | ✓ |
| [35](decisions/35-coverage-two-denominators.md) | A coverage rate needs two denominators, and “not checked” is not a rate. | active | ✓ |
| [36](decisions/36-evidence-root-explicit.md) | An evidence base is a policy, not an implicit directory. | active | ✓ |
| [37](decisions/37-unobservable-anchoring-reported.md) | Thin anchoring is reported, never silent. | active | ✓ |
| [38](decisions/38-bridge-requires-full-anchoring.md) | The verification bridge may not have its own green light. | active | ✓ |
| [39](decisions/39-forged-digest-is-a-failure.md) | A forged digest is a failure, not an untested claim. | active | ✓ |
| [40](decisions/40-doc-gates-walk-subdirectories.md) | A gate that cannot see a subdirectory is not a gate. | active | ✓ |
| [41](decisions/41-doc-gates-select-by-directory.md) | Select documents by directory, not by file suffix. | active | ✓ |
| [42](decisions/42-entries-1-8-signed-by-preamble.md) | Entries 1–8 are signed by the preamble; no signature is invented. | active | ✓ |
| [43](decisions/43-decision-log-is-an-index.md) | The decision log is an index plus one page per decision. | active | ✓ |
| [44](decisions/44-derived-artifact-expectation.md) | A derived expectation must derive the same way it checks. | active | ✓ |
| [45](decisions/45-lock-tail-cross-platform.md) | The lock tail is cross-platform, and Windows pays more of it. | amended (#46) | ✓ |
| [46](decisions/46-one-run-is-not-a-measurement.md) | One run is not a measurement: quote the run, and claim only what repeats. | active | ✓ |
