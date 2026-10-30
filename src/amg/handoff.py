"""The handoff card: one bounded record of where the work stands.

A session ends, a context window fills, an agent is swapped — and the next reader has
to answer four questions from one file, quickly: *who am I, where did we get to, what
is next, what is blocked*. That is not the same thing as a ranked search, and it is not
a status listing: it is a written handover.

The pattern is borrowed from a field-tested workbench (mashanglinyu/luanyujia-workbench,
`00-核心机制/二-记忆机制.md`), where it is called `§〇 交接` and has three rules we
adopt verbatim:

  * **overwrite, never append** — "where we are" has exactly one meaningful version;
  * **one size limit** — a handover nobody can read in 30 seconds is not a handover;
  * **pointers, not transcripts** — details belong to the nodes they describe.

So a handoff is a node of type `handoff` whose `note` is the card, and exactly one is
active at a time: writing a new one supersedes the previous, which keeps the history
auditable through the same ledger as every other change.
"""
from datetime import datetime, timezone

from .errors import ProtocolError

MAX_BYTES = 4096
TYPE = "handoff"


def bytes_of(note: str) -> int:
    return len((note or "").encode("utf-8"))


def active(doc: dict) -> dict:
    """The newest handoff that has not been superseded, or None."""
    cards = [n for n in doc.get("nodes") or []
             if n.get("type") == TYPE and n.get("status") != "superseded"]
    if not cards:
        return None
    return max(cards, key=lambda n: (n.get("updatedAt") or "", n.get("id") or ""))


def all_active(doc: dict) -> list:
    return [n for n in doc.get("nodes") or []
            if n.get("type") == TYPE and n.get("status") != "superseded"]


def render(node: dict) -> str:
    """The card as a reader should see it, with its budget stated."""
    return (node.get("note") or "").strip()


def write(memory, note: str, by: str, owner: str = None) -> dict:
    """Write a handoff card and supersede the previous one, in one transaction each.

    Two writes rather than one: adding the new node first means the supersede edge
    always points at something that exists, and if the second write fails the graph
    still has a valid (if untidy) state rather than a dangling reference.
    """
    text = (note or "").strip()
    if not text:
        raise ProtocolError("E_BAD_HANDOFF", "a handoff needs a note; an empty card is worse than none")
    size = bytes_of(text)
    if size > MAX_BYTES:
        raise ProtocolError(
            "E_HANDOFF_TOO_LARGE",
            f"handoff is {size} B, over the {MAX_BYTES} B limit — move detail into the "
            f"nodes it describes and leave pointers here")

    previous = active(memory.doc)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    node_id = f"handoff.{stamp}"
    # No valid_from: this is a registration of "where we are", not a fact with a
    # validity window, and superseding stamps valid_until — setting both made same-
    # second writes fail the check ("valid_until earlier than valid_from").
    created = memory.add_node(
        id=node_id, type=TYPE, label=f"handoff {stamp}", source=f"handoff written by {by}",
        status="open", owner=owner, note=text, by=by)
    if previous:
        memory.supersede(previous["id"], node_id,
                         note=f"replaced by handoff {stamp}", by=by)
    created["superseded"] = previous["id"] if previous else None
    created["bytes"] = size
    created["max_bytes"] = MAX_BYTES
    return created
