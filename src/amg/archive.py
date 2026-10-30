"""Cold archive of the change ledger: move old history out, prove nothing was lost.

The measured problem is documented in `docs/WRITE-COST.md`: every write rewrites the
whole JSON file, and on the 15 MB real graph a single write costs ~147 ms. Most of
that file is not current state — it is the change ledger (`changes[]`), which grows
forever and is read only by `L2` search, the fingerprint and the audit counts. Old
ledger records are the cheapest bytes to move out, and unlike nodes they have no
referential integrity: nothing points at a change record.

The discipline is borrowed from a field-tested workbench
(mashanglinyu/luanyujia-workbench, MIT — `docs/PRIOR-ART.md`): **snapshot first,
move second, prove nothing was lost third**. Its original lesson was blunt: without a
snapshot the comparison script could not even be run. So this module always writes a
full snapshot of the file it is about to change, records the digest, moves a *prefix*
of the ledger into a self-describing archive file, and then re-reads the persisted
graph and compares record by record. If the comparison fails, the snapshot is written
back and the command fails — it never leaves the caller with a half-true claim.

What it deliberately does not do:

  * it does not touch nodes or edges (state digest must be unchanged, and is checked);
  * it does not delete anything: archived records live in `archive/changes-*.json`;
  * it does not compress (no dependencies) and it does not silently drop records it
    cannot date — a record without a parseable `at` is never archived;
  * `L2` search sees live history only, which `docs/ARCHIVE.md` states plainly.
"""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

from . import fingerprint as fingerprint_mod
from . import protocol
from .const import now, parse_ts
from .errors import ProtocolError
from .store import dumps

ARCHIVE_SCHEMA = "amg/archive/v1"
SUBDIR = "archive"

# The default age at which history stops being "what happened" and becomes "the
# record". A policy, not a constant, for the same reason as AMG_STALE_DAYS
# (DECISIONS #21): the right cutoff is a property of the team's cadence.
DEFAULT_DAYS = 30
MAX_DAYS = 3650


