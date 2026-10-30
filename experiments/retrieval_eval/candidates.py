"""Candidate retrievers for the pre-registered evaluation. Not shipped code.

Each candidate exposes `search(doc, query, layer="L3", k=10, strict=False)` with
the same output shape as `amg.retrieval.search`, so `run_eval.py` can compare
them without special cases.

Why these two and not "a vector database":

- `bm25` — the honest first upgrade: proper tokens and IDF instead of substring
  matching. Ignores semantics completely, so it measures how much of the
  paraphrase gap is actually a *tokenization* problem.
- `hashed-vec` — a dependency-free vector space model: word tokens plus character
  trigrams, feature-hashed into 512 dims, IDF weighted, cosine similarity. It is
  genuinely a vector representation, but it is still lexical (no learned
  semantics), so it can only win by tolerating morphology. Included precisely so
  the "do we need a model?" question gets a measured answer.
"""
import hashlib
import json
import math
import os
import re
import urllib.request

from amg.const import CONCLUSION_TYPES, not_yet_valid

TOKEN = re.compile(r"[a-z0-9_\-]+")
WORD = re.compile(r"[a-z0-9]+")
CJK = re.compile(r"[\u3400-\u9fff]")

FIELD_WEIGHTS = {"id": 3.0, "label": 2.0, "note": 1.0, "source": 0.5, "owner": 0.5}
FIELDS = tuple(FIELD_WEIGHTS)

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "do", "does", "did", "how", "why", "what", "when", "who", "i", "it", "this",
    "that", "with", "by", "at", "as", "be", "can", "my", "we", "you", "not",
}


def tokens(text):
    """Word tokens; CJK text falls back to characters plus the whole run."""
    q = str(text or "").lower()
    out = [t for t in TOKEN.findall(q) if t and t not in STOPWORDS]
    if CJK.search(q):
        out.extend(ch for ch in q if CJK.match(ch))
    return out


def _visible(doc, layer):
    """Same hard filters as the shipped retriever: expiry is first-class."""
    nodes = [n for n in (doc.get("nodes") or [])
             if n.get("status") != "superseded" and not not_yet_valid(n)]
    if layer == "L1":
        nodes = [n for n in nodes
                 if n.get("status") in {"open", "in_progress", "blocked", "proposed"}]
    elif layer == "L4":
        nodes = [n for n in nodes if n.get("type") == "rule"]
    return nodes


def _record(node, score, fields):
    ev = node.get("evidence") or []
    return {
        "id": node.get("id"), "label": node.get("label"), "type": node.get("type"),
        "status": node.get("status"), "score": round(score, 4),
        "matched_fields": fields,
        "anchor_state": "present" if ev else "none",
        "evidence_count": len(ev),
        "evidence_grade": node.get("evidence_grade"),
        "conclusion": bool(node.get("conclusion") or node.get("type") in CONCLUSION_TYPES),
    }


def _rank(doc, scored, k, strict):
    # two-key ranking, same as the shipped retriever: anchored first, then score
    scored.sort(key=lambda h: (h["anchor_state"] == "none", -h["score"], h["id"] or ""))
    hits = scored[:k]
    if strict:
        hits = [h for h in hits if h["anchor_state"] == "present"]
    return hits


class BM25:
    """Tokenised BM25 with per-field weights. No semantics, no dependencies."""

    name = "bm25"
    COST = "none"
    K1 = 1.2
    B = 0.75

    def __init__(self):
        self._cache = {}

    def _index(self, doc, layer):
        key = (id(doc), layer)
        if key in self._cache:
            return self._cache[key]
        nodes = _visible(doc, layer)
        per_field = {}
        for field in FIELDS:
            docs = [tokens(n.get(field)) for n in nodes]
            avg = sum(len(d) for d in docs) / len(docs) if docs else 0.0
            df = {}
            for d in docs:
                for term in set(d):
                    df[term] = df.get(term, 0) + 1
            per_field[field] = {"docs": docs, "avg": avg or 1.0, "df": df, "n": len(nodes)}
        self._cache[key] = (nodes, per_field)
        return nodes, per_field

    def search(self, doc, query, layer="L3", k=10, strict=False):
        nodes, per_field = self._index(doc, layer)
        terms = tokens(query)
        if not terms or not nodes:
            return []
        scored = []
        for index, node in enumerate(nodes):
            score, matched = 0.0, []
            for field, weight in FIELD_WEIGHTS.items():
                data = per_field[field]
                d = data["docs"][index]
                if not d:
                    continue
                tf = {}
                for term in d:
                    tf[term] = tf.get(term, 0) + 1
                length = len(d)
                field_score = 0.0
                for term in terms:
                    if term not in tf:
                        continue
                    df = data["df"].get(term, 0)
                    idf = math.log(1 + (data["n"] - df + 0.5) / (df + 0.5))
                    denom = tf[term] + self.K1 * (1 - self.B + self.B * length / data["avg"])
                    field_score += idf * tf[term] * (self.K1 + 1) / denom
                if field_score > 0:
                    score += weight * field_score
                    matched.append(field)
            if score > 0:
                scored.append(_record(node, score, matched))
        return _rank(doc, scored, k, strict)


