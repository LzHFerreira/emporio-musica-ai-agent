from pathlib import Path
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from tests.test_agent_contract import tool_call

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class AgentPlainTextContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    @patch("emporio.agent.lookup_public_policy")
    def test_plain_text_answer_after_policy_lookup_is_returned_without_retry(self, lookup):
        lookup.return_value = {"outcome": "found", "data": [{"text": "Sábado: das 09:00 às 13:00"}]}
        model = Mock(side_effect=[{"tool_calls": [tool_call("lookup_public_policy", {"query": "horário sábado"})]}, {"content": "No sábado abrimos das 09:00 às 13:00."}, {"content": '{"outcome": "answer", "text": "No sábado abrimos das 09:00 às 13:00.", "reason": null}'}])
        result = run_turn("Qual é o horário no sábado?", sender="5567998123456", model_client=model)
        self.assertEqual((result["outcome"], result["text"], model.call_count), ("answer", "No sábado abrimos das 09:00 às 13:00.", 3))
