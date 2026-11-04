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
CONTROL_DRAFT = "O Giannini GF-3D Dreadnought Sunburst está sem estoque no momento."


def scripted(calls, draft):
    replies = iter([{"tool_calls": calls}])
    return lambda messages, tools: next(replies, {"content": draft})


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
        self.assertNotIn("sempre ganha mais 5%", result["text"])
        self.assertIn({"tool": "output_check", "outcome": "rejected", "check": "pix_stacking"},
                      result["operations"])

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
        result = self._run("O Giannini GF-3D está disponível em estoque?", calls, CONTROL_DRAFT)
        self.assertEqual((result["outcome"], result["text"]), ("answer", CONTROL_DRAFT))

    def test_in_stock_product_is_not_called_out_of_stock(self):
        calls = [tool_call("search_catalog", {"query": "Yamaha C40"})]
        draft = "O Yamaha C40 Nylon Natural está sem estoque no momento."
        result = self._run("O Yamaha C40 está disponível em estoque?", calls, draft)
        self.assertNotIn("sem estoque", result["text"])

    def test_in_stock_control_is_delivered(self):
        calls = [tool_call("search_catalog", {"query": "Yamaha C40"})]
        draft = "O Yamaha C40 Nylon Natural está disponível em estoque."
        result = self._run("O Yamaha C40 está disponível em estoque?", calls, draft)
        self.assertEqual((result["outcome"], result["text"]), ("answer", draft))

    def test_pix_controls_are_delivered(self):
        calls = [tool_call("search_catalog", {"query": "Kalani KAL-700T", "payment_method": "pix"}),
                 tool_call("lookup_public_policy", {"query": "PIX desconto promoção",
                                                    "topic": "promotions"}, "call-2")]
        draft = ("O Kalani KAL-700T está por R$ 323,10 na promoção; o desconto de PIX não se "
                 "aplica sobre preços promocionais.")
        result = self._run("Quanto fica o Kalani KAL-700T no PIX?", calls, draft)
        self.assertEqual((result["outcome"], result["text"]), ("answer", draft))
        calls = [tool_call("search_catalog", {"query": "Yamaha C40", "payment_method": "pix"}),
                 tool_call("lookup_public_policy", {"query": "PIX", "topic": "payments"}, "call-2")]
        draft = "O Yamaha C40 Nylon Natural está por R$ 569,91 no PIX, com 5% de desconto no PIX."
        result = self._run("Quanto fica o Yamaha C40 no PIX?", calls, draft)
        self.assertEqual((result["outcome"], result["text"]), ("answer", draft))
