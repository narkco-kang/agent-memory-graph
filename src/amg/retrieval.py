"""L3 lexical retrieval. Vector search is not implemented; a semantic candidate
was measured and rejected for the default path (experiments/retrieval_eval/).

Two hard rules (signed, failures.md:118):
- `superseded` nodes are filtered out for L1/L3/L4. Expiry is a first-class
  citizen, so a stale fact must never come back as an answer. History is not
  lost: it stays in L2 (`changes[]`), which is the only layer that shows it.
- Nodes whose `valid_from` is in the future are not yet in effect, so they are
  filtered from L1/L3/L4 too (audit reports them as "not yet valid").
- Ranking is deliberately two-key: (anchor_present, score). Degraded results are
  returned with anchor_state="none" instead of being silently dropped; `strict`
  is the only path that filters them out.
- The score is rarity-aware (v0.18.0) and bounded (v0.19.0): each matched term
  contributes `WEIGHTS[field] * idf(term)`, with the IDF computed from the document
  being searched and divided by its own maximum `ln(1 + N)`. A word that is everywhere
  (`the`, `graph`) cannot outvote the term that actually answers, and a score no longer
  grows with graph size for the same match (`issue.mem-arch-idf-live-df-drift`).
- Hits carry `score_kind` (v0.19.0): `idf` for L1/L3/L4, `recency` for L2 (a constant;
  the order is `at` descending), `expansion` for `--expand` neighbours. Scores of
  different kinds must never be compared or merged.
"""
import math
import re

from .const import CONCLUSION_TYPES, not_yet_valid

_TOKEN = re.compile(r"[a-z0-9_\-]+")
_CJK = re.compile(r"[\u3400-\u9fff]")
# Identifier punctuation: a query that contains it is a lookup, not a bag of words.
_IDENT = re.compile(r"[.:/_]")
# What counts as "inside a word" for ASCII boundary matching. `-`, `_`, `.` and `/`
# are separators on purpose: ids like `task.batch6-v6-impl` must match `batch6`.
_WORD = re.compile(r"[a-z0-9]")

WEIGHTS = {"id": 3.0, "label": 2.0, "note": 1.0, "source": 0.5, "owner": 0.5}


def rank_key(raw, anchor_present, node_id):
    """The single ordering key for L3/L4 hits (highest first).

    Anchored hits first, then the pre-normalization score rounded to the displayed precision,
    then the node id **reversed**. The id component is what breaks exact ties, so at a tie the
    rank is decided by the identifier, not by relevance: results are reproducible, but a tie is
    not a relevance judgement. Callers reading `hits[i]["score"]` see the same 3-dp rounding.
    """
    return (bool(anchor_present), round(raw, 3), node_id or "")


def _tokens(query: str):
    """Query -> matchable tokens, with two deliberate refusals.

    * An ASCII token shorter than two characters is dropped: "a" occurs inside
      `archive`, `task.batch6-a…` and almost every word, so it cannot distinguish
      anything and only manufactures hits (measured in
      `experiments/retrieval_precision/`).
    * A query containing identifier punctuation (`.`, `:`, `/`, `_`) is one phrase,
      not words: `task.a` is a lookup for that id, not a search for every `task`.
      CJK text is exempt — a character is a word there.
    """
    q = query.strip().lower()
    if not q:
        return []
    if _CJK.search(q):
        toks = [q] + [ch for ch in q if _CJK.match(ch)]
        toks += [t.strip("-_") for t in _TOKEN.findall(q)]
        return [t for t in toks if t]
    out = []
    for chunk in q.split():
        if _IDENT.search(chunk):
            # A single identifier is a lookup (`task.a`); an identifier inside a
            # sentence is still one token, and the sentence keeps its other words
            # (`reads.jsonl rotation size`).
            phrase = chunk.strip(".,;:")
            if len(phrase) >= 3:
                out.append(phrase)
            continue
        for token in _TOKEN.findall(chunk):
            token = token.strip("-_")
            if len(token) >= 2:
                out.append(token)
    return out


# Inflections a reader treats as the same word. `rank` must find `ranking`, and
# `searched` must find `search` — a boundary-only match would call those different
# words and the freeze test measured the recall that costs (experiments/
# retrieval_precision/). A tiny, explicit suffix table rather than a stemmer
# dependency: the project has no dependencies, and a wrong stem is then visible here.
_SUFFIXES = ("s", "es", "ed", "ing", "ion", "ions", "ly", "er", "ers", "ment",
             "ments", "ity", "ies", "ied")


def _forms(token: str) -> set:
    """The token and its regular inflections, in both directions."""
    stems = {token}
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            stems.add(token[: -len(suffix)])
    forms = set()
    for stem in stems:
        forms.add(stem)
        for suffix in _SUFFIXES:
            forms.add(stem + suffix)
        if stem.endswith("e") and len(stem) >= 3:
            base = stem[:-1]
            forms.update({base + "ing", base + "ed", base + "ion", base + "ions",
                          base + "y"})
        if stem.endswith("y") and len(stem) >= 4:
            forms.update({stem[:-1] + "ies", stem[:-1] + "ied"})
    return forms


