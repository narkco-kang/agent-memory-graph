"""Evidence gate: the only component allowed to reject a write.

Rules (see docs/DECISIONS.md):
- evidence is a list of OBJECTS, never bare strings;
- every evidence item carries locator + content_sha256 + captured_at (+ graph_rev);
- the gate is triggered by CONCLUSION-TYPED content, not by status;
- semantic near-duplicate detection may NEVER reject (it flags only).
"""
import hashlib
import re

from .const import LOCATOR_PREFIXES, is_conclusion
from .errors import ProtocolError

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_evidence(items, graph_rev: int) -> list:
    if items is None:
        return []
    if not isinstance(items, (list, tuple)):
        raise ProtocolError("E_EVIDENCE_FORMAT", "evidence must be a list")
    out = []
    for i, item in enumerate(items):
        if isinstance(item, str):
            raise ProtocolError(
                "E_EVIDENCE_FORMAT",
                f"evidence[{i}] is a bare string; use an object with "
                "locator/content_sha256/captured_at",
            )
        if not isinstance(item, dict):
            raise ProtocolError("E_EVIDENCE_FORMAT", f"evidence[{i}] must be an object")
        loc = item.get("locator")
        if not isinstance(loc, str) or not loc.startswith(LOCATOR_PREFIXES):
            raise ProtocolError(
                "E_EVIDENCE_FORMAT",
                f"evidence[{i}].locator must start with one of {LOCATOR_PREFIXES}",
            )
        sha = item.get("content_sha256")
        if not isinstance(sha, str) or not SHA256_RE.match(sha):
            raise ProtocolError(
                "E_EVIDENCE_FORMAT",
                f"evidence[{i}].content_sha256 must be 64 lowercase hex chars "
                "(node id or graph rev must not stand in for it)",
            )
        cap = item.get("captured_at")
        if not isinstance(cap, str) or not cap.strip():
            raise ProtocolError("E_EVIDENCE_FORMAT", f"evidence[{i}].captured_at is required")
        rev = item.get("graph_rev", graph_rev)
        if not isinstance(rev, int) or rev < 0:
            raise ProtocolError("E_EVIDENCE_FORMAT", f"evidence[{i}].graph_rev must be a non-negative int")
        grade = item.get("grade")
        # bool is a subclass of int in Python: True would otherwise pass as 1
        # and land on disk as `true`, which is not a grade.
        if grade is not None and (isinstance(grade, bool) or not isinstance(grade, int)
                                  or not 1 <= grade <= 5):
            raise ProtocolError("E_EVIDENCE_FORMAT",
                                f"evidence[{i}].grade must be an integer 1..5 (bool is not a grade)")
        entry = {
            "locator": loc,
            "content_sha256": sha,
            "captured_at": cap,
            "graph_rev": rev,
        }
        if grade is not None:
            entry["grade"] = grade
        out.append(entry)
    return out


def enforce_conclusion(node: dict, evidence: list) -> None:
    """A conclusion-typed node may exist without evidence while open,
    but it may never be *done* without evidence (IR-4, made mechanical)."""
    if not is_conclusion(node):
        return
    if node.get("status") == "done" and not evidence:
        raise ProtocolError(
            "E_EVIDENCE_MISSING",
            f"{node['id']}: conclusion-typed node cannot be done without evidence "
            "(write the evidence object or leave it in_progress)",
        )


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
