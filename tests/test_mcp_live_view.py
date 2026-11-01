"""F: read-only live view — reload per request, and a shape gate that cannot go quiet.

These pin the three properties the F plan rests on (DECISIONS #56):

1. a long-lived server re-reads the graph before every `tools/call`, so it sees
   what another process wrote while it was running (no restart, no re-adopt);
2. re-reading does not become a hole in `--read-only`: the reloaded instance is
   opened read-only, and `Memory` refuses the commit itself;
3. a graph whose shape would make hits silently incomplete is refused with an
   explicit error. Deleting `check_shape` must make `test_shape_gate_*` fail —
   that is the whole point of the test, not a decoration.

The third one is the reason this file exists. Measured on the team graph: a node
whose `label` is not a string still loads, the node count is unchanged, `search`
still returns a full page — and the node is unreachable for every query. Nothing
errors. A regression there looks exactly like success.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from amg import mcp as mcp_mod  # noqa: E402
from amg.errors import ProtocolError  # noqa: E402

SCHEMA_OK = {"schema": "group-kg/v1", "group": "t", "nodes": [], "edges": [], "changes": []}


def node(nid, label):
    return {"id": nid, "type": "task", "label": label, "status": "open",
            "owner": "", "source": "fixture", "note": "", "evidence": []}


def doc(*nodes, schema="group-kg/v1"):
    return {"schema": schema, "group": "t", "nodes": list(nodes), "edges": [], "changes": []}


def frame(**kw):
    return json.dumps(kw, ensure_ascii=False)


class ShapeGateTest(unittest.TestCase):
    """The gate must reject shapes that would produce plausible-but-incomplete hits."""

    def test_shape_gate_accepts_a_well_formed_graph(self):
        mcp_mod.check_shape(doc(node("a", "alpha")))

    def test_shape_gate_accepts_both_schemas_this_build_reads(self):
        for schema in ("amg/v1", "group-kg/v1"):
            mcp_mod.check_shape(doc(node("a", "alpha"), schema=schema))

    def test_shape_gate_rejects_a_non_string_label(self):
        """The exact mutation that goes silent: the node is still in the document."""
        for bad in (None, 123, ["list"], {"k": 1}):
            with self.assertRaises(ProtocolError) as ctx:
                mcp_mod.check_shape(doc(node("a", "alpha"), node("gone", bad)))
            self.assertEqual(ctx.exception.code, "E_GRAPH_SHAPE")
            self.assertIn("gone", str(ctx.exception),
                          "the error must name the node, not just say 'bad graph'")

    def test_shape_gate_rejects_non_string_ids(self):
        with self.assertRaises(ProtocolError) as ctx:
            mcp_mod.check_shape(doc(node(None, "alpha")))
        self.assertEqual(ctx.exception.code, "E_GRAPH_SHAPE")

    def test_shape_gate_rejects_an_unknown_schema(self):
        with self.assertRaises(ProtocolError) as ctx:
            mcp_mod.check_shape(doc(node("a", "alpha"), schema="group-kg/v2"))
        self.assertEqual(ctx.exception.code, "E_GRAPH_SHAPE")

    def test_shape_gate_rejects_a_missing_schema(self):
        bad = doc(node("a", "alpha"))
        del bad["schema"]
        with self.assertRaises(ProtocolError) as ctx:
            mcp_mod.check_shape(bad)
        self.assertEqual(ctx.exception.code, "E_GRAPH_SHAPE")

    def test_a_non_string_label_really_is_unreachable_without_the_gate(self):
        """Documents WHY the gate exists: without it, search returns a full page and misses.

        This is the measured failure, not a guess. If this ever stops being true
        (because scoring learns to coerce labels), the gate is still correct but
        the rationale needs revisiting — so the assertion is on the miss itself.
        """
        from amg.memory import Memory
        tmp = tempfile.mkdtemp(prefix="amg-shape-")
        path = tmp
        nodes = [node("target", "quantum widgets quantum widgets")]
        for i in range(10):
            nodes.append(node(f"filler{i:02d}", "quantum widgets filler"))
        nodes[-1]["label"] = None          # the healthy answer, broken silently
        broken_id = nodes[-1]["id"]        # filler10

        with open(os.path.join(path, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(*nodes), fh, ensure_ascii=False)
        memory = Memory.open(path, read_only=True)
        hits = memory.search("quantum widgets", k=5)
        ids = [h["id"] for h in hits]
        self.assertEqual(len(hits), 5, "search still returns a full page")
        self.assertNotIn(broken_id, ids, "and the broken node is simply gone")


class ReloadTest(unittest.TestCase):
    """A long-lived server must see commits made by another process."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="amg-reload-")
        self.dir = os.path.join(self.tmp, "mem")
        self.path = self.dir
        os.makedirs(self.dir, exist_ok=True)
        self.write(self.dir, "schema: group-kg/v1")
        # write a plain legacy file the server can open directly
        with open(os.path.join(self.dir, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(node("first", "alpha beta")), fh, ensure_ascii=False)

    def write(self, _dir, extra):
        return extra

    def _run(self, messages, args=("--read-only",)):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        payload = "\n".join(messages) + "\n"
        return subprocess.run([sys.executable, "-m", "amg.cli", "mcp", self.dir, *args],
                              input=payload, capture_output=True, text=True,
                              encoding="utf-8", env=env, cwd=ROOT, timeout=60)

    def test_reload_is_announced_on_stderr(self):
        res = self._run([frame(jsonrpc="2.0", id=1, method="initialize", params={})])
        self.assertIn("reload per tools/call", res.stderr)

    def test_no_reload_restores_the_old_cached_behaviour(self):
        res = self._run([frame(jsonrpc="2.0", id=1, method="initialize", params={})],
                        args=("--read-only", "--no-reload"))
        self.assertIn("no-reload", res.stderr)


class ReloadSeesExternalWriteTest(unittest.TestCase):
    """The end-to-end property: write from outside, next call sees it, no restart."""

    def test_reopen_sees_a_node_written_by_another_process(self):
        from amg.memory import Memory
        path = tempfile.mkdtemp(prefix="amg-live-")
        with open(os.path.join(path, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(node("first", "alpha beta")), fh, ensure_ascii=False)

        before = Memory.open(path, read_only=True)
        self.assertFalse(any(h["id"] == "late" for h in before.search("late arrival", k=3)))

        data = json.load(open(os.path.join(path, "graph.json"), encoding="utf-8"))
        data["nodes"].append(node("late", "late arrival marker"))
        with open(os.path.join(path, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)

        reopened = Memory.open(path, read_only=True)
        self.assertTrue(any(h["id"] == "late" for h in reopened.search("late arrival", k=3)),
                        "re-reading the graph is what makes the view live")

    def test_reload_cannot_escape_read_only(self):
        """Reopening must reuse the same read_only flag; commit refuses regardless."""
        from amg.memory import Memory
        path = tempfile.mkdtemp(prefix="amg-ro-")
        with open(os.path.join(path, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(node("first", "alpha beta")), fh, ensure_ascii=False)
        fresh = Memory.open(path, read_only=True)
        self.assertTrue(fresh.read_only)
        with self.assertRaises(ProtocolError) as ctx:
            fresh.add_node(id="nope", type="task", label="x", source="fixture", note="")
        self.assertEqual(ctx.exception.code, "E_READ_ONLY")


class ServeShapeGateTest(unittest.TestCase):
    """The gate is wired into the request path, not only callable in isolation."""

    def test_a_tools_call_on_a_broken_graph_is_an_error_not_an_empty_answer(self):
        from amg.memory import Memory

        class FakeMemory:
            def __init__(self, d):
                self.doc = d

        broken = doc(node("ok", "alpha"), node("bad", None))
        replies = []
        stdin = [frame(jsonrpc="2.0", id=1, method="tools/call",
                       params={"name": "memory_search", "arguments": {"query": "alpha"}}) + "\n"]

        class Out:
            def write(self, s):
                replies.append(s)

            def flush(self):
                pass

        mcp_mod.serve(FakeMemory(SCHEMA_OK), stdin=iter(stdin), stdout=Out(),
                      read_only=True, reopen=lambda: FakeMemory(broken))
        payload = json.loads(replies[0])
        self.assertIn("error", payload)
        self.assertIn("E_GRAPH_SHAPE", payload["error"]["message"])

    def test_no_reopen_means_the_startup_instance_is_used(self):
        class FakeMemory:
            def __init__(self, d):
                self.doc = d
                self.calls = 0

            def search(self, *_a, **_k):
                self.calls += 1
                return []

        replies = []

        class Out:
            def write(self, s):
                replies.append(s)

            def flush(self):
                pass

        mem = FakeMemory(SCHEMA_OK)
        stdin = [frame(jsonrpc="2.0", id=1, method="tools/call",
                       params={"name": "memory_search", "arguments": {"query": "x"}}) + "\n"]
        mcp_mod.serve(mem, stdin=iter(stdin), stdout=Out(), read_only=True, reopen=None)
        self.assertEqual(mem.calls, 1)
        self.assertIn("result", json.loads(replies[0]))


class ReloadKeepsReadOnlyEndToEndTest(unittest.TestCase):
    """A real server process must stay read-only across a reload.

    Mutation that this catches: opening the reloaded instance with
    `read_only=False` (i.e. reload becoming an escape hatch). Without this test
    that mutation passes every other test in this file — it did, before the test
    was written.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="amg-e2e-ro-")
        with open(os.path.join(self.dir, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(node("first", "alpha beta")), fh, ensure_ascii=False)

    def _call(self, tool, arguments):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        payload = "\n".join([
            frame(jsonrpc="2.0", id=1, method="initialize", params={}),
            frame(jsonrpc="2.0", method="notifications/initialized"),
            frame(jsonrpc="2.0", id=2, method="tools/call",
                  params={"name": tool, "arguments": arguments}),
        ]) + "\n"
        res = subprocess.run([sys.executable, "-m", "amg.cli", "mcp", self.dir, "--read-only"],
                             input=payload, capture_output=True, text=True,
                             encoding="utf-8", env=env, cwd=ROOT, timeout=60)
        replies = [json.loads(l) for l in res.stdout.splitlines() if l.strip()]
        return replies[-1], res

    def test_write_after_reload_is_still_refused(self):
        reply, res = self._call("memory_add", {
            "id": "evil", "type": "task", "label": "x", "status": "open", "source": "fixture"})
        self.assertEqual(reply["id"], 2)
        result = reply["result"]
        self.assertTrue(result.get("isError"), f"write must be refused; got {reply}")
        self.assertIn("E_READ_ONLY", result["content"][0]["text"],
                      "the refusal must be E_READ_ONLY, not a generic failure")
        self.assertIn("reload per tools/call", res.stderr,
                      "the reload path must actually be active, otherwise this test proves nothing")

    def test_graph_file_is_unchanged_after_the_session(self):
        import hashlib
        path = os.path.join(self.dir, "graph.json")
        before = hashlib.sha256(open(path, "rb").read()).hexdigest()
        self._call("memory_search", {"query": "alpha", "k": 3})
        after = hashlib.sha256(open(path, "rb").read()).hexdigest()
        self.assertEqual(before, after, "a read-only session must not touch the file")


class ReloadIsRealEndToEndTest(unittest.TestCase):
    """A running server must return a node another process wrote AFTER it started.

    Mutation this catches: `reopen = None` (silently fall back to the startup
    snapshot). Every other test in this file passes under that mutation, so
    without this one "reload per request" could be dead code that looks alive.

    The write happens between two calls of the SAME server process, which is the
    only way to prove the graph was re-read rather than cached.
    """

    def test_a_node_written_mid_session_is_visible_to_the_next_call(self):
        d = tempfile.mkdtemp(prefix="amg-mid-")
        with open(os.path.join(d, "graph.json"), "w", encoding="utf-8") as fh:
            json.dump(doc(node("first", "alpha beta")), fh, ensure_ascii=False)

        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(ROOT, "src")
        proc = subprocess.Popen(
            [sys.executable, "-m", "amg.cli", "mcp", d, "--read-only"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env, cwd=ROOT)

        def send(obj):
            proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
            proc.stdin.flush()

        def call(msg_id, query):
            send({"jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
                  "params": {"name": "memory_search", "arguments": {"query": query, "k": 3}}})
            while True:
                line = proc.stdout.readline()
                if not line:
                    raise AssertionError("server closed unexpectedly")
                payload = json.loads(line)
                if payload.get("id") == msg_id:
                    text = payload["result"]["content"][0]["text"]
                    return json.loads(text) if not payload["result"].get("isError") else text

        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            while json.loads(proc.stdout.readline()).get("id") != 1:
                pass
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})

            before = call(2, "mid session marker")
            self.assertFalse(any(h["id"] == "midway" for h in before),
                             "the node must not exist yet")

            # another process writes, while this server keeps running
            data = json.load(open(os.path.join(d, "graph.json"), encoding="utf-8"))
            data["nodes"].append(node("midway", "mid session marker"))
            with open(os.path.join(d, "graph.json"), "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)

            after = call(3, "mid session marker")
            self.assertTrue(any(h["id"] == "midway" for h in after),
                            "the same server must see a write made after it started")
        finally:
            proc.kill()
            proc.communicate(timeout=10)


class SameDataPlaneScoresTest(unittest.TestCase):
    """Direct read and adopt must score identically WHEN the nodes are the same.

    Why this exists: a 1.8% score difference was attributed to the direct-read
    path. It was not — it came from comparing a raw graph against an adopt-rewritten
    copy (`source` is backfilled, and `source` carries weight 0.5). The distinction
    matters because a guardrail must compare like with like. This test would have
    caught the misattribution: same nodes in, identical scores out.

    Note the deliberate limit: this pins the score, not `anchor_state`. Adopt moves
    bare-string evidence into `legacy_evidence` and leaves `evidence` empty, so the
    two views legitimately disagree on anchoring. Scores must match; anchor is a
    different data plane and is not compared here.
    """

    def test_identical_node_payloads_score_identically(self):
        from amg.memory import Memory
        nodes = [node("a", "anchored probe alpha"), node("b", "plain beta gamma"),
                 node("c", "another alpha delta")]
        nodes[0]["evidence"] = [{"locator": "path:x.txt", "content_sha256": "0" * 64,
                                 "captured_at": "2026-01-01T00:00:00Z"}]
        for label, schema in (("amg", "amg/v1"), ("legacy", "group-kg/v1")):
            d = tempfile.mkdtemp(prefix=f"amg-plane-{label}-")
            with open(os.path.join(d, "graph.json"), "w", encoding="utf-8") as fh:
                json.dump(doc(*nodes, schema=schema), fh, ensure_ascii=False)
            hits = Memory.open(d, read_only=True).search("alpha", k=3)
            if label == "amg":
                self.plane = {h["id"]: h["score"] for h in hits}
            else:
                self.assertEqual({h["id"]: h["score"] for h in hits}, self.plane,
                                 "same nodes must score the same in both schemas")


if __name__ == "__main__":
    unittest.main()