def _matcher(token: str):
    """A predicate over already-lowercased text.

    ASCII matches whole words **or their regular inflections** (`rank`/`ranking`).
    Raw substring matching is gone: it is what made `a` an answer to everything.
    CJK keeps substring semantics because it has no spaces.
    """
    if _CJK.search(token):
        return lambda text, token=token: token in text
    alternatives = "|".join(re.escape(form) for form in
                            sorted(_forms(token), key=len, reverse=True))
    pattern = re.compile(r"(?<![a-z0-9])(?:" + alternatives + r")(?![a-z0-9])")
    return lambda text, pattern=pattern: pattern.search(text) is not None


def _matchers(query: str):
    """Query -> (token, matcher) pairs, distinct terms only.

    A word typed twice is one term: the IDF weight belongs to the term, not to how
    often it was repeated, so duplicates cannot inflate a score.
    """
    seen, out = set(), []
    for token in _tokens(query):
        if token in seen:
            continue
        seen.add(token)
        out.append((token, _matcher(token)))
    return out


def _match_fields(nodes, matchers):
    """One pass: matched (field, term) pairs per node, and each term's document frequency.

    Two passes would read more clearly, but search is the hot path (p50 74 ms on
    10,000 nodes, `experiments/retrieval_10k/`). Keeping the matches from the first
    pass costs one short list per matching node; re-running every matcher over every
    field for the IDF pass would cost the whole scan twice.

    `df` counts each term once per node, so a node repeating a word does not look
    more common than it is.
    """
    matched, df = [], [0] * len(matchers)
    for n in nodes:
        pairs, counted = [], set()
        for field in WEIGHTS:
            value = str(n.get(field) or "").lower()
            if not value:
                continue
            for index, (_, matches) in enumerate(matchers):
                if matches(value):
                    pairs.append((field, index))
                    if index not in counted:
                        counted.add(index)
                        df[index] += 1
        if pairs:
            matched.append((n, pairs))
    return matched, df


def search(doc: dict, query: str, layer: str = "L3", k: int = 10, strict: bool = False,
           expand: bool = False, archived=None):
    if layer not in {"L1", "L2", "L3", "L4"}:
        from .errors import ProtocolError
        raise ProtocolError("E_BAD_LAYER", f"unknown layer: {layer} (use L1/L2/L3/L4)")
    matchers = _matchers(query)
    if not matchers:
        return []

    if layer == "L2":
        return _search_changes(doc, matchers, k, archived=archived)

    # Hard filters first: a superseded or not-yet-effective fact is never an
    # answer (L2 keeps history, so neither rule hides the event log).
    nodes = [n for n in (doc.get("nodes") or [])
             if n.get("status") != "superseded" and not not_yet_valid(n)]
    if layer == "L1":
        nodes = [n for n in nodes if n.get("status") in {"open", "in_progress", "blocked", "proposed"}]
    elif layer == "L4":
        nodes = [n for n in nodes if n.get("type") == "rule"]

    matched, df = _match_fields(nodes, matchers)
    total = len(nodes)
    # BM25-style IDF, normalized by its own maximum so a score is bounded in
    # (0, Σ matched field weights] and does not inflate as the graph grows
    # (v0.19.0, issue.mem-arch-idf-live-df-drift). For one query every term shares
    # the divisor ln(1 + N), so the ranking is unchanged by the normalization.
    # Positivity is preserved: ln(1 + N/(1+N)) > 0, so "matched but common" never
    # silently becomes "not matched" and a corpus where every node shares a word
    # still ranks something.
    scale = math.log(1.0 + total) if total else 1.0
    idf = [math.log(1.0 + total / (1.0 + count)) for count in df]

    scored = []
    for n, pairs in matched:
        raw, fields = 0.0, []
        for field, index in pairs:
            raw += WEIGHTS[field] * idf[index]
            if field not in fields:
                fields.append(field)
        if raw <= 0:
            continue
        ev = n.get("evidence") or []
        scored.append((raw, {
            "id": n.get("id"),
            "label": n.get("label"),
            "type": n.get("type"),
            "status": n.get("status"),
            # The displayed score is the bounded one (raw / ln(1+N)); ordering keeps
            # the pre-normalization value, so the common divisor cannot change a rank.
            "score": round(raw / scale, 3),
            "score_kind": "idf",
            "matched_fields": fields,
            "anchor_state": "present" if ev else "none",
            "evidence_count": len(ev),
            "evidence_grade": n.get("evidence_grade"),
            "conclusion": bool(n.get("conclusion") or n.get("type") in CONCLUSION_TYPES),
        }))
    if strict:
        scored = [(raw, hit) for raw, hit in scored if hit["anchor_state"] == "present"]
    scored.sort(key=lambda item: rank_key(item[0], item[1]["anchor_state"] == "present",
                                          item[1]["id"]), reverse=True)
    hits = [hit for _, hit in scored[:k]]
    if expand and layer != "L2":
        hits = _expand(doc, hits, strict=strict)
    return hits


