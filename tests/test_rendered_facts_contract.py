from json import dumps as j
from django.core.management import call_command
from django.test import TestCase
from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_critical_claims_contract import SENDER
def final(facts, text="Veja abaixo:"):
    return {"content": j({"outcome":"answer","text":text,"facts":facts})}
def run(replies, args={"query": "Giannini GF-3D"}):
    replies = [{"tool_calls": [tool_call("search_catalog", args)]}, *replies]
    seen, it = [], iter(replies)
    client = lambda msgs, tools: seen.append(list(msgs)) or next(it, replies[-1])
    return run_turn("Tem Giannini GF-3D?", sender=SENDER, model_client=client), seen
def plain_turn(replies, text):
    it = iter(replies)
    return run_turn("q", sender=SENDER, model_client=lambda m, t: next(it, {"content": j({"outcome": "answer", "text": text, "reason": None})}))
def plain_run(args, text):
    return plain_turn([{"tool_calls": [tool_call("search_catalog", args)]}], text)
class RenderedFactsContractTests(TestCase):
    def setUp(self): call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
    def test_valid_ref_renders_catalog_line(self):
        r, seen = run([final(["catalog-1"])])
        self.assertEqual(r["outcome"], "answer")
        self.assertIn("Giannini GF-3D Dreadnought Sunburst: sem estoque no momento; "
                      "R$ 799,90 (preço registrado; forma de pagamento não informada).", r["text"])
        self.assertNotIn("catalog-1", r["text"])
        self.assertIn('"ref": "catalog-1"', seen[1][-1]["content"])
    def test_promotional_price_renders_with_payment_condition(self):
        r, _ = run([final(["catalog-1"])], {"query": "Kalani KAL-700T", "payment_method": "pix"})
        self.assertIn("Kalani KAL-700T Tenor Natural: disponível em estoque; R$ 323,10 "
                      "(promoção do catálogo; pagamento integral via PIX; "
                      "não cumulativa com PIX).", r["text"])
    def test_internal_ref_never_reaches_customer(self):
        r, _ = run([final(["catalog-1"], "Veja catalog-1.")] * 5)
        self.assertNotIn("catalog-1", r["text"])
    def test_unknown_ref_rejects_draft(self):
        r, _ = run([final(["catalog-9"])] * 5)
        self.assertNotIn("catalog-9", r["text"])
        self.assertTrue(any(op.get("check") == "invalid_terminal" for op in r["operations"]))
    def test_price_in_text_with_facts_rejects_draft(self):
        r, _ = run([final(["catalog-1"], "Está disponível por R$ 799,90, veja:")] * 5)
        self.assertNotIn("Está disponível por R$ 799,90", r["text"])
        self.assertTrue(any(op.get("check") == "invalid_terminal" for op in r["operations"]))
    def test_stock_claim_in_text_with_facts_rejects_draft(self):
        r, _ = run([final(["catalog-1"], "Temos em estoque:")] * 5)
        self.assertNotIn("Temos em estoque", r["text"])
        self.assertTrue(any(op.get("check") == "invalid_terminal" for op in r["operations"]))
    def test_case_variant_ref_never_reaches_customer(self):
        for text in ("Veja Catalog-1.", "Veja CATALOG-1."):
            r, _ = run([final(["catalog-1"], text)] * 5)
            self.assertNotIn("catalog-1", r["text"].lower())
            self.assertTrue(any(op.get("check") == "invalid_terminal" for op in r["operations"]))
    def test_neutral_text_with_facts_renders_line(self):
        r, _ = run([final(["catalog-1"], "Encontrei este modelo:")])
        self.assertIn("Encontrei este modelo:", r["text"])
        self.assertIn("Giannini GF-3D Dreadnought Sunburst: sem estoque no momento", r["text"])
    def test_stock_text_without_facts_is_rejected(self):
        r = plain_run({"query": "Giannini GF-3D"}, "O Giannini GF-3D está sem estoque no momento.")
        self.assertNotIn("O Giannini GF-3D está sem estoque no momento.", r["text"])
        self.assertTrue(any(op.get("check") == "invalid_terminal" for op in r["operations"]))
    def test_price_text_without_facts_is_rejected(self):
        r = plain_run({"query": "Yamaha C40"}, "O Yamaha C40 Nylon Natural custa R$ 599,90.")
        self.assertNotIn("O Yamaha C40 Nylon Natural custa R$ 599,90.", r["text"])
        self.assertTrue(any(op.get("check") == "invalid_terminal" for op in r["operations"]))
    def test_neutral_text_with_yamaha_facts_renders_line(self):
        args = {"query": "Yamaha C40", "payment_method": "pix"}
        r, _ = run([final(["catalog-1"], "Encontrei este modelo:")], args)
        self.assertIn("Encontrei este modelo:", r["text"])
        self.assertIn("Yamaha C40 Nylon Natural: disponível em estoque; R$ 569,91", r["text"])
    def test_policy_only_price_claim_is_delivered(self):
        policy = tool_call("lookup_public_policy", {"query": "PIX", "topic": "payments"})
        r = plain_turn([{"tool_calls": [policy]}],
                       "No PIX há 5% de desconto sobre o preço de tabela.")
        self.assertEqual(r["outcome"], "answer")
        self.assertIn("No PIX há 5% de desconto sobre o preço de tabela.", r["text"])
