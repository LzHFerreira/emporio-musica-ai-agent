"""Contracts for Gemma's native terminal-reply function protocol."""

import copy
import json
from unittest.mock import Mock, patch

import httpx
from django.test import SimpleTestCase

from emporio.agent_output import output_supported
from emporio.agent_protocol import FAILURE_TEXT
from emporio.agent_schemas import TOOL_SCHEMAS
from emporio.agent_turn import run_turn
from emporio.chat.cloudflare import CloudflareClient

GEMMA = "@cf/google/gemma-4-26b-a4b-it"
REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "outcome": {"type": "string", "enum": ["answer", "clarification", "handoff"]},
        "text": {"type": "string", "minLength": 1, "maxLength": 2000},
        "reason": {"type": ["string", "null"], "enum": [None, "customer_request", "verification_failed", "unsupported", "other"]},
    },
    "required": ["outcome", "text", "reason"],
    "additionalProperties": False,
}


def _tool_call(arguments, name="respond_to_customer", identifier="reply"):
    return {"id": identifier, "type": "function", "function": {"name": name, "arguments": arguments}}


def _client_for(body, model=GEMMA, capture=None):
    def respond(request):
        if capture is not None:
            capture.append(json.loads(request.content))
        return httpx.Response(200, json=body)

    http = httpx.Client(transport=httpx.MockTransport(respond))
    return CloudflareClient(account_id="acct", api_key="cf-key", model=model, client=http), http


def _tool_names(tools):
    return [tool["function"]["name"] for tool in tools]


def _assert_reply_schema(tools):
    control = tools[-1]["function"]
    assert control["name"] == "respond_to_customer"
    assert control["parameters"] == REPLY_SCHEMA
    assert control["description"]


def _catalog_query_rule(tools):
    search = next(tool["function"] for tool in tools if tool["function"]["name"] == "search_catalog")
    return search["parameters"]["properties"]["query"], search["parameters"]


def _assert_query_description(query):
    description = query["description"].lower()
    _assert_product_reference(description)
    _assert_browse_semantics(description)


def _assert_product_reference(description):
    assert "product name" in description
    assert "brand" in description
    assert "model" in description


def _assert_browse_semantics(description):
    assert "empty string" in description
    assert "general browsing" in description
    assert "takamine" not in description


def _assert_gemma_catalog_query(tools):
    query, parameters = _catalog_query_rule(tools)
    assert "query" in parameters["required"]
    assert "default" not in query and "minLength" not in query
    _assert_query_description(query)


def _assert_required_reply_policy(payload):
    assert payload["tool_choice"] == "required"
    assert payload.get("parallel_tool_calls", True) is True


def _assert_gemma_tools(payload, business_tools):
    sent_tools = payload["tools"]
    assert _tool_names(sent_tools[:-1]) == _tool_names(business_tools)
    _assert_gemma_catalog_query(sent_tools)
    _assert_reply_schema(sent_tools)
    _assert_required_reply_policy(payload)


def _assert_private_instruction(messages):
    instruction = " ".join(message["content"] for message in messages if message["role"] == "system").lower()
    for phrase in ("respond_to_customer", "facts", "separate call", "never batch"):
        assert phrase in instruction


