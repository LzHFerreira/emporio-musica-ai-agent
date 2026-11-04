import json

from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call

SENDER = "5567998123456"
PIX_DRAFT = ("O Kalani KAL-700T está por R$ 323,10 com a promoção. "
             "Além disso, no PIX você ganha mais 5% de desconto sobre esse valor.")
RETURN_DRAFT = ("Sim, você pode solicitar a devolução online em até 7 dias corridos após o "
                "recebimento, mesmo já tendo usado o violão.")
STOCK_DRAFT = ("Sim, o Giannini GF-3D Dreadnought Sunburst está disponível em estoque, "
               "por R$ 799,90.")


def with_facts(text, facts=("catalog-1",)):
    return json.dumps({"outcome": "answer", "text": text, "reason": None, "facts": list(facts)})


def terminal_json(draft):
    if draft.lstrip().startswith("{"):
        return draft
    return json.dumps({"outcome": "answer", "text": draft, "reason": None})


def scripted(calls, draft):
    replies = iter([{"tool_calls": calls}])
    return lambda messages, tools: next(replies, {"content": terminal_json(draft)})


class CriticalClaimsContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def _run(self, question, calls, draft):
        return run_turn(question, sender=SENDER, model_client=scripted(calls, draft))

    def test_pix_discount_does_not_stack_on_promotion(self):
        calls = [
            tool_call("search_catalog", {"query": "Kalani KAL-700T", "payment_method": "pix"}),
            tool_call("lookup_public_policy", {"query": "PIX desconto promoção",
                                               "topic": "promotions"}, "call-2"),
        ]
        result = self._run("Quanto fica o Kalani KAL-700T no PIX?", calls, PIX_DRAFT)
        self.assertNotEqual(result["text"], PIX_DRAFT)

    def test_sempre_is_not_a_pix_stacking_negation(self):
        draft = ("O Kalani KAL-700T está por R$ 323,10 com a promoção. "
                 "No PIX você sempre ganha mais 5% de desconto sobre esse valor.")
        calls = [tool_call("search_catalog", {"query": "Kalani KAL-700T", "payment_method": "pix"}),
                 tool_call("lookup_public_policy", {"query": "PIX desconto promoção",
                                                    "topic": "promotions"}, "call-2")]
        result = self._run("Quanto fica o Kalani KAL-700T no PIX?", calls, draft)
        # Catalog turns with prices in prose are rejected by the M4 facts rule before pix_stacking runs.
        self.assertNotIn("sempre ganha mais 5%", result["text"])
        self.assertTrue(any(op.get("outcome") == "rejected" for op in result["operations"]))

    def test_used_item_online_return_is_not_delivered(self):
        calls = [tool_call("lookup_public_policy", {"query": "devolução online",
                                                    "topic": "returns"})]
        result = self._run("Comprei o violão pelo site, já usei ele bastante. "
                           "Posso devolver online?", calls, RETURN_DRAFT)
        self.assertNotEqual(result["text"], RETURN_DRAFT)

    def test_out_of_stock_product_is_not_called_in_stock(self):
        calls = [tool_call("search_catalog", {"query": "Giannini GF-3D"})]
        result = self._run("O Giannini GF-3D está disponível em estoque?", calls, STOCK_DRAFT)
        self.assertNotEqual(result["text"], STOCK_DRAFT)

    def test_out_of_stock_control_is_delivered(self):
        calls = [tool_call("search_catalog", {"query": "Giannini GF-3D"})]
        result = self._run("O Giannini GF-3D está disponível em estoque?", calls, with_facts("Encontrei este modelo:"))
        self.assertEqual(result["outcome"], "answer")
        self.assertIn("Giannini GF-3D Dreadnought Sunburst: sem estoque no momento; "
                      "R$ 799,90 (preço registrado; forma de pagamento não informada).", result["text"])

    def test_in_stock_product_is_not_called_out_of_stock(self):
        calls = [tool_call("search_catalog", {"query": "Yamaha C40"})]
        draft = "O Yamaha C40 Nylon Natural está sem estoque no momento."
        result = self._run("O Yamaha C40 está disponível em estoque?", calls, draft)
        self.assertNotIn("sem estoque", result["text"])

    def test_in_stock_control_is_delivered(self):
        calls = [tool_call("search_catalog", {"query": "Yamaha C40"})]
        result = self._run("O Yamaha C40 está disponível em estoque?", calls, with_facts("Encontrei este modelo:"))
        self.assertEqual(result["outcome"], "answer")
        self.assertIn("Yamaha C40 Nylon Natural: disponível em estoque; R$ 599,90", result["text"])

    def test_pix_controls_are_delivered(self):
        calls = [tool_call("search_catalog", {"query": "Kalani KAL-700T", "payment_method": "pix"}),
                 tool_call("lookup_public_policy", {"query": "PIX desconto promoção",
                                                    "topic": "promotions"}, "call-2")]
        text = ("Sobre o Kalani KAL-700T no PIX, o desconto de PIX não se "
                "aplica sobre preços promocionais.")
        result = self._run("Quanto fica o Kalani KAL-700T no PIX?", calls, with_facts(text))
        self.assertEqual(result["outcome"], "answer")
        self.assertIn(text, result["text"])
        self.assertIn("Kalani KAL-700T Tenor Natural: disponível em estoque; R$ 323,10 "
                      "(promoção do catálogo; pagamento integral via PIX; não cumulativa com PIX).", result["text"])
        calls = [tool_call("search_catalog", {"query": "Yamaha C40", "payment_method": "pix"}),
                 tool_call("lookup_public_policy", {"query": "PIX", "topic": "payments"}, "call-2")]
        result = self._run("Quanto fica o Yamaha C40 no PIX?", calls, with_facts("Segue o modelo, com 5% de desconto no PIX."))
        self.assertEqual(result["outcome"], "answer")
        self.assertIn("Yamaha C40 Nylon Natural: disponível em estoque; R$ 569,91", result["text"])
