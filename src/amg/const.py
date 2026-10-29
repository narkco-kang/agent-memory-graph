"""Enumerations and protocol constants. Mirrors docs/API.md (amg/v1)."""
import datetime
import os

SCHEMA = "amg/v1"

NODE_TYPES = {"group", "member", "task", "decision", "artifact", "issue", "model", "env", "question", "rule"}

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


def is_conclusion(node: dict) -> bool:
    if node.get("conclusion") is not None:
        return bool(node["conclusion"])
    return node.get("type") in CONCLUSION_TYPES
