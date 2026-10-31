# Decision #10

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-29.*

**Unknown validity time can never be auto-expired.** Adopted nodes carry
    `valid_time_known: false`; an expired `valid_until` on such a node is a hint, not a
    conflict, `expiry_eligible()` refuses it, and `audit` counts the class. Expiring on a
    timestamp we never had would delete a fact on a guess. Details: `docs/API.md`
    §Expiry. *Signed 2026-10-29.*
