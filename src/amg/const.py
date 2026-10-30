"""Enumerations and protocol constants. Mirrors docs/API.md (amg/v1)."""
import datetime
import os

SCHEMA = "amg/v1"

NODE_TYPES = {"group", "member", "task", "decision", "artifact", "issue", "model", "env",
              "question", "rule", "handoff"}

STATUSES = {"proposed", "open", "in_progress", "done", "blocked", "superseded"}

EDGE_KINDS = {"depends_on", "blocks", "produced_by", "owned_by", "decided_by",
              "supersedes", "relates_to", "part_of"}

# Types whose nodes assert a conclusion. The write gate is triggered by
# content type, not by status (a finished conclusion may still be in_progress).
CONCLUSION_TYPES = {"decision", "artifact"}

LOCATOR_PREFIXES = ("path:", "cmd:", "url:", "sha256:")

EXIT_OK = 0
EXIT_ERROR = 1     # protocol violation / check errors / audit conflicts
EXIT_USAGE = 2     # bad args, unknown enum, missing graph
EXIT_IO = 3        # lock timeout, io failure


def now() -> str:
    """ISO-8601 with local offset. AMG_NOW makes tests deterministic."""
    fixed = os.environ.get("AMG_NOW")
    if fixed:
        return fixed
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_ts(value):
    """Parse ISO-8601 into an aware datetime (naive values are treated as UTC).

    Returns None when the value is missing or unparseable, so callers can
    distinguish "unknown" from "malformed" by validating at the edges.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def not_yet_valid(node: dict, at: datetime.datetime = None) -> bool:
    """True when the node's validity window has not started yet.

    An absent or unparseable `valid_from` means *unknown*, not *future*:
    unknown validity is handled conservatively by expiry and never treated as
    pending. Only a parsed, future start is "not yet in effect".
    """
    start = parse_ts(node.get("valid_from"))
    if start is None:
        return False
    if at is None:
        at = parse_ts(now())
    return start > at


def is_conclusion(node: dict) -> bool:
    if node.get("conclusion") is not None:
        return bool(node["conclusion"])
    return node.get("type") in CONCLUSION_TYPES
