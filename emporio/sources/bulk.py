"""Stage fixed-schema CSV uploads and row deletions into persistent drafts."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from emporio.catalog.models import SourceAuditEvent, SourceDraft, SourceSnapshot
from emporio.sources.bulk_csv import (
    MAX_UPLOAD_BYTES as MAX_UPLOAD_BYTES,
)
from emporio.sources.bulk_csv import (
    field_value,
    identity,
    read_upload,
)
from emporio.sources.bulk_merge import (
    merge_rows,
    removed_identities,
    require_delete,
    row_counts,
    source_edits,
)
from emporio.sources.draft_audit import record_rejected
from emporio.sources.draft_data import IDENTITY, bundle, materialize, require
from emporio.sources.draft_mutation import _check_owner_revision
from emporio.sources.read import CSV_HEADERS
from emporio.sources.validate import validate_sources


def stage_upload(user, draft, source, upload, *, mode, expected_revision, confirm_deletions=False):
    """Stage a full-schema CSV; deletion confirmation is bound later at publication."""
    try:
        return _stage_upload(user, draft, source, upload, mode, expected_revision)
    except (PermissionDenied, ValidationError, ValueError) as error:
        record_rejected(user, draft, source, error)
        raise


def _stage_upload(user, draft, source, upload, mode, expected_revision):
    if source not in CSV_HEADERS:
        raise ValidationError("unknown source")
    user = require(user, "edit", source)
    uploaded = read_upload(upload, source)
    if mode not in {"append", "upsert", "replace"}:
        raise ValidationError("unknown merge mode")
    current = SourceDraft.objects.get(pk=draft.pk)
    _check_owner_revision(current, user, expected_revision)
    before = materialize(current)
    _validate(before)
    merged = merge_rows(source, before[source], uploaded, mode)
    candidate = {name: [dict(row) for row in rows] for name, rows in before.items()}
    candidate[source] = merged
    _validate(candidate)
    base = bundle(SourceSnapshot.objects.get(version=current.base_version))
    _authorize_upload_deletions(user, source, base[source], merged)
    edits = source_edits(source, base[source], merged)
    return _save_upload(user, current, source, before[source], merged, edits, expected_revision)


def _authorize_upload_deletions(user, source, base_rows, merged):
    if removed_identities(source, base_rows, merged):
        require_delete(user, source)


def _save_upload(user, draft, source, previous_rows, merged, edits, revision):
    with transaction.atomic():
        current = SourceDraft.objects.select_for_update().get(pk=draft.pk)
        _check_owner_revision(current, user, revision)
        old_edits = _source_edits(current.sources, source)
        if old_edits == edits:
            return current
        _replace_source_edits(current, source, edits)
        _audit_upload(user, current, source, previous_rows, merged)
        return current


def _audit_upload(user, draft, source, previous_rows, merged):
    SourceAuditEvent.objects.create(
        actor=user,
        draft=draft,
        event="upload_staged",
        sources=[source],
        base_version=draft.base_version,
        revision=draft.revision,
        outcome="success",
        counts=row_counts(source, previous_rows, merged),
    )


def delete_record(user, draft, source, record_id, *, expected_revision, confirm=False):
    """Stage one authorized row deletion for preview-bound publish confirmation."""
    try:
        return _delete_record(user, draft, source, record_id, expected_revision)
    except (PermissionDenied, ValidationError, ValueError) as error:
        record_rejected(user, draft, source, error)
        raise


def _delete_record(user, draft, source, record_id, expected_revision):
    if source not in IDENTITY:
        raise ValidationError("unknown source")
    user = require(user, "edit", source)
    values = _record_identity(source, record_id)
    current = SourceDraft.objects.get(pk=draft.pk)
    _check_owner_revision(current, user, expected_revision)
    require_delete(user, source)
    rows = materialize(current)[source]
    requested = _typed_identity(source, values)
    if sum(identity(row, source) == requested for row in rows) != 1:
        raise ValidationError("source row was not found")
    return _stage_deleted_candidate(user, current, source, rows, requested, expected_revision)


def _typed_identity(source, values):
    try:
        return tuple(
            field_value(source, field, value)
            for field, value in zip(IDENTITY[source], values, strict=True)
        )
    except (TypeError, ValueError, KeyError) as error:
        raise ValidationError("source row was not found") from error


def _stage_deleted_candidate(user, current, source, rows, identity_value, revision):
    candidate = materialize(current)
    candidate[source] = [row for row in rows if identity(row, source) != identity_value]
    _validate(candidate)
    base = bundle(SourceSnapshot.objects.get(version=current.base_version))
    edits = source_edits(source, base[source], candidate[source])
    return _save_delete(user, current, source, edits, revision)


def _save_delete(user, draft, source, edits, revision):
    with transaction.atomic():
        current = SourceDraft.objects.select_for_update().get(pk=draft.pk)
        _check_owner_revision(current, user, revision)
        previous = _source_edits(current.sources, source)
        if previous == edits:
            return current
        _replace_source_edits(current, source, edits)
        SourceAuditEvent.objects.create(
            actor=user,
            draft=current,
            event="record_deleted_staged",
            sources=[source],
            base_version=current.base_version,
            revision=current.revision,
            outcome="success",
            counts={"deleted": 1},
        )
        return current


def _source_edits(edits, source):
    return [edit for edit in edits if edit["source"] == source]


def _replace_source_edits(draft, source, edits):
    draft.sources = [edit for edit in draft.sources if edit["source"] != source] + edits
    draft.revision += 1
    draft.save(update_fields=["sources", "revision", "updated_at"])


def _record_identity(source, record_id):
    key = record_id if isinstance(record_id, (tuple, list)) else (record_id,)
    values = [str(part) for part in key]
    if len(values) != len(IDENTITY[source]):
        raise ValidationError("source row was not found")
    return values


def _validate(candidate):
    try:
        validate_sources(candidate)
    except (TypeError, ValueError, KeyError) as error:
        raise ValidationError(str(error)) from error
