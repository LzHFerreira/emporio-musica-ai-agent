import json
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def tool_call(name, arguments, call_id="call-1"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


class AgentTurnContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def test_combined_question_uses_catalog_and_policy_then_validates_terminal(self):
        replies = iter([
            {"tool_calls": [tool_call("search_catalog", {"query": "Takamine GD20", "mode": "resolve"}), tool_call("lookup_public_policy", {"query": "devolução", "topic": "returns"}, "call-2")]},
            {"content": json.dumps({"outcome": "answer", "text": "Vou confirmar as condições de devolução.", "reason": None})},
        ])
        seen = []

        def model(messages, tools):
            seen.append((messages, tools))
            return next(replies)

        result = run_turn("O Takamine GD20 está disponível e posso devolver?", sender="5567998123456", model_client=model)
        self.assertEqual(set(result), {"outcome", "text", "reason", "sources", "operations", "model_requests", "tool_executions", "snapshot_version"})
        self.assertEqual((result["outcome"], len(seen)), ("answer", 2))
        self.assertEqual({s["type"] for s in result["sources"]}, {"catalog", "policy"})
        schemas = [tool["function"]["parameters"]["properties"] for tool in seen[0][1]]
        self.assertEqual({tool["function"]["name"] for tool in seen[0][1]}, {"search_catalog", "lookup_public_policy", "list_own_orders", "get_own_order_status"})
        self.assertTrue(all(not {"sender", "customer_id", "snapshot_version"} & set(schema) for schema in schemas))
        self.assertNotIn("5567998123456", json.dumps(seen))

    def test_model_cannot_supply_trusted_sender_or_snapshot_arguments(self):
        replies = iter([
            {"tool_calls": [tool_call("list_own_orders", {"page": 1, "sender": "forged", "snapshot_version": "old"})]},
        ])
        with patch("emporio.agent.list_own_orders") as lookup:
            result = run_turn("Mostre meus pedidos", sender="5567998123456", model_client=lambda m, t: next(replies))
        self.assertEqual(result["text"], "Não consegui concluir sua consulta agora. Você pode tentar novamente ou pedir atendimento humano.")
        self.assertLessEqual(result["tool_executions"], 4)
        lookup.assert_not_called()
        self.assertNotIn("forged", json.dumps(result))

    def test_invalid_terminal_and_tool_budget_fail_closed(self):
        outputs = iter([
            {"content": '{"outcome":"answer","text":"raw unsafe", "reason":null,"extra":true}'},
        ])
        result = run_turn("Oi", sender="5567998123456", model_client=lambda m, t: next(outputs))
        self.assertEqual(result["text"], "Não consegui concluir sua consulta agora. Você pode tentar novamente ou pedir atendimento humano.")
        self.assertEqual((result["model_requests"], result["tool_executions"]), (1, 0))
        self.assertNotIn("raw unsafe", result["text"])

    def test_fifth_tool_call_is_never_executed_and_turn_stops_at_budget(self):
        calls = [tool_call("lookup_public_policy", {"query": "horário"}, f"call-{i}") for i in range(5)]
        responses = iter([{"tool_calls": calls}])
        result = run_turn("Qual é o horário?", sender="5567998123456", model_client=lambda m, t: next(responses))
        self.assertLessEqual(result["tool_executions"], 4)
        self.assertLessEqual(result["model_requests"], 3)
        self.assertEqual(result["text"], "Não consegui concluir sua consulta agora. Você pode tentar novamente ou pedir atendimento humano.")

    def test_handoff_discards_model_text_and_uses_fixed_confirmation(self):
        terminal = {"outcome": "handoff", "text": "private draft", "reason": "customer_request"}
        model = Mock(return_value={"content": json.dumps(terminal)})
        result = run_turn("Quero falar com alguém", sender="5567998123456", model_client=model)
        self.assertEqual((result["outcome"], result["text"]), ("handoff", "Encaminhei sua conversa para atendimento humano."))
        self.assertNotIn("private draft", result["text"])
        model.assert_called_once()
