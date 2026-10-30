# Design decisions (signed 2026-10-29)

Each entry states the decision, the evidence behind it, and what it costs.

1. **Write gate is forward-only.** A real graph already had 629 of 869 `done`
   nodes without evidence (72%). Hard-failing them on day one would make `check`
   permanently red. So: new writes are gated; legacy nodes are exempted via a
   frozen pin of the sorted id list (not a file hash — that changes every write),
   and `audit` reports the ratio `629/869` as a convergence metric. Any change in
   the pin set must be explained explicitly.

2. **Gate triggers on conclusion-typed content, not on status.** A conclusion can
   be finished while its status still says `in_progress`; status-only gating
   misses exactly the dangerous case.

3. **Anchor filter degrades, never hides.** Only 22–36% of lexical hits carry
   evidence. Default returns unanchored hits with `anchor_state: "none"`;
   `--strict` is the only filter. Ranking puts anchored hits first.

4. **Two different things never share one field.** `anchor_state` = retrieval
   quality; `evidence_grade` = how strongly the cited evidence was verified.

5. **Bi-temporal, minimally.** Validity time (`valid_from`/`valid_until`) is
   separate from transaction time (`recorded_at`/`superseded_at`). Never
   back-fill `valid_from` from the change log: `changes[].at` is *when it was
   written*, not *when the fact became true*.

6. **Semantic gates may not reject.** A synchronous near-duplicate gate can fire
   before an asynchronous contradiction detector and wrongly reject a write
   (documented in arXiv:2606.24535). Only the evidence gate may reject, and it
   must raise explicitly — never return `None` silently (the CrewAI
   `read_only → return None` case).

7. **Consolidation keeps pointers only.** Digest output references node ids and
   evidence counts; it never copies evidence payloads, and it is bounded by
   `--max-bytes` with an explicit `[truncated N items]` marker. The digest is not
   a second store, so it must stay auditable.

8. **Documentation must equal reality.** CI fails if a documented capability has
   no corresponding symbol. The check only verifies symbol existence — it makes
   no claim about semantics, because a fake semantic check would be worse than
   none.

9. **Adoption never fabricates evidence.** A legacy graph stores evidence as bare
   locator strings (658 of them on the real graph, 0 valid objects). Turning
   those into evidence objects would require inventing `content_sha256`, which
   is the exact lie the gate exists to prevent. So `amg adopt` preserves them in
   `legacy_evidence`, leaves `evidence` empty, and reports the legacy ratio that
   `audit --pin` already measures. Placeholder sources become explicit
   provenance (`adopted:<schema>:<sha12>`), `superseded_at` is inferred from
   `updatedAt` and flagged, and `valid_from` stays `null` rather than being
   back-filled from `changes[].at`. Cost: adopted history is not retro-actively
   verified — it is *labelled* as unverified, which is the honest state.
   *Signed 2026-10-29.*

10. **Unknown validity time can never be auto-expired.** `amg adopt` cannot know
    when a migrated fact became true (`changes[].at` is write time, not validity
    time), so adopted nodes carry `valid_time_known: false` and `valid_from:
    null`. Consequences, all enforced: `audit` downgrades an expired
    `valid_until` on such a node from conflict to hint; `expiry_eligible()`
    refuses them; `audit` prints the count. Expiring them would delete real
    facts on the strength of a timestamp we never had — worse than having no TTL
    at all. Cost: migrated graphs stay on the 3-day staleness rule only, until
    someone records a real validity window on the node.
    *Signed 2026-10-29.*

11. **Tamper evidence lives outside the file, not inside it.** The obvious design
    is a hash chain over `changes[]` (`changes[i].prev`). It was rejected: anyone
    who can write `graph.json` recomputes the chain in one pass, so it buys
    nothing against the only threat that matters while costing a schema migration
    and inviting misplaced trust. What ships instead is `amg fingerprint`
    (canonical `state_sha256` + `history_sha256`) and `amg verify`, whose value
    comes entirely from storing the digest elsewhere — git, a CI log, a ticket.
    The split digest does detect the cheap attacks: a node edited in place moves
    state while history stays put, and that mismatch is reported as a fact about
    the bytes. The limits are tabulated in `docs/THREAT-MODEL.md` §7a rather than
    left to the reader's optimism.
    *Signed 2026-10-30.*

