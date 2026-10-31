"""Put `src/` on `sys.path` once, for every test module.

Why this exists (v0.36.0): some test modules do `from amg import Memory` at import time
without inserting `src` themselves (`tests/test_relations.py`, `tests/test_adopt.py`, …).
Whichever module imports first wins, so collection order decided which `amg` the whole
run used: run one file and `amg` resolved to this checkout, run the suite and an `amg`
installed in the environment won instead. The symptom was a real one — `AttributeError:
module 'amg.retrieval' has no attribute 'rank_key'` on a function that plainly exists —
and it made a green single-file run disagree with the same file inside the suite.

`PYTHONPATH=src` (what CI uses) hid it; a plain `pytest tests` did not. Doing it here
makes both paths agree and keeps test modules free of per-file path juggling.
"""
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
