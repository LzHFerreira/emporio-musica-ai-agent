import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import httpx
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase, override_settings

from emporio.chat.models import IncomingMessage, OutgoingReply
from emporio.chat.ollama import OllamaClient


DATA = Path(__file__).resolve().parents[1] / "data"


@override_settings(MODEL_PROVIDER="openrouter")
class InteractChatReviewTests(TransactionTestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA), verbosity=0)

    @override_settings(OPENROUTER_API_KEY="")
    def test_missing_model_key_fails_with_a_bounded_message(self):
        with self.assertRaisesRegex(CommandError, "OPENROUTER_API_KEY"):
            call_command("interact_chat", message="Qual é o horário?", stdout=StringIO())

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_evaluator_question_uses_real_model_http_and_worker_tools(self):
        requests = []

        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            if len(requests) == 1:
                message = {"tool_calls": [{"id": "policy", "type": "function", "function": {
                    "name": "lookup_public_policy", "arguments": json.dumps({"query": "horário de funcionamento", "topic": "hours"})
                }}]}
            else:
                message = {"content": json.dumps({"outcome": "answer", "text": "A loja funciona de segunda a sexta, das 09h às 18h.", "reason": None})}
            return httpx.Response(200, json={"choices": [{"message": message}], "model": "test/model"})

        client = httpx.Client(transport=httpx.MockTransport(respond))
        question = "Qual é o horário de funcionamento?"
        with patch("emporio.chat.openrouter._http_client", return_value=client):
            call_command("interact_chat", message=question, stdout=StringIO())
        incoming = IncomingMessage.objects.get(text=question)
        reply = OutgoingReply.objects.get(source=incoming)
        self.assertEqual(reply.state, "accepted")
        self.assertTrue(reply.provider_id.startswith("demo-meta-"))
        self.assertEqual(requests[0]["messages"][-1]["content"], question)
        self.assertTrue(any(message["role"] == "tool" for message in requests[1]["messages"]))
        self.assertEqual(len(requests), 2)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_interactive_quit_stops_after_one_turn_and_cleans_up_local_transport(self):
        requests = []

        def respond(request):
            requests.append(json.loads(request.content))
            message = {"content": json.dumps({"outcome": "answer", "text": "Claro, posso ajudar.", "reason": None})}
            return httpx.Response(200, json={"choices": [{"message": message}]})

        client = httpx.Client(transport=httpx.MockTransport(respond))
        with patch("builtins.input", side_effect=["Pergunta de avaliação livre", "/quit"]), patch(
            "emporio.chat.openrouter._http_client", return_value=client
        ):
            call_command("interact_chat", stdout=StringIO())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["messages"][-1]["content"], "Pergunta de avaliação livre")
        self.assertEqual(IncomingMessage.objects.filter(text="Pergunta de avaliação livre").count(), 1)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_end_of_input_exits_cleanly_without_model_or_local_server(self):
        requests = []
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request: requests.append(request)
        ))
        with patch("builtins.input", side_effect=EOFError), patch(
            "emporio.chat.openrouter._http_client", return_value=client
        ):
            call_command("interact_chat", stdout=StringIO())
        self.assertEqual(requests, [])
        self.assertEqual(IncomingMessage.objects.count(), 0)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_followup_request_retains_budget_payment_and_named_candidate(self):
        requests = []
        answers = [
            {"outcome": "clarification", "text": "Você prefere manter a busca pelo Yamaha C40?", "reason": None},
            {"outcome": "answer", "text": "Vou considerar essa preferência.", "reason": None},
        ]

        def respond(request):
            requests.append(json.loads(request.content))
            content = json.dumps(answers[len(requests) - 1], ensure_ascii=False)
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

        client = httpx.Client(transport=httpx.MockTransport(respond))
        questions = ["Meu orçamento é R$ 1.500 e prefiro Pix.", "Pode seguir com essa opção.", "/quit"]
        with patch("builtins.input", side_effect=questions), patch(
            "emporio.chat.openrouter._http_client", return_value=client
        ):
            call_command("interact_chat", stdout=StringIO())
        transcript = json.dumps(requests[1]["messages"], ensure_ascii=False)
        self.assertIn("R$ 1.500", transcript)
        self.assertIn("Pix", transcript)
        self.assertIn("Yamaha C40", transcript)
        self.assertIn("Pode seguir com essa opção.", transcript)

    @override_settings(MODEL_PROVIDER="ollama", OPENROUTER_API_KEY="", OLLAMA_BASE_URL="http://localhost:11434/v1", OLLAMA_MODEL="qwen3:4b")
    def test_local_provider_interaction_needs_no_cloud_key_and_closes_client(self):
        requests = []
        answer = {"outcome": "answer", "text": "Olá! Sou o assistente do Empório da Música. Posso ajudar com algum produto?", "reason": None}
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": json.dumps(answer)}, "finish_reason": "stop"}], "model": "qwen3:4b"})
        client = httpx.Client(transport=httpx.MockTransport(respond))
        model = OllamaClient(base_url="http://localhost:11434/v1", model="qwen3:4b", client=client)
        with patch("emporio.chat.management.commands.interact_chat.create_model_client", return_value=model):
            call_command("interact_chat", message="Qual o horário?", stdout=StringIO())
        self.assertEqual((len(requests), requests[0].url.path), (1, "/v1/chat/completions"))
        self.assertNotIn("authorization", requests[0].headers)
        self.assertTrue(client.is_closed)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_sender_option_is_persisted_on_the_incoming_message(self):
        answer = {"content": json.dumps({"outcome": "answer", "text": "Olá!", "reason": None})}
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": answer}]})))
        with patch("emporio.chat.openrouter._http_client", return_value=client):
            call_command("interact_chat", message="Qual o horário?", sender="5567998123456", stdout=StringIO())
        self.assertEqual(IncomingMessage.objects.get(text="Qual o horário?").sender, "5567998123456")
