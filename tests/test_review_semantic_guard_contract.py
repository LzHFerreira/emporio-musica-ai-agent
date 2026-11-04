import json
from pathlib import Path
from unittest.mock import Mock

from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from emporio.agent_protocol import FAILURE_TEXT
from tests.test_agent_contract import tool_call

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
WRONG = ["O prazo para devolver é de 7 anos, conforme nossa política.", "A garantia é vitalícia.",
         "Parcelamos em 12x sem juros para qualquer valor.", "Nosso atendimento é muito bem avaliado pelos clientes.", "Abrimos aos domingos.", "No domingo a loja funciona normalmente.",
         "Sim, você pode devolver!", "Pode devolver sim, é só entrar em contato."]
RIGHT = ["Em compras online, você pode devolver em até 7 dias corridos após o recebimento.",
         "A garantia legal é de 90 dias contra defeitos de fabricação.",
         "Parcelamos em até 12x sem juros, com parcela mínima de R$ 100,00.",
         "Aos domingos e feriados a loja fica fechada.", "Não abrimos aos domingos."]


class SemanticGuardContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def _turn(self, reply):
        answer = {"content": json.dumps({"outcome": "answer", "text": reply, "reason": None})}
        model = Mock(side_effect=[{"tool_calls": [tool_call("read_store_manual", {})]}, answer, answer])
        return run_turn("Pergunta sobre a política", sender="5567998123456", model_client=model)

    def test_wrong_policy_replies_are_rejected(self):
        for reply in WRONG:
            with self.subTest(reply=reply):
                self.assertEqual(self._turn(reply)["text"], FAILURE_TEXT)

    def test_grounded_policy_replies_are_accepted(self):
        for reply in RIGHT:
            with self.subTest(reply=reply):
                result = self._turn(reply)
                self.assertEqual((result["outcome"], result["text"]), ("answer", reply))
