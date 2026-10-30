# Prior art, verified

This file exists because a prior-art claim that nobody checked is worse than no
claim: it wins an argument it should lose. The README cites five systems; two of
them were cited from a second-hand summary. This is the independent check.

## Method (so the check can be re-run)

- Primary source: `arxiv.org/api/query?id_list=…`, retrieved 2026-10-30 05:00 UTC.
- Full text: PDF `arXiv:2608.10509v1`, 14 pages, 67,906 characters extracted with
  `pypdf`, keyword scan + quote reads. Paper dated 2026-08-11.
- Keywords counted over the **body text** (bibliography included, so a term that
  only appears in a reference is called out as such). Counting is a heuristic: a
  zero means "this scan did not find it", not "proven absent".

| term | hits | note |
|---|---|---|
| `expir*` | **0** | no expiry mechanism anywhere in the text |
| `TTL` | 1 | only inside a bibliography entry (a CAMEL reference), not a mechanism |
| `supersed*` | 3 | all three say supersession is **not** implemented |
| `revok*` | 24 | revocation is a first-class event |
| `write-time` | 1 | scope intersection at write time (authorization, not evidence) |
| `task state` | **0** | the graph is not a task-state store |
| `embedding` | 6 | retrieval is semantic (embeddings), not lexical |

## What MAP-Graph (arXiv:2608.10509) actually is

> "MAP-Graph, a provenance-aware memory layer that represents agents, sources,
> memories, claims, and actions in a typed execution graph. It traces ancestry,
> excludes permission-ineligible records, reranks eligible memories by semantic
> similarity and multiplicative path trust, and applies a risk-sensitive gate
> before action execution while retaining affected lineage for audit." — p1

> "Once an action is proposed, a risk-sensitive gate re-evaluates its supporting
> memories. Affected descendants remain marked rather than deleted, preserving
> evidence for audit while constraining downstream use." — p2

Evaluated on 2,700 synthetic tasks per method across three domains: 94.96% overall
task success, 72.70% exact decision accuracy, 90.22% clean setting; seven
baselines, six ablations, two extra backbones.

**Hard authorization and graded trust are separated, and evidence requirements
scale with action risk.** That is the paper's stated contribution ("Existing
approaches … do not clearly separate hard authorization from graded trust or adapt
evidence requirements to action risk"). Both of our "design commitments" are
therefore **prior art, not our ideas** — they are implemented and ablated there.

## What it explicitly does not do

> "Semantically equivalent entries are not merged, and new observations do not
> mutate or supersede prior text; **no generic supersession or conflict-resolution
> state machine is implemented**." — p3

> "The write path rejects empty text" — p3 (the extent of write-time validation)

So: no supersession state machine, no conflict resolution, no time-based expiry,
and the graph is not a task-state store. Revocation is event-driven
(`revoke_permission`), which is not expiry: it fires when a human or policy says
so, not when a fact's validity window ends.

## Claim-by-claim

| Claim in the README / graph | Verdict | Action |
|---|---|---|
| "multi-agent shared memory with provenance" | **supported** | keep |
| "task scope" | **not supported as worded** — the paper scopes *access* (permission-eligible records) and gates *actions*; it does not scope memory by task | reworded to "scoped access and an action-level risk gate" |
| "risk gating" | **supported** (risk-sensitive gate before action execution) | keep |
| "closest prior work" | **supported** — same problem framing, direct overlap | keep |
| "we separate hard authorization from graded trust" (as our commitment) | **not ours** — implemented and ablated in MAP-Graph | reworded to prior art |
| "evidence requirements scale with action risk" (as our commitment) | **not ours** | reworded to prior art |
| "Governed Shared Memory (2606.24535) reports a synchronous near-duplicate gate pre-empting the async contradiction detector" | **supported** (abstract) | keep; relevant to any future dedup gate |

## What is left that we can claim (positions, not inventions)

Nothing here is a novel mechanism, and the README says so. Stated as positions:

1. **The graph is the state of record.** Nodes are tasks, decisions, issues,
   artifacts — the durable answer to "what is true about this project" — not a
   retrieval layer sitting beside it. MAP-Graph's graph exists to decide whether
   an agent may *use* a memory; ours is where the project's state *lives*.
2. **Expiry and supersession are first-class, with fact time.** `valid_from` /
   `valid_until` are supplied by the writer, never inferred from write time
   (measured: the write-time proxy mis-dates lagged facts in 20/20 cases), and
   `superseded` nodes are filtered out of retrieval rather than merged. MAP-Graph
   explicitly implements no supersession state machine.
3. **Evidence is required at write time for conclusions.** The gate fires when a
   conclusion-typed node is recorded, not when an action is proposed. MAP-Graph's
   write path rejects empty text; its evidence logic lives at action time.

Each of these is a *design position* with a cost (a write-time gate can block
legitimate work; fact time must come from the caller), not a capability win.

## Limitations of this check

- One paper read closely (2608.10509); 2606.24535 checked at abstract level only.
- Keyword counts cannot prove absence; the quotes are the evidence, the counts are
  the index.
- The other three cited systems (Letta MemFS, Graphiti, Mem0/A-MEM) were verified
  earlier from their repositories and docs; this file does not re-verify them.
