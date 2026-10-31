# Decision #43

[← decision log](../DECISIONS.md) · status: active

**The decision log is an index plus one page per decision.** 34 entries in one file at 24,569/24,576 B left 7 B of headroom, so no decision could be
recorded after #34: the decisions of v0.25.0–v0.31.0 were made, shipped and never logged —
a seven-version gap in the signed record. Decision: `docs/DECISIONS.md` is the index
(number, decision, status, signature, link) and each decision lives on its own page under
`docs/decisions/`; the 24 KiB budget applies per page, so the log's capacity grows with the
number of decisions — stated as policy instead of implied. `DECISIONS #N` references still
resolve by number through the index. Entries #35–#43 were backfilled in the same release,
each with the evidence it was made on. Cost: reading one decision now means opening two
files, and the index's status column is hand-maintained because nothing in the prose is
structured enough to derive it.
*Signed 2026-10-31; `tests/test_decisions_log.py`; v0.32.0.*