def resolve_days(days=None) -> int:
    """CLI/API override, then AMG_ARCHIVE_DAYS, then the default.

    Nonsense values fall back to the default and never to 0 — a typo must not
    archive everything from today (same ruling as the other thresholds).
    """
    if days is not None:
        try:
            value = int(days)
        except (TypeError, ValueError):
            return DEFAULT_DAYS
        return value if 0 < value <= MAX_DAYS else DEFAULT_DAYS
    raw = os.environ.get("AMG_ARCHIVE_DAYS")
    if raw is None:
        return DEFAULT_DAYS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_DAYS
    return value if 0 < value <= MAX_DAYS else DEFAULT_DAYS


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _atomic_write_text(path: str, text: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".amg-archive.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        if os.name != "nt":  # opening a directory for fsync is POSIX-only
            dirfd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _stamp_compact(stamp: str) -> str:
    """Filesystem-safe stamp (Windows rejects `:` in names)."""
    return "".join(ch for ch in stamp if ch.isdigit() or ch == "T")


def plan(doc: dict, days: int, at_iso: str = None) -> dict:
    """Which ledger records are cold enough to move.

    Only a *prefix* qualifies. The ledger is ordered by time, so a prefix keeps
    rev numbering contiguous after the move; a record that is old but sits behind a
    newer one is counted as `deferred_behind_newer` instead of being taken out of
    order. An undated record stops the prefix: unknown time is never a reason to
    move history (same conservative direction as TTL expiry).
    """
    day_count = resolve_days(days)
    at = parse_ts(at_iso or now())
    cutoff = at - timedelta(days=day_count)
    changes = doc.get("changes") or []
    eligible = 0
    for change in changes:
        moment = parse_ts(change.get("at"))
        if moment is None or moment >= cutoff:
            break
        eligible += 1
    tail = changes[eligible:]
    deferred = sum(1 for c in tail
                   if (parse_ts(c.get("at")) is not None and parse_ts(c.get("at")) < cutoff))
    unknown = sum(1 for c in tail if parse_ts(c.get("at")) is None)
    first = changes[0].get("rev") if eligible else None
    last = changes[eligible - 1].get("rev") if eligible else None
    return {
        "days": day_count,
        "cutoff": cutoff.isoformat(),
        "eligible": eligible,
        "rev_from": first if isinstance(first, int) else None,
        "rev_to": last if isinstance(last, int) else None,
        "deferred_behind_newer": deferred,
        "unknown_time_after_prefix": unknown,
        "changes_total": len(changes),
    }


def _archive_dir(graph_dir: str) -> str:
    return os.path.join(graph_dir, SUBDIR)


def _payload_digest(changes) -> str:
    """Digest of the records in order: a ledger is a sequence, not a set."""
    return _sha(_canon(changes))


def apply(memory, days: int = None, do_apply: bool = False, by: str = "amg archive") -> dict:
    """Dry-run by default. With `do_apply=True`: snapshot, move, prove, or restore.

    The proof is not a checksum of our own output. It compares three things that
    were produced independently: the bytes on disk before the change (the snapshot),
    the archive file as re-read from disk after writing it, and the persisted graph
    after commit. Records are compared canonically, in order; state is compared by
    `fingerprint.state_digest`, which must not move at all.
    """
    day_count = resolve_days(days)
    stamp = now()
    with memory.store.transaction() as (doc, commit):
        report = {"dry_run": not do_apply, "by": by, "archived": 0}
        report.update(plan(doc, day_count, stamp))
        if not do_apply or report["eligible"] == 0:
            memory._doc = doc
            return report

        changes = doc.get("changes") or []
        count = report["eligible"]
        moved, rest = changes[:count], changes[count:]
        snapshot_text = dumps(doc)
        state_before = fingerprint_mod.state_digest(doc)
        graph_dir = memory.store.dir
        archive_dir = _archive_dir(graph_dir)
        os.makedirs(os.path.join(archive_dir, "snapshots"), exist_ok=True)

        archive_rel = f"{SUBDIR}/changes-r{doc.get('rev', 0)}-{_stamp_compact(stamp)}.json"
        snapshot_rel = f"{SUBDIR}/snapshots/graph-r{doc.get('rev', 0)}-{_stamp_compact(stamp)}.json"
        payload = _payload_digest(moved)
        archived = {
            "schema": ARCHIVE_SCHEMA,
            "group": doc.get("group"),
            "archivedAt": stamp,
            "by": by,
            "days": report["days"],
            "cutoff": report["cutoff"],
            "sourceRev": doc.get("rev", 0),
            "count": len(moved),
            "revFrom": report["rev_from"],
            "revTo": report["rev_to"],
            "payloadSha256": payload,
            "changes": moved,
        }
        _atomic_write_text(os.path.join(graph_dir, snapshot_rel), snapshot_text)
        _atomic_write_text(os.path.join(graph_dir, archive_rel), dumps(archived))

        pointer = {
            "at": stamp, "by": by, "op": "archive", "target": archive_rel,
            "rev": int(doc.get("rev", 0)) + 1,
            "note": (f"{len(moved)} change record(s) rev {report['rev_from']}.."
                     f"{report['rev_to']} moved to {archive_rel} "
                     f"(payload {payload[:16]}…); snapshot {snapshot_rel}"),
        }
        doc["changes"] = rest + [pointer]
        commit()
        memory._doc = doc

    report["archived"] = count
    report["archive"] = {"file": archive_rel, "payload_sha256": payload,
                         "count": count, "bytes": os.path.getsize(
                             os.path.join(graph_dir, archive_rel))}
    report["snapshot"] = {"file": snapshot_rel, "sha256": _sha(snapshot_text),
                          "bytes": len(snapshot_text.encode("utf-8"))}
    report["bytes_before"] = len(snapshot_text.encode("utf-8"))
    report["rev"] = memory._doc.get("rev", 0)

    verification = _verify_roundtrip(graph_dir, moved, rest, snapshot_text, state_before)
    report["verify"] = verification
    report["bytes_after"] = os.path.getsize(memory.store.file) if os.path.exists(memory.store.file) else None
    if not verification["ok"]:
        # Put the snapshot back: a failed proof is not a reason to keep the change.
        _atomic_write_text(memory.store.file, snapshot_text)
        with memory.store.locked():
            memory._doc = memory.store.read()
        raise ProtocolError(
            "E_ARCHIVE_VERIFY",
            f"archive verification failed for {archive_rel}: {verification['reasons']}; "
            f"the graph was restored from {snapshot_rel}")
    return report


def _verify_roundtrip(graph_dir: str, moved: list, rest: list, snapshot_text: str,
                      state_before: str) -> dict:
    """Independent re-read: archive file from disk, graph from disk, snapshot bytes."""
    reasons = []
    snapshot_doc = json.loads(snapshot_text)
    graph_path = os.path.join(graph_dir, "graph.json")
    with open(graph_path, "r", encoding="utf-8") as fh:
        live = json.load(fh)

    # 1. The archive file as persisted must hold exactly the records we moved.
    archive_files = sorted(_archive_files(graph_dir))
    archived_back = []
    archive_ok = False
    if archive_files:
        with open(archive_files[-1], "r", encoding="utf-8") as fh:
            written = json.load(fh)
        archive_ok = (written.get("count") == len(moved)
                      and written.get("payloadSha256") == _payload_digest(moved)
                      and [_canon(c) for c in written.get("changes") or []] == [_canon(c) for c in moved])
        if not archive_ok:
            reasons.append("archive file does not reproduce the moved records")
        archived_back = written.get("changes") or []
    else:
        reasons.append("no archive file was written")

    # 2. What is left in the live file must be the unmoved remainder plus one pointer.
    live_changes = live.get("changes") or []
    pointer = live_changes[-1] if live_changes else {}
    body = live_changes[:-1]
    live_ok = ([_canon(c) for c in body] == [_canon(c) for c in rest]
               and pointer.get("op") == "archive"
               and [_canon(c) for c in archived_back] == [_canon(c) for c in moved])
    if not live_ok:
        reasons.append("live ledger is not remainder + one archive pointer")

    # 3. Nothing but the ledger may have moved.
    state_after = fingerprint_mod.state_digest(live)
    state_ok = state_after == state_before
    if not state_ok:
        reasons.append("state digest changed; archiving must not touch nodes or edges")

    # 4. The graph must still pass its own structural checks.
    check = protocol.check(live)
    check_ok = bool(check["ok"])
    if not check_ok:
        reasons.append(f"graph check failed after archiving: {len(check['errors'])} error(s)")

    # 5. Rev numbers must stay contiguous across the boundary (no silent hole).
    #
    # A record without an integer `rev` is *unknown*, not a violation: graphs written
    # before `amg migrate` existed can carry such records, and refusing the archive
    # because we cannot prove contiguity would be a false alarm about data that is
    # fine. The check is skipped (reported as unknown) in that case, and the fix is
    # `amg migrate`, which numbers them.
    revs = [c.get("rev") for c in archived_back if isinstance(c.get("rev"), int)]
    live_revs = [c.get("rev") for c in live_changes if isinstance(c.get("rev"), int)]
    unnumbered = sum(1 for c in list(archived_back) + list(live_changes)
                     if not isinstance(c.get("rev"), int))
    contiguous = None
    if unnumbered:
        contiguous = None
    elif revs and live_revs:
        contiguous = (max(revs) + 1 == min(live_revs)
                      and revs == sorted(revs) and live_revs == sorted(live_revs))
        if not contiguous:
            reasons.append("rev numbering is not contiguous across the archive boundary")

    return {
        "ok": not reasons,
        "archive_payload_match": archive_ok,
        "live_ledger_match": live_ok,
        "state_unchanged": state_ok,
        "check_ok": check_ok,
        "rev_contiguous": contiguous,
        "rev_unnumbered": unnumbered,
        "archived": len(moved),
        "live": len(live_changes),
        "reasons": reasons,
    }


def _archive_files(graph_dir: str) -> list:
    """Archive payload files, oldest first (`changes-*.json` only, not snapshots)."""
    directory = _archive_dir(graph_dir)
    if not os.path.isdir(directory):
        return []
    names = [n for n in os.listdir(directory) if n.startswith("changes-") and n.endswith(".json")]
    found = []

    def sort_key(name):
        try:
            with open(os.path.join(directory, name), "r", encoding="utf-8") as fh:
                head = json.load(fh)
            return (head.get("sourceRev") or 0, name)
        except (OSError, ValueError):
            return (0, name)

    found.extend(sorted(names, key=sort_key))
    return [os.path.join(directory, n) for n in found]


def verify(graph_dir: str) -> dict:
    """Audit every archive file and its boundary with the live ledger.

    Recomputes each payload digest from the file's own bytes, then checks that rev
    numbers appear exactly once and form one contiguous range across archives and
    live history. A hole here is the visible symptom of a record that was dropped —
    which is the thing the whole exercise exists to make impossible to hide.
    """
    from .store import Store

    store = Store(graph_dir)
    live = store.read_locked()
    live_changes = live.get("changes") or []
    files, total, reasons = [], 0, []
    archived_records = []

    for path in _archive_files(graph_dir):
        with open(path, "r", encoding="utf-8") as fh:
            try:
                head = json.load(fh)
            except ValueError:
                reasons.append(f"{os.path.basename(path)} is not valid JSON")
                files.append({"file": os.path.basename(path), "ok": False})
                continue
        records = head.get("changes") or []
        payload = _payload_digest(records)
        ok = (head.get("schema") == ARCHIVE_SCHEMA
              and head.get("count") == len(records)
              and head.get("payloadSha256") == payload)
        if not ok:
            reasons.append(f"{os.path.basename(path)}: payload digest or header mismatch")
        total += len(records)
        archived_records.extend(records)
        files.append({"file": os.path.basename(path), "count": len(records),
                      "revFrom": head.get("revFrom"), "revTo": head.get("revTo"),
                      "payload_sha256": payload, "ok": ok})

    revs = [c.get("rev") for c in archived_records if isinstance(c.get("rev"), int)]
    live_revs = [c.get("rev") for c in live_changes if isinstance(c.get("rev"), int)]
    all_revs = revs + live_revs
    counts = {}
    for rev in all_revs:
        counts[rev] = counts.get(rev, 0) + 1
    duplicates = sorted(rev for rev, seen in counts.items() if seen > 1)
    gaps = []
    continuity = None
    undated = sum(1 for c in archived_records + live_changes if not isinstance(c.get("rev"), int))
    if all_revs:
        expected = list(range(min(all_revs), max(all_revs) + 1))
        gaps = [r for r in expected if r not in set(all_revs)]
        # Unnumbered records (pre-`amg migrate`) make contiguity unknowable rather
        # than false; a duplicate rev is still hard evidence and is always reported.
        continuity = None if undated else (not gaps and not duplicates)
        if gaps and not undated:
            reasons.append(f"rev gap(s) across archive and live ledger: {gaps[:10]}"
                           + ("" if len(gaps) <= 10 else f" (+{len(gaps) - 10} more)"))
        if duplicates:
            reasons.append(f"rev number(s) appear twice: {duplicates[:10]}")
    return {
        "ok": not reasons,
        "files": files,
        "archived_records": total,
        "live_records": len(live_changes),
        "records_without_rev": undated,
        "rev_range": [min(all_revs), max(all_revs)] if all_revs else None,
        "rev_continuity": continuity,
        "gaps": gaps[:100],
        "duplicates": duplicates[:100],
        "reasons": reasons,
    }
