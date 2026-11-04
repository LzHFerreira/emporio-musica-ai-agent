from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_critical_claims_contract import SENDER, scripted

CATALOG = tool_call("search_catalog", {"query": "Yamaha"})
HOURS = tool_call("lookup_public_policy", {"query": "horário", "topic": "hours"})
RETURNS = tool_call("lookup_public_policy", {"query": "devolução online", "topic": "returns"})
SWAPPED_DRAFT = ("O Yamaha C40 Nylon Natural está por R$ 699,90 e o Yamaha F310 Aço Natural "
                 "por R$ 599,90.")
DAY_UNITS_DRAFT = ("Você pode devolver online em até 7 dias úteis após o recebimento, desde que "
                   "o produto esteja na embalagem original.")
HOURS_DRAFT = "Segunda a sexta das 09:00 às 18:00 e sábado das 09:00 às 13:00."


class ClaimBindingContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def _run(self, question, calls, draft):
        return run_turn(question, sender=SENDER, model_client=scripted(calls, draft))

    def test_swapped_product_prices_are_not_delivered(self):
        result = self._run("Quanto custam o Yamaha C40 e o Yamaha F310?", [CATALOG], SWAPPED_DRAFT)
        self.assertNotEqual(result["text"], SWAPPED_DRAFT)

    def test_changed_return_day_units_are_not_delivered(self):
        result = self._run("Posso devolver uma compra feita pelo site?", [RETURNS], DAY_UNITS_DRAFT)
        self.assertNotEqual(result["text"], DAY_UNITS_DRAFT)

    def test_correct_store_hours_are_delivered(self):
        result = self._run("Qual o horário de funcionamento?", [HOURS], HOURS_DRAFT)
        self.assertEqual((result["outcome"], result["text"]), ("answer", HOURS_DRAFT))
