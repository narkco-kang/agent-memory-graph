# Where to start reading

This repository ships a lot of prose, because it ships a lot of measurements. This
page is the index: which document answers which question, in what order, and —
important — **which ones are contracts and which are proposals**.

## Read the status, not just the numbers

| Status | What it means | Documents |
|---|---|---|
| **Measured** | A script in this repo produces the numbers; CI runs the safety-critical ones. | `BENCHMARKS.md`, `REAL-WORLD.md`, `WRITE-COST.md`, `CONCURRENCY.md`, `ARCHIVE.md` |
| **Contract** | Enforced by code; the doc gate or a test fails when they disagree. | `API.md`, `THREAT-MODEL.md`, and the size budget below |
| **Proposal — not built** | Design work only. Nothing behind it ships. Do not quote it as a feature. | `DESIGN-HISTORY.md` |
| **Decision record** | Why something is the way it is, including what it costs and when to revisit. | `DECISIONS.md`, `PRIOR-ART.md` |
| **Operational guide** | How to run it, not what it does. | `SCHEDULING.md`, `OPERATIONS.md` |

## If you are deciding whether to depend on this

1. **`../README.md`** — what it is, the four invariants, and an explicit list of
   what it does **not** do.
2. **[`SECURITY.md`](../SECURITY.md)** — local single-user file store, no auth, no
   socket. Read this before putting it near anything untrusted.
3. **[`THREAT-MODEL.md`](THREAT-MODEL.md)** — the only real boundary is the OS user;
   what read-only mode does and does not stop; why authorization is out of scope
   rather than unfinished.
4. **[`REAL-WORLD.md`](REAL-WORLD.md)** — one live 1,249-node graph, so you can see
   what adopt, check, audit, expiry and a single write actually cost on non-synthetic
   data. Its limits are written down: one team, one week, macOS latencies only.

## If you are going to use it

1. `../README.md` quickstart, then **`bash examples/quickstart.sh`** (runnable, and
   CI keeps it runnable).
2. **[`API.md`](API.md)** — the CLI, the `Memory` methods and every error code. This
   is the contract that the symbol gate and the exit-code test enforce.
3. **[`SCHEDULING.md`](SCHEDULING.md)** — expiry is an explicit command by design;
   this page has copy-paste cron and systemd timer entries, plus when a daemon
   would actually be justified.
4. **`../examples/mcp_client.py`** — a working MCP client: handshake, tool
   inventory, a gated write refused, read-only enforced. Run it to see the
   protocol rather than read about it.
5. **[`HANDOFF.md`](HANDOFF.md)** — what a new session should read first: the
   bounded handover card, and the three rules it follows.
6. **[`ARCHIVE.md`](ARCHIVE.md)** — when the ledger outgrows the write budget:
   `amg archive` moves cold history out and proves the move on every run, with
   before/after numbers on two real graphs and an explicit list of what it does not do.
7. **[`ADOPTION.md`](ADOPTION.md)** — bringing an existing `group-kg/v1` graph in:
   the migration rules (nothing fabricated, nothing overwritten) and the measured
   result on a real 1063-node graph.

## The documentation budget (a contract, not a preference)

A document over its budget is a document nobody finishes. This repository enforces
**README.md and `docs/README.md` ≤ 12 KiB**, and **every other `docs/*.md` ≤ 24 KiB**,
with `tools/check_doc_sizes.py` in CI. The rule is adapted from a field-tested public
workbench (credited in `PRIOR-ART.md`), where handovers are capped at 4 KB and a
single skill at 12 KB.

When a document hits its budget, the answer is to **move detail to the document that
owns it** — not to delete it. That is why the README no longer carries the adoption
table or the full prior-art list: both moved to the document responsible for them, and
the README links. `CHANGELOG.md` and `RELEASE.md` are out of scope on purpose: they are
append-only logs, and a cap there would mean deleting history.

## If you are changing the storage layer

Read in this order; each one narrows the next:

1. **[`BENCHMARKS.md`](BENCHMARKS.md)** — synthetic 1k / 5k / 10k latency and size
   tables, plus how to reproduce them.
2. **[`REAL-WORLD.md`](REAL-WORLD.md)** — the same operations on a 15.6 MB live
   graph, where the write cost stops being negligible.
3. **[`WRITE-COST.md`](WRITE-COST.md)** — where the 147 ms goes (`changes[]` is
   79.1% of the bytes) and what each candidate optimisation buys, before any code
   is written.
