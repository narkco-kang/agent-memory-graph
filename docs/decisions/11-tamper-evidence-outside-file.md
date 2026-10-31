# Decision #11

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30.*

**Tamper evidence lives outside the file, not inside it.** The obvious design
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