12. **Prior art is verified in full text, and our two "design commitments" are
    conceded.** MAP-Graph (arXiv:2608.10509) was cited from a second-hand summary
    for months. A full-text check (14 pages, quoted in `docs/PRIOR-ART.md`) found
    that it already implements and ablates both ideas this project listed as its
    own direction — hard authorization separated from graded trust, and evidence
    requirements scaling with action risk. So they move from "design only, ours"
    to "prior art, not implemented here". It also confirmed the useful boundary:
    the paper states it has "no generic supersession or conflict-resolution state
    machine", and a keyword scan finds no expiry mechanism at all. That is what we
    are allowed to point at — a scope difference, not a superiority claim.
    Consequence: no document may say or imply "no precedent" for the
    task/evidence/authorization combination; the README's "closest prior work"
    line now names what that work does.
    *Signed 2026-10-30.*

13. **No authentication, no authorization, no multi-tenancy — decided, not
    deferred.** The alternative was a token check in front of a file the caller
    can already open, which proves only that they have the file; in practice the
    token lives in a config file they can also read. All the isolation that would
    actually hold (users, containers, ACLs, read-only mounts) is enforced by the
    OS underneath. So the boundary stays where it works, and the project moves its
    effort to (a) `--read-only` bounding one session's blast radius, (b)
    `amg doctor --strict` failing when the permission boundary does not hold
    (`SEC_WORLD_WRITABLE`, network mounts, symlinked graph), and (c)
    `fingerprint`/`verify` for tamper detection. What would reopen this: a network
    transport, multi-writer concurrency, or a multi-tenant deployment — each of
    which invalidates the reasoning rather than merely making auth nicer.
    *Signed 2026-10-30.*

14. **Write cost: measure the bytes before optimising, and do not trade atomicity
    for 20 MB.** Measured on a live 15.6 MB graph: `changes[]` is 79.1% of the
    file, and one write is 148 ms split as parse 75 / render 50 / `fsync` 23 —
    moving the bytes through the process twice, not the disk. Options evaluated in
    `docs/WRITE-COST.md`: cold-archiving nodes reclaims nothing today (oldest node
    is 6 days old, so 0 candidates); compact JSON saves 2.4% and costs
    diffability; incremental writes abandon the "reader sees old or new, never a
    mix" guarantee. The only option with a real payoff is moving old history to a
    sidecar (−80% write), and its price is that the graph stops being one atomic
    copyable file — so it waits for the existing trigger (write p95 > 250 ms, file
    > 20 MB, nodes > 10k) instead of being built speculatively. No `--no-history`
    escape hatch: if history ever moves, it moves for everyone and the guarantees
    are restated with it.
    *Signed 2026-10-30.*

15. **Lock retry backs off; lock fairness is not implemented.** The burst test showed
    one write per 200 waiting ~200 ms. Instrumenting the lock (`Store.lock_stats`)
    showed the worst waiter failed only ~15 polls while seven others completed the
    burst, and shortening the poll interval (flat 20 ms → jittered 1 ms doubling to
    16 ms) raised throughput ~20% (700 → 870 writes/s) **without moving the tail**.
    So the cause is starvation from non-FIFO `flock` wakeups, and faster polling was
    not the fix. The backoff is kept for the throughput; a ticket lock or waiter
    queue is not built, because it changes the one component that must never be
    wrong and there is no evidence yet that the tail harms a real workflow. Trigger
    to build it: repeated ~200 ms stalls observed in use, or a lock timeout in the
    field — not a benchmark.
    *Signed 2026-10-30.*

