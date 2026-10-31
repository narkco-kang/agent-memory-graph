# Decision #23

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; `tests/test_handoff.py`.*

**Handover discipline is borrowed, credited, and adapted — not reinvented.**
    A public workbench (MIT) documents the same problem with three rules that survived
    real use: overwrite rather than append, a fixed size (4 KB), pointers not
    transcripts. We adopt them, credit them (`docs/PRIOR-ART.md`) and adapt them into a
    `handoff` node: one active, supersede-on-write into the same audited ledger, budget
    refused by the writer and re-checked by `audit` (`multiple_active_handoffs` is a
    conflict, not a convention). Registrations are exempt from staleness (#20). Details:
    `docs/HANDOFF.md`. *Signed 2026-10-31; `tests/test_handoff.py`.*
