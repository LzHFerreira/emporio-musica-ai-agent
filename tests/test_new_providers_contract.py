"""Wire and isolation contracts for explicitly selected cloud model providers."""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from django.test import SimpleTestCase, override_settings

ROOT = Path(__file__).resolve().parents[1]


class ProviderFactoryContractTests(SimpleTestCase):
    def test_cloudflare_api_token_fills_an_empty_primary_key(self):
        env = {**os.environ, "MODEL_PROVIDER": "cloudflare", "CLOUDFLARE_API_KEY": "", "CLOUDFLARE_API_TOKEN": "alias", "CLOUDFLARE_ACCOUNT_ID": "acct"}
        code = "import django; django.setup(); from emporio.chat.providers import create_model_client; print(create_model_client().api_key)"
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "alias")

    def test_factory_requires_explicit_paid_opt_in_and_provider_credentials(self):
        providers = importlib.import_module("emporio.chat.providers")
        with override_settings(MODEL_PROVIDER="openai", ALLOW_PAID_MODELS=False):
            with self.assertRaisesRegex(ValueError, "ALLOW_PAID_MODELS"):
                providers.create_model_client()
        with override_settings(MODEL_PROVIDER="openai", OPENAI_API_KEY="", ALLOW_PAID_MODELS=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                providers.create_model_client()
        with override_settings(MODEL_PROVIDER="openai", OPENAI_API_KEY="oa-key", ALLOW_PAID_MODELS=True):
            model = providers.create_model_client()
            self.assertEqual((type(model).__name__, model.model), ("OpenAIClient", "gpt-6-luna"))
            model.client.close()
        with override_settings(MODEL_PROVIDER="anthropic", ALLOW_PAID_MODELS=True, ANTHROPIC_API_KEY=""):
            with self.assertRaisesRegex(ValueError, "ANTHROPIC_API_KEY"):
                providers.create_model_client()
        with override_settings(MODEL_PROVIDER="anthropic", ALLOW_PAID_MODELS=True, ANTHROPIC_API_KEY="ant-key"):
            model = providers.create_model_client()
            self.assertEqual(model.model, "claude-haiku-5-5")
            model.client.close()
        with override_settings(MODEL_PROVIDER="cloudflare", CLOUDFLARE_API_KEY="key", CLOUDFLARE_ACCOUNT_ID=""):
            with self.assertRaisesRegex(ValueError, "CLOUDFLARE_ACCOUNT_ID"):
                providers.create_model_client()
        with override_settings(MODEL_PROVIDER="cloudflare", CLOUDFLARE_API_KEY="key", CLOUDFLARE_ACCOUNT_ID="acct"):
            model = providers.create_model_client()
            self.assertEqual((type(model).__name__, model.model), ("CloudflareClient", "@cf/zai-org/glm-4.7-flash"))
            model.client.close()

class CloudflareWireContractTests(SimpleTestCase):

    def test_cloudflare_uses_its_account_route_and_never_borrows_router_identity(self):
        module = importlib.import_module("emporio.chat.cloudflare")
        seen = []
        response = {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}], "model": "@cf/google/gemma-4-26b-a4b-it"}
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(200, json=response))[1]))
        model = module.CloudflareClient(account_id="acct", api_key="cf-key", model="@cf/google/gemma-4-26b-a4b-it", client=client)
        self.assertEqual(model([{"role": "user", "content": "oi"}], [])["content"], "ok")
        request = seen[0]
        self.assertEqual((request.url.host, request.url.path), ("api.cloudflare.com", "/client/v4/accounts/acct/ai/v1/chat/completions"))
        self.assertEqual(request.headers["Authorization"], "Bearer cf-key")
        self.assertNotIn("router", request.headers["Authorization"])
        self.assertEqual(json.loads(request.content)["model"], "@cf/google/gemma-4-26b-a4b-it")
        self.assertEqual(json.loads(request.content)["chat_template_kwargs"], {"enable_thinking": False})
        client.close()

    def test_cloudflare_gemma_only_template_option_is_absent_for_glm(self):
        module = importlib.import_module("emporio.chat.cloudflare")
        body = {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]}
        seen = []
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(200, json=body))[1]))
        model = module.CloudflareClient(account_id="acct", api_key="cf-key", model="@cf/zai-org/glm-4.7-flash", client=client)
        model([], [])
        self.assertEqual(json.loads(seen[0].content)["model"], "@cf/zai-org/glm-4.7-flash")
        self.assertNotIn("chat_template_kwargs", json.loads(seen[0].content))
        client.close()

    def test_cloudflare_does_not_invent_returned_model_when_metadata_is_missing(self):
        module = importlib.import_module("emporio.chat.cloudflare")
        body = {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]}
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
        model = module.CloudflareClient(account_id="acct", api_key="cf-key", model="requested", client=client)
        model([], [])
        self.assertEqual((model.returned_model, model.returned_provider), ("", "cloudflare"))
        client.close()



