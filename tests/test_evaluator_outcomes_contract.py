"""Contracts for critical-claim outcomes in the model evaluator."""

from django.test import SimpleTestCase

from emporio.model_evaluation import verdict

KALANI = "O Kalani KAL-700T está por R$ 323,10 "
KALANI_CASE = {"question": "Quanto fica o Kalani KAL-700T no PIX?", "must": ["323,10"],
               "any_groups": [], "forbid": [],
               "critical": [{"claim": r"pix.*mais \d+%|mais \d+% .*pix", "label": "incorrect"}]}
PROMO_REPLY = KALANI + "com a promoção. Além disso, no PIX você ganha mais 5% de desconto."
CORRECT_REPLY = KALANI + "na promoção; o desconto de PIX não se aplica sobre preços promocionais."


class CriticalClaimOutcomeTests(SimpleTestCase):
    def test_pix_stacking_on_promotion_is_incorrect(self):
        self.assertEqual(verdict(KALANI_CASE, PROMO_REPLY), "INCORRECT")

    def test_correct_promotion_reply_passes(self):
        self.assertEqual(verdict(KALANI_CASE, CORRECT_REPLY), "PASS")

    def test_case_without_critical_claims_keeps_its_verdict(self):
        case = {"question": "Quanto custa o Takamine GD20?", "must": ["2199,00"], "any_groups": [],
                "forbid": []}
        self.assertEqual(verdict(case, "O Takamine GD20 sai por R$ 2.199,00."), "PASS")
