import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from django.core.management import call_command
from django.test import TestCase
from emporio.agent import run_turn
from emporio.model_evaluation import evaluate_model
from tests.test_agent_contract import DATA_DIR, tool_call
from tests.test_model_evaluator_contract import CASES
MANUAL = {"tool_calls": [tool_call("read_store_manual", {})]}
def _terminal(text): return {"content": json.dumps({"outcome": "answer", "text": text, "reason": None})}
class RejectionTraceContractTests(TestCase):
    def setUp(self): call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
    def test_rejected_draft_is_traced_then_valid_reply_is_answered(self):
        model = Mock(side_effect=[MANUAL, _terminal("O prazo para devolver é de 7 anos."), _terminal("Em compras online, você pode devolver em até 7 dias corridos após o recebimento.")])
        result = run_turn("Qual o prazo para devolver?", sender="5567998123456", model_client=model)
        self.assertEqual(result["outcome"], "answer")
        self.assertEqual(result["operations"].count({"tool": "output_check", "outcome": "rejected", "check": "units"}), 1)
    def test_entitlement_rejection_is_traced_when_budget_runs_out(self):
        draft = _terminal("Sim, você pode devolver!")
        result = run_turn("Posso devolver?", sender="5567998123456", model_client=Mock(side_effect=[MANUAL, draft, draft, draft]))
        self.assertIn({"tool": "output_check", "outcome": "rejected", "check": "entitlement"}, result["operations"])
    def test_rejection_reason_names_first_failing_check(self):
        from emporio.agent_output import first_failed_check
        catalog = [{"outcome": "found", "data": [{"name": "Takamine GD20", "base_price_brl": "2199.00"}]}]
        self.assertEqual(first_failed_check("O Takamine custa R$ 9,99.", "answer", [{"type": "catalog"}], catalog), "numbers")
        self.assertIsNone(first_failed_check("O Takamine GD20 custa R$ 2.199,00.", "answer", [{"type": "catalog"}], [{"outcome": "found", "data": [{"name": "Takamine GD20", "base_price_brl": "2199.00"}]}]))
    def test_evaluator_saves_raw_model_drafts_per_reply(self):
        def fake_turn(question, *, sender, model_client):
            model_client([], [])
            return {"text": "x", "model_requests": 1, "operations": []}
        with tempfile.TemporaryDirectory() as tmp, patch("emporio.model_evaluation.run_turn", side_effect=fake_turn):
            (Path(tmp) / "cases.json").write_text(json.dumps(CASES[:1]), encoding="utf-8")
            report = evaluate_model(Path(tmp) / "cases.json", 1, Mock(return_value={"content": "rascunho"}))
        self.assertEqual(report["cases"][0]["replies"][0]["drafts"], ["rascunho"])
