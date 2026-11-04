"""Contracts for the multi-turn scenario evaluator."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from emporio.scenario_evaluation import evaluate_scenarios

REPLY = "O Takamine GD20 custa R$ 2.199,00."
PRICE = "Quanto custa o Takamine?"
TURN = {"any_groups": [], "forbid": [], "bind": [], "ordered": [], "note": ""}


class ScenarioEvaluatorContractTests(SimpleTestCase):
    def test_runs_scenario_turns_with_history_and_sender(self):
        scenarios = [
            {"id": "A", "category": "price", "sender": None, "turns": [
                {**TURN, "customer": PRICE, "must": ["2199,00"]},
                {**TURN, "customer": "E ele tem garantia?", "must": ["inexistente"]}]},
            {"id": "B", "category": "orders", "sender": "5567999990001", "turns": [
                {**TURN, "customer": PRICE, "must": ["2199,00"]}]},
        ]
        turn_call = Mock(return_value={"text": REPLY, "model_requests": 1, "operations": []})
        with tempfile.TemporaryDirectory() as tmp, patch("emporio.scenario_evaluation.run_turn", turn_call):
            path = Path(tmp) / "scenarios.json"
            path.write_text(json.dumps(scenarios), encoding="utf-8")
            report = evaluate_scenarios(path, 1, Mock())
        self.assertEqual((report["scenario_count"], report["turn_count"]), (2, 3))
        self.assertEqual(report["verdicts"], {"PASS": 2, "FAIL-CHECK": 1, "FAIL-SAFE": 0, "ERROR": 0})
        self.assertIsInstance(report["median_seconds"], float)
        self.assertEqual(report["scenarios"][0]["runs"][0][1]["verdict"], "FAIL-CHECK")
        second = turn_call.call_args_list[1]
        self.assertEqual(second.kwargs["history"], [
            {"role": "user", "content": PRICE},
            {"role": "assistant", "content": REPLY}])
        self.assertEqual(turn_call.call_args_list[2].kwargs["sender"], "5567999990001")
