"""Subprocess contracts for the MCP server's stdio boundary."""

import json
import os
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


def _receive(selector, process, request_id, buffers, stderr, replies, frames):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and request_id not in replies:
        _pump(selector, deadline - time.monotonic(), buffers, stderr, replies, frames)
    if request_id not in replies:
        raise AssertionError(f"MCP reply {request_id} timed out; frames={frames!r}; stderr={stderr.decode(errors='replace')}; exit={process.poll()}")


def _pump(selector, timeout, buffers, stderr, replies, frames):
    for key, _ in selector.select(timeout):
        chunk = os.read(key.fileobj.fileno(), 65536)
        if not chunk:
            selector.unregister(key.fileobj)
        elif key.data == "stderr":
            stderr.extend(chunk)
        else:
            _parse_frames(chunk, buffers, frames, replies)


def _parse_frames(chunk, buffers, frames, replies):
    buffers.extend(chunk)
    while b"\n" in buffers:
        line, _, rest = buffers.partition(b"\n")
        buffers[:] = rest
        if line:
            message = json.loads(line)
            frames.append(message)
            if message.get("id") is not None:
                replies[message["id"]] = message


def _exchange(process, requests):
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers, stderr, replies, frames = bytearray(), bytearray(), {}, []
    def send(message):
        process.stdin.write((json.dumps(message) + "\n").encode())
        process.stdin.flush()
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "contract", "version": "1"}}})
        _receive(selector, process, 1, buffers, stderr, replies, frames)
        send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        for message in requests:
            send(message)
            _receive(selector, process, message["id"], buffers, stderr, replies, frames)
        process.stdin.close()
        process.wait(timeout=10)
        return replies, stderr
    finally:
        selector.close()


class MCPStdioContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp = tempfile.TemporaryDirectory()
        cls.database = str(Path(cls.temp.name) / "mcp.sqlite3")
        env = {**os.environ, "EMPORIO_DB_PATH": cls.database}
        for args in (("migrate", "--noinput"), ("load_sources", "--source-dir", str(ROOT / "data"))):
            result = subprocess.run([sys.executable, "manage.py", *args], cwd=ROOT, env=env, text=True, capture_output=True)
            if result.returncode:
                raise AssertionError(result.stderr or result.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        super().tearDownClass()

    def _session(self, requests, sender=None):
        env = {**os.environ, "EMPORIO_DB_PATH": self.database}
        env.pop("EMPORIO_MCP_SENDER", None)
        if sender:
            env["EMPORIO_MCP_SENDER"] = sender
        process = subprocess.Popen([sys.executable, "manage.py", "mcp_server"], cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        try:
            replies, stderr = _exchange(process, requests)
            self.assertEqual(process.returncode, 0, stderr.decode(errors="replace"))
            return replies
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()

    def test_real_stdio_lists_exact_four_bounded_tools_and_answers_public_queries(self):
        requests = [{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_catalog", "arguments": {"query": "Takamine GD20"}}}, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "search_catalog", "arguments": {"query": "no such instrument zxqv-9281"}}}]
        replies = self._session(requests)
        tools = replies[2]["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, {"search_catalog", "lookup_public_policy", "list_own_orders", "get_own_order_status", "read_store_manual"})
        expected = {item["function"]["name"]: item["function"]["parameters"] for item in json.loads((ROOT / "docs/tool-schemas.json").read_text())}
        self.assertEqual({tool["name"]: tool["inputSchema"] for tool in tools}, expected)
        forbidden = {"sender", "customer_id", "provider", "model", "snapshot_version"}
        self.assertTrue(all(not forbidden.intersection(tool["inputSchema"]["properties"]) for tool in tools))
        output = replies[3]["result"]["content"][0]["text"]
        self.assertIn("bundle_version", output)
        self.assertIn("Takamine", output)
        no_match = json.loads(replies[4]["result"]["content"][0]["text"])
        self.assertEqual((no_match["outcome"], no_match["data"]), ("not_found", []))

    def test_stdio_exits_cleanly_after_initialized_list_and_eof(self):
        result = self._session([{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}])
        self.assertEqual(len(result[2]["result"]["tools"]), 5)

    def test_stdio_calls_keep_sender_trusted_and_reject_forged_arguments(self):
        calls = [{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_own_orders", "arguments": {}}}, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_own_orders", "arguments": {"sender": "5567998123456", "page": 1}}}, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_own_order_status", "arguments": {"order_id": 4, "customer_id": 1}}}]
        replies = self._session(calls)
        denied = replies[2]["result"]["content"][0]["text"]
        self.assertEqual(denied, replies[3]["result"]["content"][0]["text"])
        self.assertNotIn("5567998123456", denied)
        self.assertNotIn("tracking_code", denied)
        own_call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_own_order_status", "arguments": {"order_id": 4}}}
        own = json.loads(self._session([own_call], sender="5567998123456")[2]["result"]["content"][0]["text"])
        foreign = json.loads(self._session([own_call], sender="55679996547821")[2]["result"]["content"][0]["text"])
        self.assertEqual(own["outcome"], "found")
        self.assertNotIn("tracking_code", foreign)
