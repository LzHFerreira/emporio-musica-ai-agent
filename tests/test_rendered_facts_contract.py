from json import dumps as j
from django.core.management import call_command
from django.test import TestCase
from emporio.agent import run_turn
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_critical_claims_contract import SENDER
def final(facts): return {"content": j({"outcome":"answer","text":"Veja abaixo:","facts":facts})}
def run(replies):
    replies = [{"tool_calls": [tool_call("search_catalog", {"query": "Giannini GF-3D"})]}, *replies]
    seen, it = [], iter(replies)
    client = lambda msgs, tools: seen.append(list(msgs)) or next(it, replies[-1])
    return run_turn("Tem Giannini GF-3D?", sender=SENDER, model_client=client), seen
class RenderedFactsContractTests(TestCase):
    def setUp(self): call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
    def test_valid_ref_renders_catalog_line(self):
        r, seen = run([final(["catalog-1"])])
        self.assertEqual(r["outcome"], "answer")
        self.assertIn("Giannini GF-3D Dreadnought Sunburst: sem estoque no momento.", r["text"])
        self.assertNotIn("catalog-1", r["text"])
        self.assertIn('"ref": "catalog-1"', seen[1][-1]["content"])
    def test_unknown_ref_rejects_draft(self):
        r, _ = run([final(["catalog-9"])] * 5)
        self.assertNotIn("catalog-9", r["text"])
        self.assertTrue(any(op.get("check") == "invalid_terminal" for op in r["operations"]))
