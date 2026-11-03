"""Negative wire contracts for provider configuration and response parsing."""

import importlib
import json

import httpx
from django.test import SimpleTestCase


def _replayed_assistant(messages):
    return next(message for message in messages if message["role"] == "assistant")


def _replayed_tool_results(messages):
    results = []
    for message in messages:
        for block in message["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                results.append(block)
    return results


class AnthropicMalformedWireContractTests(SimpleTestCase):
    def test_anthropic_rejects_invalid_configuration_before_http(self):
        module = importlib.import_module("emporio.chat.anthropic")
        for options, message in (({"api_key": "", "model": "m"}, "ANTHROPIC_API_KEY"), ({"api_key": "key", "model": ""}, "ANTHROPIC_MODEL")):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                module.AnthropicClient(**options)

    def test_anthropic_rejects_incomplete_oversized_and_malformed_wire_blocks(self):
        module = importlib.import_module("emporio.chat.anthropic")
        bodies = [{}, {"stop_reason": "max_tokens", "content": []}, {"stop_reason": "end_turn", "content": [1]}, {"stop_reason": "end_turn", "content": [{"type": "unknown"}]}, {"stop_reason": "end_turn", "content": []}, {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "", "name": "lookup", "input": {}}]}, {"stop_reason": "end_turn", "content": [{"type": "text", "text": "x" * 33_000}]}]
        for body in bodies:
            client = httpx.Client(transport=httpx.MockTransport(lambda request, body=body: httpx.Response(200, json=body)))
            with self.assertRaises(ValueError):
                module.AnthropicClient(api_key="key", model="haiku", client=client)([], [])
            client.close()



class CloudflareMalformedWireContractTests(SimpleTestCase):
    def test_cloudflare_requires_valid_route_key_and_model(self):
        module = importlib.import_module("emporio.chat.cloudflare")
        for options, message in (({"account_id": "bad/id", "api_key": "key", "model": "m"}, "CLOUDFLARE_ACCOUNT_ID"), ({"account_id": "acct", "api_key": "", "model": "m"}, "CLOUDFLARE_API_KEY"), ({"account_id": "acct", "api_key": "key", "model": " "}, "CLOUDFLARE_MODEL")):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                module.CloudflareClient(**options)

    def test_cloudflare_rejects_oversized_normalized_content_and_tool_calls(self):
        module = importlib.import_module("emporio.chat.cloudflare")
        bodies = [
            {"choices": [{"message": {"role": "assistant", "content": "x" * 33_000}, "finish_reason": "stop"}]},
            {"choices": [{"message": {"role": "assistant", "tool_calls": [{"function": {"arguments": json.dumps({"query": "x" * 33_000})}}]}, "finish_reason": "tool_calls"}]},
        ]
        for body in bodies:
            client = httpx.Client(transport=httpx.MockTransport(lambda request, body=body: httpx.Response(200, json=body)))
            with self.assertRaises(ValueError):
                module.CloudflareClient(account_id="acct", api_key="key", client=client)([], [])
            client.close()

    def test_cloudflare_rejects_malformed_wire_messages(self):
        module = importlib.import_module("emporio.chat.cloudflare")
        bodies = [{}, {"choices": [{}]}, {"choices": [{"message": {"role": "user", "content": "bad"}}]}, {"choices": [{"message": {"role": "assistant", "content": "partial"}, "finish_reason": "length"}]}, {"choices": [{"message": {"role": "assistant", "content": 1}}]}, {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": []}}]}, {"choices": [{"message": {"role": "assistant", "tool_calls": [{"function": {"arguments": "[]"}}]}}]}]
        for body in bodies:
            client = httpx.Client(transport=httpx.MockTransport(lambda request, body=body: httpx.Response(200, json=body)))
            with self.assertRaises(ValueError):
                module.CloudflareClient(account_id="acct", api_key="key", client=client)([], [])
            client.close()



class OpenAIMalformedWireContractTests(SimpleTestCase):
    def test_openai_rejects_invalid_configuration_before_http(self):
        module = importlib.import_module("emporio.chat.openai")
        invalid = [({"api_key": "", "model": "m"}, "OPENAI_API_KEY"), ({"api_key": "key", "model": ""}, "OPENAI_MODEL"), ({"api_key": "key", "model": "m", "api_mode": "other"}, "OPENAI_API_MODE"), ({"api_key": "key", "model": "m", "reasoning_effort": "unsupported"}, "OPENAI_REASONING_EFFORT"), ({"api_key": "key", "model": "gpt-6-astra", "api_mode": "chat_completions"}, "requires OPENAI_API_MODE"), ({"api_key": "key", "model": "gpt-6-luna", "api_mode": "chat_completions", "reasoning_effort": "high"}, "reasoning effort none")]
        for options, message in invalid:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                module.OpenAIClient(**options)

    def test_openai_chat_rejects_incomplete_and_malformed_wire_messages(self):
        module = importlib.import_module("emporio.chat.openai")
        bodies = [{}, {"choices": [{}]}, {"choices": [{"finish_reason": "length", "message": {"role": "assistant"}}]}, {"choices": [{"finish_reason": "stop", "message": {"role": "user", "content": "bad"}}]}, {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": 1}}]}, {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "", "tool_calls": []}}]}]
        for body in bodies:
            client = httpx.Client(transport=httpx.MockTransport(lambda request, body=body: httpx.Response(200, json=body)))
            with self.assertRaises(ValueError):
                module.OpenAIClient(api_key="key", model="gpt-5.4-mini", api_mode="chat_completions", client=client)([], [])
            client.close()

    def test_openai_responses_reject_incomplete_unsupported_oversized_and_bad_calls(self):
        module = importlib.import_module("emporio.chat.openai")
        bodies = [{}, {"status": "completed", "output": []}, {"status": "completed", "output": ["bad"]}, {"status": "completed", "output": [{"type": "unknown"}]}, {"status": "completed", "output": [{"type": "function_call", "call_id": "c1", "name": "lookup", "arguments": "[]"}]}, {"status": "completed", "output": [{"type": "function_call", "call_id": "", "name": "lookup", "arguments": "{}"}]}, {"status": "completed", "output": [{"type": "message", "content": []}]}, {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "x" * 33_000}]}]}]
        for body in bodies:
            client = httpx.Client(transport=httpx.MockTransport(lambda request, body=body: httpx.Response(200, json=body)))
            with self.assertRaises(ValueError):
                module.OpenAIClient(api_key="key", model="gpt-6-luna", client=client)([], [])
            client.close()



