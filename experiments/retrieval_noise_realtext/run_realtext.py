#!/usr/bin/env python3
"""A noise corpus whose distractors are real prose, not token soup.

See PREREGISTRATION.md (written before the run) and DECISIONS #51, which rejected the previous
calibration attempt because the top-100 is selected by the quantity being calibrated.

Distractor text = a seeded 8-word window of a real paragraph from this repository's own
documentation. Nothing is drawn from a vocabulary list, so function words and co-occurrence are the
documentation's own. The calibration check (competing share) is reported before the recall number.

    PYTHONPATH=src python3 experiments/retrieval_noise_realtext/run_realtext.py

Writes `result.json` next to this file. `src/amg/` is untouched.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
# Outputs default to this directory; tests point REALTEXT_OUT_DIR at a temp dir to re-run
# the harness and compare bytes without touching the committed artifacts.
OUT_DIR = os.environ.get("REALTEXT_OUT_DIR") or HERE
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import retrieval  # noqa: E402

IDF_DIR = os.path.join(ROOT, "experiments", "retrieval_idf")
EVAL_DIR = os.path.join(ROOT, "experiments", "retrieval_eval")
TEN_K_DIR = os.path.join(ROOT, "experiments", "retrieval_10k")
SEED = 20261031
TARGET_NODES = 10000
DEEP_K = 100
WINDOW = 8
SHIPPED = {"control": 0.865, "n1": 0.865, "n2": 0.538, "n3": 0.865}
N2_COMPETING_SHARE = 0.918
CORPUS_SCHEMA = "realtext-corpus/1"
# The corpus is this repository's own live prose, so the numbers below move whenever README/docs
# are edited: the committed 0.673 for whole paragraphs does not reproduce at HEAD (0.654).
# Every run therefore pins what it read; see `corpus_snapshot()`.


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


idf = _load("idf_eval", os.path.join(IDF_DIR, "run_eval.py"))
run_eval = _load("run_eval", os.path.join(EVAL_DIR, "run_eval.py"))
ten_k = _load("run_10k", os.path.join(TEN_K_DIR, "run_eval.py"))
bench = _load("bench", os.path.join(ROOT, "benchmarks", "bench.py"))


CORPUS_SRC = os.path.join(HERE, "corpus_src")
CORPUS_MANIFEST = os.path.join(CORPUS_SRC, "manifest.json")
PIN_PATH = os.path.join(HERE, "corpus_pin.json")

REPRESENTATIVENESS = {
    "kind": "same-domain regression set",
    "measures": ("lexical retrieval over this repository's own prose, frozen at the corpus version "
                 "recorded here"),
    "does_not_measure": ("the distribution of user queries, or retrieval quality on any other "
                         "domain; the 26 queries, the gold nodes and the distractor prose all come "
                         "from the same documentation"),
    "known_leak": ("distractor paragraphs and gold nodes share one vocabulary: an independent "
                   "review found 20/20 sampled rare gold tokens also occur in the corpus, so a "
                   "gain here may be a gain at matching this repository's prose style"),
    "comparability": "numbers are comparable within one corpus_version, never across versions",
}


def _relative(path):
    return pathlib.Path(path).relative_to(CORPUS_SRC).as_posix()


def corpus_paths(base=None):
    """The **frozen** prose the windows are cut from: `corpus_src/`, never the live docs.

    The evaluation corpus used to be read from `README.md`/`docs/**` at run time, so every
    documentation edit moved a published number (r@1 walked 0.558 -> 0.577 -> 0.615 that way).
    The corpus is now a checked-in copy with an explicit `corpus_version`; refreshing it is an
    explicit, reviewable act (`--refresh-corpus`), not a side effect.
    """
    root = pathlib.Path(base or CORPUS_SRC)
    if not root.is_dir():
        raise SystemExit(f"missing frozen corpus at {root}; run with --refresh-corpus")
    paths = [root / "README.md"]
    paths += sorted((root / "docs").glob("*.md"))
    paths += sorted((root / "docs" / "decisions").glob("*.md"))
    return [path for path in paths if path.is_file()]


def live_paths():
    """The repository's current prose. Only `--refresh-corpus` and `--check-corpus` read these."""
    paths = [pathlib.Path(ROOT, "README.md")]
    paths += sorted(pathlib.Path(ROOT, "docs").glob("*.md"))
    paths += sorted(pathlib.Path(ROOT, "docs", "decisions").glob("*.md"))
    return [path for path in paths if path.is_file()]


