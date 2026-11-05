import copy, json
from django.core.management import call_command
from django.test import TestCase
from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call

def final(**fields):
    return {"content": json.dumps({"outcome": "answer", "reason": None, **fields}, ensure_ascii=False)}

class FactsFeedbackContractTests(TestCase):
    def run_with(self, replies):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
        seen, replies = [], iter([{"tool_calls": [tool_call("search_catalog", {"query": "Kalani KAL-700T", "payment_method": "pix"})]}, *replies])
        client = lambda messages, tools: seen.append(copy.deepcopy(messages)) or next(replies)
        result = run_turn("Quanto fica o Kalani KAL-700T no PIX?", sender="5567998123456", model_client=client)
        return result, seen, [op.get("check") for op in result["operations"]]

    def test_price_in_text_rejection_names_facts_and_refs(self):
        result, seen, checks = self.run_with([final(text="O Kalani KAL-700T fica em R$ 323,10 no PIX."), final(text="Segue o produto.", facts=["catalog-1"])])
        self.assertIn("facts_claim", checks)
        self.assertIn("catalog-1 = Kalani KAL-700T Tenor Natural", seen[-1][-1]["content"])
        self.assertIn("Kalani KAL-700T", result["text"])

    def test_unknown_ref_rejection_is_named(self):
        _, _, checks = self.run_with([final(text="Segue o produto.", facts=["catalog-9"])])
        self.assertIn("facts_unknown_ref", checks)

    def test_prose_reply_stays_invalid_terminal(self):
        _, _, checks = self.run_with([{"content": "Claro, posso ajudar com o Kalani."}])
        self.assertIn("invalid_terminal", checks)
