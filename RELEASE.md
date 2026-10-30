# Release checklists

One note on the document counts below, because they were **not coverage** before
v0.7.0: the gate took a hand-written file list, so a checklist saying "six
documents" meant six files were passed to it — the repository held eight at
v0.5.0 and nine at v0.6.0. The gate now derives its list (`README.md` plus every
`docs/*.md`), so from v0.7.0 on the count is whatever is in `docs/`, and a new
document cannot silently escape it. Checked against the tags on 2026-10-30.

## Standing CI checks (as of 2026-10-30, after v0.7.1)

Eight jobs per push. Each one exists because something passed without it:

| Job | Checks | What it would have missed |
|---|---|---|
| `test` ×4 (ubuntu 3.12/3.10, macos, windows) | 191 unit tests, editable install, doc/code gate, examples | — |
| `package` ×4 (ubuntu/windows × 3.12/3.10) | builds sdist+wheel, `tools/check_dist.py`, installs the **wheel** and asserts the import comes from `site-packages`, runs the `amg` console script; on ubuntu 3.12 also unpacks the sdist and runs the suite inside it | v0.7.0's sdist shipped 21 tests that could not run; the wheel install had never been tried on 3.10 or Windows |

The wheel install matrix is deliberate: `test` installs editable, so without it the
artifact users actually get had only been installed on one interpreter and one OS.

## v0.14.0 — 2026-10-31

Status: **released**. Behaviour change: word-aware lexical matching, with the recall
cost measured and published.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 252 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents, both gates green |
| 3 | The criteria existed before the code | ✅ `experiments/retrieval_precision/PREREGISTRATION.md`, dated before implementation |
| 4 | Every criterion's result is recorded, including failures | ✅ C1–C3 hold; C4 and C5 **failed** and are explained per query |
| 5 | The recall cost is published, not absorbed | ✅ CHANGELOG, eval README (both number sets), DECISIONS #25 |
| 6 | Regression pinned both ways | ✅ `tests/test_search_precision.py` (8 tests) + `test_retrieval_eval.py` pinned to the new numbers, old ones kept in the comment |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 252 tests pass inside the unpacked archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.14.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Measurement is re-runnable | ✅ `run_eval.py` on the frozen corpus or `--graph <legacy.json>` |

The shape of this release is the point: the honest number went **down** (overall
recall@5 0.865 → 0.808) while the useful ones went up (kw recall@5 0.969, MRR 0.763,
single-letter and fake-identifier answers 0). A pre-registered criterion was violated
and the violation is written down with the evidence that justifies overriding it,
rather than the criterion being quietly relaxed.

---

## v0.13.0 — 2026-10-31

Status: **released**. Closes the gap 0.11.0 documented: cold history stays searchable.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 244 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents, both gates green |
| 3 | Examples run | ✅ `examples/archive.sh` now proves an archived hit is findable and labelled |
| 4 | Default behaviour did not move | ✅ a test asserts plain L2 returns the same ids before and after archiving |
| 5 | Old history is labelled, not guessed | ✅ every archived hit carries `archived: true` + `archive_file` |
| 6 | A wrong call is refused, not ignored | ✅ `E_ARCHIVE_LAYER` on L1/L3/L4 (exit 2), tested at API and CLI level |
| 7 | Not-shipped list updated | ✅ no index over the archive; unmeasured on years-old history |
| 8 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 244 tests pass inside the unpacked archive |
| 9 | Clean install from the tag | ✅ `git+...@v0.13.0` |
| 10 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |

Why this was the next thing: after "I moved my old history out", the first question a
user asks is "can I still find it?". The previous release answered "no, by design".
An honest limitation is still a limitation; this release removes it without weakening
the claim that live and archived history are different things.

---

## v0.12.0 — 2026-10-31