def _normalise_bytes(data):
    """Fold CRLF to LF: a checkout's line ending is not corpus content.

    The same repository produces `\r\n` on Windows and `\n` elsewhere, so hashing raw bytes made a
    clean Windows run report *stale corpus* (CI windows-latest, v0.34.0). Folding first keeps the
    digest a property of the text.
    """
    return data.replace(b"\r\n", b"\n")


def _normalised_sha256(data):
    return hashlib.sha256(_normalise_bytes(data)).hexdigest()


def corpus_manifest():
    with open(CORPUS_MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def extract_paragraphs(base=None):
    """Every paragraph of six or more words in the frozen prose."""
    paragraphs = []
    for path in corpus_paths(base):
        for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            words = " ".join(block.split()).split()
            if len(words) >= 6:
                paragraphs.append(words)
    return paragraphs


def corpus_snapshot(paragraphs):
    """Digest of what the run actually read: the frozen files plus the extracted paragraph text."""
    manifest = corpus_manifest()
    files = []
    for path in corpus_paths():
        files.append({"path": _relative(path),
                      "sha256": _normalised_sha256(path.read_bytes())})
    text = "\n\n".join(" ".join(words) for words in paragraphs)
    encoded = text.encode("utf-8")
    # Two sources of truth must not drift: this digest is the concatenation of the frozen files in
    # manifest order, so re-hashing corpus_src in that order reproduces it exactly (see the test).
    concat = b"".join(_normalise_bytes(path.read_bytes()) for path in corpus_paths())
    return {"schema": CORPUS_SCHEMA, "extractor": "prose_pool/1",
            "corpus_version": manifest["corpus_version"],
            "created_at": manifest.get("created_at"),
            "paragraphs": len(paragraphs), "files": files,
            "source_sha256": hashlib.sha256(concat).hexdigest(),
            "extracted_sha256": _normalised_sha256(encoded),
            "extracted_bytes": len(encoded)}


def pin_corpus(paragraphs, snapshot):
    """Freeze the extracted prose. The numbers belong to this file, not to any live document."""
    text = "\n\n".join(" ".join(words) for words in paragraphs)
    payload = {"schema": "realtext-corpus-pin/1", "text": text,
               "corpus_version": snapshot["corpus_version"],
               "created_at": snapshot.get("created_at"),
               "paragraphs": len(paragraphs), "extracted_sha256": snapshot["extracted_sha256"],
               "source_sha256": snapshot["source_sha256"],
               "files": snapshot["files"]}
    with open(PIN_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return payload


def refresh_corpus():
    """Copy the repository's current prose into `corpus_src/` and bump `corpus_version`.

    This is the only path from live docs to the corpus, and it is deliberate: after it runs, every
    quoted number must be re-reviewed (the tests compare quoted numbers with artifacts).
    """
    import shutil
    import datetime

    previous = None
    if os.path.isfile(CORPUS_MANIFEST):
        previous = corpus_manifest().get("corpus_version")
    version = "v1" if not previous else f"v{int(previous.lstrip('v')) + 1}"
    if os.path.isdir(CORPUS_SRC):
        shutil.rmtree(CORPUS_SRC)
    os.makedirs(CORPUS_SRC, exist_ok=True)
    files = []
    for path in live_paths():
        rel = path.relative_to(ROOT)
        dest = pathlib.Path(CORPUS_SRC) / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        dest.write_bytes(data)
        files.append({"path": rel.as_posix(), "sha256": _normalised_sha256(data),
                      "bytes": len(data)})
    manifest = {"schema": "realtext-corpus-src/1", "corpus_version": version,
                "created_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                "note": ("frozen copies of the prose the realtext experiment reads; refresh only "
                         "on an explicit version bump"),
                "files": files}
    with open(CORPUS_MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return version


def prose_pool(rebuild=False):
    """The corpus the windows are cut from (frozen; `rebuild` bumps the version from live docs)."""
    if rebuild:
        refresh_corpus()
    if os.path.isfile(PIN_PATH):
        with open(PIN_PATH, encoding="utf-8") as fh:
            pinned = json.load(fh)
        if not rebuild:
            return [block.split() for block in pinned["text"].split("\n\n") if block.strip()]
    return extract_paragraphs()


def build_realtext(doc, paragraphs):
    rng = random.Random(SEED)
    nodes = list(doc["nodes"])
    existing = {n["id"] for n in nodes}
    index = 0
    while len(nodes) < TARGET_NODES:
        words = paragraphs[rng.randrange(len(paragraphs))]
        start = rng.randrange(max(1, len(words) - WINDOW + 1))
        window = words[start:start + WINDOW]
        node = bench.make_node(index, with_evidence=False)
        node["label"] = " ".join(window[:3])
        node["note"] = " ".join(window[3:])
        node["source"] = "synthetic real-prose distractor"
        if node["id"] not in existing:
            nodes.append(node)
            existing.add(node["id"])
        index += 1
    return {"schema": doc.get("schema"), "group": doc.get("group"),
            "nodes": nodes, "edges": [], "changes": []}


def competing_share(corpus, queries):
    nodes_by_id = {n["id"]: n for n in corpus["nodes"]}
    values = []
    for item in queries:
        query_tokens = run_eval.tokens(item["query"])
        for hit in retrieval.search(corpus, item["query"], layer="L3", k=DEEP_K):
            if hit["id"] in item["gold"]:
                continue
            node = nodes_by_id.get(hit["id"])
            if node is not None:
                tokens = run_eval.tokens(run_eval.node_text(node))
                values.append(len(query_tokens & tokens) / len(query_tokens) if query_tokens else 0.0)
    share = round(sum(1 for value in values if value >= 0.25) / len(values), 4)
    return share, {"pairs": len(values), "mean": round(sum(values) / len(values), 4),
                   "median": round(sorted(values)[len(values) // 2], 4), "share_ge_0.25": share}


def evaluate(corpus, queries, detail=None):
    """Scores one arm. `detail` (a list) receives per-query rows; see `build_ledger()`."""
    nodes_by_id = {n["id"]: n for n in corpus["nodes"]}
    buckets = {item["id"]: ("paraphrase"
                            if run_eval.overlap(item["query"],
                                                [nodes_by_id[g] for g in item["gold"]
                                                 if g in nodes_by_id]) < run_eval.PARAPHRASE_OVERLAP
                            else "keyword")
               for item in queries}
    rows = []
    tie_rows = []
    ceiling = 0
    for item in queries:
        gold = [g for g in item["gold"] if g in nodes_by_id]
        hits = retrieval.search(corpus, item["query"], layer="L3", k=DEEP_K)
        ranked = [hit["id"] for hit in hits]
        if set(ranked) & set(gold):
            ceiling += 1
        row = {"id": item["id"], "split": item["split"], "bucket": buckets[item["id"]],
               "reciprocal_rank": 0.0}
        for k in run_eval.K_VALUES:
            row[f"recall@{k}"] = round(len(set(ranked[:k]) & set(gold)) / len(gold), 4) if gold else 0.0
        boundary = {}
        for cutoff in (5, 10):
            scores = [hit["score"] for hit in hits]
            boundary[cutoff] = (len(scores) > cutoff and scores[cutoff - 1] == scores[cutoff])
        best_rank = None
        for position, node_id in enumerate(ranked, start=1):
            if node_id in gold and best_rank is None:
                best_rank = position
                row["reciprocal_rank"] = 1.0 / position
        rows.append(row)
        tie_rows.append((item["id"], boundary))
        if detail is not None:
            row_detail = _detail_row(nodes_by_id, item, gold, ranked, best_rank, row)
            row_detail["boundary_tie_at_5"] = boundary[5]
            row_detail["boundary_tie_at_10"] = boundary[10]
            detail.append(row_detail)
    result = run_eval.aggregate(run_eval.stratified_halves(rows))
    result["ceiling"] = round(ceiling / len(queries), 4)
    result["hit_or_miss@5"] = round(sum(1 for r in rows if r.get("recall@5", 0.0) > 0) / len(rows), 4)
    result["tie_surface"] = {
        f"k{cutoff}": {"queries": sum(1 for _qid, bound in tie_rows if bound[cutoff]),
                       "ids": [qid for qid, bound in tie_rows if bound[cutoff]]}
        for cutoff in (5, 10)}
    return result


def _detail_row(nodes_by_id, item, gold, ranked, best_rank, row):
    """One per-query ledger row: why it failed, in numbers someone else can recompute."""
    query_tokens = set(run_eval.tokens(item["query"]))
    gold_tokens = set()
    for gid in gold:
        gold_tokens |= set(run_eval.tokens(run_eval.node_text(nodes_by_id[gid])))
    top1 = nodes_by_id.get(ranked[0]) if ranked else None
    top1_tokens = set(run_eval.tokens(run_eval.node_text(top1))) if top1 else set()
    return {"id": item["id"], "bucket": row["bucket"], "gold": list(item["gold"]),
            "gold_in_corpus": len(gold), "recall@5": row["recall@5"],
            "best_gold_rank": best_rank, "gold_reachable_in_top_k": best_rank is not None,
            "query_tokens": sorted(query_tokens),
            "gold_shared_tokens": sorted(query_tokens & gold_tokens),
            "top1_id": ranked[0] if ranked else None,
            "top1_shared_tokens": sorted(query_tokens & top1_tokens)}


def build_ledger(detail, arm_result):
    """Aggregates plus the rows, with the conventions a reader needs to reproduce them.

    `rank_base` exists because the hand-built failure ledger used 0-based ranks while the harness
    enumerates from 1; every rank here is `rank_base: 1`. `metric` names both numbers:
    `fractional_r5` is gold coverage (a two-gold query can score 0.5) and `hit_or_miss` counts a
    query when *any* gold is inside the top five. At n=26 one query is 0.0385, so the two
    conventions disagree about whether the 0.70 target is met.
    """
    out_of_reach = sorted(row["id"] for row in detail if not row["gold_reachable_in_top_k"])
    return {
        "schema": "realtext-ledger/1",
        "metric": {
            "fractional_r5": "mean over queries of |top5 & gold| / |gold|",
            "hit_or_miss": "share of queries with any gold inside the top five",
            "best_gold_rank": "1-based rank of the best gold node, or null outside top_k",
        },
        "rank_base": 1,
        "top_k": DEEP_K,
        "n": len(detail),
        "fractional_r5": arm_result["recall@5"],
        "hit_or_miss": round(sum(1 for row in detail if row["recall@5"] > 0) / len(detail), 4),
        "out_of_reach": out_of_reach,
        "ceiling": round((len(detail) - len(out_of_reach)) / len(detail), 4),
        "failing": [row["id"] for row in detail if row["recall@5"] < 1.0],
        "rows": detail,
    }


def main(argv):
    rebuild = "--refresh-corpus" in argv or "--rebuild-corpus" in argv
    doc, queries = ten_k.load_inputs()
    paragraphs = prose_pool(rebuild=rebuild)
    realtext = build_realtext(doc, paragraphs)
    share, coverage = competing_share(realtext, queries)
    corpora = {"control": doc, "n1": ten_k.inflate(doc), "n2": ten_k.inflate_vocabulary(doc, queries),
               "n3": idf.inflate_frequent(doc), "realtext": realtext}
    snapshot = corpus_snapshot(paragraphs)
    if rebuild:
        pin_corpus(paragraphs, snapshot)
    detail = []
    arms = {}
    for name, corpus in corpora.items():
        arms[name] = evaluate(corpus, queries, detail if name == "realtext" else None)
    result = {"inputs": {"seed": SEED, "window_words": WINDOW, "paragraphs": len(paragraphs),
                         "nodes": len(realtext["nodes"]), "deep_k": DEEP_K,
                         "corpus": snapshot},
              "representativeness": dict(REPRESENTATIVENESS,
                                         corpus_version=snapshot["corpus_version"]),
              "coverage": {"realtext": coverage, "n2_reference_share_ge_0.25": N2_COMPETING_SHARE},
              "arms": arms}
    ledger = build_ledger(detail, arms["realtext"])
    verdicts = {
        "Q2_calibration_below_n2": share < N2_COMPETING_SHARE,
        "Q1_recall_at_least_0.75": result["arms"]["realtext"]["recall@5"] >= 0.75,
        "Q3_ordering_n2_lt_realtext_lt_control": (result["arms"]["n2"]["recall@5"]
                                                  < result["arms"]["realtext"]["recall@5"]
                                                  < result["arms"]["control"]["recall@5"]),
        "Q4_target_stays_attached_to_n2_unmet": True,
        "n2_r5": result["arms"]["n2"]["recall@5"],
        "realtext_r5": result["arms"]["realtext"]["recall@5"],
        "realtext_hit_or_miss@5": arms["realtext"]["hit_or_miss@5"],
        "control_r5": result["arms"]["control"]["recall@5"],
        "realtext_share_ge_0.25": share,
        "shipped_r5": SHIPPED,
        "corpus_extracted_sha256": snapshot["extracted_sha256"],
    }
    result["verdicts"] = verdicts
    for name, payload in (("result.json", result), ("ledger.json", ledger),
                          ("corpus_snapshot.json", snapshot)):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
    print("Q2' competing share >= 0.25 on real-text corpus:", share, f"(N2 reference {N2_COMPETING_SHARE})")
    for name in ("control", "n1", "n2", "n3", "realtext"):
        block = result["arms"][name]
        print(f"{name:9s} r@5={block['recall@5']:.3f} r@1={block['recall@1']:.3f} "
              f"r@10={block['recall@10']:.3f} mrr={block['mrr@10']:.3f} "
              f"hit-or-miss@5={block['hit_or_miss@5']:.3f} ceiling={block['ceiling']:.3f}")
    print(f"corpus {snapshot['paragraphs']} paragraphs / {len(snapshot['files'])} files / "
          f"extracted sha256 {snapshot['extracted_sha256'][:12]}")
    print(f"ledger {ledger['fractional_r5']:.4f} fractional / {ledger['hit_or_miss']:.4f} "
          f"hit-or-miss / out of reach {ledger['out_of_reach']}")
    print(json.dumps({k: v for k, v in verdicts.items() if k.startswith("Q")}, ensure_ascii=False))
    return 0


def check_corpus(argv):
    """Audit how far the frozen corpus has drifted from the live docs. Never fails a build.

    The corpus is deliberately decoupled: documentation moves on, the measurement does not, and the
    only way to move it is `--refresh-corpus` (an explicit version bump that re-quotes every number).
    A red gate here would just mean "docs changed", which is always true; what an operator needs is
    the drift size and the age of the pin.
    """
    import datetime

    manifest = corpus_manifest()
    frozen = {_relative(path): _normalised_sha256(path.read_bytes()) for path in corpus_paths()}
    def _label(path):
        try:
            return pathlib.Path(path).relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)

    live = {_label(path): _normalised_sha256(path.read_bytes()) for path in live_paths()}
    changed = sorted(name for name in set(frozen) & set(live) if frozen[name] != live[name])
    added = sorted(set(live) - set(frozen))
    removed = sorted(set(frozen) - set(live))
    created = manifest.get("created_at")
    age = "unknown age"
    if created:
        try:
            created_at = datetime.datetime.fromisoformat(created)
            age = f"{max(0, (datetime.datetime.now().astimezone() - created_at).days)} day(s) old"
        except ValueError:
            pass
    print(f"frozen corpus {manifest['corpus_version']} ({age}): "
          f"{len(changed)} changed / {len(added)} added / {len(removed)} removed vs live docs")
    for label, items in (("changed", changed), ("added", added), ("removed", removed)):
        for name in items[:10]:
            print(f"  {label}: {name}")
    if changed or added or removed:
        print("  this is expected; refresh only as a deliberate version bump "
              "(--refresh-corpus), then re-review every quoted number")
    return 0


if __name__ == "__main__":
    if "--check-corpus" in sys.argv:
        sys.exit(check_corpus(sys.argv))
    sys.exit(main(sys.argv))
