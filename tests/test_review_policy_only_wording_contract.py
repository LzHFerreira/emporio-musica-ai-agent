from pathlib import Path
from unittest.mock import Mock

from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from emporio.agent_protocol import FAILURE_TEXT
from tests.test_agent_contract import tool_call
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
WRONG = ["Sim! No PIX o violão está disponível com 5% de desconto.", "No PIX o violão sai por R$ 408,41."]
RIGHT = "Sim! No PIX você ganha 5% de desconto sobre o preço de tabela do violão."

class PolicyOnlyWordingContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def _turn(self, reply):
        tool = {"tool_calls": [tool_call("lookup_public_policy", {"query": "PIX desconto", "topic": "payments"})]}
        model = Mock(side_effect=[tool, {"content": reply}, {"content": reply}])
        return run_turn("E se eu pagar no PIX, muda alguma coisa?", sender="5567998123456", model_client=model)

    def test_wrong_pix_replies_are_rejected(self):
        for reply in WRONG:
            with self.subTest(reply=reply):
                self.assertEqual(self._turn(reply)["text"], FAILURE_TEXT)

    def test_policy_only_pix_reply_is_accepted(self):
        result = self._turn(RIGHT)
        self.assertEqual((result["outcome"], result["text"]), ("answer", RIGHT))
