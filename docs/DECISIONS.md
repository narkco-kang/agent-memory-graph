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