Status: **released**. New contract: documentation size budgets, plus the README
restructured to meet one.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 238 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` (15) |
| 3 | The new gate can fail | ✅ 7 tests, including a 12 KiB-over README and a 24 KiB-over doc |
| 4 | Budgets are stated where a reader looks | ✅ `docs/README.md`, asserted by a test against the constants |
| 5 | Every document is covered by default | ✅ same construction as the symbol gate, asserted by a test |
| 6 | Nothing was deleted to fit | ✅ 20,315 → 10,552 B by moving material to `ADOPTION.md`/`PRIOR-ART.md`/`API.md`/`HANDOFF.md`/`ARCHIVE.md` |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 238 tests pass inside the unpacked archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.12.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | The rule is credited | ✅ `docs/PRIOR-ART.md` + `docs/README.md` name the source (MIT) |

This round had no code change in `src/amg/`: it is a documentation-contract release.
The gate is the deliverable, because the drift it prevents had already happened — the
README restated five other documents, and one of them had fallen behind.

---

## v0.11.1 — 2026-10-31

Status: **released**. Patch: one false alarm removed from the archive proof.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 231 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` (14) |
| 3 | Examples run | ✅ five, unchanged and still green |
| 4 | The defect was reproduced before it was fixed | ✅ probe: rev-less last record → `E_ARCHIVE_VERIFY` + rollback; after fix the move succeeds |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Fixed" only; no capability added |
| 6 | Version, changelog, tag, notes agree | ✅ 0.11.1 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 231 tests pass inside the unpacked archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.11.1` |
| 9 | `python3 tools/verify.py` green | ✅ eight steps, 0 skipped |
| 10 | The fix is pinned by a test | ✅ `test_unnumbered_record_is_unknown_not_a_failure` |

Unknown and violated are different claims: a record with no `rev` means the hole
cannot be ruled out, not that it exists. The archive now says which one it is.

---

## v0.11.0 — 2026-10-31

Status: **released**. New capability: cold archiving of the change ledger, with a
proof of the move on every run and a rollback when the proof fails.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 230 tests ×4 + `package` ×5 (commit 8c3352a) |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` (now 14) |
| 3 | Examples run | ✅ quickstart, lifecycle, MCP client, handoff, **archive** (tamper case included) |
| 4 | Every "not implemented" claim re-run against code | ✅ no node archiving, no compression, no MCP tool, `L2` live-only — all still true and stated |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.11.0" |
| 6 | Version, changelog, tag, notes agree | ✅ 0.11.0 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; wheel installed and `amg archive` exercised from the installed console script; sdist's own 230 tests pass inside the unpacked archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.11.0` |
| 9 | `python3 tools/verify.py` green | ✅ eight steps, 0 skipped |
| 10 | The measurement is re-runnable, not quoted | ✅ `benchmarks/archive_cost.py` produces every number in this release from any legacy graph |

### What the proof is, in one paragraph

`--apply` snapshots the file, then compares five things produced independently: the
archive file **re-read from disk** against the records it claims to hold, the live
ledger against *remainder + one pointer*, `state_sha256` before and after (must be
identical — nodes and edges are not touched), `check()` on the persisted graph, and
the rev numbers across the archive/live boundary (must be contiguous). Any failure
writes the snapshot back and exits 1 with `E_ARCHIVE_VERIFY`. `--verify` re-runs the
same checks later from disk only, which is how a dropped record becomes a visible
hole instead of silence.

### Measured before shipping (macOS, 1-min load ≈ 3.4)

| graph | file | ledger share | moved @1 d | file after | single write |
|---|---|---|---|---|---|
| 15.7 MB real team graph | 1289 nodes / 2604 changes | 79.0% | 2275 records | 5.9 MB (−62.2%) | 226.1 → 72.7 ms |
| this project's own graph | 198 nodes / 454 changes | 48.8% | 265 records | 337 KB (−32.3%) | 7.7 → 5.5 ms |

At the default 30-day cutoff, **0 records qualify today** on both graphs (8 days
old). Quoted as measured, not extrapolated.

### Honest limits of this release