4. **[`CONCURRENCY.md`](CONCURRENCY.md)** — 200 concurrent writes, throughput, and
   the tail-latency evidence that turned a guess into "starvation", plus the
   arithmetic showing why the default 5 s lock timeout is load-dependent.
5. **[`DESIGN-HISTORY.md`](DESIGN-HISTORY.md)** — the design for cheaper writes,
   and the reason the obvious version (history sidecar) is rejected. **Proposal:
   not implemented.**
6. **[`DECISIONS.md`](DECISIONS.md)** — the signed record, including decisions later
   reversed and the trigger conditions for revisiting each one.

## If you want to audit the claims

- **[`PRIOR-ART.md`](PRIOR-ART.md)** — five systems, what was verified in full text,
  what we take credit for and what we gave back. Quotes with page numbers; hit
  counts are used as index, not as proof.
- **[`DECISIONS.md`](DECISIONS.md)** — every entry states evidence and cost, and
  several record the author being wrong.
- **`../RELEASE.md`** — each release's checklist, so "we verified it" has a shape.

## Every document, one line each

| Document | Answers | Status |
|---|---|---|
| [`API.md`](API.md) | Commands, methods, error codes — the on-disk `amg/v1` contract | contract, CI-enforced |
| [`BENCHMARKS.md`](BENCHMARKS.md) | How fast on 1k/5k/10k synthetic nodes | measured |
| [`REAL-WORLD.md`](REAL-WORLD.md) | Two live graphs of different shape, and where their numbers disagree | measured |
| [`WRITE-COST.md`](WRITE-COST.md) | Where the write time goes, and what could move it | measured, all options rejected or deferred |
| [`CONCURRENCY.md`](CONCURRENCY.md) | What concurrent writers do; why the tail exists | measured |
| [`DESIGN-HISTORY.md`](DESIGN-HISTORY.md) | How to make writes cheap without losing atomicity | **proposal, not built** |
| [`OPERATIONS.md`](OPERATIONS.md) | Runbook: healthcheck, schedule, backups, burst sizing, failure meanings | operational guide |
| [`THREAT-MODEL.md`](THREAT-MODEL.md) | Who the security boundary is; what read-only cannot do | contract / decision |
| [`SCHEDULING.md`](SCHEDULING.md) | How to expire on a timer without a daemon | operational |
| [`HANDOFF.md`](HANDOFF.md) | The bounded handover card: four questions, one 4 KB answer | operational |
| [`PRIOR-ART.md`](PRIOR-ART.md) | What others did first, verified in full text | verified reference |
| [`DECISIONS.md`](DECISIONS.md) | Decisions, their evidence, their cost — including reversals | decision record |

Root-level documents: **[`../CHANGELOG.md`](../CHANGELOG.md)**, **`../RELEASE.md`**,
**[`../CONTRIBUTING.md`](../CONTRIBUTING.md)**, **[`../SECURITY.md`](../SECURITY.md)**.

## Check a claim yourself

```bash
python3 tools/verify.py    # every check below, in order, one table
```

That covers: unit tests with `ResourceWarning` promoted to an error, the
documentation↔code gate, both end-to-end examples, the MCP client, and the artifact
check when `dist/` exists. Individually:

```bash
PYTHONPATH=src python3 -W error::ResourceWarning -m unittest discover -s tests -v
python3 tools/check_doc_symbols.py                        # README + every docs/*.md
python3 benchmarks/real_graph.py <graph.json>             # the table in REAL-WORLD.md
bash examples/quickstart.sh && bash examples/lifecycle.sh
python3 examples/mcp_client.py                            # a real MCP session

# and the published artifact, separately from the checkout
TAG=v0.7.4   # replace with the tag you mean to audit
python3 -m venv /tmp/amg-install && /tmp/amg-install/bin/pip install \
  "git+https://github.com/narkco-kang/agent-memory-graph@$TAG"
/tmp/amg-install/bin/amg version

# build the artifacts and check what is inside them
python3 -m pip install build && python3 -m build --outdir dist .
python3 tools/check_dist.py dist
```

Commands run from the repository root. The doc gate and the clean install are not
redundant with the tests: a hand-written gate list hides documents, and an editable
install hides packaging mistakes — both passed silently until v0.7.0 (see
[`../RELEASE.md`](../RELEASE.md)).

Two deliberate habits, visible throughout:

- **No estimate passes as a measurement.** Where a number is extrapolated it is
  labelled a projection, in the same sentence.
- **Every "not implemented" claim is re-run against the code before a release.**
  The symbol gate catches "documented but missing"; it cannot catch "claimed absent
  but actually shipped", so that check is a manual step in `RELEASE.md`.
