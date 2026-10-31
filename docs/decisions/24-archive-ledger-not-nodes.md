# Decision #24

[← decision log](../DECISIONS.md) · status: active · *Signed 2026-10-31; `tests/test_archive.py`.*

**Archive the ledger, not the nodes — and prove the move on every run.** Of the four
    byte-reclaim options priced in `docs/WRITE-COST.md`, this is the one that ships: on
    the 15.7 MB real graph **79% of the file is change records**, nothing points at them,
    and moving a cold prefix cut a write 226.1 → 72.7 ms. Archiving *nodes* is
    deliberately not done: edges cross the boundary. The borrowed shrink protocol
    ("snapshot first, move second, prove nothing was lost") becomes five checks on every
    `--apply`, with a snapshot written back on failure (`E_ARCHIVE_VERIFY`); an undated
    record stops the prefix. Details: `docs/ARCHIVE.md`. *Signed 2026-10-31;
    `tests/test_archive.py`.*
