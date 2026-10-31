# Decision #46

[← decision log](../DECISIONS.md) · status: active · amends #45

**One run is not a measurement: quote the run, and claim only what repeats.** v0.32.3 published
a lock-tail table assembled from one CI run, without naming the run. The independent verifier
read the job logs and found not one of the six cells reproducible: the same command on the next
two runs gave Windows p95 of 1,672 ms, 2,568 ms and 6,588 ms, and **ubuntu 2,897 ms against
164 ms** — at 80 samples p95 sits between the 76th and 77th value, so one stalled write moves it
by an order of magnitude. What survives repeats: the worst lock wait (ubuntu 10.46–11.01 s,
macOS 6.16–7.26 s, Windows 5.58–12.36 s across three runs) and the per-platform ordering of
macOS as mildest. What does not: #45's claim that Windows is materially worse — it rested on a
single p95. Corrected: #45 is `amended` by this entry, the documentation table now names the run
and job id for every cell, and a test requires those ids to be present. Cost: a published claim
withdrawn, and every future performance table carries provenance instead of a number alone.
*Signed 2026-10-31; `docs/CONCURRENCY.md`, `tests/test_concurrency_doc.py`; v0.32.4.*
