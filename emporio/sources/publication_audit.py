"""Read review evidence and write publication-related source audit events."""

from django.core.exceptions import ValidationError

from emporio.catalog.models import SourceAuditEvent
from emporio.sources.draft_audit import has_changes


def _matching_review(user, draft, revision):
    review = (
        SourceAuditEvent.objects.filter(
            draft=draft, actor=user, event="previewed", revision=revision
        )
        .order_by("-pk")
        .first()
    )
    if review is None:
        raise ValidationError("draft revision must be previewed before publication")
    return review


def _require_deletion_confirmation(review, confirmed):
    if _deletions(review) and confirmed is not True:
        raise ValidationError("reviewed deletions require separate confirmation")


def _deletions(review):
    return {name: values["deleted"] for name, values in review.counts.items() if values["deleted"]}


def _record_deletion_confirmation(user, draft, review, confirmed):
    deleted = _deletions(review)
    _require_deletion_confirmation(review, confirmed)
    if deleted:
        SourceAuditEvent.objects.create(
            actor=user,
            draft=draft,
            event="deletion_confirmed",
            sources=sorted(deleted),
            base_version=draft.base_version,
            revision=review.revision,
            outcome="confirmed",
            counts={name: {"deleted": count} for name, count in deleted.items()},
        )


def _record_publish(user, draft, version, counts):
    draft.status = "published"
    draft.save(update_fields=["status", "updated_at"])
    SourceAuditEvent.objects.create(
        actor=user,
        draft=draft,
        event="published",
        sources=sorted(name for name, item in counts.items() if has_changes(item)),
        base_version=draft.base_version,
        target_version=version,
        revision=draft.revision,
        counts=counts,
    )
