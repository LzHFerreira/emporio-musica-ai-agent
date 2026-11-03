"""Contracts for the reproducible live-model quality evaluator."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from emporio.agent_protocol import FAILURE_TEXT, HANDOFF_TEXT
from emporio.model_evaluation import verdict

FIXTURE = Path(__file__).parent / "fixtures" / "model_quality.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))
COMMAND = "emporio.chat.management.commands.evaluate_model"


class ModelVerdictTests(SimpleTestCase):
    def test_passes_when_must_strings_match_after_normalization(self):
        self.assertEqual(verdict(CASES[0], "O Takamine GD20 sai por R$ 2.199,00."), "PASS")

    def test_fail_safe_texts_are_reported_as_fail_safe(self):
        for text in (FAILURE_TEXT, HANDOFF_TEXT):
            with self.subTest(text=text):
                self.assertEqual(verdict(CASES[0], text), "FAIL-SAFE")

    def test_forbidden_string_fails_the_check(self):
        self.assertEqual(verdict(CASES[4], "Não vendemos pizza; abrimos às 13:00."), "FAIL-CHECK")

    def test_missing_any_group_hit_fails_the_check(self):
        self.assertEqual(verdict(CASES[3], "Abrimos às 09:00 no sábado."), "FAIL-CHECK")


class ModelEvaluatorCommandTests(SimpleTestCase):
    def _run(self, side_effect):
        output = StringIO()
        with patch("emporio.model_evaluation.run_turn", side_effect=side_effect) as turn, \
                patch(f"{COMMAND}.create_model_client", return_value=Mock()):
            call_command("evaluate_model", runs=2, stdout=output)
        return json.loads(output.getvalue()), turn

    def test_command_reports_pass_rate_for_every_case_and_run(self):
        reply = {"text": "R$ 2.199,00", "model_requests": 1}
        report, turn = self._run(lambda *args, **kwargs: reply)
        self.assertEqual(report["case_count"], 5)
        self.assertEqual(report["total"], 10)
        self.assertEqual(report["runs"], 2)
        self.assertEqual(report["cases"][0]["passed"], 2)
        self.assertIn("model_provider", report)
        self.assertEqual(turn.call_count, 10)

    def test_run_turn_exception_is_recorded_as_error(self):
        report, _ = self._run(RuntimeError("boom"))
        replies = [reply for case in report["cases"] for reply in case["replies"]]
        self.assertTrue(all(reply["verdict"] == "ERROR" for reply in replies))
        self.assertTrue(all(reply["text"] == "RuntimeError" for reply in replies))
        self.assertEqual(report["passed"], 0)