The archive is a second file on the same disk, protected by the same OS user: it is
not a backup, and it does not survive `rm -rf`. `L2` search no longer covers moved
history. Snapshots cost one full graph copy per run and are not auto-pruned. Nodes
are not archived at all (DECISIONS #24 explains why, and what it would cost).

---

## v0.10.0 — 2026-10-31

Status: **released**. New capability: handoff cards, adapted from a field-tested
external workbench and credited there.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 214 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` (now 12) |
| 3 | Examples run | ✅ quickstart, lifecycle, MCP client, **handoff** |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.10.0" |
| 6 | Version, changelog, tag, notes agree | ✅ 0.10.0 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 214 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.10.0` |
| 9 | `python3 tools/verify.py` green | ✅ including the artifact step and the new example |
| 10 | Borrowed pattern credited | ✅ PRIOR-ART records the source (MIT), the quoted rules, and what is ours |

### Why adapt instead of invent

The problem — a long-lived team whose sessions are all temporary — has been solved in
public with rules that survived contact with real use (overwrite, 4 KB, pointers not
transcripts). Copying three rules and crediting them is cheaper and more honest than
rediscovering them badly. What this project contributes is the node-typed form:
supersede-on-write puts the previous card in the same audit history as every other
fact, and `audit` enforces the budget on graphs edited outside the API.

---

## v0.9.0 — 2026-10-31

Status: **released**. Additive change: structured findings in `audit()`, with the
existing string lists untouched.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 203 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart, lifecycle, `examples/mcp_client.py` |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.9.0" |
| 6 | Version, changelog, tag, notes agree | ✅ 0.9.0 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 203 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.9.0` |
| 9 | `python3 tools/verify.py` green | ✅ including the artifact step |
| 10 | Backward compatibility tested | ✅ a test asserts `conflicts`/`hints` equal the findings' details in order |

### What changed for an agent, concretely

Before: `"<id>: blocked untouched for 3d (limit 3d)"` — to act on it you parse the
sentence and look up the owner. After: the same detail plus
`{"kind": "stale_work_item", "node": ..., "owner": "kimi", "age_days": 3,
"limit_days": 3}`. The string is still there; nothing that worked before breaks.

---

## v0.8.0 — 2026-10-31

Status: **released**. New capability: the staleness threshold is configurable, with
the default unchanged. No schema change, no migration.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 198 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart, lifecycle, `examples/mcp_client.py` |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.8.0" |
| 6 | Version, changelog, tag, notes agree | ✅ 0.8.0 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 198 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.8.0` |
| 9 | `python3 tools/verify.py` green | ✅ including the artifact step |
| 10 | New knob has measured justification | ✅ 3 → 1 → 0 conflicts at 3/7/14 days on the live graph; fallback behaviour tested |

### Default unchanged, on purpose

A weekly-sync team sees false alarms at 3 days and a monthly team sees none at 14.
The tool cannot know which team it is, so it keeps the original default and exposes
one environment variable — the same shape as `AMG_LOCK_TIMEOUT`, and for the same
reason.

---

## v0.7.7 — 2026-10-30

Status: **released**. First library change since 0.6.0: `audit` stops reporting
long-lived registration nodes as stale. Behaviour change, with a decision and tests.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 194 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart, lifecycle, `examples/mcp_client.py` |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.7.7" |
| 6 | Version, changelog, tag, notes agree | ✅ 0.7.7 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 194 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.7.7` |
| 9 | `python3 tools/verify.py` green | ✅ including the artifact step |
| 10 | Behaviour change has a decision and a red test first | ✅ DECISIONS #20; `test_registry_types_are_not_reported_stale` failed before the fix, and the companion test keeps unknown types checked |

### Why this is a patch, not a feature

It removes a false positive from an existing check; no new capability, no schema
change, no migration. But it *is* an output change, so the release notes say so
explicitly and the doc that quoted "4 conflicts" now says 3 with the breakdown.

---

## v0.7.6 — 2026-10-30

Status: **released**. No library change. Two quoted numbers get their context: the
stale-conflict count, and the load the timings were measured at.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 191 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart, lifecycle, `examples/mcp_client.py` |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set; no library code touched |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.7.6" — identical to 0.7.5 |
| 6 | Version, changelog, tag, notes agree | ✅ 0.7.6 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 191 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.7.6` |
| 9 | `python3 tools/verify.py` green | ✅ including the artifact step |

### A false positive, kept rather than papered over

One of the four pinned conflicts is a `group` node: long-lived by nature, flagged by a
rule that assumes a short-lived work item. Fixing it would mean changing what `audit`
reports for every user, so it is recorded as a finding for a decision, and the three
genuine work items stay visible. Making the number go to zero by editing statuses
would be the failure mode this page exists to prevent.

---

## v0.7.5 — 2026-10-30

Status: **released**. No library change. A measurement release: the real-world run
becomes a script, and a second live graph of different shape is measured.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 191 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart, lifecycle, `examples/mcp_client.py` |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set; no library code touched |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.7.5" — identical to 0.7.4 |
| 6 | Version, changelog, tag, notes agree | ✅ 0.7.5 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 191 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.7.5` |
| 9 | `python3 tools/verify.py` green | ✅ including the artifact step |
| 10 | Every published number reproducible | ✅ `benchmarks/real_graph.py` reproduces both live-graph tables |

### The point of the second graph

One graph's numbers kept being read as general properties. The second graph (0.44 MB,
no validity windows, legacy evidence throughout) shows which numbers are shape-driven:
the IR-4 conflict count (172 of 187 `done` nodes → 0 with the pin) tracks the legacy
evidence format, and write cost tracks bytes at ~10 ms/MB (4 ms at 0.44 MB, 153 ms at
15.4 MB). Reads stay single-digit milliseconds on both.

---

## v0.7.4 — 2026-10-30

Status: **released**. No library change. One-command verification, and warning
hygiene enforced by CI rather than remembered.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 191 tests ×4 (with `-W error::ResourceWarning`) + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart, lifecycle, `examples/mcp_client.py` |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set; no library code touched |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.7.4" — identical to 0.7.3 |
| 6 | Version, changelog, tag, notes agree | ✅ 0.7.4 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; wheel installed on five cells; sdist's own 191 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.7.4` |
| 9 | `python3 tools/verify.py` green | ✅ all steps passed (artifact step requires `dist/`) |

### Why a verification runner and not just a list

`docs/README.md` used to list six commands in no particular order; a reviewer had to
know which ones mattered and what a green run meant. One command with a table, and a
skipped step that is never counted as a pass, is a smaller claim to trust — and it is
the same set of checks CI performs, minus the platform matrix.

---

## v0.7.3 — 2026-10-30

Status: **released**. No library change. Adds a cross-protocol concurrency test
(two MCP servers + CLI + concurrent reader) and documents what it does not prove.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 191 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart, lifecycle, `examples/mcp_client.py` |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set; no library code touched |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.7.3" — identical to 0.7.2 |
| 6 | Version, changelog, tag, notes agree | ✅ 0.7.3 everywhere |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; wheel installed on five cells; sdist's own 191 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.7.3` |

### What this test is worth, stated narrowly

It is a regression guard for the v0.6.0 Windows failure (a read racing a replace),
not a general proof of safety under concurrency. The mutation check in
`docs/CONCURRENCY.md` shows the unlocked read is undetectable on POSIX, so the
Windows runner is what gives the test its teeth.

---

## v0.7.2 — 2026-10-30

Status: **released**. No library change. Adds a runnable MCP client, ships Python
examples in the sdist, and completes the install matrix (macOS, and 3.10 on two
platforms).

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 190 tests ×4 + `package` ×5 (ubuntu/macos/windows 3.12, ubuntu/windows 3.10) |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart, lifecycle **and the new `examples/mcp_client.py`**, in CI |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set; no library code touched |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.7.2" — identical to 0.7.1 |
| 6 | Version, changelog, tag, notes agree | ✅ 0.7.2 everywhere |
| 7 | Artifacts built, inspected, installed | ✅ `check_dist.py` clean (now requires the example); wheel installed on five cells; sdist's own 190 tests pass inside the archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.7.2` |

### What the client example proves that the tests did not

`tests/test_mcp.py` drives the handler directly with synthetic frames. The example
spawns the real server as a subprocess and speaks to it over pipes, so it also
covers process startup, stdio framing, and shutdown. It is deliberately able to
fail: step 3 asserts the *refusal* of an evidence-free write, so a regression that
lets MCP bypass the gate fails the build.

---

## v0.7.1 — 2026-10-30

Status: **released**. A packaging release: the sdist now contains everything its
own tests read, and CI builds the artifacts instead of trusting the checkout.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on five jobs | ✅ 190 tests ×4 platforms + the new `package` job (matrixed to eight jobs later the same day — see Standing checks) |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` |
| 3 | Examples run | ✅ quickstart + lifecycle |
| 4 | Every "not implemented" claim re-run against code | ✅ unchanged set; no library code touched in this release (`src/amg/` diff is the version string only) |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.7.1" — identical to 0.7.0 |
| 6 | Version, changelog, tag, notes agree | ✅ 0.7.1 everywhere |
| 7 | Artifacts built, inspected and installed from the tag | ✅ `check_dist.py` clean; wheel installed into a fresh venv; the sdist's **own 190 tests pass from inside the archive** |
| 8 | Clean install from the tag | ✅ `git+...@v0.7.1` (criterion 7 from v0.7.0) |

### What was wrong

0.7.0's sdist shipped `tests/` without `docs/`, `tools/` or `experiments/`. Its own
suite gave 17 errors and 4 failures, all file-not-found. The wheel was fine — which
is exactly why an install-only check would never have found it. `MANIFEST.in` fixes
the contents (70 KB → 376 KB) and `tools/check_dist.py` fails the build if a module
or document is absent from the artifact; expectations are derived from the working
tree, not listed.

### What to know before upgrading

No library change. If you vendor the sdist, it is now substantially larger because
it carries its documentation and experiments; the wheel is unchanged in shape.

---

## v0.7.0 — 2026-10-30

Status: **released**. A small release: one operational knob, one design note that
says "not built", and a reading index — plus a stale number in the README caught by
building the index.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on four jobs | ✅ 190 tests (1 environment-skipped), ubuntu 3.12/3.10, macos, windows |
| 2 | Documentation↔code symbol gate | ✅ README + every `docs/*.md` (12 at release time); the gate now derives its list instead of taking one |
| 3 | Examples run | ✅ quickstart + lifecycle |
| 4 | Every "not implemented" claim re-run against code | ✅ `socket`/`threading`/`encrypt`/`embedding`/`zlib`/fairness: no implementation (only prose asserting absence); designed-only history compression confirmed absent from `src/amg/` |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.7.0", naming history compression explicitly |
| 6 | Version, changelog, tag, notes agree | ✅ 0.7.0 everywhere |
| 7 | **Installed from the tag into a clean venv** (new criterion) | ✅ 0.7.0 from `git+...@v0.7.0`, zero dependencies, CLI + MCP exercised |

### Clean install from the tag (new standing check)

Until this release every test used `pip install -e .` against the checkout, so the
*artifact* had never been installed or run on its own. It is cheap to check and it
covers what an editable install cannot: the build backend, the console script, and
what actually lands in `site-packages`.

```bash
python3 -m venv /tmp/amg-install-test
/tmp/amg-install-test/bin/python -m pip install \
  "git+https://github.com/narkco-kang/agent-memory-graph@v0.7.0"
/tmp/amg-install-test/bin/amg version            # amg 0.7.0
/tmp/amg-install-test/bin/python -m pip show agent-memory-graph | grep Requires:
```

Result on 2026-10-30: install exit 0, `amg 0.7.0`, `Requires:` empty, and a graph
built entirely through the installed binary — `init`, `add`, `status`, a conclusion
with evidence, `search`, `check --strict`, `fingerprint`, `doctor`, `export
--format jsonl`, and an MCP `initialize` + `tools/list` handshake that reports
server version 0.7.0 over stdio. Only `pip` is present in the venv besides `amg`.

From v0.8.0 on this is a release criterion, not an anecdote.

### What to know before upgrading

`AMG_LOCK_TIMEOUT` is the only behaviour change: the lock timeout can now be
raised for bursty multi-writer use (on the live 15.6 MB graph, 8 × 5 writes exceeds
the 5 s default). The default is unchanged. No format change; no migration.

### What this release is honest about

- `docs/DESIGN-HISTORY.md` is a **proposal**: cheaper writes via zlib-sealed
  history segments, not implemented, with a trigger and six build items.
- The README's command count was wrong (16 vs 20). It is now a pointer to
  `docs/API.md`, and a test keeps it from rotting again.
- `docs/README.md` exists because a proposal can otherwise be read as a feature;
  every document is tagged with its status.

---

## v0.6.0 — 2026-10-30

Status: **released**. A concurrency-hardening release: one real Windows bug fixed,
one measured performance change, and the lock tail diagnosed rather than guessed.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on four jobs | ✅ 182 tests, ubuntu 3.12/3.10, macos, windows |
| 2 | Documentation↔code symbol gate | ✅ seven documents |
| 3 | Examples run | ✅ quickstart + lifecycle |
| 4 | Every change has a measurement behind it | ✅ backoff: throughput 700 → 870 writes/s, p50/p95 unchanged, tail unchanged; Windows fix: reproduced on CI before the fix |
| 5 | Not-shipped list updated | ✅ CHANGELOG "Not shipped in 0.6.0", including lock fairness |
| 6 | Version, changelog, tag, notes agree | ✅ 0.6.0 everywhere |

### What to know before upgrading

The Windows fix changes read behaviour: `Memory.open` now takes the lock while
reading, so an open can wait behind an in-flight write (milliseconds). In exchange,
a concurrent reader can no longer make a writer fail with `PermissionError
[WinError 5]`. On POSIX nothing observable changes.

---

## v0.5.0 — 2026-10-30

Status: **released**. A measurement release: two documents of numbers, no code
changes beyond the version string.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on four jobs | ✅ 176 tests (1 environment-skipped) |
| 2 | Documentation↔code symbol gate | ✅ six documents |
| 3 | Examples run | ✅ quickstart + lifecycle |
| 4 | Every claim is a measurement, not an estimate | ✅ real-graph numbers with the reproducible script; the one projection (history sidecar ≈ 30 ms) is labelled as a projection |
| 5 | No behaviour change claimed or implied | ✅ CHANGELOG opens by saying so; "Not shipped in 0.5.0" repeats the five gaps |
| 6 | Version, changelog, tag and notes agree | ✅ 0.5.0 everywhere |

### What this release is for

It makes two decisions auditable instead of memorable: what a live graph costs
(`docs/REAL-WORLD.md`) and why the obvious optimisations are not being done
(`docs/WRITE-COST.md`, DECISIONS #14). The value is in being able to disagree with
the numbers.

---

## v0.4.0 — 2026-10-30

Status: **released**. Scope: tamper detection, filesystem hygiene, an
authorization decision, and a prior-art check that took two claims away.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on four jobs | ✅ 176 tests, ubuntu 3.12/3.10, macos, windows |
| 2 | Documentation↔code symbol gate | ✅ four documents |
| 3 | Examples run | ✅ quickstart + lifecycle |
| 4 | Every "not implemented" claim re-run against code | ✅ commands re-executed; only matches are the sentences asserting absence |
| 5 | Unimplemented capabilities named | ✅ CHANGELOG "Not shipped in 0.4.0"; THREAT-MODEL §7a/§8 |
| 6 | New guarantees verified, not documented only | ✅ fingerprint: silent edit detected on a real adopted graph; hygiene: `doctor --strict` exits 1 on a world-writable graph, mcp warns without corrupting the protocol stream |
| 7 | Version, changelog, tag and release notes agree | ✅ 0.4.0 everywhere |

### What this release gives up

- Two "design commitments" are conceded to prior art: MAP-Graph implements and
  ablates both (docs/PRIOR-ART.md, DECISIONS #12). What remains claimed are three
  positions with their costs, not mechanisms.
- Authorization is dropped, with reasoning, rather than half-built (DECISIONS #13).

---

## v0.3.0 — 2026-10-30

Status: **released**. Scope: MCP server, read-only mode, threat model, Windows in
CI, and a pre-registered retrieval evaluation.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on four jobs (ubuntu 3.12 / 3.10, macos, windows) | ✅ 156 tests, all four jobs |
| 2 | Documentation↔code symbol gate | ✅ `README.md`, `docs/API.md`, `docs/THREAT-MODEL.md` |
| 3 | End-to-end examples run | ✅ `examples/quickstart.sh`, `examples/lifecycle.sh` |
| 4 | Unimplemented capabilities explicitly marked | ✅ CHANGELOG "Not shipped in 0.3.0"; THREAT-MODEL §8 |
| 5 | Read-only guarantee verified, not just documented | ✅ digest before/after over every write tool, plus an adopted real graph |
| 6 | Retrieval claims are measured or absent | ✅ baseline + two rejected candidates + blocked semantic arm |
| 7 | Version, changelog, tag and release notes agree | ✅ 0.3.0 in `pyproject.toml`, `src/amg/__init__.py`, CHANGELOG, tag |

### Not shipped (repeated here because it matters)

- Vector retrieval: two dependency-free candidates measured, both rejected; the
  semantic arm is blocked on embedding resources (`429`, code `1113`).
- Authentication / multi-tenancy: read-only bounds one session, it does not
  authenticate. Issue #4 stays open.
- Tamper-evident history, TTL scheduler, encryption at rest: absent by design or
  by scope, each stated in `docs/THREAT-MODEL.md` §7–§8.

### Known debt carried forward

- The four stale entries listed under v0.1.0 below are still stale; `audit` still
  exits 1 on the migrated graph by design, and no `--allow-stale` escape hatch
  exists.
- The retrieval eval corpus has 27 nodes; nothing there says how `recall@5`
  behaves at 10k nodes.

---

## v0.1.0 — 2026-10-29 (historical)

Status: **released** (kept for the record; superseded by 0.2.0 and 0.3.0).

## Definition of done

| # | Criterion | State |
|---|---|---|
| 1 | CI green: unit tests + doc↔code symbol gate + quickstart | ✅ 68 tests, gate cannot pass on phantom symbols |
| 2 | End-to-end example runs | ✅ `examples/quickstart.sh` |
| 3 | Documentation equals code | ✅ enforced by `tools/check_doc_symbols.py` |
| 4 | Unimplemented capabilities explicitly marked | ✅ README + CHANGELOG "Not yet" |
| 5 | Real-graph migration succeeds (6 criteria below) | ✅ measured, see below |
| 6 | LICENSE + CHANGELOG + release note | ✅ MIT, CHANGELOG.md, this file |
| 7 | Positioning reviewed independently | ✅ review complete; two claims downgraded to "design only, not implemented" in README (later superseded: both are prior art in MAP-Graph — see `docs/PRIOR-ART.md`, 0.4.0) |

## Known debt after adopting the real graph

`amg adopt` produces a graph where `check` passes with 0 errors. `amg audit`
still reports 4 conflicts, all of them **pre-existing staleness** (untouched for
more than `STALE_DAYS = 3`), not migration artefacts:

- `group.self`
- `decision.kg-per-group`
- `issue.anthropic-stream-tooluse-dropped`
- `freeze.FREEZE-20261025-112530`

Migration is judged by six criteria, all independently measured on the real
graph — **not by `audit --pin` exiting 0**:

1. `check` reports 0 errors
2. node count and change count match the source (1063 nodes; 2177 → 2178 changes
   because adoption itself is recorded)
3. no fabricated evidence (658 legacy strings stay in `legacy_evidence`,
   `evidence` stays empty, `content_sha256` never invented)
4. the exemption pin is self-consistent and recomputable
5. the pin is forward-only (a new write cannot hide behind it)
6. the source file is byte-identical before and after (`sha256` unchanged)

The 4 remaining stale entries are genuine pre-existing debt; suppressing them to
make the pin green would be exactly the fabrication criterion 3 forbids.

Policy (signed): no `--allow-stale` escape hatch will be added — such a flag
becomes the default path and silently voids the threshold. Each entry must
either be touched by its owner (status change with a note) or remain listed
here as known debt. Until then `audit` exits 1 by design.

## Not verified (state them, do not hide them)

- Windows locking; adopt under concurrency; any graph above 1,063 nodes.
- Python 3.10 / 3.12 exercised only in CI, not locally.
- Read-side audit ("who read what") is not implemented. Prior art exists
  (event-sourced audit logs, LangSmith-style traces), so it is not claimed as
  novel either.

## Positioning (pending independent sign-off)

We claim only: **task state as the authority face, expiry as a first-class
citizen, write-back discipline as a hard gate**, with hard authorization kept
separate from graded trust, and evidence requirements scaling with action risk.

Prior art that must be cited in the README before release: MAP-Graph
(arXiv:2608.10509), Letta MemFS, Graphiti (bi-temporal + provenance), Mem0,
A-MEM, Governed Shared Memory (arXiv:2606.24535). The phrase "no prior work"
must not appear anywhere.
