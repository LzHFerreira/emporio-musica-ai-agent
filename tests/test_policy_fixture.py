from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase

from emporio.sources import policy_fixture, policy_fixture_text

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class PolicyFixtureTests(TestCase):
    def test_initial_manifest_rejects_unreviewed_hash_and_empty_public_map(self):
        with self.assertRaises(ValidationError):
            policy_fixture.initial_policy_manifest(b"other", ["2 Hours"], 500)
        content = (DATA_DIR / "políticas_da_loja.pdf").read_bytes()
        with self.assertRaises(ValidationError):
            policy_fixture.initial_policy_manifest(content, ["10 Internal only"], 500)

    def test_initial_manifest_segments_sections_and_lower_numbered_heading(self):
        content = (DATA_DIR / "políticas_da_loja.pdf").read_bytes()
        pages = [
            "1. Scope",
            "This store works exclusively with musical instruments.",
            "1.2 Company data",
            "Telephone",
            "(67) 1234-5678",
            "2. Hours",
            "Monday 09:00 to 18:00.",
            "3. Payment",
            "PIX discount 5 percent.",
            "4.1 Returns",
            "Return condition retained.",
            "2. Heading in source reading order",
            "End of the return condition.",
            "10. Internal procedures",
        ]
        passages = policy_fixture.initial_policy_manifest(content, pages, 500)["passages"]
        self.assertIn("§2", {item["section"] for item in passages})
        self.assertIn("§4.1", {item["section"] for item in passages})

    def test_initial_sections_filter_internal_text_contacts_and_split_long_text(self):
        self.assertEqual(policy_fixture_text._initial_section("10", [(1, "internal")]), [])
        self.assertEqual(policy_fixture_text._initial_section("1", [(1, "no match")]), [])
        contact = policy_fixture_text._initial_section(
            "1.2", [(1, "Razao Social"), (1, "Telefone"), (1, "(67) 1234-0000")]
        )
        self.assertTrue(contact)
        privacy = policy_fixture_text._initial_section(
            "9", [(2, "Other rights"), (2, "Dados pessoais coletados para pedidos.")]
        )
        self.assertTrue(privacy[0]["text"].casefold().startswith("os dados pessoais coletados"))
        long = policy_fixture_text._initial_section(
            "2", [(3, "X" * 401), (3, "Horario segunda-feira."), (3, "Abre as 9.")]
        )
        self.assertEqual(len(long), 1)

    def test_contact_section_keeps_only_approved_whatsapp_contact(self):
        passages = policy_fixture_text._initial_section(
            "7", [(4, "WhatsApp (67) 1234-5678."), (4, "Internal phone instructions.")]
        )
        self.assertEqual(passages[0]["text"], "WhatsApp (67) 1234-5678.")