def _expand(doc: dict, hits, strict: bool):
    """Attach 1-hop neighbors of each hit, marked with the hit that pulled them in."""
    from collections import deque
    from .const import EDGE_KINDS  # noqa: F401  (kept for symmetry with relations)
    nodes = {n["id"]: n for n in doc.get("nodes") or []}
    adj = {}
    for e in doc.get("edges") or []:
        adj.setdefault(e.get("from"), []).append((e, e.get("to"), "out"))
        adj.setdefault(e.get("to"), []).append((e, e.get("from"), "in"))
    have = {h["id"] for h in hits}
    extra = []
    seen = set(have)
    for hit in list(hits):
        for edge, other, direction in adj.get(hit["id"], []):
            if other in seen:
                continue
            seen.add(other)
            n = nodes.get(other) or {}
            if strict and not n.get("evidence"):
                continue
            extra.append({
                "id": other,
                "label": n.get("label"),
                "type": n.get("type"),
                "status": n.get("status"),
                "score": 0.0,
                "score_kind": "expansion",
                "matched_fields": [],
                "anchor_state": "present" if n.get("evidence") else "none",
                "evidence_count": len(n.get("evidence") or []),
                "evidence_grade": n.get("evidence_grade"),
                "conclusion": bool(n.get("conclusion") or n.get("type") in {"decision", "artifact"}),
                "expanded_from": hit["id"],
                "via_kind": edge.get("kind"),
                "direction": direction,
            })
    extra.sort(key=lambda h: (h["anchor_state"] == "present", h["id"] or ""), reverse=True)
    return hits + extra


def _search_changes(doc: dict, matchers, k: int, archived=None):
    """L2 history search over the live ledger, optionally extended by the archive.

    Archived records are history that was moved out to keep writes cheap
    (`docs/ARCHIVE.md`); they are searched only when the caller asks, and every
    hit says which archive file it came from, so "this is old" is never a guess.

    Archived hits get a reserved share of `k` (v0.21.0, `issue.mem-arch-archive-k-starve`):
    archive records are older than live ones by construction, so a merge sorted by time
    and then cut to `k` returned **zero** archived hits whenever `k` live records
    matched — `--include-archive` silently did nothing. The reservation is
    `max(1, k // 5)` slots, one per archive file first (so no file with a match is
    invisible), then by recency. Live-only searches are untouched.
    """
    live, archive = [], []
    nodes = {n.get("id"): n for n in doc.get("nodes") or []}
    entries = [(None, c) for c in doc.get("changes") or []]
    for item in archived or []:
        entries.append((item.get("file"), item.get("record") or {}))
    for archive_file, c in entries:
        text = f"{c.get('op','')} {c.get('target','')} {c.get('note','')}".lower()
        if any(matches(text) for _, matches in matchers):
            target = c.get("target")
            node = nodes.get(target) or {}
            hit = {
                "id": target,
                "label": node.get("label"),
                "type": "change",
                "status": node.get("status"),
                "score": 1.0,
                "score_kind": "recency",
                "matched_fields": ["changes"],
                "anchor_state": "present" if node.get("evidence") else "none",
                "evidence_count": len(node.get("evidence") or []),
                "at": c.get("at"),
                "op": c.get("op"),
                "rev": c.get("rev"),
            }
            if archive_file:
                hit["archived"] = True
                hit["archive_file"] = archive_file
                archive.append(hit)
            else:
                live.append(hit)
    order = lambda h: (h.get("at") or "", h.get("rev") or 0)  # noqa: E731
    live.sort(key=order, reverse=True)
    archive.sort(key=order, reverse=True)
    if not archive:
        return live[:k]
    if k <= 0:
        return []
    # The reservation starts at k >= 5: below that a single-slot answer is dominated by
    # recency (the old behaviour, kept), from 5 up the archive always gets a share.
    quota = max(1, k // 5) if k >= 5 else 0
    if not quota:
        merged = live + archive
        merged.sort(key=order, reverse=True)
        return merged[:k]
    picked, seen = [], set()
    for hit in archive:                     # one per archive file first
        if len(picked) >= quota:
            break
        if hit["archive_file"] not in seen:
            picked.append(hit)
            seen.add(hit["archive_file"])
    for hit in archive:                     # then fill the quota by recency
        if len(picked) >= quota:
            break
        if hit not in picked:
            picked.append(hit)
    merged = live[:max(0, k - len(picked))] + picked
    for hit in archive:                     # spare capacity goes to history, not waste
        if len(merged) >= k:
            break
        if hit not in merged:
            merged.append(hit)
    merged.sort(key=order, reverse=True)
    return merged[:k]