class CloudflareGemmaProtocolContractTests(SimpleTestCase):
    def test_gemma_requires_typed_reply_control_and_normalizes_valid_terminal(self):
        terminal = {"outcome": "answer", "text": "O catálogo confirmou a opção.", "reason": None}
        body = {"choices": [{"message": {"role": "assistant", "tool_calls": [_tool_call(json.dumps(terminal))]}, "finish_reason": "tool_calls"}], "model": GEMMA}
        requests = []
        model, http = _client_for(body, capture=requests)
        business_tools = copy.deepcopy(TOOL_SCHEMAS)
        result = model([{"role": "system", "content": "trusted"}, {"role": "user", "content": "oi"}], business_tools)
        payload = requests[0]
        _assert_gemma_tools(payload, business_tools)
        _assert_private_instruction(payload["messages"])
        self.assertEqual(business_tools, TOOL_SCHEMAS)
        self.assertEqual(result.get("content"), json.dumps(terminal, ensure_ascii=False))
        self.assertFalse(result.get("tool_calls"))
        http.close()

    def test_gemma_rejects_malformed_duplicate_and_mixed_reply_control(self):
        terminal = json.dumps({"outcome": "answer", "text": "Resposta", "reason": None})
        bad_batches = [
            [_tool_call("not-json")],
            [_tool_call("[]")],
            [_tool_call(json.dumps({"outcome": "answer", "text": "Resposta", "reason": None, "extra": True}))],
            [_tool_call(json.dumps({"outcome": "unsupported", "text": "Resposta", "reason": None}))],
            [_tool_call(json.dumps({"outcome": "answer", "text": "Resposta", "reason": "unsupported"}))],
            [_tool_call(json.dumps({"outcome": "handoff", "text": "Resposta", "reason": None}))],
            [_tool_call(json.dumps({"outcome": "answer", "text": "", "reason": None}))],
            [_tool_call(terminal), _tool_call(terminal, identifier="reply-2")],
            [_tool_call(terminal), _tool_call('{"query":"Takamine GD20"}', "search_catalog", "catalog")],
        ]
        for calls in bad_batches:
            body = {"choices": [{"message": {"role": "assistant", "tool_calls": calls}, "finish_reason": "tool_calls"}]}
            model, http = _client_for(body)
            with self.assertRaises(ValueError):
                model([{"role": "user", "content": "oi"}], copy.deepcopy(TOOL_SCHEMAS))
            http.close()

    def test_glm_keeps_four_business_tools_without_gemma_protocol(self):
        body = {"choices": [{"message": {"role": "assistant", "tool_calls": [_tool_call('{"mode":"search"}', "search_catalog", "browse")]}, "finish_reason": "tool_calls"}]}
        requests = []
        model, http = _client_for(body, model="@cf/zai-org/glm-4.7-flash", capture=requests)
        result = model([{"role": "system", "content": "trusted"}], copy.deepcopy(TOOL_SCHEMAS))
        payload = requests[0]
        self.assertEqual(len(payload["tools"]), 4)
        catalog = next(tool["function"] for tool in payload["tools"] if tool["function"]["name"] == "search_catalog")
        self.assertEqual(catalog["parameters"]["properties"]["query"]["default"], "")
        self.assertNotIn("query", catalog["parameters"].get("required", []))
        self.assertNotIn("tool_choice", payload)
        self.assertNotIn("respond_to_customer", json.dumps(payload))
        self.assertEqual(result["tool_calls"][0]["function"]["arguments"], '{"mode":"search"}')
        http.close()

    def test_gemma_missing_catalog_query_is_rejected_before_handler(self):
        body = {"choices": [{"message": {"role": "assistant", "tool_calls": [_tool_call('{"mode":"search"}', "search_catalog", "catalog")]}, "finish_reason": "tool_calls"}]}
        model, http = _client_for(body)
        search = Mock(return_value={"outcome": "found", "data": [], "sources": [], "page": None})
        result = run_turn("Pode procurar?", sender="5567998123456", model_client=model, snapshot_version="bundle-v1", handlers={"search_catalog": search})
        self.assertEqual((result["text"], result["model_requests"], result["tool_executions"]), (FAILURE_TEXT, 1, 0))
        search.assert_not_called()
        http.close()

    def test_gemma_accepts_explicit_empty_query_as_intentional_browse(self):
        browse_call = _tool_call('{"query":""}', "search_catalog", "browse")
        reply = _tool_call(json.dumps({"outcome": "clarification", "text": "Você prefere um tipo de instrumento específico?", "reason": None}))
        bodies = iter([{"choices": [{"message": {"role": "assistant", "tool_calls": [browse_call]}, "finish_reason": "tool_calls"}]}, {"choices": [{"message": {"role": "assistant", "tool_calls": [reply]}, "finish_reason": "tool_calls"}]}])
        http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=next(bodies))))
        model = CloudflareClient(account_id="acct", api_key="cf-key", client=http)
        browse = Mock(return_value={"outcome": "found", "data": [], "sources": [], "page": None})
        result = run_turn("Pode me mostrar opções?", sender="5567998123456", model_client=model, snapshot_version="bundle-v1", handlers={"search_catalog": browse})
        browse.assert_called_once_with({"query": ""}, "5567998123456", "bundle-v1")
        self.assertEqual((result["outcome"], result["model_requests"], result["tool_executions"]), ("clarification", 2, 1))
        http.close()

    def test_fenced_json_is_not_repaired_and_unsupported_reply_stays_blocked(self):
        fenced = 'Resposta:\n```json\n{"outcome":"answer","text":"produto 95 custa R$ 1","reason":null}\n```'
        body = {"choices": [{"message": {"role": "assistant", "content": fenced}, "finish_reason": "stop"}]}
        model, http = _client_for(body)
        with patch("emporio.agent_turn.output_supported", wraps=output_supported) as supported:
            result = run_turn("oi", sender="5567998123456", model_client=model, snapshot_version="bundle-v1", handlers={})
        self.assertEqual((result["text"], result["model_requests"], result["tool_executions"]), (FAILURE_TEXT, 1, 0))
        supported.assert_not_called()
        http.close()

    def test_untrusted_control_claim_still_runs_the_existing_output_guard(self):
        claim = "O produto 95 custa R$ 1."
        arguments = {"outcome": "answer", "text": claim, "reason": None}
        body = {"choices": [{"message": {"role": "assistant", "tool_calls": [_tool_call(json.dumps(arguments))]}, "finish_reason": "tool_calls"}]}
        model, http = _client_for(body)
        with patch("emporio.agent_turn.output_supported", wraps=output_supported) as supported:
            result = run_turn("qual preço?", sender="5567998123456", model_client=model, snapshot_version="bundle-v1", handlers={})
        self.assertEqual((result["text"], result["model_requests"], result["tool_executions"]), (FAILURE_TEXT, 1, 0))
        supported.assert_called_once_with(claim, "answer", [], [])
        http.close()
