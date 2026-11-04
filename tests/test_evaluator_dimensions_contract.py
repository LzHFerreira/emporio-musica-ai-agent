"""Contracts for the separate evaluator dimensions reported by `assess`."""

from django.test import SimpleTestCase

from emporio.evaluation_dimensions import assess
from emporio.model_evaluation import FAIL_SAFE_TEXTS
from tests.test_evaluator_outcomes_contract import CORRECT_REPLY, KALANI_CASE, PROMO_REPLY


class EvaluatorDimensionTests(SimpleTestCase):
    def test_lexically_perfect_but_factually_wrong_reply_fails_factual_only(self):
        self.assertEqual(assess(KALANI_CASE, PROMO_REPLY), {
            "outcome": "INCORRECT", "factual": "fail", "lexical": "pass", "execution": "pass",
            "uncertainty": "n/a"})

    def test_correct_reply_passes_every_dimension(self):
        self.assertEqual(assess(KALANI_CASE, CORRECT_REPLY), {
            "outcome": "PASS", "factual": "pass", "lexical": "pass", "execution": "pass",
            "uncertainty": "n/a"})

    def test_fail_safe_text_fails_execution(self):
        text = next(iter(FAIL_SAFE_TEXTS))
        self.assertEqual(assess(KALANI_CASE, text), {
            "outcome": "FAIL-SAFE", "factual": "pass", "lexical": "fail", "execution": "fail",
            "uncertainty": "n/a"})
