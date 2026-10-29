# `valid_from` bias: is transaction time a usable proxy for fact time?

A graph records **when a fact was written**, not **when it became true**. The cheap
way out is to pretend the two are the same and derive `valid_from` from
`changes[].at`. This experiment measures how wrong that proxy is, using facts
whose true times we know.

This is the measurement behind `docs/DECISIONS.md` #5 ("never back-fill
`valid_from` from the change log") and it answers the v0.2 question: *do we need
an explicit fact-time input?*

## Pre-registered decision rule

Fixed before running, so the result cannot be rationalised afterwards:

> Fixture: 20 facts whose true time precedes their write time by 3 / 10 / 30 days
> (7 / 7 / 6). For each fact, compare the `changes[].at`-derived `valid_from` with
> the true fact time; `deviation = |derived − true|` in days.
> **If ≥ 30 % of the 20 facts deviate by more than 1 day, v0.2 MUST introduce an
> explicit fact-time input.** Otherwise keep the current behaviour and document
> the limit.

A 10-fact control group (`lag = 0`) is included so the metric is not rigged: it
measures the same quantity for facts that were written when they became true.

## Method

1. `fixture_legacy.json` — a legacy-shaped graph (`group-kg/v1`) with 30 facts and
   one `add-node` change per fact, whose `at` is the **write time**. The graph
   deliberately contains no `valid_from` / `valid_until`: legacy data has none.
2. `truth.json` — ground truth kept **outside** the graph: true fact time, write
   time and lag per fact. The graph never sees the truth.
3. Adopt the fixture with `amg adopt`, then, for each fact, take the
   `changes[].at` of its first `add-node` change as the value a naive back-fill
   would have used, and compare it with the truth.
4. `result.json` — rows + summary, written by the script.

Current implementation note: `amg adopt` refuses to invent `valid_from`
(`valid_from` stays `null`, nodes carry `valid_time_known: false`), so the
measurement reads the *transaction time a back-fill would have used*, not
`valid_from` itself. The measurement therefore does not depend on the safety
feature it is meant to justify, and the script asserts that the adopted nodes
still have `valid_from = null` and `valid_time_known = false`.

## Result (measured, 2026-10-30)

```
facts=30  adopt check ok=True
bucket     n     mean      min      max    >1d
3d         7     3.00     3.00     3.00   1.00
10d        7    10.00    10.00    10.00   1.00
30d        6    30.00    30.00    30.00   1.00
lagged >1d ratio : 20/20 = 100.0%  (threshold 30%)
control >1d ratio: 0/10 = 0.0%
all facts        : 20/30 = 66.7%
adopted valid_from all null: True
adopted valid_time_known all false: True
VERDICT: v0.2 MUST add an explicit fact-time input
```

Reading the numbers honestly:

- The lagged deviation is **exactly** the injected lag (3 / 10 / 30 days) — the
  proxy cannot recover the true time at all, it just re-labels the write time.
- The control group deviates 0 days, which is the useful half of the result: the
  proxy is not "always wrong", it is wrong **exactly by the writing lag**. So the
  30 %-threshold is met only because the fixture contains lagged facts; real
  graphs are a mixture, and the mixed ratio here is 66.7 %.
- The unmeasurable part is the real graph: on our own migrated graph (1063 nodes)
  the true fact times are **unknown**, so this deviation cannot be computed there.
  That unmeasurability is itself an argument for asking writers for the fact
  time instead of inferring it.

## Consequence for v0.2

Because the pre-registered threshold is met, v0.2 must accept an explicit fact
time rather than inferring one:

- `amg add --valid-from <iso8601>` / `Memory.add_node(valid_from=...)`, defaulting
  to "unknown" rather than to the write time;
- keep `valid_time_known` honest: a node with only a write time stays `false`;
- `audit` must keep treating unknown validity as hint-only (already implemented,
  `amg.audit.expiry_eligible`), otherwise adopting this input would start
  auto-expiring facts that were never dated.

## Limitations (do not over-read this)

- Fixture data is synthetic with exact day offsets; it measures the mechanism, not
  a production lag distribution. No claim is made about typical lag in the wild.
- Only the **adoption** path is measured. `add_node` also stamps `valid_from` from
  the wall clock, so new writes carry the same class of bias; that path was not
  separately measured here.
- Single machine, single Python version. No concurrency involved.

## Reproduce

```bash
python3 experiments/valid_from_bias/run_experiment.py
# rewrites fixture_legacy.json, truth.json, result.json in place
python -m unittest tests.test_valid_from_bias -v   # same numbers asserted in CI
```
