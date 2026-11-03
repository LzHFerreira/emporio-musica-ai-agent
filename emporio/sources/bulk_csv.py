"""Read exact-schema uploads and compare values using canonical typed fields."""

from functools import partial

from django.core.exceptions import ValidationError

from emporio.sources.draft_data import IDENTITY
from emporio.sources.read import CSV_HEADERS, SourceImportError, _parse_csv
from emporio.sources.schema import flag, integer, money, percent, required, source_date, specs_value

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
_FIELD_PARSERS = {
    "category_id": partial(integer, field="category_id", minimum=1),
    "customer_id": partial(integer, field="customer_id", minimum=1),
    "order_id": partial(integer, field="order_id", minimum=1),
    "product_id": partial(integer, field="product_id", minimum=1),
    "promotion_id": partial(integer, field="promotion_id", minimum=1),
    "quantity": partial(integer, field="quantity", minimum=1),
    "stock_quantity": partial(integer, field="stock_quantity", minimum=0),
    "price_brl": partial(money, field="price_brl"),
    "total_brl": partial(money, field="total_brl"),
    "discount_percent": percent,
    "is_active": partial(flag, field="is_active"),
    "specs": specs_value,
    "created_at": partial(source_date, field="created_at", date_format="%Y-%m-%d"),
    "order_date": partial(source_date, field="order_date"),
    "estimated_delivery": partial(source_date, field="estimated_delivery", optional=True),
    "name": partial(required, field="name"),
    "status": partial(required, field="status"),
    "payment_method": partial(required, field="payment_method"),
}


def read_upload(upload, source):
    """Read one bounded CSV and require the exact fixed source columns."""
    try:
        content = upload.read(MAX_UPLOAD_BYTES + 1)
        if isinstance(content, str):
            content = content.encode("utf-8")
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValidationError("CSV exceeds the 2 MiB upload limit")
        return _parse_csv(f"{source}.csv", content, CSV_HEADERS[source])
    except (AttributeError, OSError, UnicodeError, SourceImportError) as error:
        raise ValidationError("invalid source CSV upload") from error


def identity(row, source):
    """Return one row's canonical typed identity tuple."""
    return tuple(field_value(source, name, row[name]) for name in IDENTITY[source])


def typed_signature(source, row):
    """Return a validated typed row tuple for source-aware comparisons."""
    return tuple(field_value(source, field, row[field]) for field in CSV_HEADERS[source])


def canonicalize_identity(row, source):
    """Normalize identity cells to their canonical CSV string representation."""
    result = dict(row)
    for field in IDENTITY[source]:
        result[field] = str(field_value(source, field, result[field]))
    return result


def field_value(source, field, value):
    """Parse one canonical source field into its typed comparison value."""
    if field == "description" and source == "promotions":
        return required(value, field)
    parser = _FIELD_PARSERS.get(field)
    return parser(value) if parser else value.strip()