class AnthropicWireContractTests(SimpleTestCase):

    def test_anthropic_maps_system_and_tool_results_to_native_messages(self):
        module = importlib.import_module("emporio.chat.anthropic")
        captured = []
        blocks = [{"type": "thinking", "thinking": "opaque", "signature": "sig"}, {"type": "text", "text": "checking"}, {"type": "tool_use", "id": "use-9", "name": "lookup_public_policy", "input": {"query": "trocas"}}]
        body = {"content": blocks, "stop_reason": "tool_use", "model": "claude-haiku", "usage": {"input_tokens": 9, "output_tokens": 3}}
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (captured.append(request), httpx.Response(200, json=body))[1]))
        model = module.AnthropicClient(api_key="ant-secret", model="claude-haiku", client=client)
        messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": "trocas"}, {"role": "assistant", "tool_calls": [{"id": "use-9", "type": "function", "function": {"name": "lookup_public_policy", "arguments": "{\"query\":\"trocas\"}"}}]}, {"role": "tool", "tool_call_id": "use-9", "content": "found"}]
        result = model(messages, [{"type": "function", "function": {"name": "lookup_public_policy", "description": "policy", "parameters": {"type": "object"}}}])
        request = captured[0]
        payload = json.loads(request.content)
        self.assertEqual((request.url.host, request.url.path), ("api.anthropic.com", "/v1/messages"))
        self.assertEqual((request.headers["x-api-key"], request.headers["anthropic-version"]), ("ant-secret", "2026-10-21"))
        self.assertEqual(payload["system"], "policy")
        self.assertNotIn("system", payload["messages"])
        self.assertTrue({"temperature", "top_p", "top_k"}.isdisjoint(payload))
        self.assertEqual(payload["tools"][0]["input_schema"], {"type": "object"})
        self.assertEqual(payload["messages"][-1]["content"][0]["tool_use_id"], "use-9")
        self.assertEqual((result["content"], result["tool_calls"][0]["id"]), ("checking", "use-9"))
        self.assertEqual(result["provider_content"], blocks)
        self.assertEqual((model.returned_model, model.returned_provider), ("claude-haiku", "anthropic"))
        client.close()


    def test_anthropic_round_trip_keeps_native_assistant_blocks_and_multiple_call_ids(self):
        module = importlib.import_module("emporio.chat.anthropic")
        from unittest.mock import patch
        from emporio.agent import run_turn
        blocks = [{"type": "thinking", "thinking": "opaque reasoning", "signature": "signed"}, {"type": "tool_use", "id": "u-1", "name": "lookup_public_policy", "input": {"query": "trocas"}}, {"type": "tool_use", "id": "u-2", "name": "lookup_public_policy", "input": {"query": "horario"}}]
        bodies = iter(({"content": blocks, "stop_reason": "tool_use", "model": "haiku"}, {"content": [{"type": "text", "text": '{"outcome":"clarification","text":"Qual prefere?","reason":null}'}], "stop_reason": "end_turn", "model": "haiku"}))
        seen = []
        def respond(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json=next(bodies))
        client = httpx.Client(transport=httpx.MockTransport(respond))
        model = module.AnthropicClient(api_key="ant-secret", model="haiku", client=client)
        handler = lambda args, sender, version: {"outcome": "found", "data": [], "sources": [], "page": None}
        with patch("emporio.agent._handlers", return_value={"lookup_public_policy": handler}), patch("emporio.agent_turn._active_version", return_value="source-v1"):
            run_turn("horario da loja?", sender="5567998123456", model_client=model, snapshot_version="source-v1")
        replay = seen[1]["messages"]
        assistant = _replayed_assistant(replay)
        tool_results = _replayed_tool_results(replay)
        self.assertEqual(assistant["content"], blocks)
        self.assertEqual([item["tool_use_id"] for item in tool_results], ["u-1", "u-2"])
        client.close()
