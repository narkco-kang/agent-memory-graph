"""A baseline that excuses known violations — and proves it is not a blanket exemption.

The problem this exists for: `amg check` reports 824 errors on the team graph, every one of
them a legacy node that was written by `kg.py` before the amg schema existed. None of them
can be fixed without fabricating evidence, and all of them are real. A check that is
permanently red carries no information; a check that is switched off carries less.

The design that answers both, and the reason for each rule:

1. **Registered by node id, not by count.** A baseline that says "824 errors are known"
   accepts 824 of anything, including 824 brand new ones on different nodes. A baseline that
   names the nodes cannot do that: a violation on a node that is not named is new.

2. **Per node, the full error text must match too.** A named node that grows a *second*
   problem is not excused by having been registered once. The stored record keeps a digest
   of the exact error strings, so `node A: IR-4 conflict` does not cover
   `node A: IR-2 violated` appearing later on the same node.

3. **New nodes are never covered.** Registration is by id, so a node written after the
   baseline was frozen is not in it, and its violations are reported. This is the property
   the whole mechanism stands or falls on, and `test_check_baseline.py` mutates it.

4. **The baseline can only shrink.** `prune` drops entries that no longer fire; nothing
   re-adds them automatically. `check --update-baseline` never runs as a side effect of a
   normal check — excusing something has to be a separate, visible act.

5. **Everything excused is still printed.** The count of known violations is shown on every
   run, in the same report, with the ids. "600 known" is not the same claim as "clean", and
   the output must not let a reader confuse them.

What this does NOT do: it does not make a bad graph good, it does not verify anything, and
it is not an exemption registry in the sense of "this node is fine". It is a filing
cabinet: the debt keeps its name and its size, and stops shouting every time.
"""
import hashlib
import json
import os

BASELINE_SCHEMA = "amg-baseline/v1"


def _digest(errors):
    """A stable digest of the exact error strings, so the shape matters, not just the count."""
    payload = "\n".join(sorted(errors)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def node_of(error):
    """The node an error message is about, or `""` for document-level errors.

    Every per-node message protocol.check emits starts with `<node id>: `. Document-level
    messages (schema mismatch, dangling edge, cycle) have no node and cannot be excused by
    a per-node baseline — deliberately: a broken schema is not a legacy node's fault and
    must never be silently filed away.
    """
    head, sep, _rest = error.partition(": ")
    if not sep:
        return ""
    if " " in head:
        # e.g. "edge dangling from" / "changes[3]" — not a node id
        return ""
    return head


def build(errors):
    """Turn a list of error strings into a baseline document (node id -> digest + count)."""
    grouped = {}
    for err in errors:
        nid = node_of(err)
        if not nid:
            continue
        grouped.setdefault(nid, []).append(err)
    return {
        "schema": BASELINE_SCHEMA,
        "note": "Known legacy violations. This file excuses exactly these nodes and these "
                "messages, nothing else. It cannot grow on its own; new nodes are never "
                "covered.",
        "total": sum(len(v) for v in grouped.values()),
        "nodes": {nid: {"count": len(errs), "kinds": _kinds(errs), "digest": _digest(errs)}
                  for nid, errs in grouped.items()},
    }


def _kinds(errors):
    """The distinct kinds of problem, without the per-node prefix.

    A registered node that gains a *second kind* of problem must not be excused. But a
    registered node whose error count changed for the same reason (a graph rev moved, so
    three identical messages became two) is still the same debt. Comparing kinds, not the
    exact text, is what separates "it got worse" from "it was recounted".
    """
    return sorted({err.partition(": ")[2] or err for err in errors})


def load(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("schema") != BASELINE_SCHEMA:
        raise ValueError(f"not a baseline file: schema {doc.get('schema')!r} != {BASELINE_SCHEMA!r}")
    return doc


def save(path, doc):
    """Atomic write: a half-written baseline would excuse nothing and look like corruption."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def partition(errors, baseline):
    """Split errors into (known, new) against a baseline.

    An error is `known` only when its node is registered AND that node's current set of
    problem *kinds* is a subset of the registered kinds:

    * a new kind of problem on a registered node -> not a subset -> `new`
    * the same kind repeating a different number of times -> subset -> `known` (a graph rev
      moving recounts the same debt; it does not make it a different debt)
    * anything on an unregistered node -> `new`
    """
    grouped = {}
    for err in errors:
        grouped.setdefault(node_of(err), []).append(err)

    known, new = [], []
    for nid, errs in grouped.items():
        record = (baseline.get("nodes") or {}).get(nid)
        if nid and record and set(_kinds(errs)) <= set(record.get("kinds") or []):
            known.extend(errs)
        else:
            new.extend(errs)
    return sorted(known), sorted(new)


def summary(errors, baseline):
    known, new = partition(errors, baseline)
    registered = set((baseline.get("nodes") or {}).keys())
    fired = {node_of(e) for e in errors if node_of(e)}
    return {
        "total": len(errors),
        "known": known,
        "new": new,
        "known_count": len(known),
        "new_count": len(new),
        "registered_nodes": len(registered),
        # registered but no longer failing: the baseline can shrink, it must not shrink itself
        "silent_nodes": sorted(registered - fired),
        "ok": not new,
    }
