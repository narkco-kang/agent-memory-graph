# Decision #44

[← decision log](../DECISIONS.md) · status: active

**A derived expectation must derive the same way it checks.** `tools/check_dist.py` promised
“expectations derived from the working tree instead of a hard-coded list” (#19) — but its own
`expected_docs()` was one `listdir` filtered to `.md`, the same shape as the documentation
gates before #40/#41. v0.32.0 shipped 43 decision pages and the index and **not**
`docs/decisions/manifest.json`, the file the new test suite reads, so the sdist was broken
while four of the five `package` jobs printed a green artifact check; only the ubuntu/3.12
sentinel that unpacks the sdist and runs its own suite caught it (`FileNotFoundError`, five
errors). Decision: the artifact checker walks `docs/` recursively with no suffix filter, so
a file added for the tests must be shipped or the build fails. Cost: none, and the same rule
now appears in four places (§#18, #19, #40, #41) — which is the reason it is written down
again rather than assumed.
*Signed 2026-10-31; `MANIFEST.in`, `tools/check_dist.py`; v0.32.1.*
