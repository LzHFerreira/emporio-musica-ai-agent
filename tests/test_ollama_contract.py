import json
import os
import httpx
from django.conf import settings
from django.test import SimpleTestCase, override_settings
from emporio.chat.ollama import OllamaClient

class OllamaClientContractTests(SimpleTestCase):
    @override_settings(OPENROUTER_API_KEY="must-not-leak")
    def test_keyless_tool_continuation_and_response_metadata(self):
        seen, answers = [], iter([httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "policy-1", "type": "function", "function": {"name": "lookup", "arguments": json.dumps({"q": "x"})}}]}, "finish_reason": "tool_calls"}]}), httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": json.dumps({"ok": True})}, "finish_reason": "stop"}], "model": "qwen3:4b", "provider": "ollama"})])
        def respond(request):
            seen.append(request)
            return next(answers)
        client = httpx.Client(transport=httpx.MockTransport(respond))
        model = OllamaClient(base_url="http://localhost:11434/v1", model="qwen3:4b", client=client)
        tools = [{"type": "function", "function": {"name": "lookup"}}]
        messages = [{"role": "user", "content": "find"}]
        first = model(messages, tools)
        followup = [*messages, first, {"role": "tool", "tool_call_id": "policy-1", "content": "done"}]
        result = model(followup, tools)
        bodies = [json.loads(request.content) for request in seen]
        self.assertEqual([request.url.path for request in seen], ["/v1/chat/completions"] * 2)
        self.assertTrue(all("authorization" not in request.headers for request in seen))
        self.assertEqual((bodies[0]["max_tokens"], bodies[0]["tools"]), (1024, tools))
        self.assertEqual(bodies[1]["messages"], followup)
        self.assertEqual(seen[0].extensions["timeout"]["read"], 180)
        self.assertEqual((first["tool_calls"][0]["id"], first["tool_calls"][0]["function"]["arguments"], result["content"]), ("policy-1", json.dumps({"q": "x"}), json.dumps({"ok": True})))
        self.assertEqual((model.returned_model, model.returned_provider), ("qwen3:4b", "ollama"))
        client.close()

    def test_rejects_empty_truncated_reasoning_only_and_malformed_responses(self):
        bodies = [{"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]}, {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}, {"choices": [{"message": {"content": "", "reasoning": "private thought"}, "finish_reason": "stop"}]}, {"choices": []}]
        for body in bodies:
            client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
            with self.assertRaises(ValueError):
                OllamaClient(model="qwen3:4b", client=client)([], [])
            client.close()

    def test_provider_failure_is_not_retried(self):
        seen = []
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(429))[1]))
        with self.assertRaises(httpx.HTTPStatusError):
            OllamaClient(model="qwen3:4b", client=client)([], [])
        self.assertEqual(len(seen), 1)
        client.close()

    def test_oversized_context_is_rejected_before_network_io(self):
        seen = []
        client = httpx.Client(transport=httpx.MockTransport(lambda request: seen.append(request)))
        with self.assertRaises(ValueError):
            OllamaClient(model="qwen3:4b", client=client)([{"role": "user", "content": "x" * 33000}], [])
        self.assertEqual(seen, [])
        client.close()

    def test_rejects_injected_cloud_credentials_before_network_io(self):
        seen = []
        for options in ({"headers": {"Authorization": "Bearer cloud-secret"}}, {"auth": ("cloud", "secret")}):
            client = httpx.Client(transport=httpx.MockTransport(lambda request: seen.append(request)), **options)
            with self.assertRaises(ValueError):
                OllamaClient(base_url="http://localhost:11434/v1", model="qwen3:4b", client=client)([], [])
            client.close()
        self.assertEqual(seen, [])

    def test_local_redirect_is_not_followed(self):
        seen = []
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(307, headers={"Location": "https://cloud.example/v1/chat/completions"}))[1]))
        with self.assertRaises(httpx.HTTPStatusError):
            OllamaClient(base_url="http://localhost:11434/v1", model="qwen3:4b", client=client)([], [])
        self.assertEqual(len(seen), 1)
        self.assertNotIn("authorization", seen[0].headers)
        client.close()

    def test_rejects_malformed_assistant_protocol_and_model_mismatch(self):
        valid_call = {"id": "call-1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}
        bad_messages = [{"role": "user", "content": "text"}, {"role": "assistant", "content": 1}, {"role": "assistant", "content": None, "tool_calls": {}}, {"role": "assistant", "content": ""}, {"role": "assistant", "content": None, "tool_calls": [valid_call, valid_call]}, {"role": "assistant", "tool_calls": [{"type": "function", "function": {"name": "lookup", "arguments": "{}"}}]}, {"role": "assistant", "tool_calls": [{"id": "x", "type": "function", "function": {"name": "", "arguments": "{}"}}]}, {"role": "assistant", "tool_calls": [{"id": "x", "type": "function", "function": {"name": "lookup", "arguments": "bad"}}]}, {"role": "assistant", "tool_calls": [{"id": "x", "type": "function", "function": {"name": "lookup", "arguments": "[]"}}]}]
        bodies = [{"choices": [{"message": message, "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}]} for message in bad_messages]
        bodies.extend(({"choices": [{"message": {"role": "assistant", "content": "ok"}}]}, {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}], "model": "other-model"}))
        for body in bodies:
            with self.subTest(body=body):
                client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
                with self.assertRaises(ValueError):
                    OllamaClient(model="qwen3:4b", client=client)([], [])
                client.close()

    @override_settings(OLLAMA_TIMEOUT_SECONDS=240.0)
    def test_timeout_setting_overrides_client_timeout(self):
        self.assertEqual(OllamaClient(base_url="http://localhost:11434/v1", model="qwen3:4b").request_timeout, 240.0)

    def test_default_timeout_is_180_seconds(self):
        if "OLLAMA_TIMEOUT_SECONDS" in os.environ:
            self.skipTest("OLLAMA_TIMEOUT_SECONDS is set in the environment")
        self.assertEqual(settings.OLLAMA_TIMEOUT_SECONDS, 180.0)
        self.assertEqual(OllamaClient(base_url="http://localhost:11434/v1", model="qwen3:4b").request_timeout, 180.0)
