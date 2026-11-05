from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_critical_claims_contract import SENDER, scripted

RETURNS = tool_call("lookup_public_policy", {"query": "devolução online", "topic": "returns"})
QUESTION = "Comprei pelo site e recebi há 3 dias, posso devolver?"
ATTRIBUTED_DRAFT = ("Pelo que você informou, recebeu há 3 dias; compras online podem ser "
                    "devolvidas em até 7 dias corridos após o recebimento, desde que o produto "
                    "esteja sem sinais de uso e na embalagem original.")
UNATTRIBUTED_DRAFT = "Você recebeu há 3 dias, então pode devolver em até 7 dias corridos."
WRONG_NUMBER_DRAFT = "Pelo que você informou, recebeu há 5 dias; devolução em até 7 dias corridos."


class CustomerNumbersContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def _run(self, draft):
        return run_turn(QUESTION, sender=SENDER, model_client=scripted([RETURNS], draft))

    def test_attributed_customer_days_are_delivered(self):
        result = self._run(ATTRIBUTED_DRAFT)
        self.assertEqual((result["outcome"], result["text"]), ("answer", ATTRIBUTED_DRAFT))
    def test_unattributed_customer_days_are_not_delivered(self):
        self.assertNotEqual(self._run(UNATTRIBUTED_DRAFT)["text"], UNATTRIBUTED_DRAFT)
    def test_number_absent_from_message_and_evidence_is_not_delivered(self):
        self.assertNotEqual(self._run(WRONG_NUMBER_DRAFT)["text"], WRONG_NUMBER_DRAFT)
