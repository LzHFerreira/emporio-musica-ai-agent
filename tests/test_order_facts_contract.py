from json import dumps as j
from django.core.management import call_command
from django.test import TestCase
from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_critical_claims_contract import SENDER
LINE = "Pedido 4: delivered; rastreio BRQM7890123BR; previsão de entrega 2025-12-22."
def final(facts):
    body = {"outcome": "answer", "text": "Seu pedido:", "reason": None, "facts": facts}
    return {"content": j(body)}
def run(replies):
    calls = {"tool_calls": [tool_call("get_own_order_status", {"order_id": 4})]}
    seen, it = [], iter([calls, *replies])
    client = lambda msgs, tools: seen.append(list(msgs)) or next(it, replies[-1])
    return run_turn("Qual o status do meu pedido 4?", sender=SENDER, model_client=client), seen
class OrderFactsContractTests(TestCase):
    def setUp(self): call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
    def test_order_ref_renders_status_line(self):
        r, _ = run([final(["order-1"])])
        self.assertIn(LINE, r["text"])
        self.assertNotIn("order-1", r["text"])
    def test_order_ref_is_exposed_to_model(self):
        _, seen = run([final(["order-1"])])
        self.assertIn('"ref": "order-1"', seen[1][-1]["content"])
    def test_unknown_order_ref_rejects_draft(self):
        r, _ = run([final(["order-9"])] * 5)
        self.assertNotIn("order-9", r["text"])
        self.assertTrue(any(op.get("check") == "facts_unknown_ref" for op in r["operations"]))
    def test_status_claim_in_own_order_turn_rejects_draft(self):
        bad = {"content": j({"outcome": "answer", "text": "Seu pedido já foi enviado.", "reason": None})}
        r, _ = run([bad] * 5)
        self.assertNotIn("já foi enviado", r["text"])
        self.assertTrue(any(op.get("check") == "facts_claim" for op in r["operations"]))
    def test_neutral_text_with_order_fact_renders_status(self):
        ok = {"content": j({"outcome": "answer", "text": "Aqui está o seu pedido:", "reason": None, "facts": ["order-1"]})}
        r, _ = run([ok])
        self.assertIn(LINE, r["text"])
