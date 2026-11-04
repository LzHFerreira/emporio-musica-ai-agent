"""Safe text extraction for staff-submitted policy PDFs."""

import re
from contextlib import closing

import pypdfium2 as pdfium
from django.core.exceptions import ValidationError

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_PDF_TEXT_BYTES = 128 * 1024


def extract_pdf_pages(content: bytes) -> list[str]:
    """Extract per-page Unicode text within byte, page and text bounds."""
    _validate_pdf_bytes(content)
    try:
        document = pdfium.PdfDocument(content)
    except pdfium.PdfiumError as error:
        raise ValidationError("policy PDF extraction failed") from error
    try:
        return _read_pages(document)
    except pdfium.PdfiumError as error:
        raise ValidationError("policy PDF extraction failed") from error
    finally:
        document.close()


def _validate_pdf_bytes(content: bytes) -> None:
    if len(content) > MAX_PDF_BYTES or not content.startswith(b"%PDF-"):
        raise ValidationError("invalid policy PDF")
    raw_bytes = sum(
        len(match.group(1)) for match in re.finditer(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", content)
    )
    if raw_bytes > MAX_PDF_TEXT_BYTES:
        raise ValidationError("policy PDF extracted text exceeds 128 KiB")


def _read_pages(document: pdfium.PdfDocument) -> list[str]:
    if not 1 <= len(document) <= MAX_PDF_PAGES:
        raise ValidationError("policy PDF must contain 1 to 20 pages")
    raw_pages = [_page_text(document, index) for index in range(len(document))]
    _check_extracted_size(raw_pages)
    pages = [text.strip() for text in raw_pages]
    _check_page_text(pages)
    return pages


def _page_text(document: pdfium.PdfDocument, index: int) -> str:
    with closing(document[index]) as page, closing(page.get_textpage()) as textpage:
        text = textpage.get_text_range()
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _check_extracted_size(pages: list[str]) -> None:
    if sum(len(text.encode("utf-8")) for text in pages) > MAX_PDF_TEXT_BYTES:
        raise ValidationError("policy PDF extracted text exceeds 128 KiB")


def _check_page_text(pages: list[str]) -> None:
    if any(not text for text in pages):
        raise ValidationError("policy PDF has a page without extractable text")
