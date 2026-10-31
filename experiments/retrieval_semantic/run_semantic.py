#!/usr/bin/env python3
"""Does a semantic arm close N2? Three arms against a local embedding daemon.

See PREREGISTRATION.md (written before the run). DECISIONS #49 closed the lexical rerank family and
left two limits open: the candidate ceiling is 0.846 (so 0.70 is not impossible), and 4/26 queries
have gold beyond the top 100. An embeddings round ran earlier for paraphrase queries only; N2 was
never measured with embeddings. That is what this does.

Backend: local ollama `nomic-embed-text` (digest recorded in the pre-registration), called over
loopback HTTP. Nothing here adds a dependency to the package and `src/amg/` is not touched.

    PYTHONPATH=src python3 experiments/retrieval_semantic/run_semantic.py
    PYTHONPATH=src python3 experiments/retrieval_semantic/run_semantic.py --json
    PYTHONPATH=src python3 experiments/retrieval_semantic/run_semantic.py --embed-only

Embeddings are cached under `/tmp/amgembed-cache/<model-digest-prefix>/`, keyed by the SHA-256 of the
text, so a rerun costs nothing. Writes `result.json` next to this file.
"""
import hashlib
import importlib.util
import json
import os
import statistics
import sys
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import retrieval  # noqa: E402

IDF_DIR = os.path.join(ROOT, "experiments", "retrieval_idf")
EVAL_DIR = os.path.join(ROOT, "experiments", "retrieval_eval")
MODEL = "nomic-embed-text:latest"
MODEL_DIGEST = "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f"
HOST = "http://127.0.0.1:11434"
BATCH = 64
CACHE = os.path.join("/tmp", "amgembed-cache", MODEL_DIGEST[:12])
DEEP_K = 100
RRF_K = 60
CRITERIA = {"control_min_r5": 0.855, "n2_min_gain_r5": 0.05, "n1_min_r5": 0.855,
            "n3_min_r5": 0.845, "n2_target_r5": 0.70}
SHIPPED = {"control": 0.865, "n1": 0.865, "n2": 0.538, "n3": 0.865}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


idf = _load("idf_eval", os.path.join(IDF_DIR, "run_eval.py"))
run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
ten_k = _load("run_10k", os.path.join(ROOT, "experiments", "retrieval_10k", "run_eval.py"))


