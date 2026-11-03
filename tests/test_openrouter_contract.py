import json

import httpx
from django.test import SimpleTestCase, override_settings

from emporio.chat.openrouter import MAX_CONTEXT_BYTES, OpenRouterClient


class OpenRouterClientContractTests(SimpleTestCase):
    def test_sends_only_one_explicit_model_request_with_bounded_timeout(self):
        seen = []
        message = {"role": "assistant", "content": None, "tool_calls": []}
        def respond(request):
            seen.append(request)
            return httpx.Response(200, json={"choices": [{"message": message}]})
        client = httpx.Client(transport=httpx.MockTransport(respond))
        model = OpenRouterClient(api_key="test-key", model="google/gemma-4-26b-a4b-it:free", base_url="https://router.test/v1", client=client)
        result = model([{"role": "user", "content": "oi"}], [{"type": "function"}])
        request = seen[0]
        body = json.loads(request.content)
        self.assertEqual((result, request.url.path), (message, "/v1/chat/completions"))
        self.assertEqual((body["model"], body["temperature"]), ("google/gemma-4-26b-a4b-it:free", 0))
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(request.extensions["timeout"]["read"], 60)
        client.close()

    def test_oversized_context_is_rejected_before_network_io(self):
        seen = []
        client = httpx.Client(transport=httpx.MockTransport(lambda request: seen.append(request)))
        model = OpenRouterClient(api_key="test-key", model="free/model", client=client)
        with self.assertRaises(ValueError):
            model([{"role": "user", "content": "x" * MAX_CONTEXT_BYTES}], [])
        self.assertEqual(seen, [])
        client.close()

    @override_settings(OPENROUTER_API_KEY="configured-key", OPENROUTER_MODEL="configured/model")
    def test_configuration_defaults_and_malformed_provider_response(self):
        model = OpenRouterClient()
        self.assertEqual((model.api_key, model.model, model.client.timeout.read), ("configured-key", "configured/model", 60))
        model.client.close()
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": []})))
        model = OpenRouterClient(api_key="test", model="free/model", client=client)
        with self.assertRaises(ValueError):
            model([], [])
        client.close()

    def test_provider_failure_is_not_retried_or_switched_to_another_model(self):
        seen = []
        def respond(request):
            seen.append(json.loads(request.content)["model"])
            return httpx.Response(429, json={"error": {"code": 429}})
        client = httpx.Client(transport=httpx.MockTransport(respond))
        model = OpenRouterClient(api_key="test-key", model="free/model", client=client)
        with self.assertRaises(httpx.HTTPStatusError):
            model([], [])
        self.assertEqual(seen, ["free/model"])
        client.close()

    def test_truncated_output_is_rejected(self):
        body = {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
        with self.assertRaises(ValueError):
            OpenRouterClient(api_key="key", model="free/model", client=client)([], [])
        client.close()
