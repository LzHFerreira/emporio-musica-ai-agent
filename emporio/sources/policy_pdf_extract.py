"""Safe text extraction for staff-submitted policy PDFs."""

import re
import subprocess
import tempfile
from pathlib import Path

from django.core.exceptions import ValidationError

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_PDF_TEXT_BYTES = 128 * 1024
PDF_PARSE_TIMEOUT = 5


def extract_pdf_pages(content: bytes) -> list[str]:
    """Extract per-page Unicode text within byte, page, text and time bounds."""
    _validate_pdf_bytes(content)
    with tempfile.TemporaryDirectory(prefix="policy-pdf-") as directory:
        root = Path(directory)
        source, output = root / "source.pdf", root / "page-%03d.txt"
        source.write_bytes(content)
        _run_ghostscript(root, source, output)
        return _read_pages(root)


def _validate_pdf_bytes(content: bytes) -> None:
    if len(content) > MAX_PDF_BYTES or not content.startswith(b"%PDF-"):
        raise ValidationError("invalid policy PDF")
    raw_bytes = sum(
        len(match.group(1)) for match in re.finditer(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", content)
    )
    if raw_bytes > MAX_PDF_TEXT_BYTES:
        raise ValidationError("policy PDF extracted text exceeds 128 KiB")


def _run_ghostscript(root: Path, source: Path, output: Path) -> None:
    command = _ghostscript_command(source, output)
    try:
        subprocess.run(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PDF_PARSE_TIMEOUT,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValidationError("policy PDF extraction failed") from error


def _ghostscript_command(source: Path, output: Path) -> list[str]:
    return [
        "gs",
        "-q",
        "-dSAFER",
        "-dNOPAUSE",
        "-dBATCH",
        "-sDEVICE=txtwrite",
        "-dTextFormat=3",
        "-dFirstPage=1",
        f"-dLastPage={MAX_PDF_PAGES + 1}",
        f"-sOutputFile={output}",
        str(source),
    ]


def _read_pages(root: Path) -> list[str]:
    files = _page_files(root)
    _check_extracted_size(files)
    return _read_page_text(files)


def _page_files(root: Path) -> list[Path]:
    files = sorted(root.glob("page-*.txt"))
    if len(files) == 0 or len(files) > MAX_PDF_PAGES:
        raise ValidationError("policy PDF must contain 1 to 20 pages")
    return files


def _check_extracted_size(files: list[Path]) -> None:
    if sum(path.stat().st_size for path in files) > MAX_PDF_TEXT_BYTES:
        raise ValidationError("policy PDF extracted text exceeds 128 KiB")


def _read_page_text(files: list[Path]) -> list[str]:
    pages = [path.read_text(encoding="utf-8").strip() for path in files]
    _check_page_text(pages)
    return pages


def _check_page_text(pages: list[str]) -> None:
    if any(not text for text in pages):
        raise ValidationError("policy PDF has a page without extractable text")