class Embedder:
    """Loopback ollama client with an on-disk cache keyed by text digest."""

    def __init__(self):
        os.makedirs(CACHE, exist_ok=True)
        self.keys_path = os.path.join(CACHE, "keys.json")
        self.vecs_path = os.path.join(CACHE, "vecs.npy")
        self.keys = {}
        self.vecs = None
        if os.path.exists(self.keys_path) and os.path.exists(self.vecs_path):
            with open(self.keys_path, encoding="utf-8") as fh:
                stored = json.load(fh)
            matrix = np.load(self.vecs_path)
            self.keys = {text: index for text, index in stored.items()}
            self.vecs = matrix
        self.embedded_now = 0

    @staticmethod
    def digest(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def ensure(self, texts):
        missing = [text for text in dict.fromkeys(texts) if self.digest(text) not in self.keys]
        if missing:
            rows = []
            started = time.perf_counter()
            for start in range(0, len(missing), BATCH):
                batch = missing[start:start + BATCH]
                body = json.dumps({"model": MODEL, "input": batch}).encode("utf-8")
                request = urllib.request.Request(HOST + "/api/embed", data=body,
                                                 headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=300) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                rows.append(np.asarray(payload["embeddings"], dtype=np.float32))
                done = min(start + BATCH, len(missing))
                if done % (BATCH * 10) == 0 or done == len(missing):
                    print(f"  embedded {done}/{len(missing)} "
                          f"({time.perf_counter() - started:.1f}s)", flush=True)
            fresh = np.vstack(rows)
            if self.vecs is None or not len(self.vecs):
                self.vecs = fresh
            else:
                self.vecs = np.vstack([self.vecs, fresh])
            for offset, text in enumerate(missing):
                self.keys[self.digest(text)] = len(self.keys)
            self.embedded_now = len(missing)
            with open(self.keys_path, "w", encoding="utf-8") as fh:
                json.dump(self.keys, fh)
            np.save(self.vecs_path, self.vecs)
        # Normalise once so cosine is a dot product.
        matrix = self.vecs / np.linalg.norm(self.vecs, axis=1, keepdims=True)
        return {self.digest(text): matrix[self.keys[self.digest(text)]] for text in
                dict.fromkeys(texts)}


def rrf(lex_rank, sem_rank):
    score = 0.0
    if lex_rank is not None:
        score += 1.0 / (RRF_K + lex_rank)
    if sem_rank is not None:
        score += 1.0 / (RRF_K + sem_rank)
    return score


def order_by(hits, gold_order, vectors, query_vector, nodes_by_id):
    """Return (arm_a, arm_b, arm_c) orderings and the semantic top-100 for this query."""
    cos = {}
    for node_id, node in nodes_by_id.items():
        vector = vectors.get(node["_digest"])
        if vector is not None:
            cos[node_id] = float(np.dot(query_vector, vector))
    semantic = sorted(cos, key=lambda node_id: (-cos[node_id], node_id))[:DEEP_K]

    sem_rank_within = {node_id: position for position, node_id in enumerate(semantic, start=1)}
    lexical_rank = {node_id: position for position, node_id in enumerate(hits, start=1)}
    rerank = sorted(lexical_rank,
                    key=lambda node_id: (-rrf(lexical_rank[node_id], sem_rank_within.get(node_id)),
                                         lexical_rank[node_id]))
    union = set(hits) | set(semantic)
    hybrid = sorted(union,
                    key=lambda node_id: (-rrf(lexical_rank.get(node_id), sem_rank_within.get(node_id)),
                                         lexical_rank.get(node_id, 10 ** 6)))
    return rerank, semantic, hybrid


def score_rows(queries, ordering_by_query, gold_by_query, buckets):
    rows = []
    for item in queries:
        ranked = ordering_by_query[item["id"]]
        gold = gold_by_query[item["id"]]
        row = {"id": item["id"], "split": item["split"], "bucket": buckets[item["id"]],
               "reciprocal_rank": 0.0, "ranked": ranked[:DEEP_K]}
        for k in run_eval.K_VALUES:
            top = set(ranked[:k])
            row[f"recall@{k}"] = round(len(top & set(gold)) / len(gold), 4) if gold else 0.0
        for position, node_id in enumerate(ranked, start=1):
            if node_id in gold:
                row["reciprocal_rank"] = 1.0 / position
                break
        rows.append(row)
    return run_eval.aggregate(run_eval.stratified_halves(rows))


def evaluate_corpus(name, doc, queries, embedder):
    nodes_by_id = {n["id"]: n for n in doc["nodes"]}
    for node_id, node in nodes_by_id.items():
        node["_digest"] = embedder.digest(run_eval.node_text(node))
    node_texts = [run_eval.node_text(node) for node in nodes_by_id.values()]
    query_texts = [item["query"] for item in queries]
    vectors = embedder.ensure(node_texts + query_texts)
    query_vectors = {item["id"]: vectors[embedder.digest(item["query"])] for item in queries}

    buckets = {item["id"]: ("paraphrase"
                            if run_eval.overlap(item["query"],
                                                [nodes_by_id[g] for g in item["gold"]
                                                 if g in nodes_by_id]) < run_eval.PARAPHRASE_OVERLAP
                            else "keyword")
               for item in queries}
    gold = {item["id"]: [g for g in item["gold"] if g in nodes_by_id] for item in queries}

    orderings = {"A_rerank": {}, "B_semantic": {}, "C_hybrid": {}}
    ceilings = {"shipped": 0, "A_rerank": 0, "B_semantic": 0, "C_hybrid": 0}
    latencies = []
    for item in queries:
        started = time.perf_counter()
        hits = retrieval.search(doc, item["query"], layer="L3", k=DEEP_K)
        latencies.append((time.perf_counter() - started) * 1000)
        lexical_ids = [hit["id"] for hit in hits]
        rerank, semantic, hybrid = order_by(lexical_ids, None, vectors,
                                            query_vectors[item["id"]], nodes_by_id)
        orderings["A_rerank"][item["id"]] = rerank
        orderings["B_semantic"][item["id"]] = semantic
        orderings["C_hybrid"][item["id"]] = hybrid
        hit_gold = set(gold[item["id"]])
        for arm, members in (("shipped", lexical_ids), ("A_rerank", rerank),
                             ("B_semantic", semantic), ("C_hybrid", hybrid)):
            if any(node_id in hit_gold for node_id in members):
                ceilings[arm] += 1

    arms = {arm: score_rows(queries, ordering, gold, buckets) for arm, ordering in orderings.items()}
    arms["shipped"] = score_rows(queries, {item["id"]: [hit["id"] for hit in
                                                        retrieval.search(doc, item["query"],
                                                                         layer="L3", k=DEEP_K)]
                                           for item in queries}, gold, buckets)
    return {"nodes": len(doc["nodes"]), "arms": arms,
            "ceilings": {arm: round(value / len(queries), 4) for arm, value in ceilings.items()},
            "latency_ms": {"p50": round(statistics.median(latencies), 2),
                           "max": round(max(latencies), 2)}}


def verdicts(result):
    def r5(corpus, arm):
        return result["corpora"][corpus]["arms"][arm]["recall@5"]

    out = {}
    for arm in ("A_rerank", "B_semantic", "C_hybrid"):
        gates = {"C1_control_no_regression": r5("control", arm) >= CRITERIA["control_min_r5"],
                 "C2_n2_gain_at_least_0.05": r5("n2", arm) - SHIPPED["n2"]
                 >= CRITERIA["n2_min_gain_r5"],
                 "C3_n1_unchanged": r5("n1", arm) >= CRITERIA["n1_min_r5"],
                 "C4_n3_not_harmed": r5("n3", arm) >= CRITERIA["n3_min_r5"]}
        out[arm] = {**gates, "n2_recall@5": r5("n2", arm),
                    "n2_gain": round(r5("n2", arm) - SHIPPED["n2"], 3),
                    "N2_target_met": r5("n2", arm) >= CRITERIA["n2_target_r5"],
                    "passes_all": bool(all(gates.values())),
                    "ceiling": result["corpora"]["n2"]["ceilings"][arm]}
    return {"arms": out, "shipped_r5": SHIPPED, "criteria": CRITERIA,
            "ship": any(arm["passes_all"] for arm in out.values()),
            "model": {"name": MODEL, "digest": MODEL_DIGEST}}


def main(argv):
    as_json = "--json" in argv
    embed_only = "--embed-only" in argv
    doc, queries = ten_k.load_inputs()
    corpora = {"control": doc, "n1": ten_k.inflate(doc),
               "n2": ten_k.inflate_vocabulary(doc, queries),
               "n3": idf.inflate_frequent(doc)}
    embedder = Embedder()
    result = {"inputs": {"corpora": {name: len(corpus["nodes"]) for name, corpus in corpora.items()},
                         "deep_k": DEEP_K, "rrf_k": RRF_K, "model": MODEL,
                         "model_digest": MODEL_DIGEST},
              "criteria": CRITERIA, "corpora": {}}
    for name, corpus in corpora.items():
        print(f"embedding {name} ({len(corpus['nodes'])} nodes)...", flush=True)
        result["corpora"][name] = evaluate_corpus(name, corpus, queries, embedder)
        if embed_only:
            continue
        if not as_json:
            arms = result["corpora"][name]["arms"]
            print(f"{name:8s} " + "  ".join(f"{arm}:r@5={arms[arm]['recall@5']:.3f}"
                                            for arm in ("shipped", "A_rerank", "B_semantic", "C_hybrid"))
                  + f"  ceilings={result['corpora'][name]['ceilings']}")
    print(f"embedded this run: {embedder.embedded_now}", flush=True)
    if embed_only:
        return 0
    result["verdicts"] = verdicts(result)
    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)
    if as_json:
        print(json.dumps(result["verdicts"], ensure_ascii=False))
    else:
        for arm, block in result["verdicts"]["arms"].items():
            print(f"{arm}: N2 {block['n2_recall@5']:.3f} ({block['n2_gain']:+.3f}) "
                  f"gates={ {k: v for k, v in block.items() if k.startswith('C')} } "
                  f"ceiling={block['ceiling']} passes={block['passes_all']}")
        print(f"ship={result['verdicts']['ship']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
