"""amg — append-only, evidence-gated semantic memory graph.

v0.1 scope (verified on disk, not aspirational):
- L1 structured state (nodes/status/owner) + L2 event log (changes[])
- L3 retrieval: LEXICAL ONLY. Vector search is not implemented (see README).
- L4 procedural rules: stored, not executed.
- No auth, no network, no vector store, no delete API.
"""

from .errors import LockTimeout, ProtocolError
from .memory import Memory

__version__ = "0.3.0"
__all__ = ["Memory", "ProtocolError", "LockTimeout", "__version__"]
