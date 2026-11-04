from emporio.policy import lookup_public_policy
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class PolicyParaphraseReviewTests(SourceWorkflowFixture):
    def test_location_paraphrase_selects_public_contact_section(self):
        result = lookup_public_policy(query="Onde vocês ficam?")
        self.assertEqual({row["section"] for row in result["data"]}, {"§1.2"})

    def test_delivery_question_does_not_select_store_contact(self):
        result = lookup_public_policy(query="Vocês entregam no centro?")
        self.assertEqual({row["section"] for row in result["data"]}, {"§5.1"})

    def test_address_question_excludes_unrelated_policy_sections(self):
        result = lookup_public_policy(query="Qual é o endereço da loja?")
        sections = {row["section"] for row in result["data"]}
        self.assertIn("§1.2", sections)
        self.assertFalse(sections & {"§2", "§4.1"})

    def test_social_greeting_is_not_misclassified_as_policy_question(self):
        result = lookup_public_policy(query="Que bom dia lindo")
        self.assertEqual(result["outcome"], "not_found")

    def test_weekend_hours_paraphrase_selects_hours_passage(self):
        result = lookup_public_policy(query="Vocês abrem no domingo?")
        self.assertEqual(result["outcome"], "found")
        self.assertIn("hours", {row["topic"] for row in result["data"]})

    def test_installment_paraphrase_selects_payment_passage(self):
        result = lookup_public_policy(query="Aceitam cartão parcelado?")
        self.assertEqual(result["outcome"], "found")
        self.assertIn("payment", {row["topic"] for row in result["data"]})
