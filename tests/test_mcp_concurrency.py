"""Two MCP sessions and a CLI writing to one graph at the same time.

The existing concurrency tests use library processes; `tests/test_mcp.py` drives the
server handler with synthetic frames. Neither exercises the combination a real team
has: several long-lived agents, each with its own `amg mcp` process, plus a CLI
command, all writing one file across process boundaries.

That combination is exactly where the v0.6.0 Windows bug lived: `os.replace` cannot
replace a file another process holds open, and `Memory.open` used to read without
the lock. This test fails on that bug (it is what found it on Windows CI), and it
checks the ledger properties that matter more than latency:

  * every node that was written exists, none twice;
  * every write produced exactly one `changes[]` record;
  * the graph still passes `check --strict`;
  * no writer silently swallowed an error (a rejected write would make the counts
    disagree, so "no error reported" is not taken on faith).

One thread also opens the graph for reading (`check`) while the writes land, because
a read that races a replace is what broke Windows writers in v0.6.0.

Kept small enough for CI (15 writes, 5 reads); the latency story lives in
`docs/CONCURRENCY.md`.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

SERVERS = 2
WRITES_PER_SERVER = 5
CLI_WRITES = 5
READS = 5


def env():
    e = dict(os.environ)
    existing = e.get("PYTHONPATH")
    e["PYTHONPATH"] = SRC if not existing else SRC + os.pathsep + existing
    return e


def cli(*args, check=True):
    return subprocess.run([sys.executable, "-m", "amg.cli", *args],
                          capture_output=True, text=True, env=env(), check=check)


class McpSession:
    """The smallest possible stdio MCP client: one JSON-RPC call at a time."""

    def __init__(self, graph, timeout=30):
        self.timeout = timeout
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "amg.cli", "mcp", graph],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env())
        self.next_id = 0
        self.initialize()

    def _readline(self):
        box = {}

        def read():
            box["line"] = self.proc.stdout.readline()

        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        thread.join(self.timeout)
        if "line" not in box:
            self.proc.kill()
            raise AssertionError("MCP server stopped answering")
        return box["line"]

    def request(self, method, params):
        self.next_id += 1
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params}) + "\n")
        self.proc.stdin.flush()
        line = self._readline()
        if not line:
            raise AssertionError(f"MCP server closed the stream during {method}: "
                                 f"{self.proc.stderr.read()[:400]}")
        message = json.loads(line)
        if message.get("id") != self.next_id:
            raise AssertionError(f"response id mismatch: {message}")
        return message

    def initialize(self):
        result = self.request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "concurrency-test", "version": "1"}})
        self.server_version = result["result"]["serverInfo"]["version"]

    def add(self, node_id, label):
        response = self.request("tools/call", {"name": "memory_add", "arguments": {
            "id": node_id, "type": "task", "label": label, "source": "concurrency-test"}})
        return response["result"]

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
        finally:
            # Windows CI warned about unclosed pipes on every run; the readers'
            # threads hold them, so close them explicitly after the process is gone.
            for stream in (self.proc.stdout, self.proc.stderr):
                try:
                    stream.close()
                except (OSError, AttributeError):
                    pass


class McpConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-mcp-concurrency-")
        self.graph = os.path.join(self.dir, "mem")
        cli("init", self.graph, "--group", "concurrency", "--goal", "prove cross-process writes")

    def _run_writers(self):
        errors = []

        def server_writer(index):
            session = McpSession(self.graph)
            try:
                for n in range(WRITES_PER_SERVER):
                    result = session.add(f"task.s{index}.{n}", f"server {index} write {n}")
                    if result.get("isError"):
                        errors.append(f"server {index} write {n} was refused: {result}")
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                errors.append(f"server {index}: {type(exc).__name__}: {exc}")
            finally:
                session.close()

        def cli_writer():
            for n in range(CLI_WRITES):
                res = cli("add", self.graph, "--id", f"task.cli.{n}", "--type", "task",
                          "--label", f"cli write {n}", "--source", "concurrency-test",
                          check=False)
                if res.returncode != 0:
                    errors.append(f"cli write {n} failed ({res.returncode}): "
                                  f"{res.stderr or res.stdout}")

        def reader():
            # A read opening the graph while another process replaces it is the
            # exact shape of the v0.6.0 Windows bug: os.replace fails when another
            # process holds the file open, and reads used to take no lock.
            for n in range(READS):
                res = cli("check", self.graph, check=False)
                if res.returncode != 0:
                    errors.append(f"concurrent read {n} failed ({res.returncode}): "
                                  f"{res.stderr or res.stdout}")

        threads = [threading.Thread(target=server_writer, args=(i,)) for i in range(SERVERS)]
        threads.append(threading.Thread(target=cli_writer))
        threads.append(threading.Thread(target=reader))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        self.assertFalse([t for t in threads if t.is_alive()], "a writer thread hung")
        self.assertEqual(errors, [], "concurrent writers reported errors")

    def test_two_servers_and_a_cli_lose_nothing(self):
        self._run_writers()

        with open(os.path.join(self.graph, "graph.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        expected = SERVERS * WRITES_PER_SERVER + CLI_WRITES

        ids = [node["id"] for node in doc["nodes"]]
        self.assertEqual(len(ids), expected, "node count is wrong")
        self.assertEqual(len(set(ids)), expected, "a node id was written twice")

        adds = [change for change in doc["changes"] if change["op"] == "add-node"]
        self.assertEqual(len(adds), expected,
                         "the ledger does not have exactly one record per write")
        self.assertEqual(len({change["target"] for change in adds}), expected,
                         "a write has more than one ledger record")

        checked = cli("check", self.graph, "--strict", check=False)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)


if __name__ == "__main__":
    unittest.main()
