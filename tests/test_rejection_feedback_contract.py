import copy
from django.core.management import call_command
from django.test import TestCase
from emporio.agent import run_turn
from emporio.agent_protocol import REJECTED_TEXT
from tests.test_agent_contract import DATA_DIR, tool_call

def scripted(replies, seen):
    replies = iter(replies)
    return lambda messages, tools: seen.append(copy.deepcopy(messages)) or next(replies)

class RejectionFeedbackContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def test_numbers_rejection_names_unsupported_numbers(self):
        seen = []
        replies = [{"tool_calls": [tool_call("read_store_manual", {})]}, {"content": "Segundo o manual (página 4), o prazo é de 7 dias corridos após o recebimento, então já passou."}, {"content": "Em compras online, o prazo de devolução é de 7 dias corridos após o recebimento, então ele já passou."}]
        result = run_turn("Comprei pelo site e recebi há 10 dias, posso devolver?", sender="5567998123456", model_client=scripted(replies, seen))
        self.assertEqual((result["outcome"], len(seen)), ("answer", 3))
        self.assertIn(REJECTED_TEXT, seen[2][-1]["content"])
        self.assertIn("Estes números não aparecem nas fontes: 4;", seen[2][-1]["content"])
        self.assertIn("não repita números do cliente nem cite páginas ou seções", seen[2][-1]["content"])

    def test_policy_rejection_names_policy_tool(self):
        seen = []
        draft = "A troca é sempre gratuita, sem custo de frete."
        replies = [{"tool_calls": [tool_call("search_catalog", {"query": "Takamine GD20"})]}, {"content": draft}, {"content": draft}]
        run_turn("Quanto fica o Takamine GD20 no PIX?", sender="5567998123456", model_client=scripted(replies, seen))
        self.assertIn("lookup_public_policy", seen[2][-1]["content"])
