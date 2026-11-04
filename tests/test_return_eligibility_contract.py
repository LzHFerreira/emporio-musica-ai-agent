from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_critical_claims_contract import SENDER, scripted

RETURNS = tool_call("lookup_public_policy", {"query": "devolução online", "topic": "returns"})
GENERAL_DRAFT = ("Compras online podem ser devolvidas em até 7 dias corridos após o recebimento, "
                 "desde que o produto esteja na embalagem original e sem sinais de uso.")
USED_DRAFT = ("Como o violão já foi usado, ele não atende à condição de devolução por "
              "arrependimento, que exige o produto sem sinais de uso.")
CONDITIONAL_DRAFT = ("Você pode solicitar a devolução se estiver dentro de 7 dias corridos após o "
                     "recebimento e o produto estiver sem sinais de uso, na embalagem original.")


class ReturnEligibilityContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def _assert_delivered(self, question, draft):
        result = run_turn(question, sender=SENDER, model_client=scripted([RETURNS], draft))
        self.assertEqual((result["outcome"], result["text"]), ("answer", draft))

    def test_general_return_explanation_is_delivered(self):
        self._assert_delivered("Como funciona a devolução de compras online?", GENERAL_DRAFT)

    def test_used_item_refusal_is_delivered(self):
        self._assert_delivered("Comprei pelo site e já usei o violão, posso devolver?", USED_DRAFT)

    def test_conditional_return_answer_is_delivered(self):
        self._assert_delivered("Posso devolver o que comprei pelo site?", CONDITIONAL_DRAFT)
