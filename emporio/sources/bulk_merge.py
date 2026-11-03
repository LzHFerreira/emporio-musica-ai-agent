"""Merge source CSV rows and express candidates as base-relative draft edits."""

from django.core.exceptions import ValidationError

from emporio.sources.bulk_csv import canonicalize_identity, field_value, identity, typed_signature
from emporio.sources.draft_data import IDENTITY, require
from emporio.sources.read import CSV_HEADERS


def merge_rows(source, base_rows, uploaded, mode):
    """Apply append, upsert, or replacement semantics to a single CSV source."""
    unique = {}
    for raw in uploaded:
        key = identity(raw, source)
        row = canonicalize_identity(raw, source)
        previous = unique.get(key)
        if previous is not None and typed_signature(source, previous) != typed_signature(
            source, row
        ):
            raise ValidationError(f"conflicting uploaded rows for {key}")
        unique[key] = row
    if mode == "replace":
        return list(unique.values())
    return _merge_existing(source, base_rows, unique, mode)


def _merge_existing(source, base_rows, uploaded, mode):
    result = list(base_rows)
    positions = {identity(row, source): index for index, row in enumerate(result)}
    for key, row in uploaded.items():
        index = positions.get(key)
        if index is None:
            positions[key] = len(result)
            result.append(row)
        else:
            _apply_existing(source, result, index, key, row, mode)
    return result


def _apply_existing(source, result, index, key, row, mode):
    existing = result[index]
    if typed_signature(source, existing) == typed_signature(source, row):
        return
    if mode == "append":
        raise ValidationError(f"conflicting existing row for {key}")
    result[index] = row


def removed_identities(source, base, candidate):
    """Return canonical identities omitted from the candidate source rows."""
    kept = {identity(row, source) for row in candidate}
    return [identity(row, source) for row in base if identity(row, source) not in kept]


def require_delete(user, source):
    """Enforce explicit source deletion permission for row removal."""
    require(user, "delete", source)


def source_edits(source, base_rows, candidate_rows):
    """Represent candidate rows as identity-bound edits from the base source."""
    fields = CSV_HEADERS[source]
    identity_fields = IDENTITY[source]
    base = {identity(row, source): row for row in base_rows}
    candidate = {identity(row, source): row for row in candidate_rows}
    edits = _changed_row_edits(source, fields, identity_fields, base, candidate)
    edits.extend(_deleted_row_edits(source, identity_fields, base, candidate))
    return edits


def _changed_row_edits(source, fields, identity_fields, base, candidate):
    edits = []
    for key, row in candidate.items():
        original = base.get(key)
        if original is None:
            edits.extend(_insert_row_edits(source, key, fields, row))
            continue
        edits.extend(_update_row_edits(source, identity_fields, fields, original, row))
    return edits


def _insert_row_edits(source, key, fields, row):
    identity_values = [str(value) for value in key]
    return [
        {"source": source, "identity": identity_values, "field": field, "value": row[field]}
        for field in fields
    ]


def _update_row_edits(source, identity_fields, fields, original, row):
    identity_values = [original[field] for field in identity_fields]
    return [
        {"source": source, "identity": identity_values, "field": field, "value": row[field]}
        for field in fields
        if field not in identity_fields
        and field_value(source, field, row[field]) != field_value(source, field, original[field])
    ]


def _deleted_row_edits(source, identity_fields, base, candidate):
    edits = []
    for key in base.keys() - candidate.keys():
        values = [base[key][field] for field in identity_fields]
        edits.append(
            {"source": source, "identity": values, "field": "__deleted__", "value": "true"}
        )
    return edits


def row_counts(source, previous_rows, candidate_rows):
    """Return bounded preview counts for one staged upload."""
    previous = {identity(row, source): row for row in previous_rows}
    candidate = {identity(row, source): row for row in candidate_rows}
    common = previous.keys() & candidate.keys()
    changed = sum(
        typed_signature(source, previous[key]) != typed_signature(source, candidate[key])
        for key in common
    )
    return {
        "inserted": len(candidate.keys() - previous.keys()),
        "changed": changed,
        "unchanged": len(common) - changed,
        "deleted": len(previous.keys() - candidate.keys()),
    }
