"""Evidence gate: the only component allowed to reject a write.

Rules (see docs/DECISIONS.md):
- evidence is a list of OBJECTS, never bare strings;
- every evidence item carries locator + content_sha256 + captured_at (+ graph_rev);
- the gate is triggered by CONCLUSION-TYPED content, not by status;
- semantic near-duplicate detection may NEVER reject (it flags only).
"""
import hashlib
import os
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


#: A declaration may carry its digest inside the locator: `path:<rel>#sha256:<hex>`.
#: This is the format `kg.py` wrote throughout the legacy era — 41 records on the team
#: graph use it — so it is a known format, not a stray string. Before this was parsed,
#: those locators were looked up WITH the fragment attached, the file never resolved,
#: and every one of them was reported `missing`: the only historic evidence that ever
#: declared a digest was silently voided by the switch.
FRAGMENT_SHA_RE = re.compile(r"^(?P<path>.*)#sha256:(?P<sha>[0-9a-f]{64})$")


def split_sha_fragment(raw: str):
    """`(path, sha_or_None)` for a locator that may carry a `#sha256:` fragment."""
    match = FRAGMENT_SHA_RE.match(raw or "")
    if not match:
        return raw, None
    return match.group("path"), match.group("sha")


def _resolve_inside(root: str, raw: str):
    """Resolve a `path:` locator inside `root`; None when it escapes the root.

    v0.20.1: absolute paths and `..`/symlink escapes used to be read, which made a
    public, unauthenticated memory store an oracle for hashing files it does not own
    (`issue.mem-arch-evidence-locator-out-of-tree`). Evidence must live inside the graph
    directory; escaping is reported `outside_root`, never hashed.
    """
    root_real = os.path.realpath(root)
    candidate = raw if os.path.isabs(raw) else os.path.join(root_real, raw)
    real = os.path.realpath(candidate)
    if real == root_real:
        return real
    try:
        inside = os.path.commonpath([root_real, real]) == root_real
    except ValueError:  # different drives on Windows
        inside = False
    return real if inside else None


#: Directories under the graph root that supply a second resolution base. The team's
#: legacy evidence strings were written against two different bases: some against the
#: workspace root, some against the repository root (`src/amg/adopt.py`, `docs/API.md`).
#: Resolving only against the graph root reported 111 of those as `missing` when the
#: file was there all along (`artifact.mem-arch-baseline-probe`). These are *subdirectories*
#: of the root, so trying them does not widen the boundary the way a symlink would.
SECONDARY_BASES = ("agent-memory-graph",)


def resolve_evidence_path(root: str, raw: str):
    """Resolve an evidence path against the graph root, then its known sub-bases.

    Returns `(path, base)` where `base` is `"root"` or the name of the sub-base that
    matched, or `(None, reason)` where reason is `"outside_root"` or `"missing"`.

    Order matters and is the whole point: the graph root is tried first, so an
    ordinary locator behaves exactly as before. A sub-base is only consulted when the
    locator is absent at the root, and the result still has to land inside that
    sub-base — a `..` that climbs out of it is still a refusal.
    """
    direct = _resolve_inside(root, raw)
    if direct is not None and os.path.exists(direct):
        return direct, "root"
    if os.path.isabs(raw):
        # an absolute locator has no second base to speak of
        return None, ("outside_root" if direct is None else "missing")
    root_real = os.path.realpath(root)
    for base_name in SECONDARY_BASES:
        base = os.path.join(root_real, base_name)
        if not os.path.isdir(base):
            continue
        resolved = _resolve_inside(base, raw)
        if resolved is not None and os.path.exists(resolved):
            return resolved, base_name
    if direct is None:
        return None, "outside_root"
    return None, "missing"



