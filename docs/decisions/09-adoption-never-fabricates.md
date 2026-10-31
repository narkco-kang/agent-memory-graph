# Decision #9

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-29.*

**Adoption never fabricates evidence.** Legacy graphs store evidence as bare locator
   strings; turning them into objects would require inventing `content_sha256` — the lie
   the gate exists to prevent. `amg adopt` preserves them in `legacy_evidence`, leaves
   `evidence` empty, stamps the placeholder source as `adopted:<schema>:<sha12>`, infers
   `superseded_at` from `updatedAt` with a flag, and leaves `valid_from` null. Cost:
   adopted history is *labelled* unverified, not retro-verified. Details:
   `docs/ADOPTION.md`. *Signed 2026-10-29.*
