"""Contract tests for in-process policy PDF extraction on real PDFs."""

from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from emporio.catalog.normalize import normalize_text
from emporio.sources import policy_pdf, policy_pdf_extract
from tests.policy_pdf_fixture import text_pdf

MANUAL = Path(__file__).resolve().parents[1] / "data" / "políticas_da_loja.pdf"
MANUAL_NEEDLES = [
    "1 sobre a emporio da musica",
    "2 horario de funcionamento",
    "3 formas de pagamento",
    "4 politica de trocas e devolucoes",
    "5 politica de frete e entregas",
    "6 promocoes e descontos",
    "7 atendimento via whatsapp",
    "8 garantia",
    "9 privacidade e protecao de dados",
    "horario de funcionamento",
    "sabado",
    "09 00 as 13 00",
    "domingo e feriados",
    "fechado",
    "7 dias",
    "10 dias uteis",
    "pix",
    "garantia",
]


class PolicyPdfExtractionTests(SimpleTestCase):
    """Pin the policy PDF extraction contract."""

    def test_multi_page_pdf_returns_one_text_per_page(self):
        """Each page of a multi-page PDF yields its own text."""
        pages = policy_pdf.extract_pdf_pages(text_pdf(["Politica"], pages=2))
        self.assertEqual(len(pages), 2)
        self.assertTrue(all("Politica" in page for page in pages))

    def test_extraction_works_without_ghostscript(self):
        """Extraction succeeds even when the gs binary is unavailable."""
        with patch("subprocess.run", side_effect=FileNotFoundError("gs")):
            pages = policy_pdf.extract_pdf_pages(text_pdf(["Frete gratis"]))
        self.assertIn("Frete gratis", pages[0])

    def test_rejects_blank_page(self):
        """A page without extractable text is rejected."""
        with self.assertRaises(ValidationError):
            policy_pdf.extract_pdf_pages(text_pdf([""]))

    def test_rejects_more_than_twenty_pages(self):
        """PDFs with more than 20 pages are rejected."""
        pdf = text_pdf(["Politica"], pages=policy_pdf_extract.MAX_PDF_PAGES + 1)
        with self.assertRaises(ValidationError):
            policy_pdf.extract_pdf_pages(pdf)

    def test_rejects_non_pdf_bytes(self):
        """Bytes without a PDF header are rejected."""
        with self.assertRaises(ValidationError):
            policy_pdf.extract_pdf_pages(b"not a pdf")

    def test_rejects_oversized_raw_text(self):
        """Raw text beyond 128 KiB is rejected."""
        with self.assertRaises(ValidationError):
            policy_pdf.extract_pdf_pages(
                text_pdf(["A" * (policy_pdf_extract.MAX_PDF_TEXT_BYTES + 1)])
            )

    def test_manual_extracts_eight_pages_with_policy_sections(self):
        """The staff policy manual yields 8 pages with all policy sections."""
        pages = policy_pdf.extract_pdf_pages(MANUAL.read_bytes())
        self.assertEqual(len(pages), 8)
        text = normalize_text(" ".join(pages))
        for needle in MANUAL_NEEDLES:
            self.assertIn(needle, text)
