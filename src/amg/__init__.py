"""amg — append-only, evidence-gated memory graph.

What this library is today (measured, not aspirational):
- L1 structured state (nodes/status/owner) + L2 event log (changes[])
- L3 retrieval: LEXICAL ONLY. A semantic candidate was measured and rejected for
  the default path (experiments/retrieval_eval/).
- L4 procedural rules: stored, not executed.
- Cold archive of old L2 ledger records (`amg archive`), with a five-part proof on
  every run and a rollback when the proof fails (docs/ARCHIVE.md). It does not
  make `L2` search cover archived history; that is stated there, not hidden.
- No auth (decided out of scope, docs/DECISIONS.md #13), no network, no delete API.
"""

from .errors import LockTimeout, ProtocolError
from .memory import Memory

__version__ = "0.28.0"
__all__ = ["Memory", "ProtocolError", "LockTimeout", "__version__"]
