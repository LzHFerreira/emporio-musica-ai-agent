"""Contracts for the uncertainty dimension: clarify or abstain when the case expects it."""

from django.test import SimpleTestCase

from emporio.evaluation_dimensions import assess

CLARIFY_CASE = {"question": "quero um instrumento", "must": [], "any_groups": [], "forbid": [],
                "expect": "clarification"}
ABSTAIN_CASE = {"question": "abrem no feriado?", "must": [], "any_groups": [], "forbid": [],
                "expect": "abstain"}


class EvaluatorUncertaintyTests(SimpleTestCase):
    def test_question_reply_passes_clarification(self):
        text = "Você prefere violão ou guitarra? Qual o seu orçamento?"
        self.assertEqual(assess(CLARIFY_CASE, text)["uncertainty"], "pass")

    def test_price_reply_fails_clarification(self):
        text = "Recomendo o Yamaha C40 por R$ 599,90."
        self.assertEqual(assess(CLARIFY_CASE, text)["uncertainty"], "fail")

    def test_honest_abstain_passes_and_invented_policy_fails(self):
        honest = "O manual não detalha exceções para essa data; recomendo confirmar com a loja."
        self.assertEqual(assess(ABSTAIN_CASE, honest)["uncertainty"], "pass")
        invented = "Abrimos normalmente no feriado."
        self.assertEqual(assess(ABSTAIN_CASE, invented)["uncertainty"], "fail")

    def test_case_without_expect_is_not_applicable(self):
        case = {"question": "q", "must": [], "any_groups": [], "forbid": []}
        self.assertEqual(assess(case, "Olá!")["uncertainty"], "n/a")
