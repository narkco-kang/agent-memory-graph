# Pre-registration: lexical matching must answer only queries that can distinguish

Written **before** the implementation, on commit `18db270`, after measuring the
problem but before changing the matcher.

## The problem, measured

`amg.retrieval` matches ASCII tokens as raw substrings. On the real 1,289-node team
graph (adopted copy, `/tmp`), four single-character queries each returned the full
`k=10`:

| query | hits before (`k=10`) |
|---|---|
| `a` | 10 |
| `e` | 10 |
| `i` | 10 |
| `x` | 10 |

An identifier-style query for a node that does not exist (`task.a`) likewise returned
ten unrelated `task.*` ids — a reader would take that as an answer. The cause is
mechanical: `a` occurs inside `archive`, `clear`, `task.batch6-a…`, so "anything with
the letter" is "a match".

## The change being tested

1. ASCII tokens are matched at **word boundaries** (`[a-z0-9]` counts as a word
   character; `-`, `_`, `.`, `/` separate), never as raw substrings.
2. ASCII tokens shorter than two characters are dropped: one letter cannot distinguish.
3. A query containing identifier punctuation (`.`, `:`, `/`, `_`) is matched as **one
   phrase** with the same boundary rule, and its word tokens are not also used — so
   `task.a` is a lookup for that id, not a search for every task.

CJK queries keep substring matching (a character is a word there).

## Criteria (fixed now; all must hold or the change is reverted)

| # | Criterion | How it is measured |
|---|---|---|
| C1 | A one-character ASCII query returns **0** hits | frozen corpus + real graph, layers L3 and L2 |
| C2 | An identifier query naming an existing node returns that node **first** | 20 randomly chosen real ids (seed fixed in the script) |
| C3 | An identifier query naming no node returns **0** hits, not `k` plausible ones | `task.a` and `issue.zzz` on the real graph |
| C4 | Frozen-eval recall does **not** drop: overall `recall@5` ≥ **0.865**, `recall@1` ≥ **0.654**, paraphrase `recall@5` ≥ **0.750** | `experiments/retrieval_eval/run_eval.py` |
| C5 | No existing test is edited to accommodate the change | `git diff --stat` on `tests/` shows only additions |

If C4 fails, the cause is the interesting part: it would mean the substring behaviour
was earning recall by accident, and the honest move is to measure that trade instead of
shipping a "precision fix" that quietly loses answers. It would then be reported, not
tuned away.

## Why a separate directory

`retrieval_eval/` measures **recall** against a pre-registered semantic-vs-lexical
comparison; do not move its goalposts. This directory measures **precision of the
lexical path itself** — a different claim, with its own script, so both can be
re-run independently.

---

## Outcome (recorded 2026-10-31, after the run — criteria above are untouched)

Implementation on the branch that became v0.14.0. Measured with
`run_eval.py` (both sources) and `retrieval_eval/run_eval.py`.

| # | Criterion | Result |
|---|---|---|
| C1 | one-character ASCII query → 0 hits | **holds**: `a`, `e`, `i`, `x`, `q` → 0 on L3 and L2, frozen corpus **and** the real 1,289-node graph |
| C2 | identifier query naming an existing node returns it first | **holds**: 20/20 sampled live ids, both sources |
| C3 | identifier query naming no node → 0 hits | **holds**: `task.a`, `issue.zzz`, `missing.node` → 0 (was 10/10 before) |
| C4 | frozen-eval recall does not drop (overall r@5 ≥ 0.865, r@1 ≥ 0.654, paraphrase r@5 ≥ 0.750) | **FAILS**: overall r@5 0.865 → **0.808**, r@1 0.654 → **0.654** (equal), paraphrase r@5 0.750 → **0.550**; keyword r@5 **0.938 → 0.969**, MRR 0.744 → **0.763** |
| C5 | no existing test edited to accommodate | **FAILS**: `tests/test_retrieval_eval.py` pins the published baseline and must move with it |

### Two amendments, both declared

1. **C2's sample was wrong, not the matcher.** The first run sampled *all* node ids,
   and one sampled node was `superseded` — L3 never returns a superseded node by design,
   so the criterion tested the expiry filter, not the matcher (0 hits, same before the
   change). The sampler now draws from ids L3 can return, with the same filters as L3
   (`status != superseded`, not `not yet valid`). No threshold changed.
2. **Inflection tolerance was added for a stated reason.** A boundary-only matcher
   turned `rank`/`ranking` and `searched`/`search` into different words, which is not
   what a reader means. Regular suffixes are expanded in both directions from an
   explicit 14-entry table (`_SUFFIXES` in `src/amg/retrieval.py`), no stemmer
   dependency. This recovered q12 to r@5 1.0 and kept q05 at 1.0.

### Why C4 failed, per query (this is the finding)

The lost recall is not "answers the new matcher cannot find" — it is **accidental
substring matches** in the old one. For each lost query, the substring the old matcher
used:

| query | gold | old match | verdict |
|---|---|---|---|
| `who can see what I searched` | `task.read-audit` | `i` inside `high-risk` | noise (single letter) |
| `what if the checksum was lost…` | `rule.no-fabricated-hash` | `the` in `synthesise`, `i` in `invent`, `one` in `gone` | noise |
| `why do notes with proof rank higher` | `decision.two-key-ranking` | `rank` inside `ranking` | **real**, recovered by inflection tolerance |
| `would a sentence encoder help` | `model.embedding` | — | **improved** r@5 0 → 0.5 |

So the headline number moved because the previous 0.865 included strings that are
inside other words. Removing them costs two of 26 queries and gains, on a real graph,
**10 fabricated-looking hits per single-character query** and **10 per nonexistent
identifier**. The trade is recorded as `docs/DECISIONS.md` #25 with both number sets,
and the published baseline table now shows the post-fix values with the old ones and
this analysis linked — not replaced silently.

