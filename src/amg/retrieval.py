"""L3 lexical retrieval. Vector search is NOT implemented in v0.1.

Two hard rules (signed, failures.md:118):
- `superseded` nodes are filtered out for L1/L3/L4. Expiry is a first-class
  citizen, so a stale fact must never come back as an answer. History is not
  lost: it stays in L2 (`changes[]`), which is the only layer that shows it.
- Nodes whose `valid_from` is in the future are not yet in effect, so they are
  filtered from L1/L3/L4 too (audit reports them as "not yet valid").
- Ranking is deliberately two-key: (anchor_present, score). Degraded results are
  returned with anchor_state="none" instead of being silently dropped; `strict`
  is the only path that filters them out.
"""
import re

from .const import CONCLUSION_TYPES, not_yet_valid

_TOKEN = re.compile(r"[a-z0-9_\-]+")
_CJK = re.compile(r"[\u3400-\u9fff]")

WEIGHTS = {"id": 3.0, "label": 2.0, "note": 1.0, "source": 0.5, "owner": 0.5}


def _tokens(query: str):
    q = query.strip().lower()
    toks = _TOKEN.findall(q)
    if _CJK.search(q):
        toks.append(q)
        toks.extend(ch for ch in q if _CJK.match(ch))
    return [t for t in toks if t]


def search(doc: dict, query: str, layer: str = "L3", k: int = 10, strict: bool = False):
    if layer not in {"L1", "L2", "L3", "L4"}:
        from .errors import ProtocolError
        raise ProtocolError("E_BAD_LAYER", f"unknown layer: {layer} (use L1/L2/L3/L4)")
    toks = _tokens(query)
    if not toks:
        return []

    if layer == "L2":
        return _search_changes(doc, toks, k)

    # Hard filters first: a superseded or not-yet-effective fact is never an
    # answer (L2 keeps history, so neither rule hides the event log).
    nodes = [n for n in (doc.get("nodes") or [])
             if n.get("status") != "superseded" and not not_yet_valid(n)]
    if layer == "L1":
        nodes = [n for n in nodes if n.get("status") in {"open", "in_progress", "blocked", "proposed"}]
    elif layer == "L4":
        nodes = [n for n in nodes if n.get("type") == "rule"]

    hits = []
    for n in nodes:
        score, fields = 0.0, []
        for field, weight in WEIGHTS.items():
            value = str(n.get(field) or "").lower()
            if not value:
                continue
            for t in toks:
                if t in value:
                    score += weight
                    if field not in fields:
                        fields.append(field)
        if score <= 0:
            continue
        ev = n.get("evidence") or []
        hits.append({
            "id": n.get("id"),
            "label": n.get("label"),
            "type": n.get("type"),
            "status": n.get("status"),
            "score": round(score, 3),
            "matched_fields": fields,
            "anchor_state": "present" if ev else "none",
            "evidence_count": len(ev),
            "evidence_grade": n.get("evidence_grade"),
            "conclusion": bool(n.get("conclusion") or n.get("type") in CONCLUSION_TYPES),
        })
    if strict:
        hits = [h for h in hits if h["anchor_state"] == "present"]
    hits.sort(key=lambda h: (h["anchor_state"] == "present", h["score"], h["id"] or ""), reverse=True)
    return hits[:k]


def _search_changes(doc: dict, toks, k: int):
    hits = []
    nodes = {n.get("id"): n for n in doc.get("nodes") or []}
    for c in doc.get("changes") or []:
        text = f"{c.get('op','')} {c.get('target','')} {c.get('note','')}".lower()
        if any(t in text for t in toks):
            target = c.get("target")
            node = nodes.get(target) or {}
            hits.append({
                "id": target,
                "label": node.get("label"),
                "type": "change",
                "status": node.get("status"),
                "score": 1.0,
                "matched_fields": ["changes"],
                "anchor_state": "present" if node.get("evidence") else "none",
                "evidence_count": len(node.get("evidence") or []),
                "at": c.get("at"),
                "op": c.get("op"),
                "rev": c.get("rev"),
            })
    hits.sort(key=lambda h: (h.get("at") or "", h.get("rev") or 0), reverse=True)
    return hits[:k]
