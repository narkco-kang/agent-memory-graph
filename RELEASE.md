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

## v0.29.0 — 2026-10-31

Status: **released**. A forged legacy digest fails the run; `done` and `conclusions`
finally use the same ruler.

| # | Criterion | State |
|---|---|---|
| 1 | Both defects found by the attacker, reproduced on the tag | ✅ Glm仔 N4 / N6 (`REATTACK-V0280-GLM.md`) |
| 2 | Falsified declaration and untested claim are separated by exit code | ✅ legacy mismatch → 1, never claimed → 3 |
| 3 | One ruler for evidence in every line | ✅ `done` uses `has_evidence` too |
| 4 | The fix is visible in the project's own numbers | ✅ `done without evidence` 292 → 108 |
| 5 | Malformed digests classified, not conflated | ✅ warning (debt), not failure |
| 6 | CI green on nine jobs | ✅ 337 tests ×4 + `package` ×5 |
| 7 | Documentation↔code gates | ✅ 16 documents |
| 8 | Nothing else changed | ✅ healthcheck verdicts/exit codes unchanged |
| 9 | Tag install verified | ✅ `git+...@v0.29.0` |
| 10 | Architecture diagram re-rendered | ✅ v0.29.0 |

---

## v0.28.1 — 2026-10-31

Status: **released**. Text-only patch: the bridge's report stops contradicting itself.

| # | Criterion | State |
|---|---|---|
| 1 | Reported by verifiers, reproduced on the tag | ✅ Glm仔/Hermes 复攻 v0.28.0 的文案毛刺 |
| 2 | No behaviour change | ✅ verdicts, exit codes, counts identical to 0.28.0 |
| 3 | The numbers in the line match the warnings | ✅ `41 unanchored, 165 unobservable` |
| 4 | No more `files found 0/0` | ✅ `no path: evidence rows` |
| 5 | CI green on nine jobs | ✅ 334 tests ×4 + `package` ×5 |
| 6 | Documentation↔code gates | ✅ 16 documents |
| 7 | Tag install verified | ✅ `git+...@v0.28.1` |
| 8 | Architecture diagram re-rendered | ✅ v0.28.1 |

---

## v0.28.0 — 2026-10-31

Status: **released**. The bridge's verdict stops disagreeing with its own report.

| # | Criterion | State |
|---|---|---|
| 1 | Two independent verifiers found the same mechanism | ✅ Glm仔 N3 (`REATTACK-V0270-GLM.md`), Hermes §2 (`VERIFY-V026-V027-*.md`) |
| 2 | One implementation, two documented postures | ✅ `verdict_of(require_full_anchoring=True)` for the bridge |
| 3 | Numbers describe the graph, not the storage shape | ✅ legacy verified strings count toward anchoring |
| 4 | `--strict` exists on the bridge and cannot turn a failure into a pass | ✅ test asserts breakage still wins |
| 5 | The stricter posture is justified in the runbook | ✅ `OPERATIONS.md` bridge section |
| 6 | CI green on nine jobs | ✅ 334 tests ×4 + `package` ×5 |
| 7 | Documentation↔code gates | ✅ 16 documents |
| 8 | Nothing else changed | ✅ healthcheck debt policy, adopt/audit/archive unchanged |
| 9 | Tag install verified | ✅ `git+...@v0.28.0` |
| 10 | Architecture diagram re-rendered | ✅ v0.28.0, four gates pass |

---

## v0.27.0 — 2026-10-31

Status: **released**. Thin anchoring warns, and `--no-evidence` stops printing a ratio.

| # | Criterion | State |
|---|---|---|
| 1 | Found by an attacker, not by the author | ✅ Glm仔 re-attack of v0.25.0, case X1 |
| 2 | The failure case is encoded as a test | ✅ 1 real anchor + 19 `cmd:` conclusions warns, `--strict` exits 1 |
| 3 | "Did not look" cannot print a percentage | ✅ `conclusions: not checked …`, JSON `null` |
| 4 | The policy stays explicit | ✅ low anchoring is a warning (debt), `--strict` is the switch |
| 5 | The bridge's real boundary is documented | ✅ legacy sources only; `amg/v1` → `E_ALREADY_AMG` |
| 6 | CI green on nine jobs | ✅ 330 tests ×4 + `package` ×5 |
| 7 | Documentation↔code gates | ✅ 16 documents |
| 8 | Nothing else changed | ✅ `adopt`/`audit`/pin/bridge formats unchanged |
| 9 | Tag install verified | ✅ `git+...@v0.27.0` |
| 10 | Architecture diagram re-rendered | ✅ v0.27.0, four gates pass |