class HashedVector:
    """Feature-hashed bag of words + character trigrams, IDF weighted, cosine.

    A real vector space model and still lexical: it can only beat substring
    matching by tolerating word shapes ("encode"/"encoder", "write"/"writing").
    """

    name = "hashed-vec"
    COST = "none"          # no download, no third-party package
    SEMANTIC = False       # declared: no learned meaning, so not a semantic model
    DIM = 512

    def __init__(self):
        self._cache = {}

    @staticmethod
    def _hash(feature):
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % HashedVector.DIM

    def features(self, text):
        feats = {}
        for token in tokens(text):
            feats[f"w:{token}"] = feats.get(f"w:{token}", 0) + 1
            padded = f"^{token}$"
            for i in range(len(padded) - 2):
                gram = f"c:{padded[i:i + 3]}"
                feats[gram] = feats.get(gram, 0) + 1
        return feats

    def _index(self, doc, layer):
        key = (id(doc), layer)
        if key in self._cache:
            return self._cache[key]
        nodes = _visible(doc, layer)
        df = {}
        per_node = []
        for node in nodes:
            combined = {}
            for field, weight in FIELD_WEIGHTS.items():
                for feature, count in self.features(node.get(field)).items():
                    combined[feature] = combined.get(feature, 0.0) + weight * count
            per_node.append(combined)
            for feature in combined:
                df[feature] = df.get(feature, 0) + 1
        n = len(nodes) or 1
        vectors = []
        for combined in per_node:
            vec = {}
            norm = 0.0
            for feature, weight in combined.items():
                idf = math.log((1 + n) / (1 + df.get(feature, 0))) + 1.0
                value = weight * idf
                vec[feature] = value
                norm += value * value
            vectors.append((vec, math.sqrt(norm) or 1.0))
        self._cache[key] = (nodes, vectors)
        return nodes, vectors

    def search(self, doc, query, layer="L3", k=10, strict=False):
        nodes, vectors = self._index(doc, layer)
        if not tokens(query) or not nodes:
            return []
        qfeats = self.features(query)
        qvec = {}
        qnorm = 0.0
        # Query IDF uses the same document frequencies as the index; features not
        # in the corpus get the maximum IDF, which is correct but adds no signal.
        for feature, weight in qfeats.items():
            value = weight * 1.0
            qvec[feature] = value
            qnorm += value * value
        qnorm = math.sqrt(qnorm) or 1.0
        scored = []
        for node, (vec, norm) in zip(nodes, vectors):
            dot = 0.0
            for feature, value in qvec.items():
                other = vec.get(feature)
                if other:
                    dot += value * other
            if dot <= 0:
                continue
            score = dot / (qnorm * norm)
            matched = [f for f, w in FIELD_WEIGHTS.items()
                       if any(f"w:{t}" in vec for t in tokens(node.get(f)))]
            scored.append(_record(node, score, matched))
        return _rank(doc, scored, k, strict)


class LocalEmbedding:
    """Semantic candidate backed by a *local* embedding model via ollama.

    Cost disclosure (C3): this needs a running ollama daemon and the
    `nomic-embed-text` model (768 dims, 137M params, already present on this
    machine). It is therefore an optional extra at best — never the default path
    of a zero-dependency library — and the harness verdict must treat it that way.

    Vectors are cached on disk keyed by the exact text, so a re-run is
    deterministic and does not depend on the daemon's ordering.
    """
    name = "local-embed"
    COST = "optional-model"
    MODEL = "nomic-embed-text"
    ENDPOINT = "http://127.0.0.1:11434/api/embed"
    CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         ".embed-cache-nomic.json")

    def __init__(self):
        self._doc_cache = {}
        self._vec = self._load_cache()

    # ---------- cache ----------
    @classmethod
    def _load_cache(cls):
        try:
            with open(cls.CACHE, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("model") == cls.MODEL:
                return data["vectors"]
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        return {}

    def _save_cache(self):
        with open(self.CACHE, "w", encoding="utf-8") as fh:
            json.dump({"model": self.MODEL, "vectors": self._vec}, fh)
            fh.write("\n")

    # ---------- embedding ----------
    def _embed(self, texts):
        missing = [t for t in texts if t not in self._vec]
        if missing:
            payload = json.dumps({"model": self.MODEL, "input": missing}).encode("utf-8")
            request = urllib.request.Request(self.ENDPOINT, data=payload,
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.load(response)
            for text, vector in zip(missing, data["embeddings"]):
                self._vec[text] = vector
            self._save_cache()
        return [self._vec[t] for t in texts]

    @staticmethod
    def _node_text(node):
        return " ".join(str(node.get(f) or "") for f in ("label", "note", "id", "type", "status")).strip()

    @staticmethod
    def _cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0.0

    def _index(self, doc, layer):
        key = (id(doc), layer)
        if key in self._doc_cache:
            return self._doc_cache[key]
        nodes = _visible(doc, layer)
        texts = [self._node_text(n) for n in nodes]
        vectors = self._embed(texts) if texts else []
        self._doc_cache[key] = (nodes, vectors)
        return nodes, vectors

    def search(self, doc, query, layer="L3", k=10, strict=False):
        nodes, vectors = self._index(doc, layer)
        if not nodes or not tokens(query):
            return []
        query_vector = self._embed([query])[0]
        scored = []
        for node, vector in zip(nodes, vectors):
            score = self._cosine(query_vector, vector)
            matched = [f for f, w in FIELD_WEIGHTS.items()
                       if any(t in str(node.get(f) or "").lower() for t in tokens(query))]
            scored.append(_record(node, score, matched))
        scored = [item for item in scored if item["score"] > 0]
        return _rank(doc, scored, k, strict)


CANDIDATES = {c.name: c for c in (BM25(), HashedVector())}

def _register_local_embedding():
    try:
        import urllib.request  # noqa: F401
    except ImportError:  # pragma: no cover
        return
    CANDIDATES[LocalEmbedding.name] = LocalEmbedding()


_register_local_embedding()
