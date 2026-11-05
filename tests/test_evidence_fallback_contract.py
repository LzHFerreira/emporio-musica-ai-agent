from json import dumps as j
from django.core.management import call_command
from django.test import TestCase
from emporio.agent import run_turn
from emporio.agent_protocol import FAILURE_TEXT
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_critical_claims_contract import SENDER

def run(reply):
    it = iter([{"tool_calls": [tool_call("search_catalog", {"query": "Takamine GD20"})]}])
    return run_turn("Tem Takamine GD20?", sender=SENDER, model_client=lambda m, t: next(it, reply))

def answer(text):
    return {"content": j({"outcome": "answer", "text": text, "reason": None})}

class EvidenceFallbackContractTests(TestCase):
    def setUp(self): call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
    def test_repeated_price_claim_answers_from_catalog_evidence(self):
        r = run(answer("O Takamine GD20 Dreadnought Natural custa R$ 2.199,00 e está disponível."))
        self.assertEqual(r["outcome"], "answer")
        self.assertTrue(r["text"].startswith("Encontrei estas informações no catálogo:"))
        self.assertIn("Takamine GD20 Dreadnought Natural: disponível em estoque; "
                      "R$ 2.199,00", r["text"])
        self.assertIn("facts_claim", [op.get("check") for op in r["operations"]])
    def test_draft_naming_no_product_stays_failure(self):
        self.assertEqual(run(answer("Custa R$ 2.199,00."))["text"], FAILURE_TEXT)
    def test_prose_failure_without_facts_claim_stays_failure(self):
        r = run({"content": "Claro, posso ajudar com o Takamine."})
        self.assertEqual(r["text"], FAILURE_TEXT)
        self.assertNotIn("facts_claim", [op.get("check") for op in r["operations"]])
