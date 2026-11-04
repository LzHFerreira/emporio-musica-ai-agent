"""Focused tests for pypdfium2 error wrapping and newline normalization."""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from emporio.sources import policy_pdf_extract
from tests.policy_pdf_fixture import text_pdf


class PdfiumExtractionTests(SimpleTestCase):
    """Pin pdfium failures and text normalization."""

    def test_unparseable_pdf_body_is_reported_as_extraction_failure(self):
        """A PDF header with a corrupt body raises the public extraction error."""
        with self.assertRaisesMessage(ValidationError, "policy PDF extraction failed"):
            policy_pdf_extract.extract_pdf_pages(b"%PDF-1.4\n%%EOF garbage")

    def test_extracted_pages_use_lf_line_endings(self):
        """Carriage returns from pdfium are normalized to LF."""
        pages = policy_pdf_extract.extract_pdf_pages(text_pdf(["Linha um", "Linha dois"]))
        self.assertTrue(all("\r" not in page for page in pages))
