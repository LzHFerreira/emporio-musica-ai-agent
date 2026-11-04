import json
from pathlib import Path
from unittest import TestCase

from emporio.model_evaluation import verdict

FIXTURE = Path(__file__).parent / "fixtures" / "heldout_scenarios.json"
TURNS = {s["id"]: s["turns"] for s in json.loads(FIXTURE.read_text(encoding="utf-8"))}
PIX_PROMO = TURNS["promo-ativa-pix-nao-cumula"][1]  # promo-ativa-pix-nao-cumula, turn 2
GF_3D = TURNS["indisponivel-alternativa"][0]  # indisponivel-alternativa, turn 1
RETURN = TURNS["devolucao-arrependimento"][0]  # devolucao-arrependimento, turn 1
PIX_FALSE = "O Kalani KAL-700T sai por R$ 323,10, no PIX você ganha mais 5% de desconto."
PIX_TRUE = "O Kalani KAL-700T sai por R$ 323,10. No PIX o desconto não se aplica à promoção."
GF_3D_FALSE = "O Giannini GF-3D Dreadnought Sunburst está disponível em estoque."
GF_3D_TRUE = "O GF-3D Giannini está temporariamente indisponível; posso sugerir o GF-1R."
RETURN_TRUE = "A compra foi há 10 dias, então o prazo de 7 dias já passou. Defeitos: 30 dias."
class FixtureCriticalClaimsContract(TestCase):
    def test_pix_stock_and_return_cases_declare_critical_claims(self):
        self.assertTrue(all(turn.get("critical") for turn in (PIX_PROMO, GF_3D, RETURN)))

    def test_false_claims_are_incorrect(self):
        self.assertEqual(verdict(PIX_PROMO, PIX_FALSE), "INCORRECT")
        self.assertEqual(verdict(GF_3D, GF_3D_FALSE), "INCORRECT")

    def test_correct_replies_still_pass(self):
        self.assertEqual(verdict(PIX_PROMO, PIX_TRUE), "PASS")
        self.assertEqual(verdict(GF_3D, GF_3D_TRUE), "PASS")
        self.assertEqual(verdict(RETURN, RETURN_TRUE), "PASS")