class OpenAIWireContractTests(SimpleTestCase):

    def test_openai_does_not_follow_credential_redirects(self):
        module = importlib.import_module("emporio.chat.openai")
        seen = []
        def respond(request):
            seen.append(request)
            if len(seen) == 1:
                return httpx.Response(307, headers={"Location": "https://elsewhere.test/collect"})
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}], "model": "gpt-5.4-mini"})
        client = httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=True)
        model = module.OpenAIClient(api_key="oa-secret", model="gpt-5.4-mini", client=client)
        with self.assertRaises(httpx.HTTPStatusError):
            model([{"role": "user", "content": "json"}], [])
        self.assertEqual((len(seen), seen[0].url.host, seen[0].url.path), (1, "api.openai.com", "/v1/responses"))
        self.assertEqual(seen[0].headers["Authorization"], "Bearer oa-secret")
        client.close()


class OpenAIResponsesContractTests(SimpleTestCase):

    def test_openai_responses_round_trip_preserves_call_ids_and_opaque_items(self):
        module = importlib.import_module("emporio.chat.openai")
        from unittest.mock import patch
        from emporio.agent import run_turn
        native = [{"type": "reasoning", "id": "rs_1", "encrypted_content": "opaque"}, {"type": "function_call", "id": "fc_item", "call_id": "call_7", "name": "lookup_public_policy", "arguments": '{"query":"trocas"}'}]
        answers = iter(({"status": "completed", "output": native, "model": "gpt-6-luna"}, {"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": '{"outcome":"clarification","text":"Qual prefere?","reason":null}'}]}], "model": "gpt-6-luna"}, {"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}], "model": "gpt-6-luna"}))
        seen = []
        def respond(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json=next(answers))
        client = httpx.Client(transport=httpx.MockTransport(respond))
        model = module.OpenAIClient(api_key="oa-secret", model="gpt-6-luna", client=client)
        handler = lambda args, sender, version: {"outcome": "found", "data": [], "sources": [], "page": None}
        with patch("emporio.agent._handlers", return_value={"lookup_public_policy": handler}), patch("emporio.agent_turn._active_version", return_value="source-v1"):
            run_turn("devolução?", sender="5567998123456", model_client=model, snapshot_version="source-v1")
        items = seen[1]["input"]
        self.assertEqual(items[1:3], native)
        self.assertEqual((items[-1]["type"], items[-1]["call_id"]), ("function_call_output", "call_7"))
        self.assertNotEqual(items[-1]["call_id"], native[-1]["id"])
        self.assertFalse(seen[0]["store"])
        model([{"role": "user", "content": "another customer turn"}], [])
        self.assertNotIn("encrypted_content", json.dumps(seen[2]["input"]))
        client.close()

    def test_openai_chat_compatibility_mode_disables_reasoning_effort(self):
        module = importlib.import_module("emporio.chat.openai")
        seen = []
        response = {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}], "model": "gpt-6-luna"}
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(200, json=response))[1]))
        model = module.OpenAIClient(api_key="oa-secret", model="gpt-6-luna", api_mode="chat_completions", client=client)
        self.assertEqual(model([], [])["content"], "ok")
        payload = json.loads(seen[0].content)
        self.assertEqual((seen[0].url.path, payload["reasoning_effort"], payload["max_completion_tokens"]), ("/v1/chat/completions", "none", 1024))
        client.close()

class CloudflareMalformedWireContractTests(SimpleTestCase):
    def test_malformed_and_truncated_provider_outputs_fail_without_retry(self):
        module = importlib.import_module("emporio.chat.cloudflare")
        calls = []
        answers = iter(({"choices": []}, {"choices": [{"message": {"role": "assistant", "content": "partial"}, "finish_reason": "length"}]}))
        def respond(request):
            calls.append(request)
            return httpx.Response(200, json=next(answers))
        client = httpx.Client(transport=httpx.MockTransport(respond))
        model = module.CloudflareClient(account_id="acct", api_key="cf-key", client=client)
        for _ in range(2):
            with self.assertRaises(ValueError):
                model([], [])
        self.assertEqual(len(calls), 2)
        client.close()

    def test_provider_429_is_retried_once_and_not_routed_to_another_provider(self):
        module = importlib.import_module("emporio.chat.cloudflare")
        seen = []
        client = httpx.Client(transport=httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(429, json={"error": "limited"}))[1]))
        model = module.CloudflareClient(account_id="acct", api_key="cf-key", client=client)
        with self.assertRaises(httpx.HTTPStatusError):
            model([], [])
        self.assertEqual((len(seen), seen[0].url.host), (2, "api.cloudflare.com"))
        client.close()

class ForeignCredentialIsolationTests(SimpleTestCase):
    def test_injected_foreign_client_credentials_never_reach_any_provider(self):
        providers = [("emporio.chat.cloudflare", "CloudflareClient", {"account_id": "acct", "api_key": "cf-own"}), ("emporio.chat.openai", "OpenAIClient", {"api_key": "oa-own", "model": "gpt-6-luna"}), ("emporio.chat.anthropic", "AnthropicClient", {"api_key": "ant-own", "model": "haiku"})]
        for path, name, options in providers:
            with self.subTest(provider=name):
                module = importlib.import_module(path)
                seen = []
                client = httpx.Client(transport=httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(200))[1]), headers={"Authorization": "Bearer router-secret", "x-api-key": "foreign-secret"}, auth=("user", "basic-secret"))
                with self.assertRaisesRegex(ValueError, "must not carry provider credentials"):
                    getattr(module, name)(client=client, **options)
                self.assertEqual(seen, [])
                client.close()
