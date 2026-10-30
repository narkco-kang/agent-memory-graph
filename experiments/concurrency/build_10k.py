#!/usr/bin/env python3
"""Build a 10,000-node graph on disk for the 10k concurrency run.

Uses the same builder as `benchmarks/bench.py` so the data set is reproducible and
schema-valid without spending an hour in `add_node` (each write rewrites the file:
`WRITE-COST.md`).

    PYTHONPATH=src python3 experiments/concurrency/build_10k.py /tmp/amg-10k [--nodes 10000]
"""
import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BENCH = os.path.join(ROOT, "benchmarks", "bench.py")
spec = importlib.util.spec_from_file_location("bench", BENCH)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--nodes", type=int, default=10000)
    args = parser.parse_args(argv)
    if os.path.exists(args.path) and os.listdir(args.path):
        raise SystemExit(f"refusing to write into a non-empty directory: {args.path}")
    os.makedirs(args.path, exist_ok=True)
    bench.build(args.path, args.nodes, edges_per_node=1)
    size = os.path.getsize(os.path.join(args.path, "graph.json"))
    print(f"built {args.nodes} nodes / {args.nodes} edges at {args.path} "
          f"({size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
