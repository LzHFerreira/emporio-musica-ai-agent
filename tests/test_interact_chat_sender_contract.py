import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import httpx
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings

from emporio.chat.models import IncomingMessage


DATA = Path(__file__).resolve().parents[1] / "data"


@override_settings(MODEL_PROVIDER="openrouter")
class InteractChatSenderTests(TransactionTestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA), verbosity=0)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_sender_option_is_persisted_on_the_incoming_message(self):
        answer = {"content": json.dumps({"outcome": "answer", "text": "Olá!", "reason": None})}
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": answer}]})))
        with patch("emporio.chat.openrouter._http_client", return_value=client):
            call_command("interact_chat", message="Qual o horário?", sender="5567998123456", stdout=StringIO())
        self.assertEqual(IncomingMessage.objects.get(text="Qual o horário?").sender, "5567998123456")
