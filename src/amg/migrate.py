"""Normalize legacy `changes[]` records to one canonical shape.

Never renumbers history and never invents a rev: unknown values stay null and
are reported, because a fabricated rev would be a lie the audit cannot see.

v0.22.0 also folds the legacy `detail` key into `note` instead of dropping it or
leaving a third shape in place (`issue.mem-arch-changes-key-shapes`): data is moved
where the protocol already keeps text, never discarded, and the shapes after a run are
reported so "is it normalized now?" is a reading, not a belief.
"""
CANONICAL = ("at", "by", "op", "target", "rev", "note")


def _shapes(changes):
    shapes = {}
    for c in changes:
        key = ",".join(sorted(c.keys()))
        shapes[key] = shapes.get(key, 0) + 1
    return shapes


def normalize(doc: dict) -> dict:
    changes = doc.get("changes") or []
    before = _shapes(changes)
    filled_target = filled_rev = folded_detail = 0
    for c in changes:
        if "target" not in c:
            c["target"] = None
            filled_target += 1
        if "rev" not in c:
            c["rev"] = None
            filled_rev += 1
        c.setdefault("by", "unknown")
        if "detail" in c:
            detail = c.pop("detail")
            if detail:
                note = str(c.get("note") or "").strip()
                c["note"] = f"{note} {detail}".strip() if note else str(detail)
                folded_detail += 1
        c.setdefault("note", "")
    after = _shapes(changes)
    extras = {key: count for key, count in after.items()
              if key != ",".join(sorted(CANONICAL))}
    return {
        "changed": int(bool(filled_target or filled_rev or folded_detail)),
        "records": len(changes),
        "shapes_before": before,
        "shapes_after": after,
        "filled_target": filled_target,
        "filled_rev": filled_rev,
        "folded_detail": folded_detail,
        "non_canonical_shapes": extras,
        "note": "rev left null on legacy records on purpose; `amg check` reports them as hints",
    }