---

## v0.26.0 — 2026-10-31

Status: **released**. The bridge's evidence base becomes an explicit input, legacy
declared digests are verified, and "did not look" fails a strict run.

| # | Criterion | State |
|---|---|---|
| 1 | Every item came from a verifier, not from the author | ✅ Hermes `VERIFY-V025-V0.11.md` + `VERIFY-BPLUS-V0.10.md` |
| 2 | The base is an input and is reported | ✅ `--evidence-root`, `evidence base: … (files found N/M, P%)` |
| 3 | Coverage can grow without fabricating a hash | ✅ legacy `path:x#sha256:h` verified read-only; malformed reported |
| 4 | "Did not look" fails a strict run | ✅ `not_checked` is a warning; `--no-evidence --strict` exits 1 |
| 5 | Field names say what they count | ✅ `unanchored_conclusions` |
| 6 | The false-alarm failure mode is documented with numbers | ✅ 0/240, 113/240, 89/240 in `OPERATIONS.md` |
| 7 | CI green on nine jobs | ✅ 328 tests ×4 + `package` ×5 |
| 8 | Documentation↔code gates | ✅ 16 documents; `OPERATIONS.md` 10556 B |
| 9 | The bridge stays read-only | ✅ test asserts the source bytes are unchanged |
| 10 | Clean install from the tag | ✅ `git+...@v0.26.0` |

---

## v0.25.0 — 2026-10-31

Status: **released**. Two false greens in the health report closed, plus the snapshot
bridge for graphs whose write path is another tool's.

| # | Criterion | State |
|---|---|---|
| 1 | Both defects reported by an adversary, reproduced, not assumed | ✅ `REATTACK-HEALTHCHECK-V0240.md` (gaps A and B) |
| 2 | The denominator is stated, not implied | ✅ `evidence rows` / `conclusions` / `done nodes` printed every run |
| 3 | "Did not look" cannot read as "looked and found nothing" | ✅ `not_checked` verdict, `healthy: false` |
| 4 | Exemptions are visible to logs | ✅ `unverified_accepted: true`, `strict_scope` in JSON |
| 5 | The bridge cannot move the false green one door down | ✅ reuses `healthcheck.collect()`; exits 3 when nothing verified |
| 6 | The bridge stays read-only on the source | ✅ test asserts `src_sha256` unchanged |
| 7 | Evidence resolution is not broken by the temp copy | ✅ `evidence_root` + test (would report every file `missing` otherwise) |
| 8 | CI green on nine jobs | ✅ 323 tests ×4 + `package` ×5 |
| 9 | Documentation↔code gates | ✅ 16 documents; `OPERATIONS.md` 9572 B |
| 10 | Clean install from the tag | ✅ `git+...@v0.25.0` |

---

## v0.24.1 — 2026-10-31

Status: **released**. Documentation round: "successful adoption" becomes six testable
criteria, and the wrong criterion is named.

| # | Criterion | State |
|---|---|---|
| 1 | The deliverable criterion existed as a finding, not a hunch | ✅ `issue.mem-arch-dod5-criterion-rewrite` (2026-10-29 adoption measurement) |
| 2 | Written in the owning document, not the README | ✅ `docs/ADOPTION.md` §What counts as a successful adoption |
| 3 | Each criterion is observable on the adopted copy | ✅ six checks, each names the command or the printed count |
| 4 | The wrong criterion is named as wrong, with its failure mode | ✅ exit `0` would push closing live items / widening the threshold |
| 5 | The definition cannot silently rot | ✅ 3 tests pin the section, the count, and the exit-code warning |
| 6 | No code change smuggled in | ✅ `adopt`/`audit`/pin format identical to 0.24.0 |
| 7 | CI green on nine jobs | ✅ 312 tests ×4 + `package` ×5 |
| 8 | Documentation↔code gates | ✅ 16 documents; `ADOPTION.md` 5088/24576 B |
| 9 | The scope statement stays honest | ✅ adopted graph is gated; `kg.py`-written graph is not |
| 10 | Clean install from the tag | ✅ `git+...@v0.24.1` |

---

## v0.24.0 — 2026-10-31

Status: **released**. Correctness-of-signal round: the health report stops calling
"nothing was verified" healthy.

