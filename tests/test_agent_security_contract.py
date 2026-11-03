import json
import re
from unittest.mock import Mock, patch

from django.test import TestCase

from emporio.agent import run_turn
from emporio.agent_protocol import FAILURE_TEXT
from emporio.chat.privacy import minimize_text


class AgentSecurityContractTests(TestCase):
    def test_malformed_terminal_types_and_unhashable_tool_name_fail_closed(self):
        values = ({"outcome": [], "text": "bad", "reason": None}, {"outcome": "handoff", "text": "bad", "reason": []})
        for value in values:
            with self.subTest(value=value):
                result = run_turn("Oi", sender="5567998123456", model_client=Mock(return_value={"content": json.dumps(value)}))
                self.assertEqual(result["text"], FAILURE_TEXT)
        malformed = {"tool_calls": [{"id": "bad", "type": "function", "function": {"name": [], "arguments": "{}"}}]}
        result = run_turn("Oi", sender="5567998123456", model_client=Mock(return_value=malformed))
        self.assertEqual(result["text"], FAILURE_TEXT)

    def test_missing_empty_and_typed_tool_arguments_do_not_reach_services(self):
        cases = ({}, {"query": ""}, {"query": 4})
        for arguments in cases:
            with self.subTest(arguments=arguments), patch("emporio.agent.lookup_public_policy") as lookup:
                response = {"tool_calls": [{"id": "call", "type": "function", "function": {"name": "lookup_public_policy", "arguments": json.dumps(arguments)}}]}
                result = run_turn("Qual a política?", sender="5567998123456", model_client=Mock(return_value=response))
                self.assertEqual(result["text"], FAILURE_TEXT)
                lookup.assert_not_called()

    def test_direct_turn_minimizes_personal_contacts_but_keeps_supported_numbers(self):
        seen = []
        def model(messages, tools):
            seen.extend(messages)
            return {"content": json.dumps({"outcome": "answer", "text": "Vou verificar.", "reason": None})}
        text = "Pedido 7 custa R$ 1.000, modelo AC-39. Meu email é eva@example.com, Meu telefone é (11) 98765-4321."
        run_turn(text, sender="5567998123456", model_client=model)
        forwarded = next(item["content"] for item in seen if item["role"] == "user")
        self.assertNotIn("eva@example.com", forwarded)
        self.assertNotIn("98765-4321", forwarded)
        self.assertIn("Pedido 7", forwarded)
        self.assertIn("R$ 1.000", forwarded)
        self.assertIn("AC-39", forwarded)

    def test_minimization_preserves_store_contacts_and_numeric_references(self):
        cleaned = minimize_text("Meu telefone é (11) 98765-4321. WhatsApp (67) 3321-4500 e empresa (67) 3341-4444. Pedido 11987654321, R$ 123.456.")
        self.assertNotIn("98765-4321", cleaned)
        digits = re.sub(r"\D", "", cleaned)
        self.assertIn("6733214500", digits)
        self.assertIn("6733414444", digits)
        self.assertIn("Pedido 11987654321", cleaned)
        self.assertIn("R$ 123.456", cleaned)

    def test_minimization_rejects_missing_blank_and_oversized_input(self):
        for value in (None, "  ", "x" * 2049):
            with self.subTest(value=type(value).__name__):
                self.assertIsNone(minimize_text(value))

    def test_unproven_contact_and_internal_product_identifier_are_withheld(self):
        text = "Ligue para (67) 99812-3456 sobre produto 101."
        response = {"content": json.dumps({"outcome": "answer", "text": text, "reason": None})}
        result = run_turn("Onde posso falar?", sender="5567998123456", model_client=Mock(return_value=response))
        self.assertEqual(result["text"], FAILURE_TEXT)

    def test_source_error_is_not_relabelled_as_not_found(self):
        response = {"tool_calls": [{"id": "call", "type": "function", "function": {"name": "search_catalog", "arguments": '{"query":"Takamine GD20"}'}}]}
        second = {"content": json.dumps({"outcome": "answer", "text": "Não foi possível confirmar.", "reason": None})}
        model = Mock(side_effect=[response, second])
        with patch("emporio.agent.search_catalog", return_value={"outcome": "error", "data": [], "sources": [], "error_category": "source_unavailable"}):
            result = run_turn("Está disponível?", sender="5567998123456", model_client=model)
        self.assertEqual(result["operations"][0]["outcome"], "error")
        self.assertNotEqual(result["operations"][0]["outcome"], "not_found")

    def test_model_request_budget_stops_after_three_calls(self):
        request = {"tool_calls": [{"id": "p", "type": "function", "function": {"name": "lookup_public_policy", "arguments": '{"query":"horário"}'}}]}
        model = Mock(side_effect=[request, request, request])
        with patch("emporio.agent.lookup_public_policy", return_value={"outcome": "not_found", "sources": [], "data": []}):
            result = run_turn("Qual horário?", sender="5567998123456", model_client=model)
        self.assertEqual((model.call_count, result["model_requests"], result["tool_executions"]), (3, 3, 3))
        self.assertEqual(result["text"], FAILURE_TEXT)

    def test_tool_exception_is_bounded_and_invalid_snapshot_skips_model(self):
        request = {"tool_calls": [{"id": "p", "type": "function", "function": {"name": "lookup_public_policy", "arguments": '{"query":"horário"}'}}]}
        model = Mock(side_effect=[request, {"content": json.dumps({"outcome": "answer", "text": "Não consigo confirmar.", "reason": None})}])
        with patch("emporio.agent.lookup_public_policy", side_effect=RuntimeError("db detail")):
            result = run_turn("Qual horário?", sender="5567998123456", model_client=model)
        self.assertEqual(result["operations"][0]["outcome"], "error")
        unused = Mock()
        result = run_turn("Oi", sender="5567998123456", model_client=unused, snapshot_version=7)
        self.assertEqual((result["text"], result["model_requests"]), (FAILURE_TEXT, 0))
        unused.assert_not_called()
