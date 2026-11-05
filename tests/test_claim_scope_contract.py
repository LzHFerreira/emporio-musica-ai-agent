import json

from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_critical_claims_contract import SENDER, scripted

WARRANTY = tool_call("lookup_public_policy", {"query": "garantia", "topic": "warranty"})
CATALOG = tool_call("search_catalog", {"query": "Yamaha"})
HOURS = tool_call("lookup_public_policy", {"query": "horário", "topic": "hours"})
OTHER_ORDER = tool_call("get_own_order_status", {"order_id": 1})
INVENTED_WARRANTY = "A loja oferece garantia de 1 ano em todos os instrumentos."
CORRECT_WARRANTY = ("Todos os produtos têm garantia legal de 90 dias contra defeitos de "
                    "fabricação, contados a partir da data de recebimento.")
OTHER_ORDER_DRAFT = "Seu pedido 1 foi entregue e o código de rastreio é BRAB1234567BR."
INVENTED_CLARIFICATION = json.dumps({"outcome": "clarification",
    "text": "Você prefere o Yamaha C40, que vem com capa e afinador grátis, ou o F310?"})
CLARIFICATION_CONTROL = json.dumps({"outcome": "clarification",
    "text": "Você prefere o Yamaha C40 ou o F310?"})
SUNDAY_DRAFT = "Domingo não ficamos fechados; abrimos normalmente."
SUNDAY_CONTROL = "Aos domingos a loja fica fechada."
HOLIDAY_DRAFT = ("O manual informa que a loja fecha em feriados, mas não detalha exceções para "
                 "essa data; recomendo confirmar com a loja.")


class ClaimScopeContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def _run(self, question, calls, draft):
        return run_turn(question, sender=SENDER, model_client=scripted(calls, draft))

    def test_invented_warranty_term_is_not_delivered(self):
        result = self._run("Qual a garantia dos instrumentos?", [WARRANTY], INVENTED_WARRANTY)
        self.assertNotIn("1 ano", result["text"])

    def test_other_customer_order_status_is_not_delivered(self):
        result = self._run("Qual o status do pedido 1?", [OTHER_ORDER], OTHER_ORDER_DRAFT)
        self.assertNotIn("BRAB1234567BR", result["text"])

    def test_invented_fact_in_clarification_is_not_delivered(self):
        result = self._run("Quero um Yamaha, qual devo levar?", [CATALOG], INVENTED_CLARIFICATION)
        self.assertNotIn("afinador grátis", result["text"])

    def test_sunday_opening_claim_is_not_delivered(self):
        result = self._run("Vocês abrem no domingo?", [HOURS], SUNDAY_DRAFT)
        self.assertNotIn("abrimos normalmente", result["text"])

    def test_sunday_closed_control_is_delivered(self):
        result = self._run("Vocês abrem no domingo?", [HOURS], SUNDAY_CONTROL)
        self.assertEqual((result["outcome"], result["text"]), ("answer", SUNDAY_CONTROL))

    def test_plain_clarification_control_is_delivered(self):
        result = self._run("Quero um Yamaha, qual devo levar?", [CATALOG], CLARIFICATION_CONTROL)
        self.assertEqual(result["outcome"], "clarification")
        self.assertIn("Você prefere o Yamaha C40 ou o F310?", result["text"])

    def test_closed_sunday_and_weekday_hours_are_delivered(self):
        draft = "Domingo e feriados fechado; de segunda a sexta abrimos das 09:00 às 18:00."
        result = self._run("Qual o horário da loja?", [HOURS], draft)
        self.assertIn(draft, result["text"])

    def test_uncertain_holiday_hours_are_delivered(self):
        result = self._run("Vocês abrem no Corpus Christi?", [HOURS], HOLIDAY_DRAFT)
        self.assertEqual((result["outcome"], result["text"]), ("answer", HOLIDAY_DRAFT))

    def test_correct_legal_warranty_is_delivered(self):
        result = self._run("Qual a garantia dos produtos?", [WARRANTY], CORRECT_WARRANTY)
        self.assertEqual((result["outcome"], result["text"]), ("answer", CORRECT_WARRANTY))
