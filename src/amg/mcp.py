"""Minimal MCP server over stdio (newline-delimited JSON-RPC 2.0).

Design constraints, on purpose:

- **stdio only.** No socket, no port, no HTTP. The memory is a local file and
  this server does not make it reachable from the network.
- **no new write paths.** Every tool calls the same `Memory` methods the CLI
  uses, so the evidence gate, IR-2 and IR-4 apply unchanged.
- **no authentication**, therefore: local, trusted, single user. This is stated
  in the README and in SECURITY.md rather than implied.
- **optional read-only mode.** `--read-only` refuses the write tools before
  dispatch (and the underlying `Memory` refuses every commit anyway), so a
  prompt-injected client cannot mutate the graph through this server. It does
  not protect the file from other processes: see docs/THREAT-MODEL.md.

stdout carries protocol messages only; anything diagnostic goes to stderr, so a
client never sees a corrupted frame.
"""
import json
import sys

from . import __version__
from .errors import ProtocolError

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "amg", "version": __version__}

# Every advertised tool must land in exactly one of these sets (a test asserts
# the partition is complete), so a new tool cannot be added without deciding
# whether `--read-only` may expose it.
READ_TOOLS = frozenset({
    "memory_search", "memory_related", "memory_check", "memory_audit", "memory_digest",
})
WRITE_TOOLS = frozenset({"memory_add", "memory_status", "memory_supersede"})

READ_ONLY_INSTRUCTIONS = (
    "read-only: this server refuses memory_add, memory_status and memory_supersede. "
    "The graph file cannot be modified through this session."
)

TOOLS = [
    {
        "name": "memory_search",
        "description": "Search the memory graph. Returns hits with anchor_state, evidence count and status. "
                       "Lexical only; unanchored hits are returned by default (anchor_state='none').",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"},
            "layer": {"type": "string", "enum": ["L1", "L2", "L3", "L4"]},
            "k": {"type": "integer", "minimum": 1},
            "strict": {"type": "boolean"},
            "expand": {"type": "boolean"}},
            "required": ["query"], "additionalProperties": False},
    },
    {
        "name": "memory_add",
        "description": "Add one node. Conclusion-typed nodes cannot be 'done' without an evidence object; "
                       "bare-string evidence is rejected.",
        "inputSchema": {"type": "object", "properties": {
            "id": {"type": "string"}, "type": {"type": "string"},
            "label": {"type": "string"}, "source": {"type": "string"},
            "status": {"type": "string"}, "owner": {"type": "string"},
            "note": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "object"}},
            "valid_from": {"type": "string"}, "valid_until": {"type": "string"}},
            "required": ["id", "type", "label", "source"], "additionalProperties": False},
    },
    {
        "name": "memory_status",
        "description": "Change a node's status. A note is mandatory (IR-4). Use memory_supersede for superseding.",
        "inputSchema": {"type": "object", "properties": {
            "id": {"type": "string"}, "status": {"type": "string"}, "note": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "object"}}},
            "required": ["id", "status", "note"], "additionalProperties": False},
    },
    {
        "name": "memory_supersede",
        "description": "Supersede an old node with a new one. The old node is kept with a validity stamp.",
        "inputSchema": {"type": "object", "properties": {
            "old_id": {"type": "string"}, "new_id": {"type": "string"}, "note": {"type": "string"}},
            "required": ["old_id", "new_id", "note"], "additionalProperties": False},
    },
    {
        "name": "memory_related",
        "description": "Walk edges around a node (depth and kind filters).",
        "inputSchema": {"type": "object", "properties": {
            "id": {"type": "string"}, "depth": {"type": "integer", "minimum": 0, "maximum": 5},
            "kind": {"type": "string"}},
            "required": ["id"], "additionalProperties": False},
    },
    {
        "name": "memory_check",
        "description": "Structural checks (IR-1..IR-4, cycles on depends_on/supersedes).",
        "inputSchema": {"type": "object", "properties": {"strict": {"type": "boolean"}},
                         "additionalProperties": False},
    },
    {
        "name": "memory_audit",
        "description": "Audit: legacy coverage, staleness, expiry, dangling edges, change shapes.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "memory_digest",
        "description": "Bounded, pointer-only digest of current state.",
        "inputSchema": {"type": "object", "properties": {"max_bytes": {"type": "integer", "minimum": 256}},
                         "additionalProperties": False},
    },
]


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def tools(read_only: bool = False):
    """Advertised tool list. Hiding write tools is UX, not enforcement."""
    if not read_only:
        return TOOLS
    return [t for t in TOOLS if t["name"] in READ_TOOLS]


def _call_tool(memory, name: str, args: dict, read_only: bool = False):
    if read_only and name in WRITE_TOOLS:
        raise ProtocolError(
            "E_READ_ONLY",
            f"{name} is not available: this server was started read-only")
    if name == "memory_search":
        return memory.search(args["query"], layer=args.get("layer", "L3"),
                             k=args.get("k", 10), strict=args.get("strict", False),
                             expand=args.get("expand", False), by="mcp")
    if name == "memory_add":
        return memory.add_node(
            id=args["id"], type=args["type"], label=args["label"], source=args["source"],
            status=args.get("status", "open"), owner=args.get("owner"),
            note=args.get("note", ""), evidence=args.get("evidence"),
            valid_from=args.get("valid_from"), valid_until=args.get("valid_until"), by="mcp")
    if name == "memory_status":
        return memory.set_status(args["id"], args["status"], note=args["note"],
                                 evidence=args.get("evidence"), by="mcp")
    if name == "memory_supersede":
        return memory.supersede(args["old_id"], args["new_id"], note=args["note"], by="mcp")
    if name == "memory_related":
        return memory.related(args["id"], depth=args.get("depth", 1), kind=args.get("kind"))
    if name == "memory_check":
        return memory.check(strict=args.get("strict", False))
    if name == "memory_audit":
        return memory.audit()
    if name == "memory_digest":
        return {"digest": memory.digest(max_bytes=args.get("max_bytes", 65536))}
    raise JsonRpcError(-32601, f"unknown tool: {name}")


def handle(memory, message: dict, read_only: bool = False) -> dict:
    """Handle one JSON-RPC message. Returns a response dict or None for notifications."""
    method = message.get("method")
    msg_id = message.get("id")
    if msg_id is None and method and method.startswith("notifications/"):
        return None
    if method == "initialize":
        result = {"protocolVersion": PROTOCOL_VERSION,
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": SERVER_INFO}
        if read_only:
            result["instructions"] = READ_ONLY_INSTRUCTIONS
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools(read_only)}}
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if not name:
            raise JsonRpcError(-32602, "params.name is required")
        try:
            result = _call_tool(memory, name, args, read_only=read_only)
        except Exception as exc:  # protocol violations are reported as tool errors
            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                "isError": True}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
            "isError": False}}
    raise JsonRpcError(-32601, f"unknown method: {method}")


def serve(memory, stdin=None, stdout=None, read_only: bool = False) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"parse error: {exc}"}}
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
            continue
        try:
            response = handle(memory, message, read_only=read_only)
        except JsonRpcError as exc:
            response = {"jsonrpc": "2.0", "id": message.get("id"),
                        "error": {"code": exc.code, "message": exc.message}}
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0