| # | Criterion | State |
|---|---|---|
| 1 | The defect was reported by an adversary, reproduced, not assumed | ✅ `ATTACK-HEALTHCHECK-V023.md` §2.1–2.2 (cases B/C/D) |
| 2 | Fixed at the cause, not at the message | ✅ third verdict `unverified` + exit `3`; evidence coverage is a number, not a footnote |
| 3 | The wrong side of the boundary is now a failure too | ✅ `missing` / `not_a_file` / `unreadable` evidence fail; breakage outranks `unverified` |
| 4 | An escape hatch exists and cannot lie | ✅ `--allow-unverified` relaxes the exit code only; `healthy: false` in JSON |
| 5 | Regression tests for every case in the report | ✅ 8 new tests (16 total), including empty graph and partial coverage |
| 6 | Re-measured on the project's own graph | ✅ adopt 302/278/334 legacy strings: healthy(0) → UNVERIFIED(3); `amg init` empty: 0 → 3 |
| 7 | CI green on nine jobs | ✅ 309 tests ×4 + `package` ×5 |
| 8 | Documentation↔code gates | ✅ 16 documents; `DECISIONS` #34 added with detail moved out of #12/#17 (24569/24576 B) |
| 9 | The limits of the new verdict are stated | ✅ `OPERATIONS.md` verdict table; `healthy` ≠ correct content |
| 10 | Clean install from the tag | ✅ `git+...@v0.24.0` |

---

## v0.23.1 — 2026-10-31

Status: **released**. Patch for the Windows red that v0.23.0 shipped.

| # | Criterion | State |
|---|---|---|
| 1 | Failure diagnosed from CI, not assumed | ✅ `UnicodeEncodeError` on cp1252 stdout, three failing tests |
| 2 | Fixed at the cause | ✅ ASCII output + best-effort stream reconfigure |
| 3 | The failure has a regression test on every platform | ✅ `PYTHONIOENCODING=cp1252` run asserts problem line + verdict |
| 4 | CI green on nine jobs | ✅ 301 tests ×4 + `package` ×5 |
| 5 | Documentation↔code gates | ✅ 16 documents, sizes unchanged in meaning |
| 6 | No behaviour change beyond the fix | ✅ checks and classifications are identical |
| 7 | The story is in the log | ✅ CHANGELOG 0.23.1 |
| 8 | Clean install from the tag | ✅ `git+...@v0.23.1` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Reproducible | ✅ the code-page test reproduces the old crash path |

---

## v0.23.0 — 2026-10-31

Status: **released**. Operational-readiness round: one health command, one runbook, and
a 16-document budget that still fits.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 300 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 16 documents, both gates green |
| 3 | The tool answers a real operator question, once | ✅ `healthcheck` replaces four separate commands |
| 4 | Debt and breakage are separated | ✅ stale work warns; mismatched/outside-root evidence fails |
| 5 | The runbook cites measured numbers, not estimates | ✅ write costs, lock sizing, retrieval p50, archive effect |
| 6 | The limits are in the same document | ✅ single user, no auth, cold start unverified, Windows latency unmeasured |
| 7 | The report is tested, including failure modes | ✅ 7 tests |
| 8 | Clean install from the tag | ✅ `git+...@v0.23.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | No unmeasured claim creeps in | ✅ Not-shipped says the report is not a correctness proof |

---

## v0.22.0 — 2026-10-31

Status: **released**. Maintenance round: canonical `changes[]`, a truthful `check` hint,
and documentation re-homed before the size gates went red.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 293 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents; API 553 B and DECISIONS 33 B of headroom restored by moving detail |
| 3 | The defect was reproduced first | ✅ legacy `detail` record kept a third shape; `check` advised migrate after migrate |
| 4 | No data is deleted to normalize | ✅ `detail` is folded into `note` and counted; nothing dropped |
| 5 | The new behaviour is idempotent | ✅ second `migrate` reports `changed: 0` |
| 6 | Old behaviour still covered | ✅ pre-migrate hint still says "run `amg migrate`" |
| 7 | Content moved, not deleted, for the budget | ✅ adoption list → `ADOPTION.md`; decisions #9/#10 → owning docs |
| 8 | Clean install from the tag | ✅ `git+...@v0.22.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | The finding is in the log | ✅ CHANGELOG 0.22.0 + DECISIONS #33 |

---

## v0.21.0 — 2026-10-31

