# Security

## Supported versions

Only the latest release receives fixes. This is a v0.x project.

## What this software is (and is not)

- It is a **local, single-tenant file store**. `graph.json` is plain text.
- There is **no authentication and no authorization layer**. Any process that can
  read the file can read the memory; any process that can write it can rewrite
  it.
- It opens **no network port** and makes no outbound requests.
- With `--audit-read`, `reads.jsonl` records query text for high-risk reads. It
  is plain text and rotated, not encrypted: do not treat it as a secret store.
- Do not run it on a shared host with untrusted users, and do not expose the file
  over a network share.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository (Security → Advisories
→ Report a vulnerability). Please do not open a public issue.

## Known limitations that are not vulnerabilities

- The advisory write lock uses `fcntl` on POSIX and `msvcrt` on Windows; both paths run in CI (ubuntu, macos, windows).
- `amg adopt` reads legacy graphs and preserves their evidence strings verbatim
  in `legacy_evidence`. If a legacy graph contains secrets, they stay in the
  adopted file — review before publishing.