16. **The lock timeout is a policy knob, not a constant — and fairness is not the
    fix for bursts.** Measured on the real 15.6 MB graph: a write costs ~147 ms, so
    a 5 s default covers ~34 queued writes; 8 writers × 5 writes (40 writes) hits
    `LockTimeout` even though nothing is broken, because the queue needs ~6 s to
    drain. So `AMG_LOCK_TIMEOUT` was added (clamped to `(0, 3600]`, invalid values
    fall back to 5 s) and the default stays 5 s for interactive single-agent use.
    A FIFO lock would not help this case: the last writer still waits for the whole
    queue. The lever that does help is a cheaper write (history sidecar, priced in
    `WRITE-COST.md`: ~150 ms → ~30 ms, i.e. 34 → ~170 queued writes per 5 s).
    *Signed 2026-10-30.*

17. **History sidecar: rejected. Segmented compression: the sanctioned direction, not
    yet built.** The sidecar (state in `graph.json`, history appended to a second
    file) measured −82% write cost (147 ms → ~27 ms) and was rejected anyway:
    `changes[]` records are `{at, by, op, target, rev, note}` — descriptions, not
    replayable operations — so a split store has a crash window that can only be
    *detected*, never repaired, and the ledger can end up disagreeing with the state
    it describes. That trades the one guarantee the store is built around for speed.
    The alternative keeps one atomically replaced file and compresses history into
    sealed zlib segments: measured −54% file size, ~60 ms writes, 11 ms to decompress
    on read, round-trip verified. Its price is explicit — history stops being
    text-greppable/diffable, `fingerprint` must be defined over decompressed meaning
    rather than bytes, and it needs an `amg/v2` format bump. Deferred to the existing
    trigger (20 MB / 250 ms p95 / 10k nodes, or a real `LockTimeout` with
    `AMG_LOCK_TIMEOUT` already raised). Full design and build checklist:
    `docs/DESIGN-HISTORY.md`.
    *Signed 2026-10-30.*

18. **A coverage gate must derive its own scope; a hand-written list is a claim about
    the past.** From v0.3.0 the documentation↔code gate ran on a hand-written list of
    files (CI: two; release checklists: six or seven). Documents kept being added and
    the list did not, so every release was greener about a smaller share of the docs
    than its checklist implied — the checklists said "six documents" while `docs/`
    held eight. The gate now scans `README.md` plus every `docs/*.md`, a test asserts
    the default covers every document, and the success line names the files it
    checked. The same reasoning produced two companions: `docs/README.md` must link
    every document (tested), and every CLI command must appear in `docs/API.md`
    (tested) — a command can otherwise exist and be documented nowhere.
    *Signed 2026-10-30.*

19. **The artifact is a claim: build it, inspect it, and run the tests inside it.**
    Every check until v0.7.1 used `pip install -e .` against a checkout, so the
    published sdist had never been executed. Built and unpacked, it exposed the
    problem: `src/` and `tests/` shipped without `docs/`, `tools/` or
    `experiments/`, so its own suite gave 17 errors and 4 failures, all
    file-not-found. The wheel was complete, which is why installing the artifact
    (added as a criterion in v0.7.0) did not catch it — **an install check proves
    the code imports, not that the artifact is complete.** From v0.7.1: `MANIFEST.in`
    ships what the tests read, `tools/check_dist.py` inspects both artifacts with
    expectations derived from the working tree, and the CI `package` job installs
    the wheel and runs the sdist's shipped suite. Same rule as #18, applied one
    level out: a check that cannot name what it covered is not a check.
    *Signed 2026-10-30, after v0.7.1.*