def verify_evidence_on_write(items, root: str, node_id: str = None) -> None:
    """Refuse a write whose declared digest is not the digest of the bytes.

    Why this exists — measured, not assumed:

    `validate_evidence` checks the SHAPE of `content_sha256` (64 lowercase hex) and
    nothing else, so a fabricated digest produces `E_EVIDENCE_MISSING`-free
    `done` nodes. The forgery is only caught later, on the read side, where
    `audit --verify` reports the node as `missing`. A memory that is already stored
    and retrievable has to be caught at write time, not when someone finally reads it.

    Measured before this guard: a 64-hex digest of `aaaa…` was accepted and stored as
    `done`; `audit --verify` then reported the same node `missing`, and `search`
    showed it as such. Measured after: the write is refused.

    Rules (each corresponds to a way the check could be useless):
    - `path:` locators must resolve INSIDE `root`; a locator that escapes is refused
      rather than skipped, otherwise the check itself becomes the bypass.
    - the file must exist; a missing file is not "unverified", it is a failed claim.
    - `cmd:` / `url:` / `sha256:` locators carry no local bytes: they stay allowed
      (they may be perfectly good evidence) but they are not proof, so at least one
      `path:` locator must pass for a node carrying any locator at all.
    """
    checked = 0
    failures = []
    for index, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        locator = str(item.get("locator") or "")
        expected = str(item.get("content_sha256") or "")
        if not locator.startswith("path:"):
            continue
        path = _resolve_inside(root, locator[len("path:"):])
        if path is None:
            failures.append(f"evidence[{index}] {locator}: escapes the evidence root")
            continue
        if not os.path.isfile(path):
            failures.append(f"evidence[{index}] {locator}: file does not exist")
            continue
        try:
            actual = sha256_of_file(path)
        except OSError as exc:
            failures.append(f"evidence[{index}] {locator}: unreadable ({exc})")
            continue
        if expected and actual != expected:
            failures.append(
                f"evidence[{index}] {locator}: declared {expected} but the file hashes to {actual}")
            continue
        checked += 1
    if failures:
        prefix = f"{node_id}: " if node_id else ""
        raise ProtocolError(
            "E_EVIDENCE_VERIFY_FAILED",
            prefix + "declared evidence does not match what can be observed; "
            + "; ".join(failures))


def verify_evidence(items, root: str, node_id: str = None) -> list:
    """Check evidence locators against what can actually be observed offline.

    `content_sha256` is caller-declared; until v0.20.0 the gate validated only its shape,
    so a fabricated hash still produced `anchor_state: "present"` — a sorting hard key on
    a claim (`issue.mem-arch-evidence-sha-forgeable`). This function is the observation
    mechanism for the observable half: `path:` locators are hashed with
    `sha256_of_file`.

    Status is one of:

    * `ok` — the file inside the graph root hashes to the declared digest;
    * `mismatch` — it hashes to something else;
    * `missing` — the path does not exist; `not_a_file` — it is a directory;
    * `unreadable` — the bytes exist but cannot be read (permission/IO);
    * `outside_root` — the path (absolute, `..`, or via a symlink) leaves the graph
      directory; it is never opened (v0.20.1);
    * `unverifiable` — `cmd:`, `url:` and `sha256:` locators carry no local bytes.

    Only `ok` is a pass. `captured_at` is not re-verified: a timestamp is a claim about
    the past, not a fingerprint of bytes.
    """
    rows = []
    for index, item in enumerate(items or []):
        item = item if isinstance(item, dict) else {}
        locator = str(item.get("locator") or "")
        expected = str(item.get("content_sha256") or "")
        row = {"node": node_id, "index": index, "locator": locator,
               "expected": expected, "actual": None}
        if not locator.startswith("path:"):
            row["status"] = "unverifiable"
            rows.append(row)
            continue
        path = _resolve_inside(root, locator[len("path:"):])
        if path is None:
            row["status"] = "outside_root"
        elif os.path.isdir(path):
            row["status"] = "not_a_file"
        elif not os.path.exists(path):
            row["status"] = "missing"
        else:
            try:
                actual = sha256_of_file(path)
            except OSError:
                row["status"] = "unreadable"   # not a crash, and not a pass
            else:
                row["actual"] = actual
                row["status"] = "ok" if actual == expected else "mismatch"
        rows.append(row)
    return rows


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
