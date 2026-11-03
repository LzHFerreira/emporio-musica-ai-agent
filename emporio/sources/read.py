"""Read only the six fixed canonical source CSV files."""

import csv
import hashlib
from io import StringIO
from pathlib import Path

CSV_HEADERS = {
    "categories": ("category_id", "name", "description"),
    "customers": ("customer_id", "name", "phone", "email", "city"),
    "order_items": ("order_id", "quantity", "product_id"),
    "orders": (
        "order_id",
        "customer_id",
        "order_date",
        "status",
        "total_brl",
        "payment_method",
        "tracking_code",
        "estimated_delivery",
        "notes",
    ),
    "products": (
        "product_id",
        "price_brl",
        "name",
        "category_id",
        "description",
        "stock_quantity",
        "status",
        "specs",
        "created_at",
    ),
    "promotions": ("promotion_id", "product_id", "discount_percent", "description", "is_active"),
}
CSV_FILES = {name: f"desafio_tecnico_ai_eng - {name}.csv" for name in CSV_HEADERS}


class SourceImportError(ValueError):
    """A fixed source file is missing, malformed, or invalid."""


def read_csv_sources(source_dir: str) -> tuple[dict[str, list[dict[str, str]]], dict[str, str]]:
    """Read bounded CSV content and return rows with per-file SHA-256 hashes."""
    root = Path(source_dir).resolve(strict=True)
    rows: dict[str, list[dict[str, str]]] = {}
    hashes: dict[str, str] = {}
    for name, filename in CSV_FILES.items():
        path = (root / filename).resolve(strict=True)
        if path.parent != root or path.stat().st_size > 2 * 1024 * 1024:
            raise SourceImportError(f"invalid source file: {filename}")
        content = path.read_bytes()
        hashes[name] = hashlib.sha256(content).hexdigest()
        rows[name] = _parse_csv(filename, content, CSV_HEADERS[name])
    return rows, hashes


def _parse_csv(filename: str, content: bytes, headers: tuple[str, ...]) -> list[dict[str, str]]:
    """Parse one fixed CSV and require a bounded, exact source schema."""
    try:
        text = content.decode("utf-8-sig")
    except (UnicodeDecodeError, csv.Error) as error:
        raise SourceImportError(f"invalid CSV: {filename}") from error
    reader = csv.DictReader(StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != headers:
        raise SourceImportError(f"invalid columns: {filename}")
    rows = list(reader)
    if _invalid_rows(rows):
        raise SourceImportError(f"invalid row count or shape: {filename}")
    return rows


def _invalid_rows(rows: list[dict[str, str]]) -> bool:
    """Reject empty/oversized tables and missing or extra CSV cells."""
    return not rows or len(rows) > 10_000 or any(_invalid_row(row) for row in rows)


def _invalid_row(row: dict[str, str]) -> bool:
    """Detect short or long rows represented by missing dictionary values."""
    return None in row or any(value is None for value in row.values())
