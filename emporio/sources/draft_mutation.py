"""Create and edit persisted source drafts without exposing canonical payloads."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from emporio.catalog.models import SourceAuditEvent, SourceDraft, SourceSnapshot
from emporio.sources.draft_audit import has_changes, record_rejected, source_counts
from emporio.sources.draft_data import (
    IDENTITY,
    MODEL_PERMISSIONS,
    bundle,
    materialize,
    require,
    staff_user,
)
from emporio.sources.read import CSV_HEADERS
from emporio.sources.validate import validate_sources

READ_ONLY = {name: frozenset(IDENTITY[name]) for name in CSV_HEADERS}


def create_draft(user):
    """Persist an empty draft anchored to the verified active version."""
    user = staff_user(user)
    snapshot = SourceSnapshot.objects.get(is_active=True)
    draft = SourceDraft.objects.create(author=user, base_version=snapshot.version, sources=[])
    SourceAuditEvent.objects.create(
        actor=user, draft=draft, event="draft_created", base_version=snapshot.version
    )
    return draft


def stage_cell(user, draft, source, record_id, field, value, *, expected_revision):
    """Save one source cell as an identity-bound edit with a revision check."""
    try:
        return _stage_cell(user, draft, source, record_id, field, value, expected_revision)
    except (PermissionDenied, ValidationError, ValueError) as error:
        record_rejected(user, draft, source, error)
        raise


def _stage_cell(user, draft, source, record_id, field, value, expected_revision):
    _check_field(source, field)
    user = require(user, "edit", source)
    with transaction.atomic():
        current = _lock_draft(draft)
        _check_owner_revision(current, user, expected_revision)
        _stage_edit(current, source, record_id, field, str(value))
        return _save_edit(current, user, source)


def _check_field(source, field):
    if source not in CSV_HEADERS or field not in CSV_HEADERS[source] or field in READ_ONLY[source]:
        raise ValidationError("field is not editable")


def _lock_draft(draft):
    return SourceDraft.objects.select_for_update().get(pk=draft.pk)


def _check_owner_revision(draft, user, expected_revision):
    if draft.author.pk != user.pk or draft.status != "draft":
        raise PermissionDenied("only the draft author may edit an open draft")
    if draft.revision != expected_revision:
        raise ValidationError("stale draft revision")


def _stage_edit(draft, source, record_id, field, value):
    identity = _record_identity(source, record_id)
    rows = materialize(draft)[source]
    if not _identity_exists(rows, source, identity):
        raise ValidationError("source row was not found")
    _upsert_edit(draft, source, identity, field, value)


def _record_identity(source, record_id):
    key = record_id if isinstance(record_id, (tuple, list)) else (record_id,)
    identity = [str(item) for item in key]
    if len(identity) != len(IDENTITY[source]):
        raise ValidationError("source row was not found")
    return identity


def _identity_exists(rows, source, identity):
    return (
        sum(
            all(
                row.get(key) == value for key, value in zip(IDENTITY[source], identity, strict=True)
            )
            for row in rows
        )
        == 1
    )


def _upsert_edit(draft, source, identity, field, value):
    key = (source, identity, field)
    for edit in draft.sources:
        if (edit["source"], edit["identity"], edit["field"]) == key:
            edit["value"] = value
            return
    draft.sources.append({"source": source, "identity": identity, "field": field, "value": value})


def _save_edit(draft, user, source):
    draft.revision += 1
    draft.save(update_fields=["sources", "revision", "updated_at"])
    SourceAuditEvent.objects.create(
        actor=user,
        draft=draft,
        event="cell_staged",
        sources=[source],
        base_version=draft.base_version,
        revision=draft.revision,
    )
    return draft


def preview_draft(user, draft):
    """Validate the full candidate while returning only permitted source rows."""
    try:
        return _preview_draft(user, draft)
    except (PermissionDenied, ValidationError, ValueError) as error:
        record_rejected(user, draft, "", error)
        raise


def _preview_draft(user, draft):
    user = staff_user(user)
    current = SourceDraft.objects.get(pk=draft.pk)
    if current.author.pk != user.pk:
        raise PermissionDenied("only the draft author may review it")
    if current.policy.get("candidate_sha256"):
        require(user, "view", "policy_pdf")
    sources = materialize(current)
    _authorize_edits(user, current.sources)
    validate_sources(sources)
    base = bundle(SourceSnapshot.objects.get(version=current.base_version))
    counts, changed = _preview_counts(sources, base)
    _record_preview(user, current, counts, changed)
    return {name: rows for name, rows in sources.items() if _can_view(user, name)}


def _preview_counts(sources, base):
    counts = source_counts(sources, base)
    changed = [name for name, item in counts.items() if has_changes(item)]
    return counts, changed


def _record_preview(user, draft, counts, changed):
    for name in changed:
        require(user, "view", name)
    counts = dict(counts)
    candidate = draft.policy
    if candidate.get("candidate_sha256"):
        base = SourceSnapshot.objects.get(version=draft.base_version)
        if candidate["candidate_sha256"] != base.manifest.get("pdf_sha256"):
            counts["policy_pdf"] = {"inserted": 0, "changed": 1, "unchanged": 0, "deleted": 0}
            require(user, "view", "policy_pdf")
            changed = [*changed, "policy_pdf"]
    SourceAuditEvent.objects.create(
        actor=user,
        draft=draft,
        event="previewed",
        sources=changed,
        base_version=draft.base_version,
        revision=draft.revision,
        counts=counts,
    )


def _authorize_edits(user, edits):
    for source in {edit["source"] for edit in edits}:
        require(user, "edit", source)


def _can_view(user, source):
    return user.has_perm(f"catalog.view_{source}") or user.has_perm(
        f"catalog.view_{MODEL_PERMISSIONS[source]}"
    )
