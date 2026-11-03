"""Merge validated source rows using their canonical identities."""

type Row = dict[str, str]
type Identity = tuple[str | None, ...]

_IDENTITIES: dict[str, tuple[str, ...]] = {
    "categories": ("category_id",),
    "products": ("product_id",),
    "promotions": ("promotion_id",),
    "customers": ("customer_id",),
    "orders": ("order_id",),
    "order_items": ("order_id", "product_id"),
}


def merge_rows(source: str, base: list[Row], uploaded: list[Row], mode: str) -> list[Row]:
    """Apply append, upsert, or replacement semantics to one source dataset."""
    fields = _fields(source)
    _check_mode(mode)
    uploaded_rows = _unique_upload(uploaded, fields)
    if mode == "replace":
        return list(uploaded_rows.values())
    return _merge_existing(base, uploaded_rows, fields, mode)


def _fields(source: str) -> tuple[str, ...]:
    if source not in _IDENTITIES:
        raise ValueError(f"unknown source: {source}")
    return _IDENTITIES[source]


def _check_mode(mode: str) -> None:
    if mode not in {"append", "upsert", "replace"}:
        raise ValueError(f"unknown merge mode: {mode}")


def _identity(row: Row, fields: tuple[str, ...]) -> Identity:
    return tuple(row.get(field, row.get("source_id")) for field in fields)


def _unique_upload(rows: list[Row], fields: tuple[str, ...]) -> dict[Identity, Row]:
    unique: dict[Identity, Row] = {}
    for row in rows:
        key = _identity(row, fields)
        previous = unique.get(key)
        _check_upload_duplicate(previous, row, key)
        unique[key] = row
    return unique


def _check_upload_duplicate(previous: Row | None, row: Row, key: Identity) -> None:
    if previous is not None and previous != row:
        raise ValueError(f"conflicting uploaded rows for {key}")


def _merge_existing(
    base: list[Row], uploaded: dict[Identity, Row], fields: tuple[str, ...], mode: str
) -> list[Row]:
    result = list(base)
    positions = {_identity(row, fields): index for index, row in enumerate(result)}
    for key, row in uploaded.items():
        _merge_one(result, positions, key, row, mode)
    return result


def _merge_one(
    result: list[Row], positions: dict[Identity, int], key: Identity, row: Row, mode: str
) -> None:
    index = positions.get(key)
    if index is None:
        positions[key] = len(result)
        result.append(row)
    elif mode == "upsert":
        result[index] = row
    elif result[index] != row:
        raise ValueError(f"conflicting existing row for {key}")
