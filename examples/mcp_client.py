#!/usr/bin/env python3
"""A real MCP client for `amg mcp`, in the standard library only.

The protocol tests check frames; this script checks the thing a user cares about:
another process speaking MCP to the server, with the graph's guarantees intact.
It starts `amg mcp` twice and asserts, end to end:

  1. `initialize` answers with the server's identity;
  2. `tools/list` advertises the eight documented tools;
  3. a `done` decision **without evidence** is refused over MCP
     (`E_EVIDENCE_MISSING`, `isError: true`) — the write gate is not a CLI feature
     that JSON-RPC can walk around;
  4. a valid write succeeds, and `memory_search` finds it;
  5. a server started with `--read-only` advertises five tools and refuses the
     same write with `E_READ_ONLY`;
  6. the graph on disk is still readable by the CLI afterwards.

Run it from the repository root (works from a checkout or an installed package):

    python examples/mcp_client.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
EXPECTED_TOOLS = {
    "memory_search", "memory_add", "memory_status", "memory_supersede",
    "memory_related", "memory_check", "memory_audit", "memory_digest",
}
READ_TOOLS = {
    "memory_search", "memory_related", "memory_check", "memory_audit", "memory_digest",
}


def env():
    """Prefer the checkout's src so this runs without installing; fall back to an install."""
    e = dict(os.environ)
    if os.path.isdir(SRC):
        existing = e.get("PYTHONPATH")
        e["PYTHONPATH"] = SRC if not existing else SRC + os.pathsep + existing
    return e


def run_cli(*args, check=True):
    return subprocess.run(
        [sys.executable, "-m", "amg.cli", *args],
        capture_output=True, text=True, env=env(), check=check,
    )


class McpError(RuntimeError):
    pass


class Client:
    """Minimal line-delimited JSON-RPC client for the stdio server."""

    def __init__(self, graph, *flags, timeout=15.0):
        self.timeout = timeout
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "amg.cli", "mcp", graph, *flags],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env(),
        )
        self.next_id = 0

    def _readline(self):
        box = {}

        def read():
            box["line"] = self.proc.stdout.readline()

        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        thread.join(self.timeout)
        if "line" not in box:
            self.kill()
            raise McpError(f"server did not answer within {self.timeout}s")
        return box["line"]

    def _send(self, payload):
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params=None):
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": self.next_id, "method": method,
                    "params": params or {}})
        line = self._readline()
        if not line:
            raise McpError(f"server closed the stream while handling {method}: "
                           f"{self.proc.stderr.read()[:400]}")
        message = json.loads(line)
        if message.get("id") != self.next_id:
            raise McpError(f"response id mismatch: {message}")
        if "error" in message:
            raise McpError(f"{method} returned JSON-RPC error: {message['error']}")
        return message["result"]

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def call_tool(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def kill(self):
        try:
            self.proc.kill()
        except OSError:
            pass

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired):
            self.kill()


def text_of(result):
    return "\n".join(part.get("text", "") for part in result.get("content", []))


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    workdir = tempfile.mkdtemp(prefix="amg-mcp-client-")
    graph = os.path.join(workdir, "mem")
    run_cli("init", graph, "--group", "client-demo", "--goal", "prove MCP works")
    print(f"graph: {graph}")

    client = Client(graph)
    try:
        # 1. handshake
        hello = client.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "amg-client-example", "version": "1"},
        })
        expect("protocolVersion" in hello, f"initialize result: {hello}")
        server = hello.get("serverInfo", {})
        print(f"1. initialize: protocol {hello['protocolVersion']}, "
              f"server {server.get('name')} {server.get('version')}")

        # 2. tool inventory, compared with what the documentation claims
        listed = client.request("tools/list")["tools"]
        names = {tool["name"] for tool in listed}
        expect(names == EXPECTED_TOOLS,
               f"tools/list mismatch: missing {EXPECTED_TOOLS - names}, "
               f"unexpected {names - EXPECTED_TOOLS}")
        print(f"2. tools/list: {len(names)} tools, exactly the documented set")

        # 3. the evidence gate, over JSON-RPC
        blocked = client.call_tool("memory_add", {
            "id": "decision.unbacked", "type": "decision",
            "label": "we shipped it", "source": "standup", "status": "done",
        })
        expect(blocked.get("isError") is True, f"unbacked done write was accepted: {blocked}")
        expect("E_EVIDENCE_MISSING" in text_of(blocked),
               f"wrong rejection: {text_of(blocked)[:300]}")
        print("3. an evidence-free `done` write is refused over MCP "
              "(E_EVIDENCE_MISSING) — the gate is not a CLI feature")

        # 4. a valid write, and a search that finds it
        added = client.call_tool("memory_add", {
            "id": "task.parser", "type": "task", "label": "write the parser",
            "source": "standup", "status": "in_progress",
        })
        expect(not added.get("isError"), f"valid write failed: {text_of(added)[:300]}")
        found = client.call_tool("memory_search", {"query": "parser", "k": 3})
        expect(not found.get("isError"), f"search failed: {text_of(found)[:300]}")
        expect("task.parser" in text_of(found), f"search did not find the node: {text_of(found)[:300]}")
        print("4. a valid write succeeds and memory_search returns it")

        # 5. read-only is enforced server-side, not by hiding the tool
        readonly = Client(graph, "--read-only")
        try:
            ro_hello = readonly.request("initialize", {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "amg-client-example", "version": "1"}})
            expect("read-only" in (ro_hello.get("instructions") or "").lower(),
                   "read-only server did not explain itself in initialize")
            ro_names = {tool["name"] for tool in readonly.request("tools/list")["tools"]}
            expect(ro_names == READ_TOOLS,
                   f"read-only tools/list mismatch: {sorted(ro_names)}")
            refused = readonly.call_tool("memory_add", {
                "id": "task.sneaky", "type": "task", "label": "x", "source": "x"})
            expect("E_READ_ONLY" in text_of(refused),
                   f"read-only write was not refused by name: {text_of(refused)[:300]}")
            print(f"5. --read-only: {len(ro_names)} read tools advertised, "
                  "write refused with E_READ_ONLY")
        finally:
            readonly.close()
    finally:
        client.close()

    # 6. the file the server wrote is a normal graph
    checked = run_cli("check", graph, "--strict", check=False)
    expect(checked.returncode == 0, f"check --strict failed: {checked.stdout}{checked.stderr}")
    audit = run_cli("audit", graph, check=False)
    expect(audit.returncode in (0, 1), f"audit crashed: {audit.stderr[:300]}")
    print("6. check --strict passes on the graph the server wrote")

    print("\nMCP client demo passed: handshake, inventory, gate, read-only enforcement.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"\nMCP client demo FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
