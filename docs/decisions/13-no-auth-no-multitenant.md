# Decision #13

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-30.*

**No authentication, no authorization, no multi-tenancy — decided, not
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
