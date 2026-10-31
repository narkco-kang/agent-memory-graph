# Handoff cards: four questions, one bounded answer

A session ends. A context window fills. An agent is swapped for another model. The
next reader needs four things, fast:

1. **who am I** — which scope, which role;
2. **where did we get to** — what was done, with the evidence pointer;
3. **what is next** — the next action, in order;
4. **what is blocked** — and on whom.

A ranked search cannot answer that, and a status listing is not an answer. What
answers it is a short text somebody wrote on purpose. So the graph has a node type
for it: `handoff`.

```bash
amg handoff ./mem --by kimi --owner mini --note -   # write, reading the card from stdin
amg handoff ./mem                                   # print the active card
```

## The three rules, and where they come from

The pattern is taken from a field-tested workbench,
[mashanglinyu/luanyujia-workbench](https://github.com/mashanglinyu/luanyujia-workbench)
(`00-核心机制/二-记忆机制.md`, where it is called `§〇 交接`), because it had already
solved the failure this project also has: a long-lived agent team where every session
is temporary. Three of its rules transfer unchanged, and the third is the one people
break first:

| Rule | Why |
|---|---|
| **Overwrite, never append** | "Where we are" has exactly one meaningful version; appending turns the entry point into an archive nobody reads |
| **One size limit: 4,096 bytes** | A handover that takes longer than ~30 seconds to read does not get read, and then the discipline is decorative |
| **Pointers, not transcripts** | Detail belongs to the node it describes. The card says *where* the parser rewrite is documented, not how it went line by line |

The corresponding failure, from the same source: writing the card as a weekly report
("today I did 1, 2, 3, 4, 5"), which is both over budget and useless — after reading
it the newcomer still does not know what to do next.

## What this project adds that the source did not have

The source keeps handovers as Markdown files with a tool that archives the old version
and checks the size. Here the handover is a **node**, which buys three things for free:

- **the previous card is superseded, not deleted** — `valid_until` and a `supersedes`
  edge are stamped by the same code path as any other fact, so the history is
  auditable without a second file;
- **the budget is enforced twice** — the writer refuses an over-budget card
  (`E_HANDOFF_TOO_LARGE`, exit 2) and `audit` reports `handoff_over_budget` for a graph
  edited outside the API, so the limit is not merely advisory;
- **"exactly one active card" is a check, not a convention** — two active cards are a
  conflict (`multiple_active_handoffs`), which is what you get if two agents each write
  one without reading first.

`handoff` nodes are registrations, not work items, so they are exempt from the
staleness rule ([DECISIONS #20](decisions/20-staleness-applies-to-work.md)): a card does not become stale at three days, it becomes
stale when the work moves and nobody rewrites it.

## When to write one

- **before ending a session** that did work someone else will continue;
- **before changing model or agent** for a scope;
- **after a decision that changes direction**, because "where we are" changed.

Not after every message. A card written every turn is a log with a budget, which is
the worst of both.

## What a card looks like

```markdown
## Where we are
- did: adopted the 1,288-node legacy graph; audit pin stored at pin.json
- next: run the 8-writer burst on the real graph, then decide on fairness
- blocked: nothing
- pointers: docs/REAL-WORLD.md, docs/CONCURRENCY.md
```

Four bullets, each a pointer. That is under 300 bytes — the 4 KB limit is a ceiling,
not a target, and a card that needs 3 KB is usually a sign that detail belongs in a
node.
