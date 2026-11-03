"""Authorized staging, review and integrity checks for policy PDF sources."""

import hashlib

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from emporio.catalog.models import SourceAuditEvent, SourceDraft
from emporio.sources.draft_audit import record_rejected
from emporio.sources.draft_data import _bundle_path, _verify_pdf, require
from emporio.sources.policy_pdf_extract import extract_pdf_pages
from emporio.sources.policy_pdf_review import build_review
from emporio.sources.policy_pdf_staging import remove_candidate, stage_candidate


def stage_policy_pdf(user, draft, upload, *, expected_revision):
    """Persist an authorized candidate and invalidate any previous review."""
    try:
        return _stage_policy_pdf(user, draft, upload, expected_revision)
    except (OSError, PermissionDenied, ValidationError, ValueError) as error:
        record_rejected(user, draft, "policy_pdf", error)
        raise


def _stage_policy_pdf(user, draft, upload, revision):
    user = require(user, "edit", "policy_pdf")
    current = SourceDraft.objects.get(pk=draft.pk)
    _check_draft(current, user, revision)
    content = upload.read(10 * 1024 * 1024 + 1)
    pages = extract_pdf_pages(content)
    digest = hashlib.sha256(content).hexdigest()
    relative, target = stage_candidate(content, current.pk, current.revision + 1)
    old_path = current.policy.get("candidate_path")
    try:
        current = _persist_candidate(current, user, revision, relative, digest, pages)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    remove_candidate(old_path)
    return current


def _persist_candidate(current, user, revision, relative, digest, pages):
    with transaction.atomic():
        locked = SourceDraft.objects.select_for_update().get(pk=current.pk)
        _check_draft(locked, user, revision)
        locked.revision += 1
        locked.policy = {
            "candidate_path": relative,
            "candidate_sha256": digest,
            "pages": pages,
            "page_count": len(pages),
            "review": None,
        }
        locked.save(update_fields=["policy", "revision", "updated_at"])
        _audit(locked, user, "policy_pdf_staged")
    return locked


def review_policy_pdf(user, draft, values, *, expected_revision):
    """Store source-bound passage and pricing attestations on the draft."""
    try:
        return _review_policy_pdf(user, draft, values, expected_revision)
    except (PermissionDenied, ValidationError, ValueError) as error:
        record_rejected(user, draft, "policy_pdf", error)
        raise


def _review_policy_pdf(user, draft, values, revision):
    user = require(user, "edit", "policy_pdf")
    current = SourceDraft.objects.get(pk=draft.pk)
    _check_draft(current, user, revision)
    candidate = current.policy
    digest = candidate.get("candidate_sha256")
    if not digest:
        raise ValidationError("stage a policy PDF before review")
    review = build_review(values, candidate["pages"], digest, current.revision)
    return _persist_review(current, user, revision, digest, review)


def _persist_review(current, user, revision, digest, review):
    with transaction.atomic():
        locked = SourceDraft.objects.select_for_update().get(pk=current.pk)
        _check_draft(locked, user, revision)
        if locked.policy.get("candidate_sha256") != digest:
            raise ValidationError("policy PDF candidate changed during review")
        locked.policy["review"] = review
        locked.save(update_fields=["policy", "updated_at"])
        _audit(locked, user, "policy_pdf_reviewed")
    return locked


def _audit(draft, user, event):
    SourceAuditEvent.objects.create(
        actor=user,
        draft=draft,
        event=event,
        sources=["policy_pdf"],
        base_version=draft.base_version,
        revision=draft.revision,
    )


def _check_draft(draft, user, revision):
    if draft.author_id != user.pk or draft.status != "draft":
        raise PermissionDenied("only the draft author may edit an open draft")
    if draft.revision != revision:
        raise ValidationError("stale draft revision")


def verify_snapshot_pdf(snapshot):
    """Reject lookup when the active file does not match its reviewed manifest."""
    _verify_pdf(_bundle_path(snapshot), snapshot)