Status: **released**. Post-release review round: three boundary defects fixed, each with a
regression test, and the one that was a security exposure fixed by confinement.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 290 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents; DECISIONS moved detail to owning docs to fit |
| 3 | The defects were reproduced before being fixed | ✅ issues carry exit codes/JSON readings; tests encode them |
| 4 | The security defect is closed by refusal, not warning | ✅ outside-root evidence is never opened, exit 1 |
| 5 | Strict means strict | ✅ `all_verified` required; JSON `ok` matches the exit code |
| 6 | The flagged parameter does what it says | ✅ k=10 with 12 live hits now returns archived hits, per file |
| 7 | Old behaviour preserved where it was defensible | ✅ k < 5 order unchanged; live-only searches untouched |
| 8 | Clean install from the tag | ✅ `git+...@v0.21.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | The residual limits are stated | ✅ Not-shipped: no persisted verified state, quota is a floor |

---

## v0.20.0 — 2026-10-31

Status: **released**. Closes R3 from the retrieval attack brief with an observation
mechanism plus disclosure — not with a promise the library cannot keep.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 280 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents; DECISIONS trimmed by moving detail to the docs that own it |
| 3 | The finding is reproduced before it is fixed | ✅ the attack is a test: fake hash passes the gate, shows `present`, is caught by `verify-evidence` |
| 4 | Only what can be observed is called verified | ✅ `cmd:`/`url:`/`sha256:` = `unverifiable`, never `ok` |
| 5 | The limitation is in the product text | ✅ `docs/API.md`, `docs/THREAT-MODEL.md`, README |
| 6 | Not-shipped boundary is explicit | ✅ no per-read verification, no anchor split, `--strict` ≠ verified |
| 7 | Dead code is now used or removed | ✅ `sha256_of_file` is the verifier's hashing primitive |
| 8 | Clean install from the tag | ✅ `git+...@v0.20.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Reproducible | ✅ `amg verify-evidence` on a two-node graph, both outcomes in the tests |

The shape of the round: an unverifiable claim cannot be fixed by labelling it verified;
it can be fixed by making the observable part observable, and by saying plainly which
part is not.

---

## v0.19.1 — 2026-10-31

Status: **released**. Patch for a red CI that v0.19.0 shipped with on one platform.

| # | Criterion | State |
|---|---|---|
| 1 | The failure is diagnosed, not retried | ✅ CRLF: content 24,450 B, Windows checkout ~+300 B, budget 24,576 B |
| 2 | The fix is in the gate, not in the document | ✅ LF normalization in `check_doc_sizes.py`; no doc trimmed |
| 3 | The failure has a test | ✅ CRLF fixture whose LF content is inside budget passes |
| 4 | CI green on nine jobs (including `windows-latest`) | ✅ 269 tests ×4 + `package` ×5 |
| 5 | Documentation↔code gates unchanged in meaning | ✅ budgets untouched (12 KiB / 24 KiB) |
| 6 | No product behaviour change | ✅ `src/amg/` unchanged from v0.19.0 |
| 7 | The story is in the log | ✅ CHANGELOG 0.19.1 |
| 8 | Clean install from the tag | ✅ `git+...@v0.19.1` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Reproducible | ✅ the failing size is reproduced by the new test on any platform |

---

## v0.19.0 — 2026-10-31

Status: **released**. Defect round with a behaviour-preserving bar: bounded scores and
`score_kind`, verified to change no ranking.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 268 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents, both gates green |
| 3 | Criteria existed before the code changed | ✅ `experiments/score_scale/PREREGISTRATION.md` |
| 4 | The claim is verified, not asserted | ✅ every ranked id list + metric identical to v0.18.0 on four corpora |
| 5 | Residual weakness published | ✅ 1.375× drift vs 3.799× before; issue stays open as "bounded, not invariant" |
| 6 | My own criterion errors recorded | ✅ Amendment A: bound 3.0→7.0, ±5%→+37% |
| 7 | The change is in the product text | ✅ `docs/API.md`, README, MCP tool description, DECISIONS #30 |
| 8 | Clean install from the tag | ✅ `git+...@v0.19.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Reproducible from the repo | ✅ `experiments/score_scale/run_eval.py`, both scorers in one process |

The round's shape: a defect fix is only a defect fix if it moves nothing else — so the
acceptance test is equality, and the two things that did move (drift and the criterion
arithmetic) are written down instead of glossed.

---

## v0.18.0 — 2026-10-31

Status: **released**. Behaviour-change round: IDF term weights, pre-registered, with a
missed target published next to the wins.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 261 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents, both gates green |
| 3 | Criteria and predictions existed before the code changed | ✅ `experiments/retrieval_idf/PREREGISTRATION.md` |
| 4 | The baseline was frozen, not remembered | ✅ v0.17.0 scorer kept as `baseline.py`, run in the same process |
| 5 | Every outcome published, including a missed target | ✅ N2 r@5 0.538 against target 0.70, with the structural reason |
| 6 | Predictions that were wrong are recorded as wrong | ✅ small-corpus gain; N3 baseline |
| 7 | The change is in the product text | ✅ README, `docs/API.md`, `docs/BENCHMARKS.md`, DECISIONS #28 |
| 8 | Clean install from the tag | ✅ `git+...@v0.18.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Reproducible from the repo | ✅ `run_eval.py` rebuilds all four corpora deterministically and records their digests |