20. **Staleness applies to work, not to registrations.** The audit rule "an
    `in_progress` or `blocked` node untouched for 3 days is stale" assumed every node
    is a short-lived work item. On the first live graph it flagged a `group` node
    that had been `in_progress` for 7 days — correct by the letter, noise in
    practice: a group registration is long-lived, and its `updatedAt` does not move
    when its children change. `group`, `env` and `member` are now exempt
    (`LONG_LIVED_TYPES`), while an unknown type is still checked: exemptions are
    explicit so that a new kind of work cannot become invisible by omission. Three of
    the four original conflicts were genuine work items and remain reported.
    *Signed 2026-10-30; four tests in `tests/test_audit.py`.*

21. **The staleness threshold is policy, not a constant.** `STALE_DAYS = 3` was a
    guess baked into the code; on the first live graph it produced three conflicts at
    3 days, one at 7 and none at 14. A weekly-sync team sees false alarms at the
    default, a monthly team none. So the default stays 3 (the original rule, no
    surprise for existing users) and the threshold becomes `AMG_STALE_DAYS` (integer,
    `0 < x <= 365`, invalid falls back to 3) plus `audit --stale-days N` for a single
    run. Fallback rather than "disable": a typo must not silently turn the check off.
    Same shape as DECISIONS #16 for the lock timeout, for the same reason — the
    library serves teams with different cadences and cannot infer them.
    *Signed 2026-10-31; three tests in `tests/test_audit.py`.*

22. **One source of truth for audit output: structured findings, human strings
    derived.** `audit` used to build display strings directly, so any consumer that
    wanted the node or the owner had to parse them. Now each finding is recorded once
    as a dict (severity, kind, detail, node/edge/owner/age) and the `conflicts` and
    `hints` lists are generated from it, which makes drift between text and `--json`
    impossible by construction rather than by discipline. The string lists stay, in
    the same order, because they are the existing contract; `findings` is additive.
    A test asserts the two views match exactly.
    *Signed 2026-10-31.*

