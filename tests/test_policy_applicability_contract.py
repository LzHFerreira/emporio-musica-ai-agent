from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from emporio.policy import lookup_public_policy

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class PolicyApplicabilityContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def test_online_return_lookup_keeps_scope_period_conditions_refund_and_cost(self):
        result = lookup_public_policy(query="devolução compra online arrependimento", topic="returns")
        text = " ".join(row["text"] for row in result["data"]).casefold()
        self.assertEqual(result["outcome"], "found")
        self.assertIn("compras online", text)
        self.assertIn("7 (sete) dias corridos", text)
        self.assertIn("sem necessidade de justificativa", text)
        self.assertIn("embalagem original", text)
        self.assertIn("mesma forma de pagamento original", text)
        self.assertIn("frete de devolução é por conta da loja", text)