The honest shape of the round: one change lifted the frozen baseline and the realistic
noise model to the same number (0.865), and left the adversarial model exactly where it
was — because that model was built to be invariant to precisely this statistic.

---

## v0.17.0 — 2026-10-31

Status: **released**. Measurement round: retrieval at 10,000 nodes, pre-registered, with
one amendment and two wrong predictions recorded.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 255 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents, both gates green |
| 3 | Criteria and predictions existed before the run | ✅ `PREREGISTRATION.md`, including a prediction that was wrong |
| 4 | Amendment declared before the run it applies to | ✅ N2 noise model added after N1, predicted before N2 ran |
| 5 | No tuning in the same round | ✅ no `src/` change; criterion C4 |
| 6 | The weak result is in the product text | ✅ README + `docs/API.md` now say scoring has no IDF, with the numbers |
| 7 | Frozen baseline untouched | ✅ `retrieval_eval/result.json` and its pinned numbers unchanged |
| 8 | Clean install from the tag | ✅ `git+...@v0.17.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Reproducible from the repo | ✅ `run_eval.py` rebuilds both corpora deterministically and records digests |

The headline is uncomfortable in a useful way: making the graph 370× bigger changed
nothing, while making the noise *relevant* cost a quarter of recall@5 — and the fixed
cost is in the scorer, which this round deliberately did not touch.

---

## v0.16.0 — 2026-10-31

Status: **released**. Measurement round: 10k-node concurrency, pre-registered, with a
failing configuration shipped alongside the passing one.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 255 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents, both gates green |
| 3 | Criteria existed before the run | ✅ `PREREGISTRATION-10k.md`, with predictions |
| 4 | Every outcome recorded, including failures | ✅ run 1 (`LockTimeout`) and run 2 (pass) both in the repository |
| 5 | Predictions that were wrong are recorded as wrong | ✅ p50 did not inflate; worst wait was not < 5 s |
| 6 | The finding changes a decision, not a claim | ✅ DECISIONS #26 keeps the 5 s default and writes the sizing rule |
| 7 | The other claim (10k recall) was **not** quietly upgraded | ✅ it stays in "not shipped" |
| 8 | Clean install from the tag | ✅ `git+...@v0.16.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Reproduce instructions run as written | ✅ `build_10k.py` + `run_stress.py --graph` (documented commands, executed) |

No `src/amg/` change. The deliverable is a measured limit and a rule for sizing the
timeout — because the honest answer to "does it work at 10k?" was "yes, and not with
the default settings".

---

## v0.15.0 — 2026-10-31

Status: **released**. The archive is reachable over MCP; two false "not implemented"
claims are corrected.

| # | Criterion | State |
|---|---|---|
| 1 | CI green on nine jobs | ✅ 255 tests ×4 + `package` ×5 |
| 2 | Documentation↔code symbol gate + size budget | ✅ 15 documents, both gates green |
| 3 | The MCP change is pinned by a test | ✅ `include_archive` in the schema, tool count still 8, refusal on L3 tested over JSON-RPC |
| 4 | Every corrected claim cites evidence | ✅ windows-latest job log (test names), `BENCHMARKS.md` table; recorded in the CHANGELOG |
| 5 | Correction cut both ways | ✅ two claims were *understated*, not just overstated — underclaiming is drift too |
| 6 | No behaviour change outside MCP | ✅ CLI/library archive path untouched; 255 tests |
| 7 | Artifacts checked and installed | ✅ `check_dist.py` clean; sdist's own 255 tests pass inside the unpacked archive |
| 8 | Clean install from the tag | ✅ `git+...@v0.15.0` |
| 9 | `python3 tools/verify.py` green | ✅ nine steps, 0 skipped |
| 10 | Not-shipped list re-audited, not copied | ✅ README / store docstring / ARCHIVE / API paragraphs re-read against code and CI |

The uncomfortable part of this release is that the wrong claims were in the *safe*
direction: saying "unverified" when the matrix verifies it costs credibility in a way
that a reader cannot detect. An audit that only removes overclaims is not an audit.

---

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
