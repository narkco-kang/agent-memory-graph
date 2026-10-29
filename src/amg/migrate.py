"""Normalize legacy `changes[]` records to one canonical shape.

Never renumbers history and never invents a rev: unknown values stay null and
are reported, because a fabricated rev would be a lie the audit cannot see.
"""
CANONICAL = ("at", "by", "op", "target", "rev", "note")


def normalize(doc: dict) -> dict:
    changes = doc.get("changes") or []
    before = {}
    for c in changes:
        key = ",".join(sorted(c.keys()))
        before[key] = before.get(key, 0) + 1
    filled_target = filled_rev = 0
    for c in changes:
        if "target" not in c:
            c["target"] = None
            filled_target += 1
        if "rev" not in c:
            c["rev"] = None
            filled_rev += 1
        c.setdefault("by", "unknown")
        c.setdefault("note", "")
    after = {}
    for c in changes:
        key = ",".join(sorted(c.keys()))
        after[key] = after.get(key, 0) + 1
    return {
        "changed": int(filled_target or filled_rev),
        "records": len(changes),
        "shapes_before": before,
        "shapes_after": after,
        "filled_target": filled_target,
        "filled_rev": filled_rev,
        "note": "rev left null on legacy records on purpose; `amg check` reports them as hints",
    }
