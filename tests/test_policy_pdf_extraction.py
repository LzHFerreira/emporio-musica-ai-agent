from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from emporio.sources import policy_pdf, policy_pdf_extract
from tests.policy_pdf_fixture import text_pdf


class PolicyPdfExtractionTests(TestCase):
    def test_extraction_rejects_bad_signature_process_failure_and_missing_pages(self):
        with self.assertRaises(ValidationError):
            policy_pdf.extract_pdf_pages(b"not a pdf")
        with patch.object(policy_pdf_extract.subprocess, "run", side_effect=OSError("missing gs")):
            with self.assertRaises(ValidationError):
                policy_pdf.extract_pdf_pages(b"%PDF-1.4\n")
        with patch.object(policy_pdf_extract.subprocess, "run"):
            with self.assertRaises(ValidationError):
                policy_pdf.extract_pdf_pages(b"%PDF-1.4\n")

    def test_extraction_rejects_blank_page_and_text_output_overflow(self):
        def write_page(args, text):
            output = next(item.split("=", 1)[1] for item in args if item.startswith("-sOutputFile="))
            Path(output.replace("%03d", "001")).write_text(text, encoding="utf-8")

        with patch.object(
            policy_pdf_extract.subprocess,
            "run",
            side_effect=lambda args, **kwargs: write_page(args, "  \n"),
        ):
            with self.assertRaises(ValidationError):
                policy_pdf.extract_pdf_pages(b"%PDF-1.4\n")
        with patch.object(
            policy_pdf_extract.subprocess,
            "run",
            side_effect=lambda args, **kwargs: write_page(
                args, "x" * (policy_pdf_extract.MAX_PDF_TEXT_BYTES + 1)
            ),
        ):
            with self.assertRaises(ValidationError):
                policy_pdf.extract_pdf_pages(b"%PDF-1.4\n")

    def test_extraction_rejects_oversized_raw_text(self):
        with self.assertRaises(ValidationError):
            policy_pdf.extract_pdf_pages(
                text_pdf(["A" * (policy_pdf_extract.MAX_PDF_TEXT_BYTES + 1)])
            )