23. **Handover discipline is borrowed, credited, and adapted — not reinvented.**
    A public workbench (luanyujia-workbench, MIT) documents the same problem — a
    long-lived team whose sessions are all temporary — with three rules that survived
    real use: overwrite the handover rather than appending, keep it under a fixed size
    (4 KB), and write pointers rather than transcripts. We adopt the rules and say
    where they came from (`docs/PRIOR-ART.md`), because re-deriving them badly would
    be a worse use of the measurement budget. The adaptation is a `handoff` node:
    exactly one active, supersede-on-write so the previous card lands in the same
    audited ledger, the budget refused by the writer and re-checked by `audit`, and
    `multiple_active_handoffs` as a conflict rather than a convention. Registrations,
    including handoff nodes, are exempt from staleness (#20).
    *Signed 2026-10-31; `tests/test_handoff.py`.*

24. **Archive the ledger, not the nodes — and prove the move on every run.**
    The write-cost work (`docs/WRITE-COST.md`) priced four ways to reclaim bytes; this
    is the one that ships, and the choice is measured, not aesthetic: on the 15.7 MB
    real graph **79% of the file is change records**, they have no referential
    integrity (nothing points at a change), and moving a cold prefix of them cut a
    single write from 226.1 ms to 72.7 ms. Archiving *nodes* is the tempting
    alternative and is deliberately not done: edges cross the boundary, so a partial
    implementation would leave dangling references or a second store to keep
    consistent — the failure this project already ranks lowest. The proof is the
    borrowed shrink protocol ("snapshot first, move second, prove nothing was lost",
    credited in `docs/PRIOR-ART.md`) turned into five independent checks that run on
    every `--apply`, with the snapshot written back when they fail
    (`E_ARCHIVE_VERIFY`). Unknown times never move: an undated record stops the
    prefix, the same conservative direction as TTL expiry. `L2` search sees live
    history only, which is stated in `docs/ARCHIVE.md` rather than left to be found.
    *Signed 2026-10-31; `tests/test_archive.py`.*

25. **Lexical matching is word-aware; the recall it costs is recorded, not hidden.**
    The substring matcher answered queries that cannot distinguish anything: on the
    real 1,289-node graph, `a`, `e`, `i` and `x` each returned the full `k=10`, and an
    identifier for a node that does not exist (`task.a`) returned ten unrelated
    `task.*` ids. The fix is word-boundary matching plus a 14-entry English inflection
    table (`rank`/`ranking`), identifier queries treated as lookups, and one-character
    ASCII tokens dropped. Measured (`experiments/retrieval_precision/`): single-letter
    queries 10 → **0** hits, nonexistent identifiers 10 → **0**, identifier lookups
    **20/20** top-1, kw recall@5 0.938 → **0.969**, MRR 0.744 → **0.763**. The cost is
    real and is published: overall recall@5 0.865 → **0.808** on the frozen eval,
    because two of 26 queries had been reached only through substrings *inside* other
    words (`i` in `high-risk`, `one` in `gone`); recall@1 is unchanged at 0.654. The
    pre-registration failed C4 (recall must not drop) and C5 (no pinned numbers may
    move) — both failures are recorded in its outcome section with the per-query
    analysis, and this decision overrides them on the evidence, because raising
    `k`-many answers to "anything with this letter" is not a retrieval feature.
    `tests/test_retrieval_eval.py` pins the **new** numbers and keeps the old ones in
    its comment for audit.
    *Signed 2026-10-31; `tests/test_search_precision.py`, `experiments/retrieval_precision/`.*

26. **The 5 s lock timeout stays; the 10k burst is documented, not papered over.**
    Pre-registered run (`experiments/concurrency/PREREGISTRATION-10k.md`): 8 writers ×
    25 writes on a 10,000-node graph, default timeout. It **failed** with
    `LockTimeout after 5.0s` — and the arithmetic says it had to: a write at 10k costs
    **86.2 ms**, so 200 writes are ~17 s of serialised work (measured burst window
    17.95 s), and the last writer waits ~13.5 s (measured) before it gets the lock.
    With an adequate timeout the invariant held exactly (200/200 nodes, 0 duplicates,
    0 missing, 200 change records, `check` clean, 11.1 writes/s contended vs 11.3/s
    serial). Two pre-registered predictions were wrong and are recorded as wrong:
    contended p50 did not inflate (1.0× serial), and the worst wait was not < 5 s.
    Decision: keep the 5 s default. An interactive CLI that silently blocks for 30 s
    is worse than a fast, explicit `LockTimeout` that names `AMG_LOCK_TIMEOUT`; and a
    larger default would hide the real finding, which is that the *write cost* is the
    limit, not the lock (`WRITE-COST.md`). Burst users are told the safe sizing rule:
    timeout ≥ writers × writes × per-write cost.
    *Signed 2026-10-31; `docs/CONCURRENCY.md` §"At 10,000 nodes", `result-10k*.{json,txt}`.*

27. **Scale does not dilute lexical recall; vocabulary overlap does — and the scorer,
    not the matcher, is why.** Pre-registered at 10,000 nodes
    (`experiments/retrieval_10k/PREREGISTRATION.md`), same frozen 26 queries and gold
    set, two noise models. Unrelated distractors left every metric identical
    (0.654/0.808/0.865/0.763) — 370× more nodes cost nothing measurable, which retires
    the naive "big memory dilutes search" worry. Distractors built from the queries' own
    vocabulary cost **recall@5 0.808 → 0.538** and recall@1 0.654 → 0.481; of the 11
    misses, **7 sit beyond rank 100**, i.e. dozens of distractors outscored the gold
    node. The scorer weights fields (`id` 3.0, `label` 2.0, `note` 1.0) with **no IDF**,
    so repetition of common query words is as good as an answer. Two predictions were
    wrong and are recorded as wrong; the round touched no code on purpose (criterion
    C4). IDF weighting is now the named next candidate — it needs its own
    pre-registration and must not regress the frozen 27-node baseline.
    *Signed 2026-10-31; `experiments/retrieval_10k/`, `result.json`.*
